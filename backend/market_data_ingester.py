"""Iter 149 — Unified Market Data Ingestion Service.

Root problem found in Iter 148 audit:
    * `historical_candles` collection had only 2 assets (~2 K rows total)
    * All confluence / TQNet / auto-scan / Forex bridge read from this
      collection via `_load_candles_from_db` for tf >= 1m
    * Provider API keys were configured (Twelvedata, Oanda, Finnhub,
      Alpha Vantage, yfinance) but nothing called them on a schedule
    * → models scan empty dataframes → confidence = 0 → no signals

This module fixes it by:
    1. Providing a single `ingester.fetch_and_persist(asset, tf, limit)`
       that routes to the right provider (Twelvedata forex/OTC, Oanda
       majors, yfinance as backup) and writes candles to
       `historical_candles` in the schema the confluence gate expects.
    2. Publishing per-symbol freshness in `market_data_freshness` so the
       diagnostic endpoint can show "which provider last fed you, when".
    3. `ensure_fresh(...)` — auto-heal: if a caller wants candles that
       are stale or missing, we do an inline fetch (bounded by a
       coalescing lock so parallel callers share one HTTP round-trip).
    4. `background_refresh_loop()` — startup task that keeps the top-N
       active assets fresh at intervals appropriate to each timeframe.

Nothing in this file requires torch/scipy — pure numpy/pandas/motor.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Freshness policy per timeframe (seconds) — used by `ensure_fresh`
# ---------------------------------------------------------------------------

FRESHNESS_S: Dict[str, int] = {
    "5s":   15,      # never really used here (5s is fed by another pipe)
    "15s":  30,
    "30s":  60,
    "1m":   120,
    "3m":   240,
    "5m":   360,
    "15m":  900,
    "30m":  1800,
    "1h":   3600,
    "4h":   14400,
    "1d":   86400,
}

# How many rows to keep per (asset, tf) as a rolling window in Mongo
KEEP_ROWS_PER_KEY = 2000

# ---------------------------------------------------------------------------
# Provider adapters — thin wrappers around existing services that return a
# uniform ohlcv DataFrame (asc order, columns: timestamp/open/high/low/close/volume)
# ---------------------------------------------------------------------------

@dataclass
class ProviderResult:
    df: Optional[pd.DataFrame]
    provider: str
    error: Optional[str] = None
    latency_ms: int = 0

    @property
    def ok(self) -> bool:
        return self.df is not None and not self.df.empty


def _twelvedata(asset: str, timeframe: str, limit: int) -> ProviderResult:
    """Primary provider — best coverage for forex (incl OTC) + commodities."""
    t0 = time.time()
    try:
        from twelvedata_service import twelvedata_client
        df = twelvedata_client.get_candles(asset, timeframe, outputsize=limit)
        return ProviderResult(df=df, provider="twelvedata",
                              latency_ms=int((time.time() - t0) * 1000))
    except Exception as e:
        return ProviderResult(df=None, provider="twelvedata", error=str(e)[:200],
                              latency_ms=int((time.time() - t0) * 1000))


def _oanda(asset: str, timeframe: str, limit: int) -> ProviderResult:
    """Preferred for major FX pairs (institutional-grade candles).

    NOTE: EnhancedOandaService.get_candles_large requires an explicit
    (from_time, to_time) window rather than a count. We derive the
    window from the requested limit + timeframe.
    """
    t0 = time.time()
    try:
        from enhanced_oanda_service import EnhancedOandaService
        svc = EnhancedOandaService(
            access_token=os.environ.get("OANDA_ACCESS_TOKEN"),
            account_id=os.environ.get("OANDA_ACCOUNT_ID"),
            environment=os.environ.get("OANDA_ENVIRONMENT"),
        )
        oa_tf = {
            "1m": "M1", "5m": "M5", "15m": "M15", "30m": "M30",
            "1h": "H1", "4h": "H4", "1d": "D",
        }.get(timeframe)
        if oa_tf is None:
            return ProviderResult(df=None, provider="oanda",
                                  error=f"unsupported tf {timeframe}",
                                  latency_ms=int((time.time() - t0) * 1000))
        # Compute window: limit × tf_seconds → from_time back from now
        tf_sec = {
            "1m": 60, "5m": 300, "15m": 900, "30m": 1800,
            "1h": 3600, "4h": 14400, "1d": 86400,
        }.get(timeframe, 60)
        now = datetime.now(timezone.utc)
        from_time = (now - timedelta(seconds=tf_sec * (limit + 5))).isoformat()
        to_time = now.isoformat()
        instr = asset.replace("_OTC", "").replace("_otc", "")
        if len(instr) == 6 and instr.isalpha():
            instr = instr[:3] + "_" + instr[3:]
        df = svc.get_candles_large(
            instrument=instr, granularity=oa_tf,
            from_time=from_time, to_time=to_time,
        )
        return ProviderResult(df=df, provider="oanda",
                              latency_ms=int((time.time() - t0) * 1000))
    except Exception as e:
        return ProviderResult(df=None, provider="oanda", error=str(e)[:200],
                              latency_ms=int((time.time() - t0) * 1000))


def _yfinance(asset: str, timeframe: str, limit: int) -> ProviderResult:
    """Backup — free, no key, but slower and less accurate on short TFs."""
    t0 = time.time()
    try:
        import yfinance as yf
        # Rough yfinance TF map (yfinance uses different labels)
        yf_tf = {
            "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
            "1h": "60m", "4h": "1h", "1d": "1d",
        }.get(timeframe, "1m")
        # yfinance ticker: EURUSD -> EURUSD=X
        core = asset.replace("_OTC", "").replace("_otc", "").upper()
        if len(core) == 6 and core.isalpha():
            ticker = core + "=X"
        else:
            ticker = core
        # yfinance period must be compatible with the interval — cap by intent
        period = {
            "1m": "7d", "5m": "60d", "15m": "60d", "30m": "60d",
            "60m": "730d", "1h": "730d", "1d": "10y",
        }.get(yf_tf, "7d")
        raw = yf.Ticker(ticker).history(period=period, interval=yf_tf, auto_adjust=False)
        if raw.empty:
            return ProviderResult(df=None, provider="yfinance",
                                  error="empty history",
                                  latency_ms=int((time.time() - t0) * 1000))
        df = raw.rename(columns=str.lower).reset_index()
        # yfinance timestamp column is 'Datetime' or 'Date'
        for tscol in ("datetime", "date"):
            if tscol in df.columns:
                df = df.rename(columns={tscol: "timestamp"})
                break
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        keep = ["timestamp", "open", "high", "low", "close", "volume"]
        for c in keep:
            if c not in df.columns:
                df[c] = 0.0
        df = df[keep].tail(limit).reset_index(drop=True)
        return ProviderResult(df=df, provider="yfinance",
                              latency_ms=int((time.time() - t0) * 1000))
    except Exception as e:
        return ProviderResult(df=None, provider="yfinance", error=str(e)[:200],
                              latency_ms=int((time.time() - t0) * 1000))


# ---------------------------------------------------------------------------
# Provider routing — pick the best chain per asset class
# ---------------------------------------------------------------------------

_MAJOR_FX = {"EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD",
             "NZDUSD", "EURGBP", "EURJPY", "GBPJPY"}


def _pick_chain(asset: str) -> List:
    """Return an ordered list of provider fns to try for this asset."""
    core = asset.replace("_OTC", "").replace("_otc", "").upper()
    is_otc = "OTC" in asset.upper()
    # Majors: Oanda first (best fills), Twelvedata second, yfinance backup
    if core in _MAJOR_FX and not is_otc:
        return [_oanda, _twelvedata, _yfinance]
    # OTC / non-major forex — Twelvedata first, yfinance backup (Oanda has no OTC)
    return [_twelvedata, _yfinance]


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def _normalise_df(df: pd.DataFrame, asset: str, timeframe: str) -> List[Dict[str, Any]]:
    """Convert provider df to the historical_candles document schema."""
    docs = []
    for _, r in df.iterrows():
        ts = r.get("timestamp")
        if pd.isna(ts):
            continue
        # Coerce to datetime (Mongo-safe)
        if isinstance(ts, (int, float)):
            ts_dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)
        elif isinstance(ts, str):
            ts_dt = pd.to_datetime(ts, utc=True).to_pydatetime()
        elif hasattr(ts, "to_pydatetime"):
            ts_dt = ts.to_pydatetime()
        else:
            continue
        if ts_dt.tzinfo is None:
            ts_dt = ts_dt.replace(tzinfo=timezone.utc)
        docs.append({
            "asset": asset,
            "timeframe": timeframe,
            "timestamp": ts_dt,
            "open": float(r["open"]),
            "high": float(r["high"]),
            "low": float(r["low"]),
            "close": float(r["close"]),
            "volume": float(r.get("volume") or 0.0),
        })
    return docs


async def _persist_candles(db, asset: str, timeframe: str,
                           docs: List[Dict[str, Any]]) -> int:
    """Upsert into historical_candles keyed by (asset, timeframe, timestamp).
    Returns the number of documents written or updated."""
    if not docs or db is None:
        return 0
    n = 0
    n_seen = 0
    first_err = None
    for d in docs:
        try:
            r = await db.historical_candles.update_one(
                {"asset": d["asset"], "timeframe": d["timeframe"],
                 "timestamp": d["timestamp"]},
                {"$set": d},
                upsert=True,
            )
            n_seen += 1
            if r.upserted_id or r.modified_count:
                n += 1
        except Exception as e:
            if first_err is None:
                first_err = str(e)[:200]
    if first_err:
        # Iter 149 — surface persist errors at WARNING; a silent failure
        # here means the ingester says "fetched 200 rows" but the DB has 0.
        logger.warning(
            f"[ingester] persist error for {asset}/{timeframe} "
            f"(seen={n_seen}/{len(docs)}, n_written={n}): {first_err}"
        )
    # Prune old rows so any single (asset, tf) doesn't grow unbounded
    try:
        cnt = await db.historical_candles.count_documents(
            {"asset": asset, "timeframe": timeframe}
        )
        if cnt > KEEP_ROWS_PER_KEY:
            # Find the timestamp of the row we want to keep as the boundary
            cutoff_cur = db.historical_candles.find(
                {"asset": asset, "timeframe": timeframe}
            ).sort("timestamp", -1).skip(KEEP_ROWS_PER_KEY - 1).limit(1)
            cutoff_list = await cutoff_cur.to_list(1)
            if cutoff_list:
                cutoff_ts = cutoff_list[0]["timestamp"]
                await db.historical_candles.delete_many({
                    "asset": asset, "timeframe": timeframe,
                    "timestamp": {"$lt": cutoff_ts},
                })
    except Exception as e:
        logger.debug(f"[ingester] prune failed for {asset}/{timeframe}: {e}")
    return n


# ---------------------------------------------------------------------------
# The Ingester singleton
# ---------------------------------------------------------------------------

@dataclass
class IngestReport:
    asset: str
    timeframe: str
    ok: bool
    provider: Optional[str]
    rows: int
    latency_ms: int
    error: Optional[str] = None
    attempts: List[Dict[str, Any]] = field(default_factory=list)


class MarketDataIngester:
    """Fetch → normalise → persist orchestration.

    All public methods coalesce concurrent calls for the same (asset, tf)
    so parallel confluence scans don't hammer Twelvedata's rate limit.
    """

    def __init__(self):
        self.db = None
        self._inflight: Dict[Tuple[str, str], asyncio.Future] = {}
        self._freshness_cache: Dict[Tuple[str, str], Dict[str, Any]] = {}

    def bind_db(self, db):
        self.db = db

    # ------------------------------------------------------------------
    async def fetch_and_persist(self, asset: str, timeframe: str,
                                limit: int = 500) -> IngestReport:
        """Try each provider in order, persist the first success.

        Coalesces concurrent callers for the same (asset, tf) so we do a
        single HTTP round-trip.
        """
        key = (asset, timeframe)
        # If a fetch is already in flight for this key, wait for it
        inflight = self._inflight.get(key)
        if inflight is not None and not inflight.done():
            try:
                return await inflight
            except Exception:
                pass  # fall through to a fresh attempt
        loop = asyncio.get_event_loop()
        fut = loop.create_future()
        self._inflight[key] = fut
        try:
            report = await self._do_fetch(asset, timeframe, limit)
            fut.set_result(report)
            return report
        except Exception as e:
            fut.set_exception(e)
            raise
        finally:
            # Only clear if it's still our future
            if self._inflight.get(key) is fut:
                self._inflight.pop(key, None)

    async def _do_fetch(self, asset: str, timeframe: str,
                        limit: int) -> IngestReport:
        chain = _pick_chain(asset)
        attempts: List[Dict[str, Any]] = []
        for provider_fn in chain:
            # Provider is sync + does IO → offload to a thread
            res: ProviderResult = await asyncio.to_thread(provider_fn, asset, timeframe, limit)
            attempts.append({
                "provider": res.provider,
                "ok": res.ok,
                "rows": 0 if res.df is None else len(res.df),
                "latency_ms": res.latency_ms,
                "error": res.error,
            })
            if not res.ok:
                continue
            docs = _normalise_df(res.df, asset, timeframe)
            written = await _persist_candles(self.db, asset, timeframe, docs)
            # Iter 149.1 — Only mark as fresh if candles actually landed in
            # the DB. Prior version cached "fresh=True" even when persist
            # failed silently — poisoning ensure_fresh's cache_hit path.
            db_rows = 0
            if self.db is not None:
                try:
                    db_rows = await self.db.historical_candles.count_documents(
                        {"asset": asset, "timeframe": timeframe}
                    )
                except Exception:
                    pass
            self._freshness_cache[(asset, timeframe)] = {
                "asset": asset,
                "timeframe": timeframe,
                "provider": res.provider,
                "rows": len(docs),
                "written": written,
                "db_rows": db_rows,
                "last_fetch_iso": datetime.now(timezone.utc).isoformat(),
                "last_bar_ts": docs[-1]["timestamp"].isoformat() if docs else None,
                "latency_ms": res.latency_ms,
            }
            # Persist a lightweight freshness marker so the status endpoint
            # can see it even after a restart.
            if self.db is not None:
                try:
                    await self.db.market_data_freshness.update_one(
                        {"asset": asset, "timeframe": timeframe},
                        {"$set": self._freshness_cache[(asset, timeframe)]},
                        upsert=True,
                    )
                except Exception:
                    pass
            return IngestReport(
                asset=asset, timeframe=timeframe, ok=True,
                provider=res.provider, rows=len(docs),
                latency_ms=res.latency_ms, attempts=attempts,
            )
        return IngestReport(
            asset=asset, timeframe=timeframe, ok=False,
            provider=None, rows=0, latency_ms=0,
            error="all providers failed",
            attempts=attempts,
        )

    # ------------------------------------------------------------------
    async def ensure_fresh(self, asset: str, timeframe: str,
                           limit: int = 500,
                           max_age_s: Optional[int] = None) -> Dict[str, Any]:
        """Return latest freshness metadata, triggering a fetch if stale.

        Called by `_load_candles_from_db` — this is the auto-heal path.
        """
        if max_age_s is None:
            max_age_s = FRESHNESS_S.get(timeframe, 300)
        entry = self._freshness_cache.get((asset, timeframe))
        # Also consult DB if in-mem cache is empty (post-restart)
        if entry is None and self.db is not None:
            try:
                doc = await self.db.market_data_freshness.find_one(
                    {"asset": asset, "timeframe": timeframe}
                )
                if doc:
                    entry = {k: v for k, v in doc.items() if k != "_id"}
                    self._freshness_cache[(asset, timeframe)] = entry
            except Exception:
                pass

        needs_fetch = True
        if entry and entry.get("last_bar_ts"):
            try:
                last_ts = datetime.fromisoformat(entry["last_bar_ts"])
                age_s = (datetime.now(timezone.utc) - last_ts).total_seconds()
                # Iter 149.1 — Only trust the cache when:
                #   (a) age is within the window, AND
                #   (b) actual DB rows exist (persist worked), AND
                #   (c) age isn't NEGATIVE (would happen when the provider
                #       returns future-dated bars for 24/7 OTC markets and
                #       our server clock is behind — treat as stale so we
                #       actually verify against fresh data).
                db_rows_ok = int(entry.get("db_rows") or 0) > 0
                if 0 <= age_s < max_age_s and db_rows_ok:
                    needs_fetch = False
            except Exception:
                pass

        if not needs_fetch:
            return {"fresh": True, **entry, "action": "cache_hit"}
        report = await self.fetch_and_persist(asset, timeframe, limit)
        entry = self._freshness_cache.get((asset, timeframe), {})
        return {
            "fresh": report.ok,
            "action": "refetched",
            "report": {
                "ok": report.ok, "provider": report.provider,
                "rows": report.rows, "latency_ms": report.latency_ms,
                "error": report.error, "attempts": report.attempts,
            },
            **entry,
        }

    # ------------------------------------------------------------------
    async def status(self) -> Dict[str, Any]:
        """Freshness table for the diagnostic endpoint."""
        out: List[Dict[str, Any]] = []
        entries = dict(self._freshness_cache)
        if self.db is not None:
            try:
                async for doc in self.db.market_data_freshness.find({}):
                    key = (doc.get("asset"), doc.get("timeframe"))
                    if key not in entries:
                        entries[key] = {k: v for k, v in doc.items() if k != "_id"}
            except Exception:
                pass
        for (asset, tf), e in entries.items():
            entry = dict(e)
            entry["asset"] = asset
            entry["timeframe"] = tf
            entry["max_age_s"] = FRESHNESS_S.get(tf, 300)
            # Compute current age
            try:
                if e.get("last_bar_ts"):
                    last_ts = datetime.fromisoformat(e["last_bar_ts"])
                    entry["age_s"] = round(
                        (datetime.now(timezone.utc) - last_ts).total_seconds(), 1
                    )
                    entry["is_fresh"] = entry["age_s"] < entry["max_age_s"]
            except Exception:
                entry["age_s"] = None
                entry["is_fresh"] = None
            out.append(entry)
        out.sort(key=lambda x: (x["asset"] or "", x["timeframe"] or ""))
        return {"count": len(out), "entries": out,
                "freshness_policy_s": FRESHNESS_S}

    # ------------------------------------------------------------------
    async def providers_health(self) -> Dict[str, Any]:
        """Cheap health check — is each provider callable with a test symbol?"""
        results = {}
        for prov_fn, test_symbol, test_tf in [
            (_twelvedata, "EURUSD", "1m"),
            (_oanda, "EURUSD", "1m"),
            (_yfinance, "EURUSD", "1m"),
        ]:
            res = await asyncio.to_thread(prov_fn, test_symbol, test_tf, 5)
            results[res.provider] = {
                "ok": res.ok,
                "rows": 0 if res.df is None else len(res.df),
                "latency_ms": res.latency_ms,
                "error": res.error,
            }
        return {
            "providers": results,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }


# Module-level singleton
ingester = MarketDataIngester()


# ---------------------------------------------------------------------------
# Background refresh loop — called from server startup
# ---------------------------------------------------------------------------

DEFAULT_REFRESH_ASSETS = [
    "EURUSD_OTC", "GBPUSD_OTC", "USDJPY_OTC", "AUDUSD_OTC", "NZDUSD_OTC",
    "USDCAD_OTC", "USDCHF_OTC", "EURJPY_OTC", "EURGBP_OTC", "GBPJPY_OTC",
]
DEFAULT_REFRESH_TFS = ["1m", "5m", "15m"]


async def background_refresh_loop(assets: Optional[List[str]] = None,
                                  timeframes: Optional[List[str]] = None,
                                  interval_s: int = 180):
    """Long-running task; keeps `historical_candles` warm for the top assets.

    Fires every `interval_s` (default 180 s). For each (asset, tf) we call
    `ensure_fresh` which is a no-op when data is already within its
    freshness window — so actual HTTP calls happen roughly at each
    timeframe's natural cadence.

    Iter 149.1 — Twelvedata free tier caps at 8 requests / minute. We now
    sleep 8 s between provider calls so the 60-key ~= (10 pairs × 3 TFs
    × 2 batches) fits inside the budget over a 3-minute cycle rather than
    constantly triggering the local rate-limiter timeout.
    """
    assets = assets or DEFAULT_REFRESH_ASSETS
    timeframes = timeframes or DEFAULT_REFRESH_TFS
    logger.info(f"[ingester] background refresh loop starting: {len(assets)}"
                f" × {len(timeframes)} keys, cadence {interval_s}s")
    while True:
        try:
            for asset in assets:
                for tf in timeframes:
                    try:
                        r = await ingester.ensure_fresh(asset, tf, limit=200)
                        if r.get("action") == "refetched" and not r.get("fresh"):
                            logger.debug(f"[ingester] refresh failed {asset}/{tf}: "
                                         f"{r.get('report', {}).get('error')}")
                    except Exception as e:
                        logger.debug(f"[ingester] tick error {asset}/{tf}: {e}")
                    # Space provider calls out to respect free-tier rate limits
                    # (Twelvedata: 8 req/min → ~7.5 s per call minimum)
                    await asyncio.sleep(8.0)
        except Exception as e:
            logger.warning(f"[ingester] loop error: {e}")
        await asyncio.sleep(interval_s)
