"""
Custom Strategy Builder Service
================================

Allows users to create, save, and manage custom trading strategies
with full condition builder logic (AND/OR combinations of indicators).

Supports all Pocket Option indicators including:
- Trend indicators (SMA, EMA, WMA, VWMA, etc.)
- Momentum indicators (RSI, MACD, Stochastic, CCI, etc.)
- Volatility indicators (Bollinger Bands, ATR, Keltner Channel, etc.)
- Volume indicators (Volume, OBV, etc.)
- Custom patterns (Support/Resistance, Candlestick patterns)
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict
from enum import Enum
import uuid
import json
import numpy as np
import pandas as pd
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


class IndicatorCategory(str, Enum):
    """Indicator categories"""
    TREND = "trend"
    MOMENTUM = "momentum"
    VOLATILITY = "volatility"
    VOLUME = "volume"
    OSCILLATOR = "oscillator"
    PATTERN = "pattern"
    CUSTOM = "custom"


class ComparisonOperator(str, Enum):
    """Comparison operators for conditions"""
    GREATER_THAN = ">"
    LESS_THAN = "<"
    EQUAL = "="
    GREATER_EQUAL = ">="
    LESS_EQUAL = "<="
    CROSSES_ABOVE = "crosses_above"
    CROSSES_BELOW = "crosses_below"
    BETWEEN = "between"
    NOT_BETWEEN = "not_between"


class LogicalOperator(str, Enum):
    """Logical operators for combining conditions"""
    AND = "AND"
    OR = "OR"


class SignalDirection(str, Enum):
    """Signal direction"""
    CALL = "CALL"
    PUT = "PUT"


# All available indicators with their parameters
AVAILABLE_INDICATORS = {
    # Trend Indicators
    "SMA": {
        "name": "Simple Moving Average",
        "category": IndicatorCategory.TREND,
        "parameters": {
            "period": {"type": "int", "default": 14, "min": 1, "max": 500, "description": "Period length"}
        },
        "outputs": ["value"]
    },
    "EMA": {
        "name": "Exponential Moving Average",
        "category": IndicatorCategory.TREND,
        "parameters": {
            "period": {"type": "int", "default": 14, "min": 1, "max": 500, "description": "Period length"}
        },
        "outputs": ["value"]
    },
    "WMA": {
        "name": "Weighted Moving Average",
        "category": IndicatorCategory.TREND,
        "parameters": {
            "period": {"type": "int", "default": 14, "min": 1, "max": 500, "description": "Period length"}
        },
        "outputs": ["value"]
    },
    "TMA": {
        # Iter 129 — Triangular Moving Average (double-smoothed SMA).
        # Centre-weighted, low-noise trend filter.
        "name": "Triangular Moving Average",
        "category": IndicatorCategory.TREND,
        "parameters": {
            "period": {"type": "int", "default": 14, "min": 2, "max": 500, "description": "Period length"}
        },
        "outputs": ["value"]
    },
    "TRIPLE_MA_CROSSOVER": {
        # Iter 129 — 3-MA ribbon with per-line type selection.
        # e.g. fast=EMA(5), medium=WMA(13), slow=TMA(34) or any combination.
        "name": "3 Moving Averages Crossover",
        "category": IndicatorCategory.TREND,
        "parameters": {
            "fast_type":     {"type": "select", "default": "EMA", "options": ["SMA", "EMA", "WMA", "TMA"], "description": "Fast MA type"},
            "fast_period":   {"type": "int",    "default": 5,     "min": 2, "max": 100, "description": "Fast period"},
            "medium_type":   {"type": "select", "default": "WMA", "options": ["SMA", "EMA", "WMA", "TMA"], "description": "Medium MA type"},
            "medium_period": {"type": "int",    "default": 13,    "min": 2, "max": 200, "description": "Medium period"},
            "slow_type":     {"type": "select", "default": "TMA", "options": ["SMA", "EMA", "WMA", "TMA"], "description": "Slow MA type"},
            "slow_period":   {"type": "int",    "default": 34,    "min": 2, "max": 400, "description": "Slow period"},
        },
        "outputs": ["fast", "medium", "slow", "alignment"]
    },
    "VWMA": {
        "name": "Volume Weighted Moving Average",
        "category": IndicatorCategory.TREND,
        "parameters": {
            "period": {"type": "int", "default": 20, "min": 1, "max": 500, "description": "Period length"}
        },
        "outputs": ["value"]
    },
    "DEMA": {
        "name": "Double Exponential Moving Average",
        "category": IndicatorCategory.TREND,
        "parameters": {
            "period": {"type": "int", "default": 14, "min": 1, "max": 500, "description": "Period length"}
        },
        "outputs": ["value"]
    },
    "TEMA": {
        "name": "Triple Exponential Moving Average",
        "category": IndicatorCategory.TREND,
        "parameters": {
            "period": {"type": "int", "default": 14, "min": 1, "max": 500, "description": "Period length"}
        },
        "outputs": ["value"]
    },
    "SUPERTREND": {
        "name": "SuperTrend",
        "category": IndicatorCategory.TREND,
        "parameters": {
            "period": {"type": "int", "default": 10, "min": 1, "max": 100, "description": "ATR Period"},
            "multiplier": {"type": "float", "default": 3.0, "min": 0.1, "max": 10.0, "description": "ATR Multiplier"}
        },
        "outputs": ["value", "direction"]
    },
    "PARABOLIC_SAR": {
        "name": "Parabolic SAR",
        "category": IndicatorCategory.TREND,
        "parameters": {
            "acceleration": {"type": "float", "default": 0.02, "min": 0.01, "max": 0.5, "description": "Acceleration factor"},
            "maximum": {"type": "float", "default": 0.2, "min": 0.1, "max": 1.0, "description": "Maximum acceleration"}
        },
        "outputs": ["value"]
    },
    "ICHIMOKU": {
        "name": "Ichimoku Cloud",
        "category": IndicatorCategory.TREND,
        "parameters": {
            "tenkan_period": {"type": "int", "default": 9, "min": 1, "max": 100, "description": "Tenkan-sen period"},
            "kijun_period": {"type": "int", "default": 26, "min": 1, "max": 100, "description": "Kijun-sen period"},
            "senkou_b_period": {"type": "int", "default": 52, "min": 1, "max": 200, "description": "Senkou Span B period"}
        },
        "outputs": ["tenkan", "kijun", "senkou_a", "senkou_b", "chikou"]
    },
    
    # Momentum Indicators
    "RSI": {
        "name": "Relative Strength Index",
        "category": IndicatorCategory.MOMENTUM,
        "parameters": {
            "period": {"type": "int", "default": 14, "min": 2, "max": 100, "description": "Period length"}
        },
        "outputs": ["value"]
    },
    "MACD": {
        "name": "Moving Average Convergence Divergence",
        "category": IndicatorCategory.MOMENTUM,
        "parameters": {
            "fast_period": {"type": "int", "default": 12, "min": 1, "max": 100, "description": "Fast EMA period"},
            "slow_period": {"type": "int", "default": 26, "min": 1, "max": 200, "description": "Slow EMA period"},
            "signal_period": {"type": "int", "default": 9, "min": 1, "max": 50, "description": "Signal line period"}
        },
        "outputs": ["macd_line", "signal_line", "histogram"]
    },
    "STOCHASTIC": {
        "name": "Stochastic Oscillator",
        "category": IndicatorCategory.MOMENTUM,
        "parameters": {
            "k_period": {"type": "int", "default": 14, "min": 1, "max": 100, "description": "%K period"},
            "d_period": {"type": "int", "default": 3, "min": 1, "max": 50, "description": "%D period"},
            "slowing": {"type": "int", "default": 3, "min": 1, "max": 10, "description": "Slowing period"}
        },
        "outputs": ["k", "d"]
    },
    "STOCHASTIC_RSI": {
        "name": "Stochastic RSI",
        "category": IndicatorCategory.MOMENTUM,
        "parameters": {
            "rsi_period": {"type": "int", "default": 14, "min": 2, "max": 100, "description": "RSI period"},
            "stoch_period": {"type": "int", "default": 14, "min": 2, "max": 100, "description": "Stochastic period"},
            "k_smooth": {"type": "int", "default": 3, "min": 1, "max": 10, "description": "%K smoothing"},
            "d_smooth": {"type": "int", "default": 3, "min": 1, "max": 10, "description": "%D smoothing"}
        },
        "outputs": ["k", "d"]
    },
    "CCI": {
        "name": "Commodity Channel Index",
        "category": IndicatorCategory.MOMENTUM,
        "parameters": {
            "period": {"type": "int", "default": 20, "min": 5, "max": 100, "description": "Period length"}
        },
        "outputs": ["value"]
    },
    "WILLIAMS_R": {
        "name": "Williams %R",
        "category": IndicatorCategory.MOMENTUM,
        "parameters": {
            "period": {"type": "int", "default": 14, "min": 2, "max": 100, "description": "Period length"}
        },
        "outputs": ["value"]
    },
    "MOM": {
        "name": "Momentum",
        "category": IndicatorCategory.MOMENTUM,
        "parameters": {
            "period": {"type": "int", "default": 10, "min": 1, "max": 100, "description": "Period length"}
        },
        "outputs": ["value"]
    },
    "ROC": {
        "name": "Rate of Change",
        "category": IndicatorCategory.MOMENTUM,
        "parameters": {
            "period": {"type": "int", "default": 10, "min": 1, "max": 100, "description": "Period length"}
        },
        "outputs": ["value"]
    },
    "AO": {
        "name": "Awesome Oscillator",
        "category": IndicatorCategory.MOMENTUM,
        "parameters": {
            "fast_period": {"type": "int", "default": 5, "min": 2, "max": 50, "description": "Fast period"},
            "slow_period": {"type": "int", "default": 34, "min": 10, "max": 100, "description": "Slow period"}
        },
        "outputs": ["value"]
    },
    "AC": {
        "name": "Acceleration Oscillator",
        "category": IndicatorCategory.MOMENTUM,
        "parameters": {
            "fast_period": {"type": "int", "default": 5, "min": 2, "max": 50, "description": "Fast period"},
            "slow_period": {"type": "int", "default": 34, "min": 10, "max": 100, "description": "Slow period"}
        },
        "outputs": ["value"]
    },
    "ADX": {
        "name": "Average Directional Index",
        "category": IndicatorCategory.MOMENTUM,
        "parameters": {
            "period": {"type": "int", "default": 14, "min": 2, "max": 100, "description": "Period length"}
        },
        "outputs": ["adx", "plus_di", "minus_di"]
    },
    
    # Volatility Indicators
    "BOLLINGER_BANDS": {
        "name": "Bollinger Bands",
        "category": IndicatorCategory.VOLATILITY,
        "parameters": {
            "period": {"type": "int", "default": 20, "min": 5, "max": 100, "description": "SMA period"},
            "std_dev": {"type": "float", "default": 2.0, "min": 0.5, "max": 5.0, "description": "Standard deviation multiplier"}
        },
        "outputs": ["upper", "middle", "lower", "bandwidth", "percent_b"]
    },
    "ATR": {
        "name": "Average True Range",
        "category": IndicatorCategory.VOLATILITY,
        "parameters": {
            "period": {"type": "int", "default": 14, "min": 1, "max": 100, "description": "Period length"}
        },
        "outputs": ["value"]
    },
    "KELTNER_CHANNEL": {
        "name": "Keltner Channel",
        "category": IndicatorCategory.VOLATILITY,
        "parameters": {
            "ema_period": {"type": "int", "default": 20, "min": 5, "max": 100, "description": "EMA period"},
            "atr_period": {"type": "int", "default": 10, "min": 1, "max": 50, "description": "ATR period"},
            "multiplier": {"type": "float", "default": 1.5, "min": 0.5, "max": 5.0, "description": "ATR multiplier"}
        },
        "outputs": ["upper", "middle", "lower"]
    },
    "DONCHIAN_CHANNEL": {
        "name": "Donchian Channel",
        "category": IndicatorCategory.VOLATILITY,
        "parameters": {
            "period": {"type": "int", "default": 20, "min": 5, "max": 100, "description": "Period length"}
        },
        "outputs": ["upper", "middle", "lower"]
    },
    "STANDARD_DEVIATION": {
        "name": "Standard Deviation",
        "category": IndicatorCategory.VOLATILITY,
        "parameters": {
            "period": {"type": "int", "default": 20, "min": 2, "max": 100, "description": "Period length"}
        },
        "outputs": ["value"]
    },
    
    # Volume Indicators
    "VOLUME": {
        "name": "Volume",
        "category": IndicatorCategory.VOLUME,
        "parameters": {},
        "outputs": ["value"]
    },
    "OBV": {
        "name": "On-Balance Volume",
        "category": IndicatorCategory.VOLUME,
        "parameters": {},
        "outputs": ["value"]
    },
    "VOLUME_SMA": {
        "name": "Volume SMA",
        "category": IndicatorCategory.VOLUME,
        "parameters": {
            "period": {"type": "int", "default": 20, "min": 1, "max": 100, "description": "Period length"}
        },
        "outputs": ["value"]
    },
    "MFI": {
        "name": "Money Flow Index",
        "category": IndicatorCategory.VOLUME,
        "parameters": {
            "period": {"type": "int", "default": 14, "min": 2, "max": 100, "description": "Period length"}
        },
        "outputs": ["value"]
    },
    "VWAP": {
        "name": "Volume Weighted Average Price",
        "category": IndicatorCategory.VOLUME,
        "parameters": {},
        "outputs": ["value"]
    },
    "CMF": {
        "name": "Chaikin Money Flow",
        "category": IndicatorCategory.VOLUME,
        "parameters": {
            "period": {"type": "int", "default": 20, "min": 5, "max": 100, "description": "Period length"}
        },
        "outputs": ["value"]
    },
    
    # Oscillators
    "AROON": {
        "name": "Aroon",
        "category": IndicatorCategory.OSCILLATOR,
        "parameters": {
            "period": {"type": "int", "default": 25, "min": 5, "max": 100, "description": "Period length"}
        },
        "outputs": ["aroon_up", "aroon_down", "oscillator"]
    },
    "ULTIMATE_OSCILLATOR": {
        "name": "Ultimate Oscillator",
        "category": IndicatorCategory.OSCILLATOR,
        "parameters": {
            "period1": {"type": "int", "default": 7, "min": 1, "max": 50, "description": "Short period"},
            "period2": {"type": "int", "default": 14, "min": 5, "max": 100, "description": "Medium period"},
            "period3": {"type": "int", "default": 28, "min": 10, "max": 200, "description": "Long period"}
        },
        "outputs": ["value"]
    },
    "TRIX": {
        "name": "TRIX",
        "category": IndicatorCategory.OSCILLATOR,
        "parameters": {
            "period": {"type": "int", "default": 18, "min": 5, "max": 100, "description": "Period length"}
        },
        "outputs": ["value"]
    },
    "DPO": {
        "name": "Detrended Price Oscillator",
        "category": IndicatorCategory.OSCILLATOR,
        "parameters": {
            "period": {"type": "int", "default": 20, "min": 5, "max": 100, "description": "Period length"}
        },
        "outputs": ["value"]
    },
    
    # Pattern Indicators
    "SUPPORT_RESISTANCE": {
        "name": "Support/Resistance Levels",
        "category": IndicatorCategory.PATTERN,
        "parameters": {
            "lookback": {"type": "int", "default": 50, "min": 10, "max": 200, "description": "Lookback period"}
        },
        "outputs": ["nearest_support", "nearest_resistance", "position"]
    },
    "PIVOT_POINTS": {
        "name": "Pivot Points",
        "category": IndicatorCategory.PATTERN,
        "parameters": {
            "type": {"type": "select", "default": "classic", "options": ["classic", "fibonacci", "woodie", "camarilla"], "description": "Pivot type"}
        },
        "outputs": ["pivot", "r1", "r2", "r3", "s1", "s2", "s3"]
    },
    "FIBONACCI_RETRACEMENT": {
        "name": "Fibonacci Retracement",
        "category": IndicatorCategory.PATTERN,
        "parameters": {
            "lookback": {"type": "int", "default": 50, "min": 10, "max": 200, "description": "Lookback for swing points"}
        },
        "outputs": ["level_0", "level_236", "level_382", "level_500", "level_618", "level_786", "level_1"]
    },
    "CANDLESTICK_PATTERN": {
        "name": "Candlestick Patterns",
        "category": IndicatorCategory.PATTERN,
        "parameters": {
            "patterns": {"type": "multiselect", "default": ["doji", "hammer", "engulfing"], 
                        "options": ["doji", "hammer", "inverted_hammer", "engulfing", "morning_star", "evening_star", 
                                   "three_white_soldiers", "three_black_crows", "harami", "piercing_line", "dark_cloud_cover"],
                        "description": "Patterns to detect"}
        },
        "outputs": ["pattern_name", "is_bullish", "is_bearish"]
    },
    
    # Price-based comparisons
    "PRICE": {
        "name": "Price",
        "category": IndicatorCategory.CUSTOM,
        "parameters": {
            "type": {"type": "select", "default": "close", "options": ["open", "high", "low", "close", "hl2", "hlc3", "ohlc4"], "description": "Price type"}
        },
        "outputs": ["value"]
    },
    "HEIKIN_ASHI": {
        "name": "Heikin Ashi",
        "category": IndicatorCategory.CUSTOM,
        "parameters": {},
        "outputs": ["ha_open", "ha_high", "ha_low", "ha_close", "is_green"]
    },
    
    # Pocket Option native indicators
    "ALLIGATOR": {
        "name": "Alligator (Bill Williams)",
        "category": IndicatorCategory.TREND,
        "parameters": {
            "jaws_period": {"type": "int", "default": 13, "min": 5, "max": 50, "description": "Jaws period"},
            "teeth_period": {"type": "int", "default": 8, "min": 3, "max": 30, "description": "Teeth period"},
            "lips_period": {"type": "int", "default": 5, "min": 2, "max": 20, "description": "Lips period"}
        },
        "outputs": ["jaws", "teeth", "lips"]
    },
    "AWESOME_OSCILLATOR": {
        "name": "Awesome Oscillator (AO)",
        "category": IndicatorCategory.MOMENTUM,
        "parameters": {
            "fast_period": {"type": "int", "default": 5, "min": 2, "max": 50, "description": "Fast period"},
            "slow_period": {"type": "int", "default": 34, "min": 10, "max": 100, "description": "Slow period"}
        },
        "outputs": ["value"]
    },
    "FRACTAL": {
        "name": "Williams Fractal",
        "category": IndicatorCategory.PATTERN,
        "parameters": {
            "period": {"type": "int", "default": 2, "min": 1, "max": 5, "description": "Fractal period (each side)"}
        },
        "outputs": ["up_fractal", "down_fractal", "last_pivot"]
    },
    "DEMARKER": {
        "name": "DeMarker",
        "category": IndicatorCategory.MOMENTUM,
        "parameters": {
            "period": {"type": "int", "default": 14, "min": 5, "max": 50, "description": "Period"}
        },
        "outputs": ["value"]
    },
    "ENVELOPES": {
        "name": "Envelopes",
        "category": IndicatorCategory.VOLATILITY,
        "parameters": {
            "period": {"type": "int", "default": 14, "min": 5, "max": 100, "description": "MA period"},
            "deviation": {"type": "float", "default": 0.1, "min": 0.05, "max": 5.0, "description": "Deviation %"}
        },
        "outputs": ["upper", "middle", "lower"]
    },
    "OSMA": {
        "name": "OsMA (MA of Oscillator)",
        "category": IndicatorCategory.MOMENTUM,
        "parameters": {
            "fast_period": {"type": "int", "default": 12, "min": 1, "max": 50, "description": "Fast EMA"},
            "slow_period": {"type": "int", "default": 26, "min": 1, "max": 100, "description": "Slow EMA"},
            "signal_period": {"type": "int", "default": 9, "min": 1, "max": 30, "description": "Signal SMA"}
        },
        "outputs": ["value"]
    },
    "VORTEX": {
        "name": "Vortex Indicator",
        "category": IndicatorCategory.TREND,
        "parameters": {
            "period": {"type": "int", "default": 14, "min": 5, "max": 50, "description": "Period"}
        },
        "outputs": ["vi_plus", "vi_minus"]
    },
    "BULLS_POWER": {
        "name": "Bulls Power",
        "category": IndicatorCategory.MOMENTUM,
        "parameters": {
            "period": {"type": "int", "default": 13, "min": 5, "max": 50, "description": "EMA Period"}
        },
        "outputs": ["value"]
    },
    "BEARS_POWER": {
        "name": "Bears Power",
        "category": IndicatorCategory.MOMENTUM,
        "parameters": {
            "period": {"type": "int", "default": 13, "min": 5, "max": 50, "description": "EMA Period"}
        },
        "outputs": ["value"]
    },
    "ZIGZAG": {
        "name": "ZigZag",
        "category": IndicatorCategory.PATTERN,
        "parameters": {
            "depth": {"type": "int", "default": 12, "min": 3, "max": 50, "description": "Depth"},
            "deviation": {"type": "float", "default": 5.0, "min": 1.0, "max": 20.0, "description": "Deviation %"},
            "backstep": {"type": "int", "default": 3, "min": 1, "max": 10, "description": "Backstep"}
        },
        "outputs": ["last_pivot", "is_high", "is_low"]
    }
}


@dataclass
class IndicatorCondition:
    """Single indicator condition - supports both legacy and TradingView-style formats"""
    id: str
    indicator: str  # e.g., "RSI", "EMA_CROSSOVER", "BOLLINGER_BANDS"
    parameters: Dict[str, Any]  # e.g., {"period": 14}
    # TradingView-style condition type (e.g., "crosses_above_oversold", "golden_cross")
    condition_type: Optional[str] = None
    # Reversal flag - if True, inverts the signal direction (CALL→PUT, PUT→CALL)
    reversal: bool = False
    # Legacy fields for backward compatibility
    output: str = "value"  # e.g., "value" for RSI, "k" for Stochastic
    operator: Optional[ComparisonOperator] = None
    compare_to: str = "value"  # Can be: "value", "indicator", "previous"
    compare_value: Any = None  # The value or indicator config to compare against
    
    def to_dict(self) -> Dict:
        result = {
            "id": self.id,
            "indicator": self.indicator,
            "parameters": self.parameters,
            "reversal": self.reversal,  # Include reversal flag
        }
        # Include TradingView-style condition type if present
        if self.condition_type:
            result["conditionType"] = self.condition_type
        # Include legacy fields
        result["output"] = self.output
        if self.operator:
            result["operator"] = self.operator.value if isinstance(self.operator, ComparisonOperator) else self.operator
        result["compare_to"] = self.compare_to
        result["compare_value"] = self.compare_value
        return result


@dataclass
class ConditionGroup:
    """Group of conditions with logical operator"""
    id: str
    conditions: List[IndicatorCondition]
    logical_operator: LogicalOperator = LogicalOperator.AND
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "conditions": [c.to_dict() for c in self.conditions],
            "logical_operator": self.logical_operator.value if isinstance(self.logical_operator, LogicalOperator) else self.logical_operator
        }


@dataclass
class CustomStrategy:
    """Complete custom strategy definition"""
    id: str
    name: str
    description: str
    user_id: str
    
    # Signal conditions
    call_conditions: List[ConditionGroup]  # Conditions for CALL signal
    put_conditions: List[ConditionGroup]   # Conditions for PUT signal
    
    # Trading parameters
    timeframes: List[str]  # e.g., ["5s", "1m", "5m"]
    assets: List[str]  # e.g., ["EURUSD", "BTCUSD"]
    markets: List[str]  # e.g., ["regular", "otc"]
    
    # Risk parameters
    min_confidence: float = 75.0
    max_signals_per_hour: int = 10
    cooldown_seconds: int = 60
    
    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    is_active: bool = True
    # Iter 82 — Publish/Unpublish flow.
    # `is_active`   = "generator switch — is this strategy allowed to fire signals?"
    # `is_published` = "is this strategy exposed in the timeframe-selection UI
    #                   (React dashboard AND Tampermonkey `/strategies/available`)?"
    # Default False so newly-built strategies stay as **Drafts** until the
    # user explicitly publishes them.
    is_published: bool = False
    win_rate: float = 0.0
    total_signals: int = 0
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "user_id": self.user_id,
            "call_conditions": [g.to_dict() for g in self.call_conditions],
            "put_conditions": [g.to_dict() for g in self.put_conditions],
            "timeframes": self.timeframes,
            "assets": self.assets,
            "markets": self.markets,
            "min_confidence": self.min_confidence,
            "max_signals_per_hour": self.max_signals_per_hour,
            "cooldown_seconds": self.cooldown_seconds,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "is_active": self.is_active,
            "is_published": self.is_published,
            "win_rate": self.win_rate,
            "total_signals": self.total_signals
        }


class CustomStrategyService:
    """Service for managing custom strategies"""
    
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db.custom_strategies
        logger.info("✅ Custom Strategy Service initialized")
    
    async def get_available_indicators(self) -> Dict[str, Any]:
        """Get all available indicators with their parameters"""
        return {
            "indicators": AVAILABLE_INDICATORS,
            "categories": [e.value for e in IndicatorCategory],
            "operators": [e.value for e in ComparisonOperator],
            "logical_operators": [e.value for e in LogicalOperator]
        }
    
    async def create_strategy(self, strategy_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new custom strategy"""
        try:
            strategy_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc)
            
            # Parse conditions
            call_conditions = self._parse_condition_groups(strategy_data.get("call_conditions", []))
            put_conditions = self._parse_condition_groups(strategy_data.get("put_conditions", []))
            
            strategy = CustomStrategy(
                id=strategy_id,
                name=strategy_data.get("name", "Unnamed Strategy"),
                description=strategy_data.get("description", ""),
                user_id=strategy_data.get("user_id", "default_user"),
                call_conditions=call_conditions,
                put_conditions=put_conditions,
                timeframes=strategy_data.get("timeframes", ["1m"]),
                assets=strategy_data.get("assets", ["EURUSD"]),
                markets=strategy_data.get("markets", ["regular"]),
                min_confidence=strategy_data.get("min_confidence", 75.0),
                max_signals_per_hour=strategy_data.get("max_signals_per_hour", 10),
                cooldown_seconds=strategy_data.get("cooldown_seconds", 60),
                created_at=now,
                updated_at=now,
                is_active=strategy_data.get("is_active", True),
                is_published=strategy_data.get("is_published", False),
            )
            
            # Save to database
            await self.collection.insert_one(strategy.to_dict())
            
            logger.info(f"✅ Created custom strategy: {strategy.name} (ID: {strategy_id})")
            
            return {
                "success": True,
                "strategy": strategy.to_dict(),
                "message": f"Strategy '{strategy.name}' created successfully"
            }
            
        except Exception as e:
            logger.error(f"Error creating strategy: {e}")
            return {"success": False, "error": str(e)}
    
    def _parse_condition_groups(self, groups_data: List[Dict]) -> List[ConditionGroup]:
        """Parse condition groups from dict data - supports both legacy and TradingView-style formats"""
        groups = []
        for group_data in groups_data:
            conditions = []
            for cond_data in group_data.get("conditions", []):
                # Extract operator with proper handling
                operator_val = cond_data.get("operator")
                operator = None
                if operator_val:
                    try:
                        operator = ComparisonOperator(operator_val)
                    except ValueError:
                        operator = None
                
                condition = IndicatorCondition(
                    id=cond_data.get("id", str(uuid.uuid4())),
                    indicator=cond_data.get("indicator"),
                    parameters=cond_data.get("parameters", {}),
                    # TradingView-style condition type
                    condition_type=cond_data.get("conditionType"),
                    # Reversal flag - inverts signal direction
                    reversal=cond_data.get("reversal", False),
                    # Legacy fields
                    output=cond_data.get("output", "value"),
                    operator=operator,
                    compare_to=cond_data.get("compare_to", "value"),
                    compare_value=cond_data.get("compare_value")
                )
                conditions.append(condition)
            
            group = ConditionGroup(
                id=group_data.get("id", str(uuid.uuid4())),
                conditions=conditions,
                logical_operator=LogicalOperator(group_data.get("logical_operator", "AND"))
            )
            groups.append(group)
        
        return groups
    
    async def get_strategy(self, strategy_id: str) -> Optional[Dict[str, Any]]:
        """Get a strategy by ID"""
        strategy = await self.collection.find_one({"id": strategy_id}, {"_id": 0})
        return strategy
    
    async def get_all_strategies(self, user_id: str = "default_user") -> List[Dict[str, Any]]:
        """Get all strategies for a user"""
        strategies = await self.collection.find(
            {"user_id": user_id}, 
            {"_id": 0}
        ).sort("created_at", -1).to_list(100)
        return strategies
    
    async def update_strategy(self, strategy_id: str, update_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing strategy"""
        try:
            update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
            
            # Parse conditions if provided
            if "call_conditions" in update_data:
                parsed = self._parse_condition_groups(update_data["call_conditions"])
                update_data["call_conditions"] = [g.to_dict() for g in parsed]
            if "put_conditions" in update_data:
                parsed = self._parse_condition_groups(update_data["put_conditions"])
                update_data["put_conditions"] = [g.to_dict() for g in parsed]
            
            result = await self.collection.update_one(
                {"id": strategy_id},
                {"$set": update_data}
            )
            
            if result.modified_count > 0:
                strategy = await self.get_strategy(strategy_id)
                return {"success": True, "strategy": strategy}
            else:
                return {"success": False, "error": "Strategy not found or no changes made"}
                
        except Exception as e:
            logger.error(f"Error updating strategy: {e}")
            return {"success": False, "error": str(e)}
    
    async def delete_strategy(self, strategy_id: str) -> Dict[str, Any]:
        """Delete a strategy"""
        result = await self.collection.delete_one({"id": strategy_id})
        if result.deleted_count > 0:
            return {"success": True, "message": "Strategy deleted successfully"}
        return {"success": False, "error": "Strategy not found"}
    
    async def toggle_strategy(self, strategy_id: str, is_active: bool) -> Dict[str, Any]:
        """Toggle strategy active status"""
        return await self.update_strategy(strategy_id, {"is_active": is_active})

    async def set_published(self, strategy_id: str, is_published: bool) -> Dict[str, Any]:
        """Set the publish state of a strategy (draft ↔ published)."""
        return await self.update_strategy(strategy_id, {"is_published": bool(is_published)})

    async def toggle_published(self, strategy_id: str) -> Dict[str, Any]:
        """Flip the publish state of a strategy."""
        current = await self.get_strategy(strategy_id)
        if not current:
            return {"success": False, "error": "Strategy not found"}
        new_state = not bool(current.get("is_published", False))
        return await self.set_published(strategy_id, new_state)

    async def list_published(
        self, timeframe: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Return all published custom strategies. If `timeframe` is given,
        filter to strategies that declare that timeframe in their
        `timeframes` array.
        """
        q: Dict[str, Any] = {"is_published": True}
        if timeframe:
            q["timeframes"] = timeframe
        cursor = self.collection.find(q, {"_id": 0}).sort("updated_at", -1)
        return [d async for d in cursor]
    
    async def duplicate_strategy(self, strategy_id: str, new_name: str) -> Dict[str, Any]:
        """Duplicate an existing strategy"""
        original = await self.get_strategy(strategy_id)
        if not original:
            return {"success": False, "error": "Original strategy not found"}
        
        # Create a clean copy without any MongoDB ObjectIds
        duplicated = {
            "id": str(uuid.uuid4()),
            "name": new_name,
            "description": original.get("description", ""),
            "call_conditions": original.get("call_conditions", []),
            "put_conditions": original.get("put_conditions", []),
            "timeframes": original.get("timeframes", []),
            "assets": original.get("assets", []),
            "markets": original.get("markets", []),
            "min_confidence": original.get("min_confidence", 75),
            "user_id": original.get("user_id", "default_user"),
            "is_active": True,
            # Duplicated strategies start as drafts — user must publish them
            # explicitly. Prevents accidental publishing of experimental copies.
            "is_published": False,
            "win_rate": 0.0,
            "total_signals": 0,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        
        await self.collection.insert_one(duplicated.copy())
        return {"success": True, "strategy": duplicated}


# Global service instance
_custom_strategy_service: Optional[CustomStrategyService] = None


def get_custom_strategy_service(db: AsyncIOMotorDatabase) -> CustomStrategyService:
    """Get or create custom strategy service"""
    global _custom_strategy_service
    if _custom_strategy_service is None:
        _custom_strategy_service = CustomStrategyService(db)
    return _custom_strategy_service
