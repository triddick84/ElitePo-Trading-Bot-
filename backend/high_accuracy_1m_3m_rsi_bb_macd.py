"""
High Accuracy 1-3 Minute Binary Options Strategy
RSI + Bollinger Bands + MACD Triple Confirmation

Research-backed strategy with reported 73-90% win rate
Source: Quantified Strategies, TradingView, YouTube tutorials 2024-2025

STRATEGY LOGIC:
- RSI (2-4 period): Identify overbought/oversold (extreme sensitivity for short timeframes)
- Bollinger Bands (20 period, 2 std dev): Volatility breakouts and reversals
- MACD (12,26,9): Trend confirmation and momentum
- BUY: RSI<20 + Price near lower BB + MACD crossover bullish
- SELL: RSI>80 + Price near upper BB + MACD crossover bearish
"""

import logging
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import yfinance as yf
import talib

logger = logging.getLogger(__name__)

class HighAccuracy1M3MRsiBbMacd:
    """
    1-3 Minute High Accuracy Strategy using RSI + Bollinger Bands + MACD
    Triple confirmation system for maximum accuracy
    """
    
    def __init__(self):
        self.name = "RSI-BB-MACD 1-3M High Accuracy"
        
        # RSI Settings (Short period for 1-3 minute sensitivity)
        self.rsi_period = 4  # Fast RSI for short timeframes
        self.rsi_oversold = 20
        self.rsi_overbought = 80
        
        # Bollinger Bands Settings
        self.bb_period = 20
        self.bb_std_dev = 2
        
        # MACD Settings (Tuned for short timeframes)
        self.macd_fast = 12
        self.macd_slow = 26
        self.macd_signal = 9
        
    def generate_signal(self, symbol: str, timeframe: str = '1m', chart_data: Optional[pd.DataFrame] = None) -> Optional[Dict[str, Any]]:
        """Generate trading signal using RSI + BB + MACD"""
        try:
            logger.info(f"🎯 Generating RSI-BB-MACD {timeframe} signal for {symbol}")
            
            # Fetch data
            if chart_data is None:
                chart_data = self._fetch_data(symbol, timeframe)
            
            if chart_data is None or len(chart_data) < 50:
                logger.warning(f"Insufficient data for {symbol}")
                return None
            
            # Calculate all indicators
            rsi = self._calculate_rsi(chart_data)
            bb_upper, bb_middle, bb_lower = self._calculate_bollinger_bands(chart_data)
            macd_line, macd_signal, macd_hist = self._calculate_macd(chart_data)
            
            # Analyze for triple confirmation
            analysis = self._analyze_triple_confirmation(
                chart_data, rsi, bb_upper, bb_middle, bb_lower,
                macd_line, macd_signal, macd_hist
            )
            
            if analysis['signal_direction'] is None:
                logger.info(f"No RSI-BB-MACD signal for {symbol}: {analysis['reason']}")
                return None
            
            signal = {
                'direction': analysis['signal_direction'],
                'confidence': analysis['confidence'],
                'probability': analysis['probability'],
                'entry_price': analysis['entry_price'],
                'reasoning': analysis['reasoning'],
                'chart_timeframe': timeframe,
                'signal_duration': timeframe,
                'strategy_name': self.name,
                'technical_analysis': {
                    'rsi': float(analysis['rsi']),
                    'bb_position': analysis['bb_position'],
                    'macd_signal': analysis['macd_signal'],
                    'confirmations': analysis['confirmations'],
                    'trend_strength': analysis['trend_strength']
                }
            }
            
            logger.info(f"✅ RSI-BB-MACD signal: {signal['direction']} at {signal['confidence']}% ({analysis['confirmations']}/3 confirmations)")
            return signal
            
        except Exception as e:
            logger.error(f"Error in RSI-BB-MACD strategy for {symbol}: {e}")
            return None
    
    def _fetch_data(self, symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
        """Fetch candle data"""
        try:
            yf_symbol = symbol.replace('EURUSD', 'EURUSD=X').replace('GBPUSD', 'GBPUSD=X')
            yf_symbol = yf_symbol.replace('BTCUSD', 'BTC-USD').replace('ETHUSD', 'ETH-USD')
            
            # Map timeframe to yfinance interval
            interval_map = {'1m': '1m', '3m': '1m', '5m': '5m'}
            interval = interval_map.get(timeframe, '1m')
            
            ticker = yf.Ticker(yf_symbol)
            df = ticker.history(period='1d', interval=interval)
            
            if df is None or len(df) == 0:
                return None
            
            return df
            
        except Exception as e:
            logger.error(f"Error fetching data: {e}")
            return None
    
    def _calculate_rsi(self, df: pd.DataFrame) -> pd.Series:
        """Calculate RSI with short period for sensitivity"""
        try:
            close_prices = df['Close'].values
            rsi = talib.RSI(close_prices, timeperiod=self.rsi_period)
            return pd.Series(rsi, index=df.index)
        except Exception as e:
            logger.error(f"Error calculating RSI: {e}")
            return pd.Series([50] * len(df))
    
    def _calculate_bollinger_bands(self, df: pd.DataFrame) -> tuple:
        """Calculate Bollinger Bands"""
        try:
            close_prices = df['Close'].values
            upper, middle, lower = talib.BBANDS(
                close_prices,
                timeperiod=self.bb_period,
                nbdevup=self.bb_std_dev,
                nbdevdn=self.bb_std_dev,
                matype=0
            )
            return (
                pd.Series(upper, index=df.index),
                pd.Series(middle, index=df.index),
                pd.Series(lower, index=df.index)
            )
        except Exception as e:
            logger.error(f"Error calculating Bollinger Bands: {e}")
            neutral = pd.Series([df['Close'].mean()] * len(df))
            return neutral, neutral, neutral
    
    def _calculate_macd(self, df: pd.DataFrame) -> tuple:
        """Calculate MACD"""
        try:
            close_prices = df['Close'].values
            macd, signal, hist = talib.MACD(
                close_prices,
                fastperiod=self.macd_fast,
                slowperiod=self.macd_slow,
                signalperiod=self.macd_signal
            )
            return (
                pd.Series(macd, index=df.index),
                pd.Series(signal, index=df.index),
                pd.Series(hist, index=df.index)
            )
        except Exception as e:
            logger.error(f"Error calculating MACD: {e}")
            zero = pd.Series([0] * len(df))
            return zero, zero, zero
    
    def _analyze_triple_confirmation(self, df: pd.DataFrame, rsi: pd.Series,
                                     bb_upper: pd.Series, bb_middle: pd.Series, bb_lower: pd.Series,
                                     macd_line: pd.Series, macd_signal: pd.Series, macd_hist: pd.Series) -> Dict[str, Any]:
        """Analyze all three indicators for triple confirmation"""
        try:
            current_price = float(df['Close'].iloc[-1])
            
            # Get current indicator values
            rsi_current = float(rsi.iloc[-1])
            rsi_prev = float(rsi.iloc[-2])
            
            bb_upper_val = float(bb_upper.iloc[-1])
            bb_lower_val = float(bb_lower.iloc[-1])
            bb_middle_val = float(bb_middle.iloc[-1])
            
            macd_current = float(macd_line.iloc[-1])
            macd_sig_current = float(macd_signal.iloc[-1])
            macd_prev = float(macd_line.iloc[-2])
            macd_sig_prev = float(macd_signal.iloc[-2])
            macd_hist_current = float(macd_hist.iloc[-1])
            
            # Calculate price position in BB
            bb_range = bb_upper_val - bb_lower_val
            price_position_pct = (current_price - bb_lower_val) / bb_range if bb_range > 0 else 0.5
            
            # Initialize analysis
            signal_direction = None
            confidence = 75.0
            confirmations = 0
            reasoning_parts = []
            
            # BUY Signal Analysis (Triple Confirmation)
            buy_rsi = rsi_current < self.rsi_oversold  # RSI oversold
            buy_bb = price_position_pct < 0.15  # Price near lower BB
            buy_macd = macd_current > macd_sig_current and macd_prev <= macd_sig_prev  # MACD bullish crossover
            
            if buy_rsi:
                confirmations += 1
                confidence += 5.0
                reasoning_parts.append(f"RSI oversold ({rsi_current:.1f})")
            
            if buy_bb:
                confirmations += 1
                confidence += 5.0
                reasoning_parts.append(f"Price at lower BB ({price_position_pct:.1%})")
            
            if buy_macd:
                confirmations += 1
                confidence += 8.0
                reasoning_parts.append(f"MACD bullish crossover")
            
            # Generate BUY if at least 2 confirmations
            if confirmations >= 2 and (buy_rsi or buy_bb):
                signal_direction = 'CALL'
                reasoning = f"🟢 BUY: {' + '.join(reasoning_parts)}"
                
                # Bonus for all 3 confirmations
                if confirmations == 3:
                    confidence += 10.0
                    reasoning += " (TRIPLE CONFIRMATION)"
            
            # SELL Signal Analysis (Triple Confirmation)
            sell_rsi = rsi_current > self.rsi_overbought  # RSI overbought
            sell_bb = price_position_pct > 0.85  # Price near upper BB
            sell_macd = macd_current < macd_sig_current and macd_prev >= macd_sig_prev  # MACD bearish crossover
            
            if signal_direction is None:  # Only check SELL if no BUY signal
                confirmations = 0
                reasoning_parts = []
                
                if sell_rsi:
                    confirmations += 1
                    confidence += 5.0
                    reasoning_parts.append(f"RSI overbought ({rsi_current:.1f})")
                
                if sell_bb:
                    confirmations += 1
                    confidence += 5.0
                    reasoning_parts.append(f"Price at upper BB ({price_position_pct:.1%})")
                
                if sell_macd:
                    confirmations += 1
                    confidence += 8.0
                    reasoning_parts.append(f"MACD bearish crossover")
                
                # Generate SELL if at least 2 confirmations
                if confirmations >= 2 and (sell_rsi or sell_bb):
                    signal_direction = 'PUT'
                    reasoning = f"🔴 SELL: {' + '.join(reasoning_parts)}"
                    
                    # Bonus for all 3 confirmations
                    if confirmations == 3:
                        confidence += 10.0
                        reasoning += " (TRIPLE CONFIRMATION)"
            
            # Calculate trend strength
            trend_strength = abs(macd_hist_current)
            if trend_strength > 0.001 and signal_direction:
                confidence += 3.0
            
            # Cap confidence
            confidence = min(confidence, 95.0)
            
            if signal_direction is None:
                reason = f"Waiting for 2+ confirmations (RSI={rsi_current:.1f}, BB pos={price_position_pct:.1%}, MACD pending)"
            else:
                reason = ""
            
            return {
                'signal_direction': signal_direction,
                'confidence': confidence,
                'probability': confidence,
                'entry_price': current_price,
                'reasoning': reasoning if signal_direction else reason,
                'rsi': rsi_current,
                'bb_position': f"{price_position_pct:.1%}",
                'macd_signal': 'bullish' if macd_current > macd_sig_current else 'bearish',
                'confirmations': confirmations,
                'trend_strength': float(trend_strength),
                'reason': reason
            }
            
        except Exception as e:
            logger.error(f"Error analyzing triple confirmation: {e}")
            return {
                'signal_direction': None,
                'confidence': 0,
                'probability': 0,
                'entry_price': 0,
                'reasoning': f"Error: {str(e)}",
                'rsi': 50,
                'bb_position': '50%',
                'macd_signal': 'neutral',
                'confirmations': 0,
                'trend_strength': 0,
                'reason': f"Error: {str(e)}"
            }

# Global instance
high_accuracy_1m_3m_rsi_bb_macd = HighAccuracy1M3MRsiBbMacd()
