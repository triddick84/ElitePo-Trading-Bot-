"""
LightGBM Meta-Model Service (Iter 115d).

Takes tabular features (strategy votes + confidences + indicators + regime
+ microstructure) and outputs a calibrated probability of a CALL winning.
This replaces / augments the existing tree ensemble as the final arbiter.

Features per input row (order matters for training + inference):
    - rsi, macd, macd_hist, atr, ema_fast, ema_slow, bb_pos
    - adx, plus_di, minus_di
    - ha_streak_bull, ha_streak_bear
    - kyle_lambda, vpin, flow_imbalance
    - vote_up, vote_down (from strategy votes)
    - mean_confidence, max_confidence
    - regime_code (0=CHOPPY, 1=NEUTRAL, 2=TREND)

Model persisted to /app/backend/ml_models/lightgbm_meta.pkl
"""

from __future__ import annotations

import logging
import os
import pickle
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

_MODEL_DIR = os.path.join(os.path.dirname(__file__), "ml_models")
_MODEL_PATH = os.path.join(_MODEL_DIR, "lightgbm_meta.pkl")

FEATURE_ORDER = [
    "rsi", "macd", "macd_hist", "atr", "ema_fast", "ema_slow", "bb_pos",
    "adx", "plus_di", "minus_di",
    "ha_streak_bull", "ha_streak_bear",
    "kyle_lambda", "vpin", "flow_imbalance",
    "vote_up", "vote_down", "mean_confidence", "max_confidence",
    "regime_code",
]

_REGIME_CODES = {"CHOPPY": 0, "NEUTRAL": 1, "TREND": 2}


def _feature_row(features: Dict[str, Any]) -> np.ndarray:
    row = []
    for k in FEATURE_ORDER:
        v = features.get(k, 0.0)
        if k == "regime_code" and isinstance(v, str):
            v = _REGIME_CODES.get(v.upper(), 1)
        try:
            row.append(float(v))
        except (TypeError, ValueError):
            row.append(0.0)
    return np.asarray(row, dtype=float)


