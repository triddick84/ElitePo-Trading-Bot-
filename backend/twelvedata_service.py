"""
Twelve Data integration (Iter 61, May 27 2026)
==============================================

Drop-in market-data provider that complements OANDA + the OTC pool.

Used by:
  - `historical_data_service.get_candles_for_backtest()` as a fallback
  - `/api/market/twelvedata/*` real-time / candle endpoints (live dashboard)
  - `train_from_trade_reports()` as a last-resort backfill source

Design notes:
  - Sync `requests`-based client wrapped in `asyncio.to_thread` (consistent
    with how `enhanced_oanda_service` already works in this codebase)
  - Token-bucket rate limiter: 8 calls / 60s window (free-tier limit)
  - Symbol normalization: PO-internal symbols → TD canonical (EUR/USD form)
  - Returns pandas DataFrame with [timestamp, open, high, low, close, volume]
    columns — matches every other provider in this codebase
"""
from __future__ import annotations
import os
import time
import logging
import threading
from typing import Dict, List, Optional, Any
from datetime import datetime

import requests
import pandas as pd

logger = logging.getLogger(__name__)

TD_API_KEY = os.environ.get("TWELVEDATA_API_KEY")
TD_BASE_URL = "https://api.twelvedata.com"

# Free-tier limit: 8 credits per minute. We cap at 8 requests/60s.
_RATE_CAPACITY = 8
_RATE_WINDOW_S = 60.0
_RATE_LOCK = threading.Lock()
_RATE_TIMES: List[float] = []


def _acquire_rate_token(max_wait_s: float = 30.0) -> bool:
    """Token-bucket gate. Blocks up to `max_wait_s` for an available slot."""
    deadline = time.time() + max_wait_s
    while True:
        with _RATE_LOCK:
            now = time.time()
            # Drop timestamps older than the window
            cutoff = now - _RATE_WINDOW_S
            while _RATE_TIMES and _RATE_TIMES[0] < cutoff:
                _RATE_TIMES.pop(0)
            if len(_RATE_TIMES) < _RATE_CAPACITY:
                _RATE_TIMES.append(now)
                return True
            wait = _RATE_TIMES[0] + _RATE_WINDOW_S - now
        if time.time() + wait > deadline:
            return False
        time.sleep(max(0.1, min(wait, 2.0)))


# ---------------------------------------------------------------------------
# Symbol mapping — PO internal → TwelveData canonical
# ---------------------------------------------------------------------------
_FOREX_TRIPLES = {"EUR", "USD", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD",
                  "SGD", "HKD", "SEK", "NOK", "PLN", "MXN", "ZAR", "TRY",
                  "CNH", "CNY", "INR", "BRL", "RUB", "KRW", "DKK", "HUF"}

_EXPLICIT_MAP: Dict[str, str] = {
    # Commodities
    "XAUUSD": "XAU/USD", "XAGUSD": "XAG/USD",
    "XAUUSD_OTC": "XAU/USD", "XAGUSD_OTC": "XAG/USD",
    "WTI": "WTI/USD", "BRENT": "BRENT/USD",
    "XPTUSD": "XPT/USD", "XPDUSD": "XPD/USD",
    # Crypto
    "BTCUSD": "BTC/USD", "ETHUSD": "ETH/USD", "LTCUSD": "LTC/USD",
    "XRPUSD": "XRP/USD", "BCHUSD": "BCH/USD", "DOGEUSD": "DOGE/USD",
    "ADAUSD": "ADA/USD", "SOLUSD": "SOL/USD",
    # Indices (TD uses these tickers for index futures/cash)
    "SPX500": "SPX", "NDX100": "NDX", "DJI30": "DJI",
    "DAX40": "DAX", "FTSE100": "FTSE",
}


def normalize_symbol(internal: str) -> Optional[str]:
    """Map PO-internal symbol to TwelveData canonical (e.g. EURUSD_OTC → EUR/USD)."""
    if not internal:
        return None
    s = internal.upper()
    if s in _EXPLICIT_MAP:
        return _EXPLICIT_MAP[s]
    # Strip _OTC suffix
    core = s.replace("_OTC", "")
    # 6-letter forex pair → split into 3+3
    if len(core) == 6 and core[:3] in _FOREX_TRIPLES and core[3:] in _FOREX_TRIPLES:
        return f"{core[:3]}/{core[3:]}"
    # Already in slash form (e.g. EUR/USD)
    if "/" in core and len(core.replace("/", "")) == 6:
        return core
    return None


