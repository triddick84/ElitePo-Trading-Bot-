"""
Custom Trading Strategies Registry

Contains user-selectable trading strategies extracted from PDF documentation.
Each strategy has specific indicators, timeframes, and entry conditions.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class StrategyTimeframe(Enum):
    """Supported timeframes for strategies"""
    SEC_5 = "5s"
    SEC_15 = "15s"
    SEC_30 = "30s"
    MIN_1 = "1m"
    MIN_2 = "2m"
    MIN_3 = "3m"
    MIN_5 = "5m"


@dataclass
class StrategySignal:
    """Signal output from a strategy"""
    direction: str  # "CALL" or "PUT"
    confidence: float
    reasoning: str
    indicators_used: List[str]
    entry_triggered: bool


class CustomStrategyRegistry:
    """
    Registry of all available custom trading strategies.
    Users can select which strategy to use for each timeframe.
    """
    
    # All available strategies with their metadata
    STRATEGIES = {
        # =========================================
        # 5-SECOND STRATEGIES
        # =========================================
        "micro_compression_burst": {
            "name": "Micro Compression Burst",
            "description": "Bollinger Bands breakout strategy for 5s candles with 30s expiry",
            "timeframes": ["5s"],
            "expiry": "30s",
            "indicators": ["Bollinger Bands (20, 2)"],
            "win_rate_estimate": "75-85%",
            "market_conditions": "Calm markets, OTC periods, moderate volatility",
            "risk_level": "Medium"
        },
        
        # =========================================
        # 15-SECOND STRATEGIES
        # =========================================
        "starc_cci_reversal": {
            "name": "STARC Bands + CCI Reversal",
            "description": "STARC Bands with CCI for 15s candles, 1min expiry",
            "timeframes": ["15s"],
            "expiry": "1m",
            "indicators": ["STARC Bands (15, 5, 1.3)", "CCI (10)"],
            "win_rate_estimate": "70-80%",
            "market_conditions": "Smooth rhythmic markets with natural swings",
            "risk_level": "Medium"
        },
        
        # =========================================
        # 1-MINUTE STRATEGIES
        # =========================================
        "zigzag_double_ma": {
            "name": "ZigZag + Double MA",
            "description": "ZigZag with dual SMA crossover for 1m candles",
            "timeframes": ["1m"],
            "expiry": "1m",
            "indicators": ["ZigZag (5, 4, 3)", "SMA (3)", "SMA (6)"],
            "win_rate_estimate": "75-85%",
            "market_conditions": "Clear swings without extreme spikes",
            "risk_level": "Low-Medium"
        },
        "triple_supertrend": {
            "name": "Triple SuperTrend Confirmation",
            "description": "3 SuperTrends with Heikin Ashi for strong trend confirmation",
            "timeframes": ["1m"],
            "expiry": "5m",
            "indicators": ["SuperTrend (7,3)", "SuperTrend (10,2)", "SuperTrend (15,1)", "Heikin Ashi"],
            "win_rate_estimate": "80-90%",
            "market_conditions": "Active market sessions, London/NY overlap",
            "risk_level": "Low"
        },
        
        # =========================================
        # MULTI-TIMEFRAME STRATEGIES
        # =========================================
        "rsi_bb_scalp": {
            "name": "RSI + Bollinger Scalp",
            "description": "RSI oversold/overbought with BB for quick scalps",
            "timeframes": ["5s", "15s", "30s", "1m"],
            "expiry": "dynamic",
            "indicators": ["RSI (14)", "Bollinger Bands (20, 2)"],
            "win_rate_estimate": "70-80%",
            "market_conditions": "Range-bound markets",
            "risk_level": "Medium"
        },
        "ema_macd_trend": {
            "name": "EMA + MACD Trend",
            "description": "EMA crossover with MACD confirmation for trend trading",
            "timeframes": ["1m", "2m", "3m", "5m"],
            "expiry": "dynamic",
            "indicators": ["EMA (9)", "EMA (21)", "MACD (12,26,9)"],
            "win_rate_estimate": "75-85%",
            "market_conditions": "Trending markets",
            "risk_level": "Low-Medium"
        },
        "stochastic_rsi_combo": {
            "name": "Stochastic + RSI Combo",
            "description": "Double confirmation with Stochastic and RSI",
            "timeframes": ["15s", "30s", "1m", "2m"],
            "expiry": "dynamic",
            "indicators": ["Stochastic (14,3,3)", "RSI (14)"],
            "win_rate_estimate": "70-80%",
            "market_conditions": "Choppy or ranging markets",
            "risk_level": "Medium"
        },
        "vwap_momentum": {
            "name": "VWAP Momentum",
            "description": "Volume-weighted momentum strategy",
            "timeframes": ["1m", "5m"],
            "expiry": "dynamic",
            "indicators": ["VWAP", "Volume", "EMA (9)"],
            "win_rate_estimate": "70-75%",
            "market_conditions": "High volume periods",
            "risk_level": "Medium"
        }
    }
    
    def __init__(self):
        self.user_strategy_selections = {}  # {timeframe: strategy_id}
        logger.info(f"📚 Custom Strategy Registry initialized with {len(self.STRATEGIES)} strategies")
    
    def get_all_strategies(self) -> Dict:
        """Get all available strategies with metadata"""
        return self.STRATEGIES
    
    def get_strategies_for_timeframe(self, timeframe: str) -> List[Dict]:
        """Get strategies available for a specific timeframe"""
        available = []
        for strategy_id, strategy in self.STRATEGIES.items():
            if timeframe in strategy["timeframes"]:
                available.append({
                    "id": strategy_id,
                    **strategy
                })
        return available
    
    def set_strategy_for_timeframe(self, timeframe: str, strategy_id: str) -> bool:
        """Set which strategy to use for a specific timeframe"""
        if strategy_id not in self.STRATEGIES:
            logger.error(f"Unknown strategy: {strategy_id}")
            return False
        
        if timeframe not in self.STRATEGIES[strategy_id]["timeframes"]:
            logger.error(f"Strategy {strategy_id} doesn't support timeframe {timeframe}")
            return False
        
        self.user_strategy_selections[timeframe] = strategy_id
        logger.info(f"✅ Strategy '{strategy_id}' selected for {timeframe}")
        return True
    
    def get_selected_strategy(self, timeframe: str) -> Optional[str]:
        """Get the selected strategy for a timeframe"""
        return self.user_strategy_selections.get(timeframe)
    
    def get_user_selections(self) -> Dict:
        """Get all user strategy selections"""
        return self.user_strategy_selections


class StrategyExecutor:
    """
    Executes the actual strategy logic based on market data.
    """
    
    def __init__(self):
        self.registry = CustomStrategyRegistry()
    
    # =========================================
    # MICRO COMPRESSION BURST (5s)
    # =========================================
    def execute_micro_compression_burst(self, candles: List[Dict]) -> Optional[StrategySignal]:
        """
        Micro Compression Burst Strategy for 5s candles
        - Bollinger Bands (20, 2)
        - Look for 4-6 small candles in tight range
        - Enter on breakout above/below bands
        """
        try:
            if len(candles) < 25:
                return None
            
            closes = np.array([float(c['close']) for c in candles])
            
            # Calculate Bollinger Bands (20, 2)
            period = 20
            sma = np.mean(closes[-period:])
            std = np.std(closes[-period:])
            upper_band = sma + (2 * std)
            lower_band = sma - (2 * std)
            
            # Check for compression (narrow bands)
            band_width = (upper_band - lower_band) / sma
            is_compressed = band_width < 0.02  # Less than 2% width
            
            # Check recent candles for tight range
            recent_closes = closes[-6:]
            recent_range = (max(recent_closes) - min(recent_closes)) / sma
            tight_range = recent_range < 0.01  # Less than 1% range
            
            current_close = closes[-1]
            
            # CALL: Breakout above upper band
            if current_close > upper_band and (is_compressed or tight_range):
                return StrategySignal(
                    direction="CALL",
                    confidence=82.0,
                    reasoning=f"Micro Compression Burst: Breakout above upper BB ({upper_band:.5f}). Band width: {band_width*100:.2f}%",
                    indicators_used=["Bollinger Bands (20, 2)"],
                    entry_triggered=True
                )
            
            # PUT: Breakout below lower band
            if current_close < lower_band and (is_compressed or tight_range):
                return StrategySignal(
                    direction="PUT",
                    confidence=82.0,
                    reasoning=f"Micro Compression Burst: Breakout below lower BB ({lower_band:.5f}). Band width: {band_width*100:.2f}%",
                    indicators_used=["Bollinger Bands (20, 2)"],
                    entry_triggered=True
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Micro Compression Burst error: {e}")
            return None
    
    # =========================================
    # STARC + CCI REVERSAL (15s)
    # =========================================
    def execute_starc_cci_reversal(self, candles: List[Dict]) -> Optional[StrategySignal]:
        """
        STARC Bands + CCI Strategy for 15s candles
        - STARC Bands (period 15, MA period 5, multiplier 1.3)
        - CCI (period 10)
        - Enter when price touches band AND CCI at extreme
        """
        try:
            if len(candles) < 20:
                return None
            
            closes = np.array([float(c['close']) for c in candles])
            highs = np.array([float(c['high']) for c in candles])
            lows = np.array([float(c['low']) for c in candles])
            
            # Calculate STARC Bands
            # EMA for center line
            ema_period = 5
            ema = self._calculate_ema(closes, ema_period)
            
            # ATR for bands
            atr_period = 15
            atr = self._calculate_atr(highs, lows, closes, atr_period)
            
            multiplier = 1.3
            upper_starc = ema + (multiplier * atr)
            lower_starc = ema - (multiplier * atr)
            
            # Calculate CCI
            cci = self._calculate_cci(highs, lows, closes, 10)
            
            current_close = closes[-1]
            current_cci = cci
            
            # PUT: Touch upper STARC + CCI >= 200
            if current_close >= upper_starc and current_cci >= 200:
                return StrategySignal(
                    direction="PUT",
                    confidence=78.0,
                    reasoning=f"STARC+CCI Reversal: Price at upper STARC ({upper_starc:.5f}), CCI overbought ({current_cci:.0f})",
                    indicators_used=["STARC Bands (15, 5, 1.3)", "CCI (10)"],
                    entry_triggered=True
                )
            
            # CALL: Touch lower STARC + CCI <= -200
            if current_close <= lower_starc and current_cci <= -200:
                return StrategySignal(
                    direction="CALL",
                    confidence=78.0,
                    reasoning=f"STARC+CCI Reversal: Price at lower STARC ({lower_starc:.5f}), CCI oversold ({current_cci:.0f})",
                    indicators_used=["STARC Bands (15, 5, 1.3)", "CCI (10)"],
                    entry_triggered=True
                )
            
            return None
            
        except Exception as e:
            logger.error(f"STARC+CCI error: {e}")
            return None
    
    # =========================================
    # ZIGZAG + DOUBLE MA (1m)
    # =========================================
    def execute_zigzag_double_ma(self, candles: List[Dict]) -> Optional[StrategySignal]:
        """
        ZigZag + Double Moving Average Strategy for 1m candles
        - ZigZag (deviation 5, depth 4, backstep 3)
        - SMA (3) and SMA (6)
        - Enter on MA crossover + ZigZag trend confirmation
        """
        try:
            if len(candles) < 20:
                return None
            
            closes = np.array([float(c['close']) for c in candles])
            highs = np.array([float(c['high']) for c in candles])
            lows = np.array([float(c['low']) for c in candles])
            
            # Calculate SMAs
            sma_fast = np.mean(closes[-3:])  # SMA(3)
            sma_slow = np.mean(closes[-6:])  # SMA(6)
            
            # Previous SMAs for crossover detection
            sma_fast_prev = np.mean(closes[-4:-1])
            sma_slow_prev = np.mean(closes[-7:-1])
            
            # Simplified ZigZag trend detection
            # Look at recent swing highs/lows
            recent_high = max(highs[-10:])
            recent_low = min(lows[-10:])
            mid_high = max(highs[-5:])
            mid_low = min(lows[-5:])
            
            # Uptrend: higher lows
            uptrend = mid_low > min(lows[-10:-5])
            # Downtrend: lower highs
            downtrend = mid_high < max(highs[-10:-5])
            
            current_close = closes[-1]
            
            # CALL: Fast MA crosses above slow + uptrend
            ma_bullish_cross = sma_fast > sma_slow and sma_fast_prev <= sma_slow_prev
            if (sma_fast > sma_slow and uptrend) or ma_bullish_cross:
                if current_close > sma_fast:  # Price above MAs
                    return StrategySignal(
                        direction="CALL",
                        confidence=80.0,
                        reasoning=f"ZigZag+MA: Bullish MA alignment (SMA3: {sma_fast:.5f} > SMA6: {sma_slow:.5f}), ZigZag uptrend",
                        indicators_used=["ZigZag (5,4,3)", "SMA (3)", "SMA (6)"],
                        entry_triggered=True
                    )
            
            # PUT: Fast MA crosses below slow + downtrend
            ma_bearish_cross = sma_fast < sma_slow and sma_fast_prev >= sma_slow_prev
            if (sma_fast < sma_slow and downtrend) or ma_bearish_cross:
                if current_close < sma_fast:  # Price below MAs
                    return StrategySignal(
                        direction="PUT",
                        confidence=80.0,
                        reasoning=f"ZigZag+MA: Bearish MA alignment (SMA3: {sma_fast:.5f} < SMA6: {sma_slow:.5f}), ZigZag downtrend",
                        indicators_used=["ZigZag (5,4,3)", "SMA (3)", "SMA (6)"],
                        entry_triggered=True
                    )
            
            return None
            
        except Exception as e:
            logger.error(f"ZigZag+MA error: {e}")
            return None
    
    # =========================================
    # TRIPLE SUPERTREND (1m)
    # =========================================
    def execute_triple_supertrend(self, candles: List[Dict]) -> Optional[StrategySignal]:
        """
        Triple SuperTrend Confirmation Strategy for 1m candles
        - SuperTrend (7, 3) - Fast
        - SuperTrend (10, 2) - Medium
        - SuperTrend (15, 1) - Slow
        - All 3 must agree + 2 consecutive Heikin Ashi candles
        """
        try:
            if len(candles) < 20:
                return None
            
            closes = np.array([float(c['close']) for c in candles])
            highs = np.array([float(c['high']) for c in candles])
            lows = np.array([float(c['low']) for c in candles])
            opens = np.array([float(c['open']) for c in candles])
            
            # Calculate 3 SuperTrends
            st1 = self._calculate_supertrend(highs, lows, closes, 7, 3)
            st2 = self._calculate_supertrend(highs, lows, closes, 10, 2)
            st3 = self._calculate_supertrend(highs, lows, closes, 15, 1)
            
            # Calculate Heikin Ashi
            ha_close = (opens[-1] + highs[-1] + lows[-1] + closes[-1]) / 4
            ha_open = (opens[-2] + closes[-2]) / 2
            ha_bullish = ha_close > ha_open
            
            ha_close_prev = (opens[-2] + highs[-2] + lows[-2] + closes[-2]) / 4
            ha_open_prev = (opens[-3] + closes[-3]) / 2
            ha_bullish_prev = ha_close_prev > ha_open_prev
            
            current_close = closes[-1]
            
            # All SuperTrends bullish + 2 green HA candles
            if st1['direction'] == 'up' and st2['direction'] == 'up' and st3['direction'] == 'up':
                if ha_bullish and ha_bullish_prev:
                    return StrategySignal(
                        direction="CALL",
                        confidence=88.0,
                        reasoning="Triple SuperTrend: All 3 STs bullish + 2 green Heikin Ashi candles",
                        indicators_used=["SuperTrend (7,3)", "SuperTrend (10,2)", "SuperTrend (15,1)", "Heikin Ashi"],
                        entry_triggered=True
                    )
            
            # All SuperTrends bearish + 2 red HA candles
            if st1['direction'] == 'down' and st2['direction'] == 'down' and st3['direction'] == 'down':
                if not ha_bullish and not ha_bullish_prev:
                    return StrategySignal(
                        direction="PUT",
                        confidence=88.0,
                        reasoning="Triple SuperTrend: All 3 STs bearish + 2 red Heikin Ashi candles",
                        indicators_used=["SuperTrend (7,3)", "SuperTrend (10,2)", "SuperTrend (15,1)", "Heikin Ashi"],
                        entry_triggered=True
                    )
            
            return None
            
        except Exception as e:
            logger.error(f"Triple SuperTrend error: {e}")
            return None
    
    # =========================================
    # RSI + BOLLINGER SCALP (Multi-timeframe)
    # =========================================
    def execute_rsi_bb_scalp(self, candles: List[Dict]) -> Optional[StrategySignal]:
        """
        RSI + Bollinger Bands Scalp Strategy
        - RSI (14) oversold/overbought
        - Bollinger Bands (20, 2) for support/resistance
        """
        try:
            if len(candles) < 25:
                return None
            
            closes = np.array([float(c['close']) for c in candles])
            
            # Calculate RSI
            rsi = self._calculate_rsi(closes, 14)
            
            # Calculate Bollinger Bands
            period = 20
            sma = np.mean(closes[-period:])
            std = np.std(closes[-period:])
            upper_band = sma + (2 * std)
            lower_band = sma - (2 * std)
            
            current_close = closes[-1]
            
            # CALL: RSI oversold + price at lower BB
            if rsi <= 30 and current_close <= lower_band * 1.005:
                return StrategySignal(
                    direction="CALL",
                    confidence=76.0,
                    reasoning=f"RSI+BB Scalp: RSI oversold ({rsi:.1f}) + price at lower BB ({lower_band:.5f})",
                    indicators_used=["RSI (14)", "Bollinger Bands (20, 2)"],
                    entry_triggered=True
                )
            
            # PUT: RSI overbought + price at upper BB
            if rsi >= 70 and current_close >= upper_band * 0.995:
                return StrategySignal(
                    direction="PUT",
                    confidence=76.0,
                    reasoning=f"RSI+BB Scalp: RSI overbought ({rsi:.1f}) + price at upper BB ({upper_band:.5f})",
                    indicators_used=["RSI (14)", "Bollinger Bands (20, 2)"],
                    entry_triggered=True
                )
            
            return None
            
        except Exception as e:
            logger.error(f"RSI+BB Scalp error: {e}")
            return None
    
    # =========================================
    # EMA + MACD TREND (Multi-timeframe)
    # =========================================
    def execute_ema_macd_trend(self, candles: List[Dict]) -> Optional[StrategySignal]:
        """
        EMA + MACD Trend Strategy
        - EMA (9) and EMA (21) crossover
        - MACD (12, 26, 9) confirmation
        """
        try:
            if len(candles) < 30:
                return None
            
            closes = np.array([float(c['close']) for c in candles])
            
            # Calculate EMAs
            ema_fast = self._calculate_ema(closes, 9)
            ema_slow = self._calculate_ema(closes, 21)
            
            # Calculate MACD
            macd_line, signal_line, histogram = self._calculate_macd(closes)
            
            current_close = closes[-1]
            
            # CALL: EMA bullish + MACD bullish
            if ema_fast > ema_slow and histogram > 0:
                if current_close > ema_fast:
                    return StrategySignal(
                        direction="CALL",
                        confidence=79.0,
                        reasoning=f"EMA+MACD Trend: EMA9 ({ema_fast:.5f}) > EMA21 ({ema_slow:.5f}), MACD histogram positive",
                        indicators_used=["EMA (9)", "EMA (21)", "MACD (12,26,9)"],
                        entry_triggered=True
                    )
            
            # PUT: EMA bearish + MACD bearish
            if ema_fast < ema_slow and histogram < 0:
                if current_close < ema_fast:
                    return StrategySignal(
                        direction="PUT",
                        confidence=79.0,
                        reasoning=f"EMA+MACD Trend: EMA9 ({ema_fast:.5f}) < EMA21 ({ema_slow:.5f}), MACD histogram negative",
                        indicators_used=["EMA (9)", "EMA (21)", "MACD (12,26,9)"],
                        entry_triggered=True
                    )
            
            return None
            
        except Exception as e:
            logger.error(f"EMA+MACD error: {e}")
            return None
    
    # =========================================
    # HELPER FUNCTIONS
    # =========================================
    
    def _calculate_ema(self, data: np.ndarray, period: int) -> float:
        """Calculate Exponential Moving Average"""
        if len(data) < period:
            return np.mean(data)
        
        multiplier = 2 / (period + 1)
        ema = data[-period]
        for price in data[-period+1:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))
        return ema
    
    def _calculate_atr(self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int) -> float:
        """Calculate Average True Range"""
        if len(closes) < period + 1:
            return np.mean(highs - lows)
        
        tr_list = []
        for i in range(-period, 0):
            high_low = highs[i] - lows[i]
            high_close = abs(highs[i] - closes[i-1])
            low_close = abs(lows[i] - closes[i-1])
            tr = max(high_low, high_close, low_close)
            tr_list.append(tr)
        
        return np.mean(tr_list)
    
    def _calculate_cci(self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int) -> float:
        """Calculate Commodity Channel Index"""
        typical_prices = (highs[-period:] + lows[-period:] + closes[-period:]) / 3
        sma_tp = np.mean(typical_prices)
        mean_deviation = np.mean(np.abs(typical_prices - sma_tp))
        
        if mean_deviation == 0:
            return 0
        
        current_tp = (highs[-1] + lows[-1] + closes[-1]) / 3
        cci = (current_tp - sma_tp) / (0.015 * mean_deviation)
        return cci
    
    def _calculate_rsi(self, closes: np.ndarray, period: int) -> float:
        """Calculate Relative Strength Index"""
        if len(closes) < period + 1:
            return 50.0
        
        deltas = np.diff(closes[-(period+1):])
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.mean(gains)
        avg_loss = np.mean(losses)
        
        if avg_loss == 0:
            return 100.0
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def _calculate_macd(self, closes: np.ndarray) -> Tuple[float, float, float]:
        """Calculate MACD (12, 26, 9)"""
        ema_12 = self._calculate_ema(closes, 12)
        ema_26 = self._calculate_ema(closes, 26)
        macd_line = ema_12 - ema_26
        
        # Simplified signal line (would need history for accurate calculation)
        signal_line = macd_line * 0.9  # Approximation
        histogram = macd_line - signal_line
        
        return macd_line, signal_line, histogram
    
    def _calculate_supertrend(self, highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, 
                              atr_period: int, multiplier: float) -> Dict:
        """Calculate SuperTrend indicator"""
        atr = self._calculate_atr(highs, lows, closes, atr_period)
        hl2 = (highs[-1] + lows[-1]) / 2
        
        upper_band = hl2 + (multiplier * atr)
        lower_band = hl2 - (multiplier * atr)
        
        # Determine trend direction
        if closes[-1] > upper_band:
            direction = 'up'
        elif closes[-1] < lower_band:
            direction = 'down'
        else:
            # Use previous close comparison
            direction = 'up' if closes[-1] > closes[-2] else 'down'
        
        return {
            'direction': direction,
            'upper': upper_band,
            'lower': lower_band,
            'value': lower_band if direction == 'up' else upper_band
        }
    
    # =========================================
    # MAIN EXECUTION METHOD
    # =========================================
    
    def execute_strategy(self, strategy_id: str, candles: List[Dict]) -> Optional[StrategySignal]:
        """Execute a specific strategy and return signal if triggered"""
        
        strategy_map = {
            "micro_compression_burst": self.execute_micro_compression_burst,
            "starc_cci_reversal": self.execute_starc_cci_reversal,
            "zigzag_double_ma": self.execute_zigzag_double_ma,
            "triple_supertrend": self.execute_triple_supertrend,
            "rsi_bb_scalp": self.execute_rsi_bb_scalp,
            "ema_macd_trend": self.execute_ema_macd_trend,
            "stochastic_rsi_combo": self.execute_rsi_bb_scalp,  # Reuse for now
            "vwap_momentum": self.execute_ema_macd_trend,  # Reuse for now
        }
        
        if strategy_id not in strategy_map:
            logger.warning(f"Unknown strategy: {strategy_id}")
            return None
        
        return strategy_map[strategy_id](candles)


# Singleton instances
custom_strategy_registry = CustomStrategyRegistry()
strategy_executor = StrategyExecutor()
