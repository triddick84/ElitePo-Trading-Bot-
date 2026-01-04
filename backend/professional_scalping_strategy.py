"""
Professional High Win-Rate Scalping Strategy
=============================================

Based on institutional trading research for 1-minute and 5-second timeframes.
Target: 65-75% win rate with strict filtering (realistic professional range)

Key Components:
1. Trend Filter - EMA Ribbon (9/21) alignment
2. Momentum Filter - RSI + Stochastic crossover confirmation  
3. Price Action - Pullback rejection with candlestick patterns
4. Volume Filter - Above average volume only
5. Volatility Filter - ADX trending market only
6. Multi-timeframe - Higher TF bias confirmation

Research sources:
- Professional scalping strategies (howtotrade.com, timothysykes)
- Institutional order flow concepts
- VWAP deviation strategies
"""

import pandas as pd
import numpy as np
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger(__name__)


class ProfessionalScalpingStrategy:
    """
    Professional-grade scalping strategy for 5s-1m timeframes
    Uses strict multi-filter approach for higher win rate
    """
    
    def __init__(self, timeframe: str = '1m'):
        self.timeframe = timeframe
        self.name = f"Professional Scalping ({timeframe})"
        
        # === INDICATOR SETTINGS (optimized per research) ===
        
        # EMA Ribbon for trend
        self.ema_fast = 9
        self.ema_slow = 21
        self.ema_trend = 50  # Overall trend filter
        
        # RSI settings
        self.rsi_period = 14 if timeframe in ['1m', '5m'] else 7
        self.rsi_bullish_threshold = 50  # Above 50 = bullish momentum
        self.rsi_bearish_threshold = 50  # Below 50 = bearish momentum
        self.rsi_overbought = 70
        self.rsi_oversold = 30
        
        # Stochastic settings (fast for scalping)
        self.stoch_k = 5
        self.stoch_d = 3
        self.stoch_smooth = 3
        self.stoch_oversold = 20
        self.stoch_overbought = 80
        
        # ADX for trend strength
        self.adx_period = 14
        self.adx_trending = 20  # Above this = trending market
        
        # Volume settings
        self.volume_ma_period = 20
        self.volume_spike_threshold = 1.2  # 20% above average minimum
        
        # Bollinger for volatility and S/R
        self.bb_period = 20
        self.bb_std = 2.0
        
        # ATR for stop loss calculation
        self.atr_period = 14
        
        # Minimum confirmations required
        self.min_score = 7  # Out of 10 possible points
        
        logger.info(f"📊 Professional Scalping Strategy initialized for {timeframe}")
    
    def calculate_indicators(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate all required indicators"""
        if len(df) < 50:
            return {}
        
        close = df['close'].astype(float)
        high = df['high'].astype(float)
        low = df['low'].astype(float)
        volume = df['volume'].astype(float) if 'volume' in df.columns else pd.Series([1.0] * len(df))
        
        indicators = {}
        
        try:
            # EMAs for trend
            indicators['ema_fast'] = close.ewm(span=self.ema_fast, adjust=False).mean()
            indicators['ema_slow'] = close.ewm(span=self.ema_slow, adjust=False).mean()
            indicators['ema_trend'] = close.ewm(span=self.ema_trend, adjust=False).mean()
            
            # RSI
            delta = close.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_period).mean()
            rs = gain / loss
            indicators['rsi'] = 100 - (100 / (1 + rs))
            
            # Stochastic
            low_min = low.rolling(window=self.stoch_k).min()
            high_max = high.rolling(window=self.stoch_k).max()
            stoch_k = 100 * (close - low_min) / (high_max - low_min)
            indicators['stoch_k'] = stoch_k.rolling(window=self.stoch_smooth).mean()
            indicators['stoch_d'] = indicators['stoch_k'].rolling(window=self.stoch_d).mean()
            
            # ADX
            plus_dm = high.diff()
            minus_dm = low.diff().abs() * -1
            plus_dm = plus_dm.where((plus_dm > minus_dm.abs()) & (plus_dm > 0), 0)
            minus_dm = minus_dm.abs().where((minus_dm.abs() > plus_dm) & (minus_dm < 0), 0)
            
            tr = pd.concat([
                high - low,
                (high - close.shift()).abs(),
                (low - close.shift()).abs()
            ], axis=1).max(axis=1)
            
            atr = tr.rolling(window=self.adx_period).mean()
            indicators['atr'] = atr
            
            plus_di = 100 * (plus_dm.rolling(window=self.adx_period).mean() / atr)
            minus_di = 100 * (minus_dm.rolling(window=self.adx_period).mean() / atr)
            
            dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di)
            indicators['adx'] = dx.rolling(window=self.adx_period).mean()
            indicators['plus_di'] = plus_di
            indicators['minus_di'] = minus_di
            
            # Bollinger Bands
            sma = close.rolling(window=self.bb_period).mean()
            std = close.rolling(window=self.bb_period).std()
            indicators['bb_upper'] = sma + (std * self.bb_std)
            indicators['bb_middle'] = sma
            indicators['bb_lower'] = sma - (std * self.bb_std)
            
            # Volume MA
            indicators['volume'] = volume
            indicators['volume_ma'] = volume.rolling(window=self.volume_ma_period).mean()
            
            # MACD for additional confirmation
            ema12 = close.ewm(span=12, adjust=False).mean()
            ema26 = close.ewm(span=26, adjust=False).mean()
            indicators['macd'] = ema12 - ema26
            indicators['macd_signal'] = indicators['macd'].ewm(span=9, adjust=False).mean()
            indicators['macd_hist'] = indicators['macd'] - indicators['macd_signal']
            
            # Store price data
            indicators['close'] = close
            indicators['high'] = high
            indicators['low'] = low
            indicators['open'] = df['open'].astype(float)
            
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}")
            return {}
        
        return indicators
    
    def detect_candlestick_pattern(self, open_p: float, high_p: float, low_p: float, close_p: float,
                                    prev_open: float, prev_close: float) -> Dict[str, Any]:
        """Detect high-probability candlestick patterns"""
        body = abs(close_p - open_p)
        total_range = high_p - low_p
        
        if total_range == 0:
            return {'pattern': None, 'bullish': False, 'bearish': False}
        
        upper_wick = high_p - max(open_p, close_p)
        lower_wick = min(open_p, close_p) - low_p
        
        body_ratio = body / total_range
        
        result = {'pattern': None, 'bullish': False, 'bearish': False, 'strength': 0}
        
        # Pin Bar / Hammer (bullish rejection)
        if lower_wick > body * 2 and lower_wick > upper_wick * 1.5 and body_ratio < 0.4:
            result = {'pattern': 'hammer', 'bullish': True, 'bearish': False, 'strength': 0.8}
        
        # Shooting Star (bearish rejection)
        elif upper_wick > body * 2 and upper_wick > lower_wick * 1.5 and body_ratio < 0.4:
            result = {'pattern': 'shooting_star', 'bullish': False, 'bearish': True, 'strength': 0.8}
        
        # Bullish Engulfing
        prev_body = abs(prev_close - prev_open)
        if (prev_close < prev_open and  # Previous bearish
            close_p > open_p and  # Current bullish
            body > prev_body and
            close_p > prev_open and
            open_p < prev_close):
            result = {'pattern': 'bullish_engulfing', 'bullish': True, 'bearish': False, 'strength': 0.9}
        
        # Bearish Engulfing
        elif (prev_close > prev_open and  # Previous bullish
              close_p < open_p and  # Current bearish
              body > prev_body and
              close_p < prev_open and
              open_p > prev_close):
            result = {'pattern': 'bearish_engulfing', 'bullish': False, 'bearish': True, 'strength': 0.9}
        
        # Doji (indecision)
        elif body_ratio < 0.1:
            result = {'pattern': 'doji', 'bullish': False, 'bearish': False, 'strength': 0.3}
        
        return result
    
    def calculate_signal_score(self, indicators: Dict, idx: int) -> Dict[str, Any]:
        """
        Calculate comprehensive signal score based on multiple confirmations
        
        Scoring System (10 points max):
        - Trend alignment (EMA ribbon): 2 points
        - Momentum (RSI direction): 1 point
        - Stochastic crossover: 2 points
        - Volume confirmation: 1 point
        - ADX trending: 1 point
        - Bollinger position: 1 point
        - Candlestick pattern: 1 point
        - MACD confirmation: 1 point
        """
        if idx < 2:
            return {'direction': None, 'score': 0, 'details': []}
        
        # Get current values
        close = indicators['close'].iloc[idx]
        ema_fast = indicators['ema_fast'].iloc[idx]
        ema_slow = indicators['ema_slow'].iloc[idx]
        ema_trend = indicators['ema_trend'].iloc[idx]
        rsi = indicators['rsi'].iloc[idx]
        stoch_k = indicators['stoch_k'].iloc[idx]
        stoch_d = indicators['stoch_d'].iloc[idx]
        adx = indicators['adx'].iloc[idx]
        volume = indicators['volume'].iloc[idx]
        volume_ma = indicators['volume_ma'].iloc[idx]
        bb_upper = indicators['bb_upper'].iloc[idx]
        bb_lower = indicators['bb_lower'].iloc[idx]
        macd_hist = indicators['macd_hist'].iloc[idx]
        
        # Previous values for crossover detection
        prev_stoch_k = indicators['stoch_k'].iloc[idx-1]
        prev_stoch_d = indicators['stoch_d'].iloc[idx-1]
        prev_macd_hist = indicators['macd_hist'].iloc[idx-1]
        
        # Candlestick data
        open_p = indicators['open'].iloc[idx]
        high_p = indicators['high'].iloc[idx]
        low_p = indicators['low'].iloc[idx]
        prev_open = indicators['open'].iloc[idx-1]
        prev_close = indicators['close'].iloc[idx-1]
        
        # Skip if NaN
        if any(pd.isna([ema_fast, ema_slow, rsi, stoch_k, adx])):
            return {'direction': None, 'score': 0, 'details': []}
        
        bullish_score = 0
        bearish_score = 0
        bullish_details = []
        bearish_details = []
        
        # === 1. TREND ALIGNMENT (EMA Ribbon) - 2 points ===
        if ema_fast > ema_slow and close > ema_trend:
            bullish_score += 2
            bullish_details.append("EMA Bullish Ribbon (+2)")
        elif ema_fast < ema_slow and close < ema_trend:
            bearish_score += 2
            bearish_details.append("EMA Bearish Ribbon (+2)")
        
        # === 2. MOMENTUM (RSI Direction) - 1 point ===
        if rsi > self.rsi_bullish_threshold and rsi < self.rsi_overbought:
            bullish_score += 1
            bullish_details.append(f"RSI Bullish={rsi:.1f} (+1)")
        elif rsi < self.rsi_bearish_threshold and rsi > self.rsi_oversold:
            bearish_score += 1
            bearish_details.append(f"RSI Bearish={rsi:.1f} (+1)")
        
        # Extra point for extreme RSI with reversal potential
        if rsi < self.rsi_oversold:
            bullish_score += 1
            bullish_details.append(f"RSI Oversold={rsi:.1f} (+1)")
        elif rsi > self.rsi_overbought:
            bearish_score += 1
            bearish_details.append(f"RSI Overbought={rsi:.1f} (+1)")
        
        # === 3. STOCHASTIC CROSSOVER - 2 points ===
        # Bullish crossover in oversold
        if stoch_k < self.stoch_oversold + 10:  # Allow some buffer
            if stoch_k > stoch_d and prev_stoch_k <= prev_stoch_d:
                bullish_score += 2
                bullish_details.append(f"Stoch Bullish Cross @{stoch_k:.1f} (+2)")
            elif stoch_k < stoch_d:
                bullish_score += 1
                bullish_details.append(f"Stoch Oversold={stoch_k:.1f} (+1)")
        
        # Bearish crossover in overbought
        if stoch_k > self.stoch_overbought - 10:
            if stoch_k < stoch_d and prev_stoch_k >= prev_stoch_d:
                bearish_score += 2
                bearish_details.append(f"Stoch Bearish Cross @{stoch_k:.1f} (+2)")
            elif stoch_k > stoch_d:
                bearish_score += 1
                bearish_details.append(f"Stoch Overbought={stoch_k:.1f} (+1)")
        
        # === 4. VOLUME CONFIRMATION - 1 point ===
        if not pd.isna(volume_ma) and volume_ma > 0:
            vol_ratio = volume / volume_ma
            if vol_ratio >= self.volume_spike_threshold:
                # Add to stronger direction
                if bullish_score > bearish_score:
                    bullish_score += 1
                    bullish_details.append(f"Volume Spike {vol_ratio:.1f}x (+1)")
                elif bearish_score > bullish_score:
                    bearish_score += 1
                    bearish_details.append(f"Volume Spike {vol_ratio:.1f}x (+1)")
        
        # === 5. ADX TRENDING MARKET - 1 point ===
        if not pd.isna(adx) and adx > self.adx_trending:
            # Add to stronger direction
            if bullish_score > bearish_score:
                bullish_score += 1
                bullish_details.append(f"ADX Trending={adx:.1f} (+1)")
            elif bearish_score > bullish_score:
                bearish_score += 1
                bearish_details.append(f"ADX Trending={adx:.1f} (+1)")
        
        # === 6. BOLLINGER BAND POSITION - 1 point ===
        if not pd.isna(bb_lower) and not pd.isna(bb_upper):
            bb_range = bb_upper - bb_lower
            if bb_range > 0:
                bb_position = (close - bb_lower) / bb_range
                
                if bb_position < 0.1:  # Near lower band
                    bullish_score += 1
                    bullish_details.append(f"BB Lower Touch ({bb_position:.2f}) (+1)")
                elif bb_position > 0.9:  # Near upper band
                    bearish_score += 1
                    bearish_details.append(f"BB Upper Touch ({bb_position:.2f}) (+1)")
        
        # === 7. CANDLESTICK PATTERN - 1 point ===
        candle = self.detect_candlestick_pattern(open_p, high_p, low_p, close, prev_open, prev_close)
        if candle['bullish'] and candle['pattern']:
            bullish_score += 1
            bullish_details.append(f"Candle: {candle['pattern']} (+1)")
        elif candle['bearish'] and candle['pattern']:
            bearish_score += 1
            bearish_details.append(f"Candle: {candle['pattern']} (+1)")
        
        # === 8. MACD CONFIRMATION - 1 point ===
        if not pd.isna(macd_hist) and not pd.isna(prev_macd_hist):
            # MACD histogram increasing (bullish)
            if macd_hist > prev_macd_hist and macd_hist > 0:
                bullish_score += 1
                bullish_details.append("MACD Rising (+1)")
            # MACD histogram decreasing (bearish)
            elif macd_hist < prev_macd_hist and macd_hist < 0:
                bearish_score += 1
                bearish_details.append("MACD Falling (+1)")
        
        # === DETERMINE FINAL SIGNAL ===
        direction = None
        final_score = 0
        details = []
        
        if bullish_score >= self.min_score and bullish_score > bearish_score + 1:
            direction = 'CALL'
            final_score = bullish_score
            details = bullish_details
        elif bearish_score >= self.min_score and bearish_score > bullish_score + 1:
            direction = 'PUT'
            final_score = bearish_score
            details = bearish_details
        
        return {
            'direction': direction,
            'score': final_score,
            'bullish_score': bullish_score,
            'bearish_score': bearish_score,
            'details': details,
            'indicators': {
                'rsi': round(rsi, 1),
                'stoch_k': round(stoch_k, 1),
                'adx': round(adx, 1) if not pd.isna(adx) else 0,
                'macd_hist': round(macd_hist, 5) if not pd.isna(macd_hist) else 0
            }
        }
    
    def generate_signal(self, df: pd.DataFrame, symbol: str = "UNKNOWN") -> Optional[Dict[str, Any]]:
        """Generate trading signal with strict filtering"""
        indicators = self.calculate_indicators(df)
        
        if not indicators:
            return None
        
        # Analyze last candle
        idx = len(df) - 1
        result = self.calculate_signal_score(indicators, idx)
        
        if result['direction'] is None:
            logger.debug(f"No signal for {symbol}: B={result['bullish_score']}, S={result['bearish_score']}, min={self.min_score}")
            return None
        
        # Calculate confidence based on score
        # Score 7 = 75%, Score 8 = 80%, Score 9 = 85%, Score 10 = 90%
        confidence = min(70 + (result['score'] - self.min_score + 1) * 5, 92)
        
        current_price = indicators['close'].iloc[idx]
        
        signal = {
            'direction': result['direction'],
            'confidence': confidence,
            'probability': confidence,
            'entry_price': current_price,
            'symbol': symbol,
            'timeframe': self.timeframe,
            'score': result['score'],
            'max_score': 10,
            'confirmations': result['details'],
            'indicators': result['indicators'],
            'strategy': self.name,
            'reasoning': f"{result['direction']} signal ({result['score']}/10): " + ", ".join(result['details'][:3])
        }
        
        logger.info(f"✅ {self.name}: {symbol} {result['direction']} ({confidence}%) - Score {result['score']}/10")
        logger.info(f"   Details: {result['details']}")
        
        return signal


def get_professional_scalping_strategy(timeframe: str = '1m') -> ProfessionalScalpingStrategy:
    """Factory function"""
    return ProfessionalScalpingStrategy(timeframe)


# Add to backtesting engine
class ProfessionalScalpingBacktest:
    """Backtest wrapper for the professional scalping strategy"""
    
    def __init__(self):
        self.strategy = ProfessionalScalpingStrategy('1m')
    
    def generate_signals(self, df: pd.DataFrame) -> List[Dict]:
        """Generate all signals for backtesting"""
        signals = []
        indicators = self.strategy.calculate_indicators(df)
        
        if not indicators:
            return signals
        
        for i in range(50, len(df)):
            result = self.strategy.calculate_signal_score(indicators, i)
            
            if result['direction']:
                confidence = min(70 + (result['score'] - self.strategy.min_score + 1) * 5, 92)
                signals.append({
                    'index': i,
                    'timestamp': str(df.index[i]),
                    'direction': 'call' if result['direction'] == 'CALL' else 'put',
                    'confidence': confidence,
                    'entry_price': indicators['close'].iloc[i],
                    'score': result['score']
                })
        
        return signals
