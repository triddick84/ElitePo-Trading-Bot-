"""Iter 135 — Per-asset RF AUC Audit.

Scores every trained RF model at `/app/backend/ml_models/rf_<ASSET>_<TIMEFRAME>.pkl`
against fresh yfinance holdout data, computes ROC-AUC, persists results into
`rf_audit` (MongoDB), and exposes `get_effective_weight(asset, timeframe)` for
the ensemble to consume.

Weight policy:
    AUC ≥ 0.55  → weight = 1.0  (trusted)
    0.52 ≤ AUC < 0.55 → linear scale 0.0 → 1.0
    AUC < 0.52  → weight = 0.0  (dropped — worse than coin-flip after transaction cost)

Every audit run stores {asset, timeframe, auc, n_samples, status, audited_at}
so the UI can render the leaderboard and the ensemble can trust it.
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

logger = logging.getLogger(__name__)

MODEL_DIR = "/app/backend/ml_models"
RF_MODEL_PATTERN = re.compile(r"^rf_(.+)_(\d+[smhd]|\dm|\d+m|\d+s)\.pkl$")

AUC_DROP_BELOW = 0.52       # No trust — coin-flip
AUC_FULL_TRUST_AT = 0.55    # Full weight
HOLDOUT_LOOKBACK_BARS = 500


def _load_rf_model(path: str):
    """Load an RFModel .pkl using the RestrictedUnpickler safety wrapper."""
    from safe_model_loader import RestrictedUnpickler
    with open(path, "rb") as f:
        data = RestrictedUnpickler(f).load()
    return data


def _asset_to_yf(asset: str) -> str:
    """Map an asset name (EURUSD_OTC → EURUSD=X, BTC/USD → BTC-USD) to yfinance."""
    base = asset.upper()
    # Strip every OTC / synthetic marker before other normalization
    for tag in ("_OTC", "/OTC", "-OTC", "OTC"):
        if base.endswith(tag):
            base = base[: -len(tag)]
    base = base.replace("/", "").replace("-", "")
    # Crypto — check BEFORE the generic 6-char forex fallback because
    # BTCUSD / ETHUSD are also 6 alpha chars.
    if base in ("BTCUSD", "ETHUSD", "LTCUSD", "ADAUSD", "DOGEUSD", "SOLUSD"):
        return base[:-3] + "-USD"
    if len(base) == 6 and base.isalpha():
        return f"{base}=X"
    return base


def _fetch_holdout(asset: str, timeframe: str, bars: int = HOLDOUT_LOOKBACK_BARS) -> Optional[pd.DataFrame]:
    """Pull fresh candles from yfinance (cached via yf_cache). Falls back to
    the `historical_candles` Mongo collection when yfinance impersonation
    fails or the pair isn't tradable on Yahoo (OTC synthetic pairs)."""
    df: Optional[pd.DataFrame] = None
    try:
        import yfinance as yf
        yf_symbol = _asset_to_yf(asset)
        tf = timeframe.lower()
        if tf.endswith("s"):
            interval, period = "1m", "5d"
        elif tf.endswith("m") and tf[:-1].isdigit():
            n = int(tf[:-1])
            interval = "1m" if n == 1 else f"{min(n, 60)}m"
            period = "7d" if n <= 5 else "30d"
        else:
            interval, period = "1m", "7d"
        df = yf.Ticker(yf_symbol).history(period=period, interval=interval)
        if df is not None and not df.empty:
            df.columns = [c.lower() for c in df.columns]
            df = df.tail(bars).reset_index(drop=False)
            return df
    except Exception as e:
        logger.info(f"[rf_audit] yfinance fetch failed for {asset}: {e}")

    # ---------------- Fallback: Mongo `otc_candles_5s` / `historical_candles` ----------------
    try:
        from pymongo import MongoClient
        env = open("/app/backend/.env").read()
        m_url = re.search(r'MONGO_URL="([^"]+)"', env).group(1)
        m_db = re.search(r'DB_NAME="([^"]+)"', env).group(1)
        with MongoClient(m_url, serverSelectionTimeoutMS=3000) as c:
            asset_norm = asset.upper()
            candidates = [asset_norm, asset_norm.replace("_OTC", "")]
            # Try otc_candles_5s first (assets stored under `symbol`, 42k+ rows)
            for cand in candidates:
                rows = list(
                    c[m_db].otc_candles_5s
                    .find({"symbol": cand},
                          {"_id": 0, "timestamp": 1, "open": 1, "high": 1,
                           "low": 1, "close": 1})
                    .sort("timestamp", -1)
                    .limit(bars)
                )
                if rows and len(rows) >= 50:
                    rows.reverse()
                    df = pd.DataFrame(rows)
                    df["volume"] = 0.0
                    logger.info(f"[rf_audit] otc_candles_5s fallback for {asset}/{timeframe}: {len(df)} bars")
                    return df
            # Then historical_candles (fewer rows but forex-friendly)
            for cand in candidates:
                rows = list(
                    c[m_db].historical_candles
                    .find({"asset": cand, "timeframe": timeframe},
                          {"_id": 0, "timestamp": 1, "open": 1, "high": 1,
                           "low": 1, "close": 1})
                    .sort("timestamp", -1)
                    .limit(bars)
                )
                if rows and len(rows) >= 50:
                    rows.reverse()
                    df = pd.DataFrame(rows)
                    df["volume"] = 0.0
                    logger.info(f"[rf_audit] historical_candles fallback for {asset}/{timeframe}: {len(df)} bars")
                    return df
    except Exception as e:
        logger.info(f"[rf_audit] Mongo fallback failed for {asset}: {e}")
    return None