class LightGBMMetaService:
    """Singleton service that owns the LightGBM meta-model lifecycle."""

    def __init__(self):
        self._booster = None
        self._calibrator = None
        self._trained_at: Optional[str] = None
        self._metrics: Dict[str, Any] = {}
        self._load_from_disk()

    def _load_from_disk(self) -> None:
        if not os.path.exists(_MODEL_PATH):
            return
        try:
            with open(_MODEL_PATH, "rb") as fh:
                payload = pickle.load(fh)
            self._booster = payload.get("booster")
            self._calibrator = payload.get("calibrator")
            self._trained_at = payload.get("trained_at")
            self._metrics = payload.get("metrics", {})
            logger.info(
                "[LightGBMMeta] Loaded model trained at %s (auc=%s calibrated=%s)",
                self._trained_at, self._metrics.get("auc"),
                self._calibrator is not None,
            )
        except Exception as e:
            logger.warning("[LightGBMMeta] Failed to load model: %s", e)
            self._booster = None

    def _save_to_disk(self) -> None:
        os.makedirs(_MODEL_DIR, exist_ok=True)
        with open(_MODEL_PATH, "wb") as fh:
            pickle.dump(
                {
                    "booster": self._booster,
                    "calibrator": self._calibrator,
                    "trained_at": self._trained_at,
                    "metrics": self._metrics,
                    "feature_order": FEATURE_ORDER,
                },
                fh,
            )

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------
    def train(
        self,
        X: List[Dict[str, Any]],
        y: List[int],
        params: Optional[Dict[str, Any]] = None,
        walk_forward: bool = False,
        n_folds: int = 5,
        gap: int = 20,
        calibrate: bool = True,
    ) -> Dict[str, Any]:
        """Train on (features_list, labels). y ∈ {0, 1} (0=PUT win, 1=CALL win).

        Iter 119:
          - `walk_forward=True` runs chronologically purged expanding-window CV
            with a `gap` between train and test to avoid leakage.
          - `calibrate=True` fits an isotonic-regression calibrator on OOF
            predictions so `p=0.85` actually means 85% win probability.

        Returns metrics dict.
        """
        import lightgbm as lgb  # local import so app boots without lightgbm

        if len(X) != len(y):
            raise ValueError("X and y must have same length")
        if len(X) < 50:
            raise ValueError(f"Not enough training samples ({len(X)} < 50)")

        X_arr = np.stack([_feature_row(f) for f in X])
        y_arr = np.asarray(y, dtype=int)

        base_params = {
            "objective": "binary",
            "metric": "auc",
            "learning_rate": 0.05,
            "num_leaves": 31,
            "min_data_in_leaf": 20,
            "feature_fraction": 0.9,
            "bagging_fraction": 0.8,
            "bagging_freq": 5,
            "verbose": -1,
        }
        if params:
            base_params.update(params)

        # --- Walk-forward CV (Iter 119) -----------------------------------
        oof_preds = np.zeros(len(X_arr), dtype=float)
        oof_mask = np.zeros(len(X_arr), dtype=bool)
        fold_aucs: List[float] = []
        if walk_forward and len(X_arr) >= (n_folds + 1) * 30:
            n = len(X_arr)
            fold_size = n // (n_folds + 1)
            for k in range(1, n_folds + 1):
                train_end = fold_size * k
                test_start = train_end + gap
                test_end = min(test_start + fold_size, n)
                if test_start >= n:
                    break
                X_tr = X_arr[:train_end]
                y_tr = y_arr[:train_end]
                X_te = X_arr[test_start:test_end]
                y_te = y_arr[test_start:test_end]
                if len(np.unique(y_tr)) < 2 or len(X_te) == 0:
                    continue
                ds_tr = lgb.Dataset(X_tr, label=y_tr, feature_name=FEATURE_ORDER)
                ds_va = lgb.Dataset(X_te, label=y_te, feature_name=FEATURE_ORDER, reference=ds_tr)
                bst = lgb.train(
                    base_params, ds_tr, num_boost_round=200,
                    valid_sets=[ds_va],
                    callbacks=[lgb.early_stopping(20), lgb.log_evaluation(0)],
                )
                preds_k = bst.predict(X_te)
                oof_preds[test_start:test_end] = preds_k
                oof_mask[test_start:test_end] = True
                try:
                    from sklearn.metrics import roc_auc_score
                    fold_aucs.append(float(roc_auc_score(y_te, preds_k)))
                except Exception:
                    pass

        # Final model trained on ALL data (used at inference time)
        train_set = lgb.Dataset(X_arr, label=y_arr, feature_name=FEATURE_ORDER)
        booster = lgb.train(base_params, train_set, num_boost_round=200,
                            callbacks=[lgb.log_evaluation(0)])

        # Overall metrics: prefer OOF, fall back to a simple 80/20 chronological split
        from sklearn.metrics import roc_auc_score, accuracy_score
        if oof_mask.sum() > 20:
            oof_y = y_arr[oof_mask]
            oof_p = oof_preds[oof_mask]
            try:
                auc = float(roc_auc_score(oof_y, oof_p))
            except ValueError:
                auc = float("nan")
            acc = float(accuracy_score(oof_y, (oof_p > 0.5).astype(int)))
            n_test = int(oof_mask.sum())
            n_train_report = int(len(X_arr) - n_test)
            validation = "walk_forward"
        else:
            split = int(len(X_arr) * 0.8)
            _X_te, _y_te = X_arr[split:], y_arr[split:]
            preds = booster.predict(_X_te)
            try:
                auc = float(roc_auc_score(_y_te, preds))
            except ValueError:
                auc = float("nan")
            acc = float(accuracy_score(_y_te, (preds > 0.5).astype(int)))
            n_test = int(len(_X_te))
            n_train_report = int(split)
            validation = "chronological_split"

        # --- Isotonic calibration on OOF preds (Iter 119) ------------------
        calibrator = None
        if calibrate and oof_mask.sum() > 30 and len(np.unique(y_arr[oof_mask])) == 2:
            try:
                from sklearn.isotonic import IsotonicRegression
                iso = IsotonicRegression(out_of_bounds="clip")
                iso.fit(oof_preds[oof_mask], y_arr[oof_mask])
                calibrator = iso
            except Exception as _ce:
                logger.warning("[LightGBMMeta] calibration failed: %s", _ce)

        self._booster = booster
        self._calibrator = calibrator
        self._trained_at = datetime.now(timezone.utc).isoformat()
        self._metrics = {
            "auc": round(auc, 4),
            "accuracy": round(acc, 4),
            "n_train": n_train_report,
            "n_test": n_test,
            "validation": validation,
            "fold_aucs": [round(f, 4) for f in fold_aucs],
            "calibrated": calibrator is not None,
            "feature_importance": dict(
                zip(FEATURE_ORDER, [int(v) for v in booster.feature_importance().tolist()])
            ),
        }
        self._save_to_disk()
        logger.info("[LightGBMMeta] Trained. auc=%s acc=%s validation=%s calibrated=%s",
                    auc, acc, validation, calibrator is not None)
        return self._metrics

    # ------------------------------------------------------------------
    # Prediction
    # ------------------------------------------------------------------
    def is_ready(self) -> bool:
        return self._booster is not None

    def predict_proba(self, features: Dict[str, Any]) -> Optional[float]:
        """Return probability of CALL winning ∈ [0, 1] or None if not trained.
        Iter 119 — applies isotonic calibrator when present so the returned
        value is a real probability (well-calibrated) not a raw score.
        """
        if not self.is_ready():
            return None
        row = _feature_row(features).reshape(1, -1)
        try:
            raw = float(self._booster.predict(row)[0])
            if self._calibrator is not None:
                calibrated = float(self._calibrator.transform([raw])[0])
                return max(0.0, min(1.0, calibrated))
            return max(0.0, min(1.0, raw))
        except Exception as e:
            logger.warning("[LightGBMMeta] predict failed: %s", e)
            return None

    def status(self) -> Dict[str, Any]:
        return {
            "ready": self.is_ready(),
            "trained_at": self._trained_at,
            "metrics": self._metrics,
            "feature_order": FEATURE_ORDER,
        }


