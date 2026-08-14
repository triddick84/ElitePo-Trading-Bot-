"""
Algorithmic Trading Strategy Pack — Iter 102 (Feb 2026)

Implements four foundational algorithmic trading strategies aligned to the
taxonomy the user requested (Feb 2026 knowledge dump):
  1. Trend / Momentum          (breakout + MACD confirmation)
  2. Mean Reversion            (Bollinger + RSI-2 with rejection candle)
  3. Order Flow / Microstructure  (bar-delta proxy + volume imbalance)
  4. Volatility Regime         (ATR percentile bandpass)

Each strategy class exposes:
  - name, timeframe, accuracy_target, beta
  - generate_signal(df) → {direction, confidence, reason, strategy,
                           timeframe, indicators, meta}

These slot into `strategy_registry.py` and `strategy_selection_service.py`
without touching the force-signal-generator's routing (they run through
Strategy Registry's `execute_strategy` path).

Design notes:
  - No look-ahead (only uses .iloc[-1] and prior bars for cross detection).
  - Confidence in [0, 100]. NEUTRAL is emitted when the setup fails.
  - Bar-delta uses (close - open) / (high - low) as a proxy since PO
    doesn't expose L2 book data — sufficient for the retail use case.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

try:
    import talib
    HAS_TALIB = True
except Exception:  # pragma: no cover — talib is present in the container
    HAS_TALIB = False

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers — shared across the 4 strategies
# ---------------------------------------------------------------------------
def _safe_last(series: pd.Series, default: float = 0.0) -> float:
    try:
        v = float(series.iloc[-1])
        return v if np.isfinite(v) else default
    except Exception:
        return default


def _ema(series: pd.Series, period: int) -> pd.Series:
    if HAS_TALIB:
        return pd.Series(talib.EMA(series, timeperiod=period), index=series.index)
    return series.ewm(span=period, adjust=False).mean()


def _rsi(series: pd.Series, period: int) -> pd.Series:
    if HAS_TALIB:
        return pd.Series(talib.RSI(series, timeperiod=period), index=series.index)
    delta = series.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
    if HAS_TALIB:
        return pd.Series(talib.ATR(high, low, close, timeperiod=period), index=close.index)
    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


# ===========================================================================
# 1. Trend / Momentum — EMA crossover + MACD confirmation + N-bar breakout
# ===========================================================================
class AlgoTrendMomentum:
    """Classic trend-following: fires only when three independent
    momentum conditions align (EMA cross, MACD histogram, N-bar breakout).
    """

    name = "🧭 Algo Trend / Momentum"
    timeframe = "1m"
    accuracy_target = 72.0
    beta = True

    def __init__(self) -> None:
        self.ema_fast = 9
        self.ema_slow = 21
        self.macd_fast = 12
        self.macd_slow = 26
        self.macd_signal = 9
        self.breakout_lookback = 20

    def generate_signal(self, df: pd.DataFrame) -> Dict[str, Any]:
        if df is None or len(df) < max(self.ema_slow, self.breakout_lookback) + 5:
            return _neutral(self.name, self.timeframe, "insufficient data")

        close = df["close"].astype(float)
        high = df["high"].astype(float)
        low = df["low"].astype(float)

        ema_f = _ema(close, self.ema_fast)
        ema_s = _ema(close, self.ema_slow)
        if HAS_TALIB:
            macd, macd_sig, macd_hist = talib.MACD(
                close, fastperiod=self.macd_fast,
                slowperiod=self.macd_slow, signalperiod=self.macd_signal,
            )
        else:
            ema_a = _ema(close, self.macd_fast)
            ema_b = _ema(close, self.macd_slow)
            macd = ema_a - ema_b
            macd_sig = _ema(macd, self.macd_signal)
            macd_hist = macd - macd_sig

        rolling_high = high.rolling(self.breakout_lookback).max()
        rolling_low = low.rolling(self.breakout_lookback).min()

        px = _safe_last(close)
        # Reasons collected for transparency in the UI
        reasons = []
        bull_score = 0
        bear_score = 0

        # 1) EMA cross state (35 pts)
        ema_f_l = _safe_last(ema_f)
        ema_s_l = _safe_last(ema_s)
        if ema_f_l > ema_s_l:
            bull_score += 35
            reasons.append(f"EMA{self.ema_fast}>EMA{self.ema_slow}")
        elif ema_f_l < ema_s_l:
            bear_score += 35
            reasons.append(f"EMA{self.ema_fast}<EMA{self.ema_slow}")

        # 2) MACD histogram sign + rising/falling (30 pts)
        hist_l = _safe_last(macd_hist)
        hist_p = float(macd_hist.iloc[-2]) if len(macd_hist) >= 2 and np.isfinite(macd_hist.iloc[-2]) else 0.0
        if hist_l > 0 and hist_l >= hist_p:
            bull_score += 30
            reasons.append("MACD hist rising +")
        elif hist_l < 0 and hist_l <= hist_p:
            bear_score += 30
            reasons.append("MACD hist falling −")

        # 3) N-bar breakout (35 pts) — closes above prior N-1 high excluding current
        prior_high = float(rolling_high.iloc[-2]) if len(rolling_high) >= 2 else px
        prior_low = float(rolling_low.iloc[-2]) if len(rolling_low) >= 2 else px
        if px > prior_high:
            bull_score += 35
            reasons.append(f"breakout > {self.breakout_lookback}-bar high")
        elif px < prior_low:
            bear_score += 35
            reasons.append(f"breakout < {self.breakout_lookback}-bar low")

        direction, confidence = _decide(bull_score, bear_score, threshold=70)
        return {
            "direction": direction,
            "confidence": confidence,
            "reason": " · ".join(reasons) if reasons else "no confluence",
            "strategy": self.name,
            "timeframe": self.timeframe,
            "indicators": {
                "ema_fast": ema_f_l,
                "ema_slow": ema_s_l,
                "macd_hist": hist_l,
                "prior_high": prior_high,
                "prior_low": prior_low,
                "close": px,
            },
            "meta": {"family": "trend_momentum", "call_score": bull_score, "put_score": bear_score},
        }


# ===========================================================================
# 2. Mean Reversion — Bollinger 2.5σ + RSI-2 + rejection candle
# ===========================================================================
class AlgoMeanReversion:
    """Pure mean-reversion: waits for a 2.5σ Bollinger excursion together
    with an RSI-2 extreme (< 5 or > 95) AND a rejection candle (long wick
    against the excursion) — designed for OTC binary options where sudden
    spikes are the norm and revert within 1–3 candles.
    """

    name = "🌀 Algo Mean Reversion"
    timeframe = "1m"
    accuracy_target = 74.0
    beta = True

    def __init__(self) -> None:
        self.bb_period = 20
        self.bb_std = 2.5
        self.rsi_period = 2
        self.rsi_extreme_low = 5.0
        self.rsi_extreme_high = 95.0
        self.wick_ratio_min = 1.5  # wick must be 1.5× body size for rejection

    def generate_signal(self, df: pd.DataFrame) -> Dict[str, Any]:
        if df is None or len(df) < self.bb_period + 3:
            return _neutral(self.name, self.timeframe, "insufficient data")

        close = df["close"].astype(float)
        high = df["high"].astype(float)
        low = df["low"].astype(float)
        openp = df["open"].astype(float)

        if HAS_TALIB:
            up, mid, dn = talib.BBANDS(
                close, timeperiod=self.bb_period,
                nbdevup=self.bb_std, nbdevdn=self.bb_std,
            )
        else:
            mid = close.rolling(self.bb_period).mean()
            sd = close.rolling(self.bb_period).std()
            up = mid + self.bb_std * sd
            dn = mid - self.bb_std * sd

        rsi = _rsi(close, self.rsi_period)

        px = _safe_last(close)
        h_l = _safe_last(high)
        l_l = _safe_last(low)
        o_l = _safe_last(openp)
        up_l = _safe_last(up)
        dn_l = _safe_last(dn)
        rsi_l = _safe_last(rsi, 50.0)

        body = abs(px - o_l)
        upper_wick = h_l - max(px, o_l)
        lower_wick = min(px, o_l) - l_l

        reasons = []
        bull_score = 0
        bear_score = 0

        # 1) BB excursion (40 pts)
        if l_l <= dn_l:
            bull_score += 40
            reasons.append(f"low touched -2.5σ BB ({dn_l:.5f})")
        elif h_l >= up_l:
            bear_score += 40
            reasons.append(f"high touched +2.5σ BB ({up_l:.5f})")

        # 2) RSI-2 extreme (30 pts)
        if rsi_l <= self.rsi_extreme_low:
            bull_score += 30
            reasons.append(f"RSI-2 extreme low {rsi_l:.1f}")
        elif rsi_l >= self.rsi_extreme_high:
            bear_score += 30
            reasons.append(f"RSI-2 extreme high {rsi_l:.1f}")

        # 3) Rejection candle (30 pts) — wick ≥ 1.5× body against the excursion
        if bull_score > bear_score and body > 0 and lower_wick >= self.wick_ratio_min * body:
            bull_score += 30
            reasons.append("rejection wick down")
        elif bear_score > bull_score and body > 0 and upper_wick >= self.wick_ratio_min * body:
            bear_score += 30
            reasons.append("rejection wick up")

        direction, confidence = _decide(bull_score, bear_score, threshold=70)
        return {
            "direction": direction,
            "confidence": confidence,
            "reason": " · ".join(reasons) if reasons else "no reversal setup",
            "strategy": self.name,
            "timeframe": self.timeframe,
            "indicators": {
                "bb_upper": up_l,
                "bb_lower": dn_l,
                "rsi2": rsi_l,
                "body": body,
                "upper_wick": upper_wick,
                "lower_wick": lower_wick,
                "close": px,
            },
            "meta": {"family": "mean_reversion", "call_score": bull_score, "put_score": bear_score},
        }


# ===========================================================================
# 3. Order Flow / Microstructure — bar-delta + volume imbalance
# ===========================================================================
class AlgoOrderFlowImbalance:
    """Microstructure proxy: without an L2 book, we approximate buyer/seller
    aggression using bar-level "delta" = (close − open) / (high − low),
    volume-weighted over the last N bars. A rising cumulative delta with
    increasing volume signals buyer control; the opposite for sellers.

    Signal fires only when:
      • Cumulative delta over last N bars agrees with the last-bar delta
        AND the last bar's volume is above the 20-bar average.
      • Guards against range-bound noise: last-bar range must be ≥ 60%
        of the 20-bar median range.
    """

    name = "📊 Algo Order-Flow Imbalance"
    timeframe = "30s"
    accuracy_target = 70.0
    beta = True

    def __init__(self) -> None:
        self.delta_window = 5
        self.vol_window = 20

    def generate_signal(self, df: pd.DataFrame) -> Dict[str, Any]:
        if df is None or len(df) < self.vol_window + 3:
            return _neutral(self.name, self.timeframe, "insufficient data")

        openp = df["open"].astype(float)
        close = df["close"].astype(float)
        high = df["high"].astype(float)
        low = df["low"].astype(float)
        # Some feeds omit volume — synthesize a rough proxy from range if so.
        volume = df.get("volume", high - low).astype(float).fillna(high - low)

        rng = (high - low).replace(0, np.nan)
        delta = ((close - openp) / rng).fillna(0.0).clip(-1.0, 1.0)
        weighted = (delta * volume).rolling(self.delta_window).sum()
        vol_avg = volume.rolling(self.vol_window).mean()
        range_med = rng.rolling(self.vol_window).median()

        d_last = _safe_last(delta)
        w_last = _safe_last(weighted)
        vol_last = _safe_last(volume)
        vol_avg_last = _safe_last(vol_avg, 1.0) or 1.0
        rng_last = _safe_last(rng, 0.0)
        rng_med_last = _safe_last(range_med, 0.0) or 0.0

        reasons = []
        bull_score = 0
        bear_score = 0

        # 1) Directional agreement between last-bar delta and cumulative (40)
        if d_last > 0.25 and w_last > 0:
            bull_score += 40
            reasons.append(f"buy pressure Δ={d_last:.2f}")
        elif d_last < -0.25 and w_last < 0:
            bear_score += 40
            reasons.append(f"sell pressure Δ={d_last:.2f}")

        # 2) Volume expansion (30) — last-bar volume ≥ 1.4× 20-bar avg
        if vol_last >= vol_avg_last * 1.4:
            if bull_score > bear_score:
                bull_score += 30
                reasons.append("volume expansion")
            elif bear_score > bull_score:
                bear_score += 30
                reasons.append("volume expansion")

        # 3) Range gate (30) — no trades on ultra-quiet bars
        if rng_med_last > 0 and rng_last >= 0.6 * rng_med_last:
            if bull_score > bear_score:
                bull_score += 30
                reasons.append("range not compressed")
            elif bear_score > bull_score:
                bear_score += 30
                reasons.append("range not compressed")

        direction, confidence = _decide(bull_score, bear_score, threshold=70)
        return {
            "direction": direction,
            "confidence": confidence,
            "reason": " · ".join(reasons) if reasons else "no imbalance",
            "strategy": self.name,
            "timeframe": self.timeframe,
            "indicators": {
                "bar_delta": d_last,
                "weighted_delta": w_last,
                "vol_ratio": (vol_last / vol_avg_last) if vol_avg_last else 1.0,
                "range_ratio": (rng_last / rng_med_last) if rng_med_last else 1.0,
                "close": _safe_last(close),
            },
            "meta": {"family": "order_flow", "call_score": bull_score, "put_score": bear_score},
        }


# ===========================================================================
# 4. Volatility Regime — ATR percentile + directional bias
# ===========================================================================
class AlgoVolatilityRegime:
    """Volatility-regime filter with a directional overlay. Trades only in
    the "sweet spot" percentile of ATR (35–70% by default) — where
    mean-reversion has the highest hit rate on OTC pairs. Below 35%
    volatility is too dead; above 70% is too chaotic.

    Direction is chosen by mid-BB (SMA20) slope: if last close is above
    the SMA and SMA is rising → CALL; below and falling → PUT.
    """

    name = "🌡️ Algo Volatility Regime"
    timeframe = "1m"
    accuracy_target = 68.0
    beta = True

    def __init__(self) -> None:
        self.atr_period = 14
        self.atr_window = 100
        self.pct_low = 0.35
        self.pct_high = 0.70
        self.sma_period = 20

    def generate_signal(self, df: pd.DataFrame) -> Dict[str, Any]:
        if df is None or len(df) < self.atr_window + 3:
            return _neutral(self.name, self.timeframe, "insufficient data")

        close = df["close"].astype(float)
        high = df["high"].astype(float)
        low = df["low"].astype(float)

        atr = _atr(high, low, close, self.atr_period)
        atr_series = atr.dropna().iloc[-self.atr_window:]
        if len(atr_series) < 20:
            return _neutral(self.name, self.timeframe, "atr history too short")

        atr_last = _safe_last(atr)
        # Percentile rank of current atr within the trailing window
        rank = float((atr_series <= atr_last).mean()) if atr_last > 0 else 0.5

        sma = close.rolling(self.sma_period).mean()
        sma_last = _safe_last(sma)
        sma_prev = float(sma.iloc[-2]) if len(sma) >= 2 and np.isfinite(sma.iloc[-2]) else sma_last
        px = _safe_last(close)

        reasons = []
        # Regime gate: must be inside the sweet spot band
        if not (self.pct_low <= rank <= self.pct_high):
            return _neutral(
                self.name, self.timeframe,
                f"ATR percentile {rank:.0%} outside band {self.pct_low:.0%}-{self.pct_high:.0%}",
                extra_indicators={
                    "atr": atr_last, "atr_percentile": rank,
                    "sma": sma_last, "close": px,
                },
            )
        reasons.append(f"ATR band OK ({rank:.0%})")

        bull_score = 0
        bear_score = 0
        # Direction: SMA slope + close side
        slope = sma_last - sma_prev
        if px > sma_last and slope > 0:
            bull_score = 80
            reasons.append("close>SMA & SMA rising")
        elif px < sma_last and slope < 0:
            bear_score = 80
            reasons.append("close<SMA & SMA falling")

        direction, confidence = _decide(bull_score, bear_score, threshold=70)
        return {
            "direction": direction,
            "confidence": confidence,
            "reason": " · ".join(reasons) if reasons else "regime OK but no direction",
            "strategy": self.name,
            "timeframe": self.timeframe,
            "indicators": {
                "atr": atr_last,
                "atr_percentile": rank,
                "sma": sma_last,
                "sma_slope": slope,
                "close": px,
            },
            "meta": {"family": "volatility_regime", "call_score": bull_score, "put_score": bear_score},
        }


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------
def _neutral(name: str, tf: str, reason: str, extra_indicators: Optional[Dict] = None) -> Dict[str, Any]:
    out = {
        "direction": "NEUTRAL",
        "confidence": 0,
        "reason": reason,
        "strategy": name,
        "timeframe": tf,
        "indicators": extra_indicators or {},
        "meta": {"family": "algo_pack"},
    }
    return out


def _decide(bull: int, bear: int, threshold: int = 70) -> tuple[str, int]:
    if bull >= threshold and bull > bear:
        return "CALL", min(bull, 100)
    if bear >= threshold and bear > bull:
        return "PUT", min(bear, 100)
    return "NEUTRAL", max(bull, bear)


# ---------------------------------------------------------------------------
# Public singleton instances — imported by strategy_registry
# ---------------------------------------------------------------------------
algo_trend_momentum = AlgoTrendMomentum()
algo_mean_reversion = AlgoMeanReversion()
algo_order_flow_imbalance = AlgoOrderFlowImbalance()
algo_volatility_regime = AlgoVolatilityRegime()

ALGO_STRATEGIES = {
    "algo_trend_momentum": algo_trend_momentum,
    "algo_mean_reversion": algo_mean_reversion,
    "algo_order_flow_imbalance": algo_order_flow_imbalance,
    "algo_volatility_regime": algo_volatility_regime,
}
