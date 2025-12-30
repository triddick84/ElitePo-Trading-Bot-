# Strategies package
# Contains all trading strategies for the GPT Signal Bot

from .candlestick_bible_strategy import (
    CandlestickBibleStrategy,
    candlestick_bible_strategy,
    analyze_candles,
    PatternType,
    CandlestickPattern
)

from .pocket_option_1m_scalping import (
    PocketOption1MinuteStrategy,
    pocket_option_1m_strategy,
    analyze_1m_candles,
    get_sr_levels,
    SupportResistanceAnalyzer,
    SignalStrength
)

from .pocket_option_5s_pro import (
    PocketOption5SecondStrategy,
    pocket_option_5s_strategy,
    analyze_5s_candles,
    get_5s_strategy_config,
    AIPatternRecognition,
    TradeDirection,
    SignalQuality
)

from .strategy_5s_supertrend_reversal import (
    SupertrendReversal5s,
    generate_5s_supertrend_signal
)

__all__ = [
    # Candlestick Bible
    'CandlestickBibleStrategy',
    'candlestick_bible_strategy', 
    'analyze_candles',
    'PatternType',
    'CandlestickPattern',
    # 1-Minute Scalping
    'PocketOption1MinuteStrategy',
    'pocket_option_1m_strategy',
    'analyze_1m_candles',
    'get_sr_levels',
    'SupportResistanceAnalyzer',
    'SignalStrength',
    # 5-Second Pro
    'PocketOption5SecondStrategy',
    'pocket_option_5s_strategy',
    'analyze_5s_candles',
    'get_5s_strategy_config',
    'AIPatternRecognition',
    'TradeDirection',
    'SignalQuality'
]