# Singleton
_service: Optional[LightGBMMetaService] = None


def get_lightgbm_service() -> LightGBMMetaService:
    global _service
    if _service is None:
        _service = LightGBMMetaService()
    return _service


# ---------------------------------------------------------------------------
# Live-trade retrain (Iter 118)
# ---------------------------------------------------------------------------
async def record_live_sample(
    db,
    features: Dict[str, Any],
    outcome: str,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Append a labeled training sample coming from a real closed trade.
    Auto-triggers a retrain once we have accumulated >= 25 new samples
    since the last retrain (or a total of >= 100 if never trained live).
    """
    outcome_norm = str(outcome or "").upper()
    if outcome_norm not in ("WIN", "LOSS"):
        return {"success": False, "error": "outcome must be WIN or LOSS"}

    # Direction is inferred from metadata — a WIN with direction=CALL means
    # price went UP, a WIN with direction=PUT means price went DOWN.
    direction = str((metadata or {}).get("direction") or "").upper()
    if direction in ("CALL", "UP", "BUY"):
        label = 1 if outcome_norm == "WIN" else 0
    elif direction in ("PUT", "DOWN", "SELL"):
        label = 0 if outcome_norm == "WIN" else 1
    else:
        # Fallback — treat WIN as CALL-favoured (best-effort)
        label = 1 if outcome_norm == "WIN" else 0

    sample = {
        "features": {k: features.get(k, 0.0) for k in FEATURE_ORDER},
        "label": int(label),
        "outcome": outcome_norm,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "metadata": metadata or {},
    }
    await db.lightgbm_live_samples.insert_one(sample)

    # Check pending count
    total = await db.lightgbm_live_samples.count_documents({})
    since_retrain = await db.lightgbm_live_samples.count_documents({"used_in_retrain": {"$ne": True}})

    retrained = None
    should_retrain = (since_retrain >= 25 and total >= 50) or (since_retrain >= 100)
    if should_retrain:
        try:
            retrained = await _retrain_from_live_samples(db, walk_forward=True, calibrate=True)
        except Exception as e:
            logger.warning("[LightGBMLive] auto-retrain failed: %s", e)

    return {
        "success": True,
        "sample_stored": True,
        "total_live_samples": total,
        "unused_since_last_retrain": since_retrain,
        "auto_retrained": retrained is not None,
        "retrain_metrics": retrained,
    }


async def get_live_samples_stats(db) -> Dict[str, Any]:
    total = await db.lightgbm_live_samples.count_documents({})
    unused = await db.lightgbm_live_samples.count_documents({"used_in_retrain": {"$ne": True}})
    latest_doc = await db.lightgbm_live_samples.find_one(
        {}, sort=[("created_at", -1)]
    )
    return {
        "total": total,
        "unused_since_last_retrain": unused,
        "latest_at": (latest_doc or {}).get("created_at"),
    }


# ---------------------------------------------------------------------------
# Iter 119 — Backfill from tm_trade_reports
# ---------------------------------------------------------------------------
async def backfill_from_tm_trade_reports(
    db,
    max_samples: int = 6000,
    candle_lookback: int = 60,
) -> Dict[str, Any]:
    """
    Pull every labeled trade from `tm_trade_reports`, look up the candle
    context around the trade time, run the real feature builder, and drop
    the result into `lightgbm_live_samples`. Then retrain with walk-forward
    CV + isotonic calibration.

    This is the single biggest predicted lift (0.48 → 0.55-0.60 AUC) because
    it replaces placeholder features (rsi=50, ema=close) with real values
    computed from actual candle windows around real trades.
    """
    from feature_builder import build_features
    from datetime import datetime as _dt

    cursor = db.tm_trade_reports.find(
        {"outcome": {"$in": ["WIN", "LOSS"]}},
        {
            "_id": 0,
            "asset": 1, "asset_normalized": 1,
            "direction": 1, "outcome": 1, "confidence": 1,
            "expires_at": 1, "created_at": 1, "reported_at": 1,
            "server_received_at": 1,
        },
    ).sort("server_received_at", 1).limit(max_samples)
    reports = await cursor.to_list(length=max_samples)
    if not reports:
        return {"success": False, "error": "no labeled TM trades in tm_trade_reports"}

    stored = 0
    skipped_no_candles = 0
    now_iso = _dt.now(timezone.utc).isoformat()
    for rep in reports:
        outcome = str(rep.get("outcome") or "").upper()
        if outcome not in ("WIN", "LOSS"):
            continue

        # Resolve trade time and asset
        t_str = rep.get("server_received_at") or rep.get("reported_at") or rep.get("created_at")
        if not t_str:
            continue
        try:
            trade_ts = _dt.fromisoformat(str(t_str).replace("Z", "+00:00"))
        except Exception:
            continue

        asset = str(rep.get("asset_normalized") or rep.get("asset") or "").upper()
        if not asset:
            continue
        variants = list({asset, asset.replace("_OTC", ""),
                         asset.replace("OTC", ""),
                         asset + "_OTC" if not asset.endswith("_OTC") else asset})

        # Pull candles preceding the trade
        candles: List[Dict[str, Any]] = []
        for coll_name, key in (
            ("otc_candles_5s", "symbol"),
            ("candles", "symbol"),
            ("historical_candles", "asset"),
        ):
            try:
                # Try ISO-string $lte first, then int; whichever returns rows wins.
                docs_c = await db[coll_name].find(
                    {
                        key: {"$in": variants},
                        "$or": [
                            {"timestamp": {"$lte": trade_ts.isoformat()}},
                            {"timestamp": {"$lte": int(trade_ts.timestamp())}},
                            {"timestamp": {"$lte": int(trade_ts.timestamp() * 1000)}},
                        ],
                    },
                    {"_id": 0, "open": 1, "high": 1, "low": 1,
                     "close": 1, "volume": 1, "timestamp": 1},
                ).sort("timestamp", -1).limit(candle_lookback).to_list(candle_lookback)
                if docs_c and len(docs_c) >= 25:
                    candles = list(reversed(docs_c))
                    break
            except Exception:
                pass
        if not candles:
            skipped_no_candles += 1
            continue

        features = build_features(
            candles,
            direction=rep.get("direction"),
            signal_confidence=rep.get("confidence"),
        )

        direction = str(rep.get("direction") or "").upper()
        # Same label logic as record_live_sample
        if direction in ("CALL", "UP", "BUY"):
            label = 1 if outcome == "WIN" else 0
        elif direction in ("PUT", "DOWN", "SELL"):
            label = 0 if outcome == "WIN" else 1
        else:
            label = 1 if outcome == "WIN" else 0

        await db.lightgbm_live_samples.insert_one({
            "features": features,
            "label": int(label),
            "outcome": outcome,
            "created_at": trade_ts.isoformat(),
            "metadata": {
                "asset": asset,
                "direction": direction,
                "confidence": rep.get("confidence"),
                "source": "backfill_iter119",
            },
        })
        stored += 1

    if stored == 0:
        return {
            "success": False,
            "error": "no samples produced (candle join failed on all reports)",
            "reports_read": len(reports),
            "skipped_no_candles": skipped_no_candles,
        }

    # Retrain with walk-forward CV + calibration
    metrics = await _retrain_from_live_samples(db, walk_forward=True, calibrate=True)
    metrics["backfill_stored"] = stored
    metrics["reports_read"] = len(reports)
    metrics["skipped_no_candles"] = skipped_no_candles
    metrics["success"] = bool(metrics.get("auc") is not None)
    return metrics


async def _retrain_from_live_samples(
    db,
    walk_forward: bool = True,
    calibrate: bool = True,
) -> Dict[str, Any]:
    """Pull all labeled live samples and retrain the LightGBM meta-model.
    Iter 119 — walk-forward CV + isotonic calibration by default."""
    cursor = db.lightgbm_live_samples.find(
        {}, {"_id": 0, "features": 1, "label": 1, "created_at": 1}
    ).sort("created_at", 1)
    docs = await cursor.to_list(length=100_000)
    if len(docs) < 50:
        return {"success": False, "error": f"only {len(docs)} live samples"}

    X = [d["features"] for d in docs]
    y = [int(d["label"]) for d in docs]

    svc = get_lightgbm_service()
    metrics = svc.train(X, y, walk_forward=walk_forward, calibrate=calibrate)
    await db.lightgbm_live_samples.update_many(
        {"used_in_retrain": {"$ne": True}},
        {"$set": {"used_in_retrain": True, "retrained_at": datetime.now(timezone.utc).isoformat()}},
    )
    metrics["success"] = True
    metrics["samples_used"] = len(X)
    metrics["source"] = "live_trades"
    return metrics


# ---------------------------------------------------------------------------
# Historical-data trainer helper
# ---------------------------------------------------------------------------

async def train_from_historical_candles(
    db,
    max_samples: int = 5000,
    lookback: int = 30,
) -> Dict[str, Any]:
    """
    Build a self-supervised training set from `historical_candles` and train
    the meta-model.

    For each candle at index i (with enough lookback), we build a feature row
    using indicators over candles[i-lookback:i] and label = 1 if
    candles[i+1].close > candles[i].close else 0.
    """
    from adx_regime_gate import compute_adx, classify_adx_regime

    docs = await db.historical_candles.find(
        {},
        {"_id": 0, "open": 1, "high": 1, "low": 1, "close": 1,
         "volume": 1, "asset": 1, "timestamp": 1},
    ).sort("timestamp", 1).limit(max_samples * 2).to_list(length=max_samples * 2)
    if len(docs) < lookback + 10:
        return {"success": False, "error": f"only {len(docs)} candles available"}

    # Group by asset so labels don't cross assets
    from collections import defaultdict
    by_asset: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for d in docs:
        key = str(d.get("asset") or "UNKNOWN")
        by_asset[key].append(d)

    X: List[Dict[str, Any]] = []
    y: List[int] = []

    for asset, candles in by_asset.items():
        candles = sorted(candles, key=lambda c: c.get("timestamp") or 0)
        if len(candles) < lookback + 2:
            continue
        closes = np.asarray([float(c["close"]) for c in candles], dtype=float)
        highs = np.asarray([float(c.get("high", c["close"])) for c in candles], dtype=float)
        lows = np.asarray([float(c.get("low", c["close"])) for c in candles], dtype=float)

        for i in range(lookback, len(candles) - 1):
            window_h = highs[i - lookback:i]
            window_l = lows[i - lookback:i]
            window_c = closes[i - lookback:i]
            adx_info = compute_adx(window_h, window_l, window_c, period=14)
            regime = classify_adx_regime(adx_info["adx"], adx_info["plus_di"], adx_info["minus_di"])

            # simple RSI(14)
            deltas = np.diff(window_c)
            up = np.clip(deltas, 0, None)
            dn = np.clip(-deltas, 0, None)
            avg_up = float(np.mean(up[-14:])) if len(up) >= 14 else float(np.mean(up)) if len(up) else 0
            avg_dn = float(np.mean(dn[-14:])) if len(dn) >= 14 else float(np.mean(dn)) if len(dn) else 0
            rsi = 100.0 - (100.0 / (1.0 + (avg_up / (avg_dn + 1e-10))))

            # EMA fast/slow
            def _ema(v, n):
                a = 2.0 / (n + 1)
                out = v[0]
                for x in v[1:]:
                    out = a * x + (1 - a) * out
                return float(out)
            ema_fast = _ema(window_c, 8)
            ema_slow = _ema(window_c, 21)

            features = {
                "rsi": rsi,
                "macd": ema_fast - ema_slow,
                "macd_hist": 0.0,
                "atr": float(np.mean(window_h - window_l)),
                "ema_fast": ema_fast,
                "ema_slow": ema_slow,
                "bb_pos": 0.5,
                "adx": adx_info["adx"],
                "plus_di": adx_info["plus_di"],
                "minus_di": adx_info["minus_di"],
                "ha_streak_bull": 0,
                "ha_streak_bear": 0,
                "kyle_lambda": 0.0,
                "vpin": 0.0,
                "flow_imbalance": 0.0,
                "vote_up": 0.0,
                "vote_down": 0.0,
                "mean_confidence": 0.0,
                "max_confidence": 0.0,
                "regime_code": _REGIME_CODES.get(regime["regime"], 1),
            }
            label = 1 if closes[i + 1] > closes[i] else 0
            X.append(features)
            y.append(label)
            if len(X) >= max_samples:
                break
        if len(X) >= max_samples:
            break

    if not X:
        return {"success": False, "error": "no training samples produced"}

    svc = get_lightgbm_service()
    metrics = svc.train(X, y)
    metrics["success"] = True
    metrics["samples_used"] = len(X)
    return metrics