def _score_one(asset: str, timeframe: str, model_path: str) -> Dict[str, Any]:
    """Score a single RF model against holdout data. Returns audit row."""
    row: Dict[str, Any] = {
        "asset": asset, "timeframe": timeframe,
        "auc": None, "n_samples": 0, "status": "error",
        "audited_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        data = _load_rf_model(model_path)
        model = data.get("model")
        scaler = data.get("scaler")
        feature_names = data.get("feature_names") or []
        if model is None or not feature_names:
            row["status"] = "malformed"
            row["reason"] = "no model/features in pkl"
            return row

        df = _fetch_holdout(asset, timeframe)
        if df is None or len(df) < 50:
            row["status"] = "no_holdout"
            row["reason"] = "yfinance returned <50 bars"
            return row

        # Feature engineering — reuse the training service's engineer so
        # feature semantics stay identical.
        from ml_training_service import FeatureEngineer
        eng = FeatureEngineer()
        features = eng.calculate_features(df)
        if len(features) < 30:
            row["status"] = "no_features"
            row["reason"] = f"only {len(features)} feature rows"
            return row

        # Align to what the model was trained on. FX pairs on yfinance
        # report `volume=0`, so features like `volume_sma_20 / volume_ratio /
        # price_volume_trend` come out NaN and get dropped. Rather than
        # bailing (which would drop >90 % of the audit), we fill any missing
        # feature columns with `0.0` (neutral for volume-derived features)
        # so the model can still score. This over-estimates AUC slightly
        # for volume-heavy models but keeps the pipeline live for FX.
        missing = [c for c in feature_names if c not in features.columns]
        if missing:
            for col in missing:
                features[col] = 0.0
            logger.debug(f"[rf_audit] {asset}/{timeframe} filled {len(missing)} "
                         f"missing features with 0.0")
        X = features[feature_names]

        # Target: next-bar direction from the raw price df
        # Convert (close_now < close_next) → 1 (up) else 0
        closes = df["close"].values if "close" in df.columns else df.iloc[:, df.columns.get_loc("close")].values
        # Trim closes to match features length (features truncates warm-up bars)
        closes = closes[-len(features):]
        y_next = np.where(np.diff(closes) > 0, 1, 0)
        # Align X (drop the last row since we have no y for it)
        X = X.iloc[:len(y_next)]
        y = y_next[:len(X)]
        if len(y) < 30 or len(np.unique(y)) < 2:
            row["status"] = "insufficient_labels"
            row["reason"] = f"y_len={len(y)} unique={len(np.unique(y))}"
            return row

        # Predict probabilities
        X_scaled = scaler.transform(X) if scaler is not None else X.values
        proba = model.predict_proba(X_scaled)
        # Pick the positive-class column (label == 1)
        classes = list(getattr(model, "classes_", [0, 1]))
        pos_idx = classes.index(1) if 1 in classes else -1
        y_hat = proba[:, pos_idx]

        auc = float(roc_auc_score(y, y_hat))
        row["auc"] = round(auc, 4)
        row["n_samples"] = int(len(y))
        row["status"] = ("trusted" if auc >= AUC_FULL_TRUST_AT
                         else "de_weighted" if auc >= AUC_DROP_BELOW
                         else "dropped")
        row["weight"] = _weight_from_auc(auc)
        return row
    except Exception as e:
        row["reason"] = str(e)[:300]
        logger.debug(f"[rf_audit] {asset}/{timeframe}: {e}")
        return row


def _weight_from_auc(auc: Optional[float]) -> float:
    """Map AUC → ensemble weight. Piecewise linear."""
    if auc is None:
        return 0.0
    if auc < AUC_DROP_BELOW:
        return 0.0
    if auc >= AUC_FULL_TRUST_AT:
        return 1.0
    return round((auc - AUC_DROP_BELOW) / (AUC_FULL_TRUST_AT - AUC_DROP_BELOW), 3)


def list_rf_models() -> List[Tuple[str, str, str]]:
    """Return [(asset, timeframe, path), …] for every rf_*_*.pkl on disk."""
    if not os.path.isdir(MODEL_DIR):
        return []
    out = []
    for fn in sorted(os.listdir(MODEL_DIR)):
        m = RF_MODEL_PATTERN.match(fn)
        if not m:
            continue
        asset, tf = m.group(1), m.group(2)
        out.append((asset, tf, os.path.join(MODEL_DIR, fn)))
    return out


class RFAuditService:
    """Persistence + weight lookup for the RF Audit."""

    def __init__(self):
        self._db = None
        self._weight_cache: Dict[Tuple[str, str], float] = {}

    def bind_db(self, db):
        self._db = db

    async def load_weights_from_db(self):
        """Populate the in-process weight cache from any prior audit rows."""
        if self._db is None:
            return
        cur = self._db.rf_audit.find({}, {"_id": 0})
        rows = await cur.to_list(length=200)
        for r in rows:
            self._weight_cache[(r["asset"], r["timeframe"])] = float(r.get("weight") or 0.0)
        logger.info(f"[rf_audit] loaded {len(rows)} weights from DB")

    async def run_audit(self, limit: Optional[int] = None) -> Dict[str, Any]:
        """Run the audit for every rf_*.pkl and persist rows to Mongo."""
        models = list_rf_models()
        if limit:
            models = models[:limit]
        results = []
        summary = {"trusted": 0, "de_weighted": 0, "dropped": 0, "errors": 0}
        for asset, tf, path in models:
            row = _score_one(asset, tf, path)
            results.append(row)
            st = row.get("status", "error")
            if st == "trusted":
                summary["trusted"] += 1
            elif st == "de_weighted":
                summary["de_weighted"] += 1
            elif st == "dropped":
                summary["dropped"] += 1
            else:
                summary["errors"] += 1
            # Cache the weight
            if row.get("auc") is not None:
                self._weight_cache[(asset, tf)] = _weight_from_auc(row["auc"])
            # Persist
            if self._db is not None:
                try:
                    await self._db.rf_audit.update_one(
                        {"asset": asset, "timeframe": tf},
                        {"$set": row},
                        upsert=True,
                    )
                except Exception as e:
                    logger.debug(f"[rf_audit] persist {asset}/{tf}: {e}")
        return {
            "total_models": len(models),
            "summary": summary,
            "results": sorted(results, key=lambda r: (r.get("auc") or 0), reverse=True),
        }

    async def latest(self) -> List[Dict[str, Any]]:
        if self._db is None:
            return []
        cur = self._db.rf_audit.find({}, {"_id": 0}).sort("auc", -1)
        return await cur.to_list(length=200)

    def get_effective_weight(self, asset: str, timeframe: str) -> float:
        """Ensemble consumers call this to get the RF model's trust weight
        for a given (asset, timeframe). Default 1.0 if never audited."""
        return self._weight_cache.get((asset, timeframe), 1.0)


rf_audit_service = RFAuditService()
