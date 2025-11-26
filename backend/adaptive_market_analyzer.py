"""
Adaptive Market Analyzer
Automatically detects market conditions and applies optimal strategies

For Trending Markets:
- Indicators: MACD + Parabolic SAR, EMA + Trendlines
- Logic: Momentum following, breakout detection
- Execution: Slightly longer delay to avoid whipsaws

For Ranging/Volatile Markets:
- Indicators: RSI(14) + Volume, Bollinger Bands + EMA
- Logic: Mean-reversion, oversold/overbought
- Threshold: Higher signal threshold to filter noise
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class AdaptiveMarketAnalyzer:
    """Detects market conditions and applies optimal strategies"""
    
    def __init__(self, config=None):
        # Default thresholds
        self.trending_threshold = 25  # ADX-like value
        self.ranging_threshold = 20  # Below this = ranging
        self.volatility_threshold = 1.5  # Volatility multiplier
        
        # User configuration (can be overridden)
        self.config = config
        
        # Update thresholds from config if provided
        if config:
            self.trending_threshold = config.adx_trending_threshold
            self.ranging_threshold = config.adx_ranging_threshold
            self.trending_execution_delay = config.trending_execution_delay
            self.ranging_execution_delay = config.ranging_execution_delay
            self.ranging_signal_threshold = config.ranging_signal_threshold
            self.trending_indicators = config.trending_indicators
            self.ranging_indicators = config.ranging_indicators
        else:
            # Default values
            self.trending_execution_delay = 3.0
            self.ranging_execution_delay = 1.5
            self.ranging_signal_threshold = 80.0
            self.trending_indicators = ["MACD", "Parabolic_SAR", "EMA"]
            self.ranging_indicators = ["RSI", "Volume", "Bollinger_Bands", "EMA"]
        
        logger.info(f"🎯 Adaptive Market Analyzer initialized - Trending: {self.trending_indicators}, Ranging: {self.ranging_indicators}")
    
    def update_config(self, config):
        """Update analyzer configuration"""
        self.config = config
        self.trending_threshold = config.adx_trending_threshold
        self.ranging_threshold = config.adx_ranging_threshold
        self.trending_execution_delay = config.trending_execution_delay
        self.ranging_execution_delay = config.ranging_execution_delay
        self.ranging_signal_threshold = config.ranging_signal_threshold
        self.trending_indicators = config.trending_indicators
        self.ranging_indicators = config.ranging_indicators
        logger.info(f"🔄 Updated adaptive config - ADX Trending>{self.trending_threshold}, Ranging<{self.ranging_threshold}")
    
    def detect_market_condition(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Detect whether market is trending or ranging/volatile
        
        Returns:
            Dict with market_type, strength, volatility, and confidence
        """
        try:
            if df is None or len(df) < 50:
                return {'market_type': 'unknown', 'strength': 0, 'confidence': 0}
            
            # Calculate trend strength (ADX-like)
            trend_strength = self._calculate_trend_strength(df)
            
            # Calculate volatility
            volatility_ratio = self._calculate_volatility_ratio(df)
            
            # Determine market type
            if trend_strength > self.trending_threshold:
                if volatility_ratio > self.volatility_threshold:
                    market_type = 'trending_volatile'
                    strategy_type = 'trending'
                else:
                    market_type = 'trending_stable'
                    strategy_type = 'trending'
            else:
                if volatility_ratio > self.volatility_threshold:
                    market_type = 'ranging_volatile'
                    strategy_type = 'ranging'
                else:
                    market_type = 'ranging_stable'
                    strategy_type = 'ranging'
            
            # Determine trend direction if trending
            trend_direction = None
            if strategy_type == 'trending':
                ema_20 = df['close'].ewm(span=20, adjust=False).mean()
                ema_50 = df['close'].ewm(span=50, adjust=False).mean()
                trend_direction = 'bullish' if ema_20.iloc[-1] > ema_50.iloc[-1] else 'bearish'
            
            result = {
                'market_type': market_type,
                'strategy_type': strategy_type,
                'trend_strength': trend_strength,
                'volatility_ratio': volatility_ratio,
                'trend_direction': trend_direction,
                'confidence': min(trend_strength + 50, 95) if strategy_type == 'trending' else 75
            }
            
            logger.info(f"📊 Market Condition: {market_type} | Trend: {trend_strength:.1f} | Vol: {volatility_ratio:.2f}x")
            
            return result
            
        except Exception as e:
            logger.error(f"Error detecting market condition: {e}")
            return {'market_type': 'unknown', 'strategy_type': 'ranging', 'confidence': 50}
    
    def analyze_trending_market(self, df: pd.DataFrame, trend_direction: str) -> Optional[Dict[str, Any]]:
        """
        Analyze trending market using user-selected indicators
        
        Strategy:
        - Follow momentum
        - Detect breakouts
        - User-configurable execution delay to avoid whipsaws
        """
        try:
            current_price = df['close'].iloc[-1]
            signal_direction = None
            confidence = 50
            reason = ""
            indicators_used = {}
            confirmations = []
            
            # Calculate selected indicators
            macd_bullish = macd_bearish = False
            psar_bullish = psar_bearish = False
            ema_bullish = ema_bearish = False
            rsi_bullish = rsi_bearish = False
            stoch_bullish = stoch_bearish = False
            bb_breakout_bullish = bb_breakout_bearish = False
            
            if "MACD" in self.trending_indicators:
                ema_12 = df['close'].ewm(span=12, adjust=False).mean()
                ema_26 = df['close'].ewm(span=26, adjust=False).mean()
                macd = ema_12 - ema_26
                macd_signal = macd.ewm(span=9, adjust=False).mean()
                current_macd = macd.iloc[-1]
                current_signal = macd_signal.iloc[-1]
                indicators_used['macd'] = current_macd
                indicators_used['macd_signal'] = current_signal
                macd_bullish = current_macd > current_signal
                macd_bearish = current_macd < current_signal
            
            if "Parabolic_SAR" in self.trending_indicators:
                psar = self._calculate_parabolic_sar(df)
                current_psar = psar.iloc[-1]
                indicators_used['psar'] = current_psar
                psar_bullish = current_price > current_psar
                psar_bearish = current_price < current_psar
            
            if "EMA" in self.trending_indicators:
                ema_20 = df['close'].ewm(span=20, adjust=False).mean()
                ema_50 = df['close'].ewm(span=50, adjust=False).mean()
                indicators_used['ema_20'] = ema_20.iloc[-1]
                indicators_used['ema_50'] = ema_50.iloc[-1]
                ema_bullish = ema_20.iloc[-1] > ema_50.iloc[-1]
                ema_bearish = ema_20.iloc[-1] < ema_50.iloc[-1]
            
            if "RSI" in self.trending_indicators:
                rsi = self._calculate_rsi(df['close'], 14)
                current_rsi = rsi.iloc[-1]
                indicators_used['rsi'] = current_rsi
                rsi_bullish = current_rsi > 50 and current_rsi < 70
                rsi_bearish = current_rsi < 50 and current_rsi > 30
            
            if "Stochastic" in self.trending_indicators:
                stoch_k = self._calculate_stochastic(df)
                current_stoch = stoch_k.iloc[-1] if len(stoch_k) > 0 else 50
                indicators_used['stochastic'] = current_stoch
                stoch_bullish = current_stoch > 50
                stoch_bearish = current_stoch < 50
            
            if "Bollinger_Bands" in self.trending_indicators:
                bb_period = 20
                bb_middle = df['close'].rolling(bb_period).mean()
                bb_std_dev = df['close'].rolling(bb_period).std()
                bb_upper = bb_middle + (bb_std_dev * 2)
                bb_lower = bb_middle - (bb_std_dev * 2)
                indicators_used['bb_upper'] = bb_upper.iloc[-1]
                indicators_used['bb_lower'] = bb_lower.iloc[-1]
                bb_breakout_bullish = current_price > bb_upper.iloc[-1]
                bb_breakout_bearish = current_price < bb_lower.iloc[-1]
            
            # Count confirmations for CALL
            bullish_score = sum([macd_bullish, psar_bullish, ema_bullish, rsi_bullish, stoch_bullish, bb_breakout_bullish])
            bearish_score = sum([macd_bearish, psar_bearish, ema_bearish, rsi_bearish, stoch_bearish, bb_breakout_bearish])
            
            # Build confirmation list for CALL
            if macd_bullish:
                confirmations.append("MACD bullish")
            if psar_bullish:
                confirmations.append("Price above PSAR")
            if ema_bullish:
                confirmations.append("EMA uptrend")
            if rsi_bullish:
                confirmations.append("RSI momentum")
            if stoch_bullish:
                confirmations.append("Stochastic up")
            if bb_breakout_bullish:
                confirmations.append("BB breakout")
            
            # Determine signal based on majority confirmation
            min_confirmations = max(2, len(self.trending_indicators) // 2)  # At least 2 or half of indicators
            
            if bullish_score >= min_confirmations:
                signal_direction = "CALL"
                confidence = 75 + (bullish_score * 3)  # More confirmations = higher confidence
                reason = f"Bullish trending - {', '.join(confirmations)}"
                logger.info(f"🟢 TRENDING BUY: {reason}")
            elif bearish_score >= min_confirmations:
                signal_direction = "PUT"
                confidence = 75 + (bearish_score * 3)
                bearish_confirmations = []
                if macd_bearish:
                    bearish_confirmations.append("MACD bearish")
                if psar_bearish:
                    bearish_confirmations.append("Price below PSAR")
                if ema_bearish:
                    bearish_confirmations.append("EMA downtrend")
                if rsi_bearish:
                    bearish_confirmations.append("RSI momentum")
                if stoch_bearish:
                    bearish_confirmations.append("Stochastic down")
                if bb_breakout_bearish:
                    bearish_confirmations.append("BB breakdown")
                reason = f"Bearish trending - {', '.join(bearish_confirmations)}"
                logger.info(f"🔴 TRENDING SELL: {reason}")
            
            if signal_direction:
                return {
                    'direction': signal_direction,
                    'confidence': min(confidence, 95),
                    'reason': reason,
                    'strategy': 'Trending Market Strategy',
                    'execution_delay': self.trending_execution_delay,
                    'indicators': indicators_used,
                    'confirmations': confirmations if signal_direction == "CALL" else bearish_confirmations
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error analyzing trending market: {e}")
            return None
    
    def analyze_ranging_market(self, df: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """
        Analyze ranging/volatile market using RSI + Volume + Bollinger Bands
        
        Strategy:
        - Mean-reversion
        - Buy at oversold (RSI < 40)
        - Sell at overbought (RSI > 60)
        - Higher signal threshold to filter noise
        """
        try:
            # RSI Calculation
            rsi = self._calculate_rsi(df['close'], 14)
            current_rsi = rsi.iloc[-1]
            
            # Volume Analysis
            if 'volume' in df.columns and df['volume'].sum() > 0:
                volume_ma = df['volume'].rolling(20).mean()
                current_volume = df['volume'].iloc[-1]
                volume_ratio = current_volume / volume_ma.iloc[-1] if volume_ma.iloc[-1] > 0 else 1
            else:
                volume_ratio = 1.0
            
            # Bollinger Bands
            bb_period = 20
            bb_std = 2
            bb_middle = df['close'].rolling(bb_period).mean()
            bb_std_dev = df['close'].rolling(bb_period).std()
            bb_upper = bb_middle + (bb_std_dev * bb_std)
            bb_lower = bb_middle - (bb_std_dev * bb_std)
            
            current_price = df['close'].iloc[-1]
            current_bb_upper = bb_upper.iloc[-1]
            current_bb_lower = bb_lower.iloc[-1]
            current_bb_middle = bb_middle.iloc[-1]
            
            # EMA for additional confirmation
            ema_20 = df['close'].ewm(span=20, adjust=False).mean()
            
            signal_direction = None
            confidence = 50
            reason = ""
            signal_threshold = 80  # Higher threshold for volatile markets
            
            # BUY Signal: Oversold conditions
            if current_rsi < 40 and current_price <= current_bb_lower * 1.005:
                signal_direction = "CALL"
                confidence = 75
                
                # Volume confirmation
                if volume_ratio > 1.3:
                    confidence += 8
                    reason = "Strong oversold reversal - RSI < 40 + Price at BB lower + Volume spike"
                else:
                    reason = "Oversold reversal - RSI < 40 + Price at BB lower band"
                
                # Deep oversold bonus
                if current_rsi < 30:
                    confidence += 5
                    reason += " (deeply oversold)"
                
                logger.info(f"🟢 RANGING BUY: {reason}")
            
            # SELL Signal: Overbought conditions
            elif current_rsi > 60 and current_price >= current_bb_upper * 0.995:
                signal_direction = "PUT"
                confidence = 75
                
                # Volume confirmation
                if volume_ratio > 1.3:
                    confidence += 8
                    reason = "Strong overbought reversal - RSI > 60 + Price at BB upper + Volume spike"
                else:
                    reason = "Overbought reversal - RSI > 60 + Price at BB upper band"
                
                # Deep overbought bonus
                if current_rsi > 70:
                    confidence += 5
                    reason += " (deeply overbought)"
                
                logger.info(f"🔴 RANGING SELL: {reason}")
            
            # Only return signal if it meets higher threshold
            if signal_direction and confidence >= signal_threshold:
                return {
                    'direction': signal_direction,
                    'confidence': confidence,
                    'reason': reason,
                    'strategy': 'Ranging Market Strategy',
                    'execution_delay': 1.5,  # Shorter delay for mean-reversion
                    'signal_threshold': signal_threshold,
                    'indicators': {
                        'rsi': current_rsi,
                        'volume_ratio': volume_ratio,
                        'bb_upper': current_bb_upper,
                        'bb_middle': current_bb_middle,
                        'bb_lower': current_bb_lower,
                        'price_position': (current_price - current_bb_lower) / (current_bb_upper - current_bb_lower)
                    }
                }
            elif signal_direction:
                logger.info(f"⏸️ Signal filtered: Confidence {confidence}% < threshold {signal_threshold}%")
            
            return None
            
        except Exception as e:
            logger.error(f"Error analyzing ranging market: {e}")
            return None
    
    def generate_adaptive_signal(self, df: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """
        Main entry point: Detect market condition and apply optimal strategy
        """
        try:
            # Step 1: Detect market condition
            market_condition = self.detect_market_condition(df)
            
            # Step 2: Apply appropriate strategy
            if market_condition['strategy_type'] == 'trending':
                signal = self.analyze_trending_market(df, market_condition.get('trend_direction'))
            else:
                signal = self.analyze_ranging_market(df)
            
            # Step 3: Add market condition info to signal
            if signal:
                signal['market_condition'] = market_condition
                signal['adaptive_strategy'] = True
            
            return signal
            
        except Exception as e:
            logger.error(f"Error generating adaptive signal: {e}")
            return None
    
    def _calculate_trend_strength(self, df: pd.DataFrame) -> float:
        """Calculate trend strength (ADX-like)"""
        try:
            # Directional movement
            high_diff = df['high'].diff()
            low_diff = -df['low'].diff()
            
            pos_dm = high_diff.where((high_diff > low_diff) & (high_diff > 0), 0)
            neg_dm = low_diff.where((low_diff > high_diff) & (low_diff > 0), 0)
            
            # True Range
            high_low = df['high'] - df['low']
            atr = high_low.rolling(14).mean()
            
            # Directional Indicators
            pos_di = 100 * (pos_dm.rolling(14).mean() / atr)
            neg_di = 100 * (neg_dm.rolling(14).mean() / atr)
            
            # DX
            dx = 100 * abs(pos_di - neg_di) / (pos_di + neg_di)
            
            # ADX
            adx = dx.rolling(14).mean()
            
            return adx.iloc[-1] if not pd.isna(adx.iloc[-1]) else 15
            
        except Exception as e:
            logger.error(f"Error calculating trend strength: {e}")
            return 15
    
    def _calculate_volatility_ratio(self, df: pd.DataFrame) -> float:
        """Calculate volatility ratio (current vs average)"""
        try:
            high_low = df['high'] - df['low']
            atr = high_low.rolling(14).mean()
            current_atr = atr.iloc[-1]
            avg_atr = atr.mean()
            
            return current_atr / avg_atr if avg_atr > 0 else 1.0
            
        except Exception as e:
            logger.error(f"Error calculating volatility: {e}")
            return 1.0
    
    def _calculate_parabolic_sar(self, df: pd.DataFrame, af_start=0.02, af_increment=0.02, af_max=0.2) -> pd.Series:
        """Calculate Parabolic SAR indicator"""
        try:
            high = df['high']
            low = df['low']
            close = df['close']
            
            psar = close.copy()
            psarbull = [None] * len(close)
            psarbear = [None] * len(close)
            bull = True
            af = af_start
            hp = high.iloc[0]
            lp = low.iloc[0]
            
            for i in range(2, len(close)):
                if bull:
                    psar.iloc[i] = psar.iloc[i-1] + af * (hp - psar.iloc[i-1])
                else:
                    psar.iloc[i] = psar.iloc[i-1] + af * (lp - psar.iloc[i-1])
                
                reverse = False
                
                if bull:
                    if low.iloc[i] < psar.iloc[i]:
                        bull = False
                        reverse = True
                        psar.iloc[i] = hp
                        lp = low.iloc[i]
                        af = af_start
                else:
                    if high.iloc[i] > psar.iloc[i]:
                        bull = True
                        reverse = True
                        psar.iloc[i] = lp
                        hp = high.iloc[i]
                        af = af_start
                
                if not reverse:
                    if bull:
                        if high.iloc[i] > hp:
                            hp = high.iloc[i]
                            af = min(af + af_increment, af_max)
                        if low.iloc[i-1] < psar.iloc[i]:
                            psar.iloc[i] = low.iloc[i-1]
                        if low.iloc[i-2] < psar.iloc[i]:
                            psar.iloc[i] = low.iloc[i-2]
                    else:
                        if low.iloc[i] < lp:
                            lp = low.iloc[i]
                            af = min(af + af_increment, af_max)
                        if high.iloc[i-1] > psar.iloc[i]:
                            psar.iloc[i] = high.iloc[i-1]
                        if high.iloc[i-2] > psar.iloc[i]:
                            psar.iloc[i] = high.iloc[i-2]
                
                if bull:
                    psarbull[i] = psar.iloc[i]
                else:
                    psarbear[i] = psar.iloc[i]
            
            return psar
            
        except Exception as e:
            logger.error(f"Error calculating Parabolic SAR: {e}")
            return df['close']
    
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate RSI"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi


# Global instance
adaptive_market_analyzer = AdaptiveMarketAnalyzer()