# Interval mapping — PO/backtest tf → TwelveData interval
_INTERVAL_MAP = {
    "M1": "1min", "1m": "1min", "1min": "1min",
    "M5": "5min", "5m": "5min", "5min": "5min",
    "M15": "15min", "15m": "15min", "15min": "15min",
    "M30": "30min", "30m": "30min", "30min": "30min",
    "H1": "1h", "1h": "1h", "H4": "4h", "4h": "4h",
    "D": "1day", "D1": "1day", "1d": "1day", "1day": "1day",
}


def normalize_interval(tf: str) -> str:
    """Map any common interval label to TwelveData's expected form."""
    return _INTERVAL_MAP.get(tf, "1min")


# ---------------------------------------------------------------------------
# Twelve Data client
# ---------------------------------------------------------------------------
class TwelveDataClient:
    def __init__(self, api_key: Optional[str] = None, timeout: float = 12.0):
        self.api_key = api_key or TD_API_KEY
        self.timeout = timeout
        if not self.api_key:
            logger.warning("TwelveDataClient: TWELVEDATA_API_KEY missing — calls will fail")

    def _get(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if not self.api_key:
            return {"status": "error", "message": "TWELVEDATA_API_KEY not configured"}
        if not _acquire_rate_token():
            return {"status": "error", "message": "rate_limit_local_timeout"}
        params = dict(params)
        params["apikey"] = self.api_key
        url = f"{TD_BASE_URL}{path}"
        try:
            r = requests.get(url, params=params, timeout=self.timeout)
            if r.status_code == 429:
                return {"status": "error", "message": "rate_limit_429"}
            if r.status_code >= 400:
                return {"status": "error", "message": f"http_{r.status_code}", "body": r.text[:200]}
            data = r.json()
            if isinstance(data, dict) and data.get("status") == "error":
                return data
            return data if isinstance(data, dict) else {"status": "error", "message": "non_dict_response"}
        except requests.exceptions.RequestException as e:
            return {"status": "error", "message": f"network: {e}"}

    def get_candles(
        self,
        symbol: str,
        timeframe: str,
        outputsize: int = 500,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Optional[pd.DataFrame]:
        """
        Fetch OHLCV candles for a PO-internal symbol. Returns a DataFrame with
        columns [timestamp, open, high, low, close, volume] sorted ascending,
        or None on failure / empty response.
        """
        td_sym = normalize_symbol(symbol)
        if not td_sym:
            logger.debug(f"[twelvedata] cannot map symbol {symbol!r}")
            return None

        interval = normalize_interval(timeframe)
        params: Dict[str, Any] = {
            "symbol": td_sym,
            "interval": interval,
            "outputsize": min(int(outputsize), 5000),
            "format": "JSON",
        }
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date

        data = self._get("/time_series", params)
        if data.get("status") == "error":
            logger.warning(f"[twelvedata] {td_sym} {interval}: {data.get('message')}")
            return None

        values = data.get("values")
        if not values:
            return None

        df = pd.DataFrame(values)
        df.rename(columns={"datetime": "timestamp"}, inplace=True)
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
        for col in ("open", "high", "low", "close", "volume"):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
            else:
                df[col] = 0.0
        df = df.dropna(subset=["timestamp", "open", "high", "low", "close"])
        df.sort_values("timestamp", inplace=True)
        df.reset_index(drop=True, inplace=True)
        return df[["timestamp", "open", "high", "low", "close", "volume"]]

    def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        td_sym = normalize_symbol(symbol)
        if not td_sym:
            return None
        data = self._get("/quote", {"symbol": td_sym, "format": "JSON"})
        if data.get("status") == "error":
            return None
        return data

    def get_price(self, symbol: str) -> Optional[float]:
        td_sym = normalize_symbol(symbol)
        if not td_sym:
            return None
        data = self._get("/price", {"symbol": td_sym, "format": "JSON"})
        if data.get("status") == "error":
            return None
        try:
            return float(data.get("price"))
        except (TypeError, ValueError):
            return None

    def api_credits_status(self) -> Dict[str, Any]:
        """Probe `/api_usage` to report remaining credits + return rate-bucket state."""
        data = self._get("/api_usage", {})
        with _RATE_LOCK:
            tokens_used = len(_RATE_TIMES)
        return {
            "tokens_used_in_window": tokens_used,
            "capacity": _RATE_CAPACITY,
            "window_seconds": _RATE_WINDOW_S,
            "remote": data,
        }


# Singleton used everywhere
twelvedata_client = TwelveDataClient()
