"""
Iter 124 — Rolling Micro-ML Strategy

Inspired by `po_bot_ml.py` (Vitaly Svyatyuk / MIT-licensed public repo). The
philosophy port is: constantly re-fit a TINY model on a short lookback window
so the model tracks short-term regime shifts, rather than relying on a stable
train-once-and-serve pipeline.

What differs from Vitaly's original
--------------------------------------
* **Richer features** — instead of Vitaly's 4 booleans (AO, PSAR, CCI, MACD)
  we use 8 numeric features from our own `feature_builder`: RSI, MACD hist,
  ATR, BB pos, ADX, +DI, -DI, HA bull streak. All continuous (no dummy
  booleans), which lets the RF split more finely.
* **Walk-forward split (not random)** — Vitaly does `train_test_split(...,
  random_state=42)` which leaks future data into training. We use the LAST
  20% of the window as the holdout so the reported accuracy is honest.
* **Probability threshold is tunable** — default 0.60 matches Vitaly's but
  the strategy accepts it as a per-run param for the autotuner.
* **Fire only when holdout accuracy passes a floor** — Vitaly fires whenever
  probability > 0.60 even if the model is trash. We require `holdout_acc ≥
  0.55` so no-signal windows correctly abstain.
* **Composes with LightGBM** — this strategy carries `meta.family='ml_rolling'`
  which the ADX-regime gate treats as NEUTRAL, letting it fire in any regime.

This is a NEW independent signal source. Users can ensemble it with Ridicolous
or LightGBM via the existing ensemble/voting layer.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import accuracy_score
    _SKLEARN_OK = True
except Exception:  # pragma: no cover
    _SKLEARN_OK = False


class RollingMicroML:
    """Per-bar RandomForest fit on a rolling window."""

    name = "🌀 Rolling Micro-ML [Iter 124]"
    timeframe = "1m"
    accuracy_target = 60.0
    beta = True

    def __init__(
        self,
        lookback: int = 200,
        n_estimators: int = 100,
        min_history: int = 80,
        min_confidence: float = 60.0,
        holdout_acc_floor: float = 0.55,
    ) -> None:
        self.lookback = int(np.clip(lookback, 60, 1000))
        self.n_estimators = int(np.clip(n_estimators, 20, 500))
        self.min_history = int(np.clip(min_history, 30, 500))
        self.min_confidence = float(np.clip(min_confidence, 40.0, 95.0))
        self.holdout_acc_floor = float(np.clip(holdout_acc_floor, 0.5, 0.9))

    # ------------------------------------------------------------------
    # Config helpers (for backtest params + config endpoints later)
    # ------------------------------------------------------------------
    def apply_config(self, cfg: Dict[str, Any]) -> Dict[str, Any]:
        if cfg.get("lookback") is not None:
            self.lookback = int(np.clip(int(cfg["lookback"]), 60, 1000))
        if cfg.get("n_estimators") is not None:
            self.n_estimators = int(np.clip(int(cfg["n_estimators"]), 20, 500))
        if cfg.get("min_history") is not None:
            self.min_history = int(np.clip(int(cfg["min_history"]), 30, 500))
        if cfg.get("min_confidence") is not None:
            self.min_confidence = float(np.clip(float(cfg["min_confidence"]), 40.0, 95.0))
        if cfg.get("holdout_acc_floor") is not None:
            self.holdout_acc_floor = float(np.clip(float(cfg["holdout_acc_floor"]), 0.5, 0.9))
        return self.get_config()

    def get_config(self) -> Dict[str, Any]:
        return {
            "lookback": self.lookback,
            "n_estimators": self.n_estimators,
            "min_history": self.min_history,
            "min_confidence": self.min_confidence,
            "holdout_acc_floor": self.holdout_acc_floor,
        }

    # ------------------------------------------------------------------
    # Feature builders (vectorised — no reliance on external libs)
    # ------------------------------------------------------------------
    @staticmethod
    def _rsi(closes: np.ndarray, period: int = 14) -> np.ndarray:
        n = len(closes)
        if n < period + 1:
            return np.full(n, 50.0)
        deltas = np.diff(closes, prepend=closes[0])
        gains = np.where(deltas > 0, deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)
        avg_gain = np.zeros(n)
        avg_loss = np.zeros(n)
        avg_gain[period] = np.mean(gains[1:period + 1])
        avg_loss[period] = np.mean(losses[1:period + 1])
        for i in range(period + 1, n):
            avg_gain[i] = (avg_gain[i - 1] * (period - 1) + gains[i]) / period
            avg_loss[i] = (avg_loss[i - 1] * (period - 1) + losses[i]) / period
        rs = avg_gain / (avg_loss + 1e-12)
        rsi = 100 - (100 / (1 + rs))
        rsi[:period] = 50.0
        return rsi

    @staticmethod
    def _macd_hist(closes: np.ndarray) -> np.ndarray:
        n = len(closes)
        if n < 26:
            return np.zeros(n)
        ema_fast = pd.Series(closes).ewm(span=12, adjust=False).mean().to_numpy()
        ema_slow = pd.Series(closes).ewm(span=26, adjust=False).mean().to_numpy()
        macd = ema_fast - ema_slow
        signal = pd.Series(macd).ewm(span=9, adjust=False).mean().to_numpy()
        return macd - signal

    @staticmethod
    def _atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> np.ndarray:
        n = len(closes)
        if n < 2:
            return np.zeros(n)
        prev_close = np.roll(closes, 1)
        prev_close[0] = closes[0]
        tr = np.maximum.reduce([
            highs - lows,
            np.abs(highs - prev_close),
            np.abs(lows - prev_close),
        ])
        return pd.Series(tr).ewm(alpha=1 / period, adjust=False).mean().to_numpy()

    @staticmethod
    def _bb_pos(closes: np.ndarray, period: int = 20) -> np.ndarray:
        s = pd.Series(closes)
        mid = s.rolling(period, min_periods=1).mean()
        std = s.rolling(period, min_periods=1).std().fillna(0)
        upper = mid + 2 * std
        lower = mid - 2 * std
        rng = (upper - lower).replace(0, np.nan)
        pos = ((s - lower) / rng).fillna(0.5).clip(0, 1)
        return pos.to_numpy()

    @staticmethod
    def _adx_di(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14):
        n = len(closes)
        if n < period + 1:
            z = np.zeros(n)
            return z, z, z
        up = np.diff(highs, prepend=highs[0])
        dn = -np.diff(lows, prepend=lows[0])
        plus_dm = np.where((up > dn) & (up > 0), up, 0.0)
        minus_dm = np.where((dn > up) & (dn > 0), dn, 0.0)
        tr = np.maximum.reduce([
            highs - lows,
            np.abs(highs - np.roll(closes, 1)),
            np.abs(lows - np.roll(closes, 1)),
        ])
        tr[0] = highs[0] - lows[0]
        atr = pd.Series(tr).ewm(alpha=1 / period, adjust=False).mean().to_numpy()
        plus_di = 100 * pd.Series(plus_dm).ewm(alpha=1 / period, adjust=False).mean().to_numpy() / (atr + 1e-12)
        minus_di = 100 * pd.Series(minus_dm).ewm(alpha=1 / period, adjust=False).mean().to_numpy() / (atr + 1e-12)
        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di + 1e-12)
        adx = pd.Series(dx).ewm(alpha=1 / period, adjust=False).mean().to_numpy()
        return adx, plus_di, minus_di

    @staticmethod
    def _ha_bull_streak(opens: np.ndarray, closes: np.ndarray) -> np.ndarray:
        """Simple bull-candle streak (not full HA — closes>opens counter)."""
        bull = closes > opens
        streak = np.zeros(len(closes), dtype=int)
        run = 0
        for i, b in enumerate(bull):
            if b:
                run += 1
            else:
                run = 0
            streak[i] = run
        return streak

    def _build_feature_matrix(self, df: pd.DataFrame) -> np.ndarray:
        o = df["open"].to_numpy(dtype=float)
        h = df["high"].to_numpy(dtype=float)
        l = df["low"].to_numpy(dtype=float)
        c = df["close"].to_numpy(dtype=float)
        adx, plus_di, minus_di = self._adx_di(h, l, c)
        feats = np.column_stack([
            self._rsi(c),
            self._macd_hist(c),
            self._atr(h, l, c),
            self._bb_pos(c),
            adx,
            plus_di,
            minus_di,
            self._ha_bull_streak(o, c),
        ])
        # Sanitize nans/inf
        feats = np.nan_to_num(feats, nan=0.0, posinf=0.0, neginf=0.0)
        return feats

    # ------------------------------------------------------------------
    # Signal
    # ------------------------------------------------------------------
    def generate_signal(self, df: pd.DataFrame) -> Dict[str, Any]:
        if not _SKLEARN_OK:
            return self._neutral("sklearn not available")
        if df is None or len(df) < self.min_history:
            return self._neutral(f"insufficient history ({0 if df is None else len(df)}/{self.min_history})")

        try:
            df = df[["open", "high", "low", "close"]].astype(float).copy()
        except Exception as e:
            return self._neutral(f"missing OHLC column: {e}")

        window = df.iloc[-self.lookback:] if len(df) >= self.lookback else df
        n = len(window)
        if n < self.min_history:
            return self._neutral(f"window too small ({n}/{self.min_history})")

        try:
            feats = self._build_feature_matrix(window)
        except Exception as e:
            return self._neutral(f"feature build failed: {e}")

        # Label: next-bar direction — 1 if close_{i+1} > close_i else 0
        closes = window["close"].to_numpy()
        # X uses features[i], y uses direction of (i → i+1). Last row has no
        # label yet — that's what we predict on.
        X_all = feats[:-1]
        y = (closes[1:] > closes[:-1]).astype(int)
        if len(X_all) < self.min_history or len(np.unique(y)) < 2:
            return self._neutral("single-class training set")

        # Walk-forward split (last 20% is holdout, chronologically)
        split = int(len(X_all) * 0.8)
        X_train, X_test = X_all[:split], X_all[split:]
        y_train, y_test = y[:split], y[split:]

        try:
            model = RandomForestClassifier(
                n_estimators=self.n_estimators,
                max_depth=6,
                min_samples_leaf=3,
                random_state=42,
                n_jobs=1,
            )
            model.fit(X_train, y_train)
            holdout_acc = float(accuracy_score(y_test, model.predict(X_test))) if len(X_test) else 0.0
            proba = model.predict_proba(feats[-1:])
        except Exception as e:
            return self._neutral(f"training failed: {e}")

        # sklearn `classes_` may be [0, 1] or [1, 0] depending on training data
        classes = list(model.classes_)
        idx_up = classes.index(1) if 1 in classes else None
        idx_dn = classes.index(0) if 0 in classes else None
        p_up = float(proba[0][idx_up]) if idx_up is not None else 0.5
        p_dn = float(proba[0][idx_dn]) if idx_dn is not None else 0.5

        # Gate 1: holdout accuracy floor
        if holdout_acc < self.holdout_acc_floor:
            return self._neutral(
                f"holdout_acc {holdout_acc:.2f} < floor {self.holdout_acc_floor:.2f}",
                extra={"holdout_acc": holdout_acc, "p_up": p_up, "p_dn": p_dn},
            )

        # Gate 2: probability threshold
        if p_up >= p_dn:
            direction = "CALL"
            confidence = p_up * 100.0
        else:
            direction = "PUT"
            confidence = p_dn * 100.0

        if confidence < self.min_confidence:
            return self._neutral(
                f"conf {confidence:.1f}% < min {self.min_confidence:.1f}%",
                extra={"holdout_acc": holdout_acc, "p_up": p_up, "p_dn": p_dn},
            )

        return {
            "direction": direction,
            "confidence": round(min(confidence, 99.0), 2),
            "reason": (
                f"RF({self.n_estimators}) · lookback={self.lookback} · "
                f"holdout_acc={holdout_acc:.2f} · p_up={p_up:.2f}"
            ),
            "strategy": self.name,
            "timeframe": self.timeframe,
            "indicators": {
                "holdout_accuracy": round(holdout_acc, 4),
                "p_up": round(p_up, 4),
                "p_dn": round(p_dn, 4),
                "training_samples": len(X_train),
                "holdout_samples": len(X_test),
                "lookback_used": n,
                "feature_importances": {
                    fname: float(round(imp, 4))
                    for fname, imp in zip(
                        ["rsi", "macd_hist", "atr", "bb_pos", "adx", "plus_di", "minus_di", "ha_bull_streak"],
                        model.feature_importances_,
                    )
                },
            },
            "meta": {
                "family": "ml_rolling",
                "source": "port_from_po_bot_ml.py__vitalysvyatyuk",
                "n_estimators": self.n_estimators,
                "min_confidence": self.min_confidence,
                "holdout_acc_floor": self.holdout_acc_floor,
            },
        }

    def _neutral(self, reason: str, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {
            "direction": "NEUTRAL",
            "confidence": 0,
            "reason": reason,
            "strategy": self.name,
            "timeframe": self.timeframe,
            "indicators": (extra or {}),
            "meta": {"family": "ml_rolling", "source": "port_from_po_bot_ml.py__vitalysvyatyuk"},
        }


# ---------------------------------------------------------------------------
rolling_micro_ml = RollingMicroML()
ROLLING_ML_STRATEGIES = {
    "rolling_micro_ml": rolling_micro_ml,
}
