"""Iter 139 — Mean Reversion Playbook.

Dedicated regime-aware strategy for RANGING OTC pairs. Fires only when
several independent mean-reversion filters agree:

    1. **Regime filter (ADX < 20)** — market must be non-trending. ADX
       above the threshold → skip (mean reversion loses on strong trends).
    2. **Z-score(price, EMA_N)** at extreme (|z| ≥ 2.0 default).
    3. **RSI** at overbought (≥ 70) / oversold (≤ 30).
    4. **Bollinger tag** — bar's high pierces upper band OR low pierces
       lower band.
    5. Optional **volume fade** confirmation — if the tag bar has volume
       below the last-20 average, the reversion odds go up.

Returns a `MeanReversionSignal` dict compatible with the confluence
engine (source `strategy:mean_reversion`). Consumers can either use the
strategy standalone or feed the signal into `score_confluence`.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


@dataclass
class MeanReversionSignal:
    direction: str                    # "CALL" | "PUT" | "NEUTRAL"
    confidence: float                 # [0, 1]
    reason: str
    entry: Optional[float]
    stop: Optional[float]
    target: Optional[float]
    meta: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Indicators
# ---------------------------------------------------------------------------

def _ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    up = delta.clip(lower=0.0)
    dn = -delta.clip(upper=0.0)
    roll_up = up.ewm(alpha=1.0 / period, adjust=False).mean()
    roll_dn = dn.ewm(alpha=1.0 / period, adjust=False).mean()
    rs = roll_up / roll_dn.replace(0.0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50.0)


def _adx(df: pd.DataFrame, period: int = 14) -> float:
    """Wilder's ADX — single scalar for the LAST bar."""
    if len(df) < period * 2 + 2:
        return 0.0
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    close = df["close"].astype(float)
    plus_dm = (high.diff().clip(lower=0)).where(
        (high.diff() > -low.diff()) & (high.diff() > 0), 0.0
    )
    minus_dm = ((-low.diff()).clip(lower=0)).where(
        (-low.diff() > high.diff()) & (-low.diff() > 0), 0.0
    )
    tr = pd.concat(
        [
            high - low,
            (high - close.shift()).abs(),
            (low - close.shift()).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr = tr.ewm(alpha=1.0 / period, adjust=False).mean().replace(0.0, np.nan)
    plus_di = 100 * plus_dm.ewm(alpha=1.0 / period, adjust=False).mean() / atr
    minus_di = 100 * minus_dm.ewm(alpha=1.0 / period, adjust=False).mean() / atr
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0.0, np.nan)
    adx = dx.ewm(alpha=1.0 / period, adjust=False).mean()
    val = adx.iloc[-1]
    return 0.0 if pd.isna(val) else float(val)


def _bollinger(close: pd.Series, period: int = 20, k: float = 2.0):
    ma = close.rolling(period).mean()
    sd = close.rolling(period).std(ddof=0)
    upper = ma + k * sd
    lower = ma - k * sd
    return ma, upper, lower


# ---------------------------------------------------------------------------
# Strategy entry point
# ---------------------------------------------------------------------------

def mean_reversion_signal(
    df: pd.DataFrame,
    *,
    ema_period: int = 20,
    z_threshold: float = 2.0,
    rsi_period: int = 14,
    rsi_overbought: float = 70.0,
    rsi_oversold: float = 30.0,
    adx_period: int = 14,
    adx_max: float = 20.0,
    bb_period: int = 20,
    bb_k: float = 2.0,
) -> MeanReversionSignal:
    """Compute the mean-reversion signal for the LAST bar.

    Returns NEUTRAL when the regime is trending (ADX ≥ adx_max) or when
    fewer than 2 of {z-score, RSI, BB} agree on direction.
    """
    n_needed = max(bb_period, ema_period, rsi_period, adx_period * 2) + 5
    if df is None or len(df) < n_needed:
        return MeanReversionSignal(
            direction="NEUTRAL", confidence=0.0,
            reason=f"insufficient data ({len(df) if df is not None else 0} < {n_needed})",
            entry=None, stop=None, target=None, meta={},
        )
    required = {"open", "high", "low", "close"}
    if not required.issubset(df.columns):
        return MeanReversionSignal(
            direction="NEUTRAL", confidence=0.0,
            reason="missing OHLC columns", entry=None, stop=None, target=None, meta={},
        )

    close = df["close"].astype(float)

    # Regime filter
    adx = _adx(df, adx_period)
    if adx >= adx_max:
        return MeanReversionSignal(
            direction="NEUTRAL", confidence=0.0,
            reason=f"trending regime (ADX={adx:.1f} ≥ {adx_max})",
            entry=None, stop=None, target=None,
            meta={"adx": adx, "adx_max": adx_max},
        )

    # Indicators on the last bar
    ema = _ema(close, ema_period)
    resid = close - ema
    std = resid.rolling(ema_period).std(ddof=0).iloc[-1]
    if not std or pd.isna(std) or std == 0:
        return MeanReversionSignal(
            direction="NEUTRAL", confidence=0.0,
            reason="std=0 — flat price, no signal",
            entry=None, stop=None, target=None, meta={"adx": adx},
        )
    z = float((close.iloc[-1] - ema.iloc[-1]) / std)

    rsi_series = _rsi(close, rsi_period)
    rsi = float(rsi_series.iloc[-1])

    _, upper, lower = _bollinger(close, bb_period, bb_k)
    last_high = float(df["high"].iloc[-1])
    last_low = float(df["low"].iloc[-1])
    upper_now = float(upper.iloc[-1]) if not pd.isna(upper.iloc[-1]) else None
    lower_now = float(lower.iloc[-1]) if not pd.isna(lower.iloc[-1]) else None

    bb_tag_upper = upper_now is not None and last_high >= upper_now
    bb_tag_lower = lower_now is not None and last_low <= lower_now

    # Volume fade (optional)
    vol_fade = False
    if "volume" in df.columns and len(df) >= 20:
        v = df["volume"].astype(float)
        if v.iloc[-1] < v.iloc[-20:].mean() * 0.9:
            vol_fade = True

    # Score each side — need at least 2/3 agreement on same direction
    put_votes: List[str] = []
    if z >= z_threshold: put_votes.append(f"z={z:.2f}")
    if rsi >= rsi_overbought: put_votes.append(f"RSI={rsi:.1f}")
    if bb_tag_upper: put_votes.append("BB upper tag")

    call_votes: List[str] = []
    if z <= -z_threshold: call_votes.append(f"z={z:.2f}")
    if rsi <= rsi_oversold: call_votes.append(f"RSI={rsi:.1f}")
    if bb_tag_lower: call_votes.append("BB lower tag")

    direction = "NEUTRAL"
    votes: List[str] = []
    if len(put_votes) >= 2 and len(put_votes) > len(call_votes):
        direction, votes = "PUT", put_votes
    elif len(call_votes) >= 2 and len(call_votes) > len(put_votes):
        direction, votes = "CALL", call_votes

    if direction == "NEUTRAL":
        return MeanReversionSignal(
            direction="NEUTRAL", confidence=0.0,
            reason="fewer than 2 filters agree",
            entry=None, stop=None, target=None,
            meta={
                "adx": adx, "z_score": z, "rsi": rsi,
                "bb_upper": upper_now, "bb_lower": lower_now,
                "put_votes": put_votes, "call_votes": call_votes,
            },
        )

    # Confidence: base 0.55 + 0.10 per extra vote + 0.10 for volume fade + 0.10 for low ADX
    conf = 0.55 + 0.10 * (len(votes) - 2)  # 2 votes = 0.55, 3 votes = 0.65
    if vol_fade: conf += 0.10
    if adx < adx_max * 0.6: conf += 0.10   # very quiet market: high-quality mean-rev
    conf = min(0.90, conf)

    price = float(close.iloc[-1])
    if direction == "PUT":
        entry = price
        stop = float(df["high"].iloc[-1])
        target = float(ema.iloc[-1])       # revert to the mean
    else:
        entry = price
        stop = float(df["low"].iloc[-1])
        target = float(ema.iloc[-1])

    return MeanReversionSignal(
        direction=direction,
        confidence=conf,
        reason=f"{direction} · " + " · ".join(votes) + (" · vol-fade" if vol_fade else "") + f" · ADX={adx:.1f}",
        entry=entry, stop=stop, target=target,
        meta={
            "adx": adx, "z_score": z, "rsi": rsi,
            "bb_upper": upper_now, "bb_lower": lower_now,
            "vol_fade": vol_fade,
            "put_votes": put_votes, "call_votes": call_votes,
        },
    )
