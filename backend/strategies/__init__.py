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
    'SignalStrength'
]
