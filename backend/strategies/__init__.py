# Strategies package
# Contains all trading strategies for the GPT Signal Bot

from .candlestick_bible_strategy import (
    CandlestickBibleStrategy,
    candlestick_bible_strategy,
    analyze_candles,
    PatternType,
    CandlestickPattern
)

__all__ = [
    'CandlestickBibleStrategy',
    'candlestick_bible_strategy', 
    'analyze_candles',
    'PatternType',
    'CandlestickPattern'
]
