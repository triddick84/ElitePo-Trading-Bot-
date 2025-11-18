"""
Ultra-Precision 5-Second Strategy
Maximum Accuracy for 5s Binary Options Trading

STRATEGY: Multi-Confirmation System with Strict Filters
- Triple EMA crossover (3, 7, 21 periods)
- RSI extreme levels (< 15 or > 85)
- Stochastic confirmation (< 20 or > 80)
- Price action momentum filter
- Volume spike confirmation
- Minimum 3 out of 5 confirmations required

Target: 90%+ accuracy with strict filtering
"""

import logging
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import yfinance as yf
import talib

logger = logging.getLogger(__name__)

class UltraPrecision5sStrategy:
    """
    Ultra-precision 5-second strategy with maximum accuracy
    Strict multi-confirmation system to filter low-quality signals
    """
    
    def __init__(self):
        self.name = "Ultra-Precision 5S"
        
        # Triple EMA System
        self.ema_fast = 3
        self.ema_medium = 7
        self.ema_slow = 21
        
        # RSI Settings (Extreme levels for 5s)
        self.rsi_period = 3  # Ultra-fast for 5s
        self.rsi_oversold = 15  # Extreme oversold
        self.rsi_overbought = 85  # Extreme overbought
        
        # Stochastic Settings
        self.stoch_k = 5
        self.stoch_d = 3
        self.stoch_oversold = 20
        self.stoch_overbought = 80
        
        # Momentum Filter
        self.momentum_period = 3
        self.momentum_threshold = 0.0001  # Minimum momentum required
        
        # Minimum confirmations needed
        self.min_confirmations = 3  # Out of 5 possible
        
    def generate_signal(self, symbol: str, chart_data: Optional[pd.DataFrame] = None) -> Optional[Dict[str, Any]]:
        """Generate ultra-precise 5-second signal"""
        try:
            logger.info(f"🎯 Generating Ultra-Precision 5S signal for {symbol}")
            
            # Fetch 1-minute data (proxy for 5s)
            if chart_data is None:
                chart_data = self._fetch_data(symbol)
            
            if chart_data is None or len(chart_data) < 50:
                logger.warning(f"Insufficient data for {symbol}")
                return None
            
            # Calculate all indicators
            ema_fast = self._calculate_ema(chart_data['Close'], self.ema_fast)
            ema_medium = self._calculate_ema(chart_data['Close'], self.ema_medium)
            ema_slow = self._calculate_ema(chart_data['Close'], self.ema_slow)
            
            rsi = self._calculate_rsi(chart_data['Close'], self.rsi_period)
            
            stoch_k, stoch_d = self._calculate_stochastic(chart_data)
            
            momentum = self._calculate_momentum(chart_data['Close'], self.momentum_period)
            
            volume_spike = self._detect_volume_spike(chart_data)
            
            # Analyze with strict multi-confirmation
            analysis = self._analyze_ultra_precise(
                chart_data, ema_fast, ema_medium, ema_slow,
                rsi, stoch_k, stoch_d, momentum, volume_spike
            )
            
            if analysis['signal_direction'] is None:
                logger.info(f"No ultra-precision signal for {symbol}: {analysis['reason']}")
                return None
            
            signal = {
                'direction': analysis['signal_direction'],
                'confidence': analysis['confidence'],
                'probability': analysis['probability'],
                'entry_price': analysis['entry_price'],
                'reasoning': analysis['reasoning'],
                'chart_timeframe': '5s',
                'signal_duration': '5s',
                'strategy_name': self.name,
                'technical_analysis': {
                    'confirmations': analysis['confirmations'],
                    'total_possible': 5,
                    'rsi': float(analysis['rsi']),
                    'stochastic': float(analysis['stoch_k']),
                    'ema_alignment': analysis['ema_alignment'],
                    'momentum': float(analysis['momentum']),
                    'volume_spike': analysis['volume_spike']
                }
            }
            
            logger.info(f"✅ Ultra-Precision 5S: {signal['direction']} with {analysis['confirmations']}/5 confirmations ({signal['confidence']:.1f}%)")
            return signal
            
        except Exception as e:
            logger.error(f"Error in Ultra-Precision 5S strategy for {symbol}: {e}")
            return None
    
    def _fetch_data(self, symbol: str) -> Optional[pd.DataFrame]:
        """Fetch 1-minute data as proxy for 5-second"""
        try:
            yf_symbol = symbol.replace('EURUSD', 'EURUSD=X').replace('GBPUSD', 'GBPUSD=X')
            yf_symbol = yf_symbol.replace('BTCUSD', 'BTC-USD').replace('ETHUSD', 'ETH-USD')
            
            ticker = yf.Ticker(yf_symbol)
            df = ticker.history(period='1d', interval='1m')
            
            if df is None or len(df) == 0:
                return None
            
            return df
            
        except Exception as e:
            logger.error(f"Error fetching data: {e}")
            return None
    
    def _calculate_ema(self, prices: pd.Series, period: int) -> pd.Series:
        """Calculate Exponential Moving Average"""
        try:
            return prices.ewm(span=period, adjust=False).mean()
        except:
            return pd.Series([prices.mean()] * len(prices))
    
    def _calculate_rsi(self, prices: pd.Series, period: int) -> pd.Series:
        """Calculate RSI"""
        try:
            rsi = talib.RSI(prices.values, timeperiod=period)
            return pd.Series(rsi, index=prices.index)
        except:
            return pd.Series([50] * len(prices))
    
    def _calculate_stochastic(self, df: pd.DataFrame) -> tuple:
        """Calculate Stochastic Oscillator"""
        try:
            stoch_k, stoch_d = talib.STOCH(
                df['High'].values,
                df['Low'].values,
                df['Close'].values,
                fastk_period=self.stoch_k,
                slowk_period=self.stoch_d,
                slowd_period=self.stoch_d
            )
            return (
                pd.Series(stoch_k, index=df.index),
                pd.Series(stoch_d, index=df.index)
            )
        except:
            neutral = pd.Series([50] * len(df))
            return neutral, neutral
    
    def _calculate_momentum(self, prices: pd.Series, period: int) -> pd.Series:
        """Calculate price momentum"""
        try:
            return prices.diff(period)
        except:
            return pd.Series([0] * len(prices))
    
    def _detect_volume_spike(self, df: pd.DataFrame) -> bool:
        """Detect if current volume is significantly higher than average"""
        try:
            if 'Volume' not in df.columns:
                return False
            
            current_volume = df['Volume'].iloc[-1]
            avg_volume = df['Volume'].iloc[-20:-1].mean()
            
            # Volume spike if current > 1.5x average
            return current_volume > (avg_volume * 1.5)
        except:
            return False
    
    def _analyze_ultra_precise(self, df: pd.DataFrame, ema_fast: pd.Series,
                                ema_medium: pd.Series, ema_slow: pd.Series,
                                rsi: pd.Series, stoch_k: pd.Series, stoch_d: pd.Series,
                                momentum: pd.Series, volume_spike: bool) -> Dict[str, Any]:
        """Analyze with strict multi-confirmation system"""
        try:
            current_price = float(df['Close'].iloc[-1])
            
            # Get current values
            ema_f = float(ema_fast.iloc[-1])
            ema_m = float(ema_medium.iloc[-1])
            ema_s = float(ema_slow.iloc[-1])
            
            ema_f_prev = float(ema_fast.iloc[-2])
            ema_m_prev = float(ema_medium.iloc[-2])
            
            rsi_val = float(rsi.iloc[-1])
            stoch_k_val = float(stoch_k.iloc[-1])
            stoch_d_val = float(stoch_d.iloc[-1])
            
            momentum_val = float(momentum.iloc[-1])
            
            # Initialize
            signal_direction = None
            confirmations = 0
            confirmation_list = []
            confidence = 75.0
            
            # === BUY SIGNAL CONFIRMATIONS ===
            
            # 1. Triple EMA Bullish Alignment
            ema_bullish_alignment = (ema_f > ema_m > ema_s)
            ema_bullish_crossover = (ema_f > ema_m and ema_f_prev <= ema_m_prev)
            
            if ema_bullish_alignment or ema_bullish_crossover:
                buy_ema_conf = True
            else:
                buy_ema_conf = False
            
            # 2. RSI Extreme Oversold
            buy_rsi_conf = rsi_val < self.rsi_oversold
            
            # 3. Stochastic Oversold
            buy_stoch_conf = stoch_k_val < self.stoch_oversold and stoch_k_val > stoch_d_val
            
            # 4. Positive Momentum
            buy_momentum_conf = momentum_val > self.momentum_threshold
            
            # 5. Volume Spike
            buy_volume_conf = volume_spike
            
            # Count BUY confirmations
            buy_confirmations = sum([
                buy_ema_conf, buy_rsi_conf, buy_stoch_conf,
                buy_momentum_conf, buy_volume_conf
            ])
            
            # === SELL SIGNAL CONFIRMATIONS ===
            
            # 1. Triple EMA Bearish Alignment
            ema_bearish_alignment = (ema_f < ema_m < ema_s)
            ema_bearish_crossover = (ema_f < ema_m and ema_f_prev >= ema_m_prev)
            
            if ema_bearish_alignment or ema_bearish_crossover:
                sell_ema_conf = True
            else:
                sell_ema_conf = False
            
            # 2. RSI Extreme Overbought
            sell_rsi_conf = rsi_val > self.rsi_overbought
            
            # 3. Stochastic Overbought
            sell_stoch_conf = stoch_k_val > self.stoch_overbought and stoch_k_val < stoch_d_val
            
            # 4. Negative Momentum
            sell_momentum_conf = momentum_val < -self.momentum_threshold
            
            # 5. Volume Spike
            sell_volume_conf = volume_spike
            
            # Count SELL confirmations
            sell_confirmations = sum([
                sell_ema_conf, sell_rsi_conf, sell_stoch_conf,
                sell_momentum_conf, sell_volume_conf
            ])
            
            # === DECISION: Need minimum 3 confirmations ===
            
            if buy_confirmations >= self.min_confirmations:
                signal_direction = 'CALL'
                confirmations = buy_confirmations
                confidence = 75.0 + (buy_confirmations * 4.0)  # +4% per confirmation
                
                if buy_ema_conf:
                    confirmation_list.append("EMA Bullish")
                if buy_rsi_conf:
                    confirmation_list.append(f"RSI Oversold ({rsi_val:.1f})")
                if buy_stoch_conf:
                    confirmation_list.append(f"Stoch Oversold ({stoch_k_val:.1f})")
                if buy_momentum_conf:
                    confirmation_list.append("Positive Momentum")
                if buy_volume_conf:
                    confirmation_list.append("Volume Spike")
                
                reasoning = f"🟢 BUY: {confirmations}/5 confirmations - {', '.join(confirmation_list)}"
                
            elif sell_confirmations >= self.min_confirmations:
                signal_direction = 'PUT'
                confirmations = sell_confirmations
                confidence = 75.0 + (sell_confirmations * 4.0)  # +4% per confirmation
                
                if sell_ema_conf:
                    confirmation_list.append("EMA Bearish")
                if sell_rsi_conf:
                    confirmation_list.append(f"RSI Overbought ({rsi_val:.1f})")
                if sell_stoch_conf:
                    confirmation_list.append(f"Stoch Overbought ({stoch_k_val:.1f})")
                if sell_momentum_conf:
                    confirmation_list.append("Negative Momentum")
                if sell_volume_conf:
                    confirmation_list.append("Volume Spike")
                
                reasoning = f"🔴 SELL: {confirmations}/5 confirmations - {', '.join(confirmation_list)}"
            
            # Boost confidence for perfect 5/5 confirmations
            if confirmations == 5:
                confidence += 10.0
                reasoning += " (PERFECT SETUP)"
            
            # Cap confidence
            confidence = min(confidence, 98.0)
            
            if signal_direction is None:
                reason = f"Insufficient confirmations (BUY:{buy_confirmations}/5, SELL:{sell_confirmations}/5, need {self.min_confirmations})"
            else:
                reason = ""
            
            return {
                'signal_direction': signal_direction,
                'confidence': confidence,
                'probability': confidence,
                'entry_price': current_price,
                'reasoning': reasoning if signal_direction else "",
                'confirmations': confirmations,
                'rsi': rsi_val,
                'stoch_k': stoch_k_val,
                'ema_alignment': 'bullish' if ema_f > ema_m > ema_s else 'bearish' if ema_f < ema_m < ema_s else 'neutral',
                'momentum': momentum_val,
                'volume_spike': volume_spike,
                'reason': reason
            }
            
        except Exception as e:
            logger.error(f"Error analyzing ultra-precise signal: {e}")
            return {
                'signal_direction': None,
                'confidence': 0,
                'probability': 0,
                'entry_price': 0,
                'reasoning': f"Error: {str(e)}",
                'confirmations': 0,
                'rsi': 50,
                'stoch_k': 50,
                'ema_alignment': 'unknown',
                'momentum': 0,
                'volume_spike': False,
                'reason': f"Error: {str(e)}"
            }

# Global instance
ultra_precision_5s_strategy = UltraPrecision5sStrategy()
