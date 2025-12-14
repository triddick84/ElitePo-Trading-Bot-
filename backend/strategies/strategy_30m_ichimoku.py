"""
30-Minute Ichimoku Cloud Strategy
Accuracy Target: 84%+

Based on research:
- Ichimoku cloud analysis
- Tenkan/Kijun crossovers
- Cloud breakouts

Entry Rules:
CALL: Price above cloud + Tenkan crosses Kijun up + Chikou above price
PUT: Price below cloud + Tenkan crosses Kijun down + Chikou below price
"""

import pandas as pd
import numpy as np
from typing import Dict
import talib
import logging

logger = logging.getLogger(__name__)


class Strategy30mIchimoku:
    def __init__(self):
        self.name = "30m Ichimoku Cloud"
        self.timeframe = "30m"
        self.accuracy_target = 84.0
    
    def calculate_ichimoku(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate Ichimoku indicators"""
        try:
            # Tenkan-sen (Conversion Line): (9-period high + 9-period low)/2
            nine_high = df['high'].rolling(window=9).max()
            nine_low = df['low'].rolling(window=9).min()
            df['tenkan_sen'] = (nine_high + nine_low) / 2
            
            # Kijun-sen (Base Line): (26-period high + 26-period low)/2
            twenty_six_high = df['high'].rolling(window=26).max()
            twenty_six_low = df['low'].rolling(window=26).min()
            df['kijun_sen'] = (twenty_six_high + twenty_six_low) / 2
            
            # Senkou Span A (Leading Span A): (Tenkan-sen + Kijun-sen)/2
            df['senkou_a'] = ((df['tenkan_sen'] + df['kijun_sen']) / 2).shift(26)
            
            # Senkou Span B (Leading Span B): (52-period high + 52-period low)/2
            fifty_two_high = df['high'].rolling(window=52).max()
            fifty_two_low = df['low'].rolling(window=52).min()
            df['senkou_b'] = ((fifty_two_high + fifty_two_low) / 2).shift(26)
            
            # Chikou Span (Lagging Span): Close shifted back 26 periods
            df['chikou_span'] = df['close'].shift(-26)
            
            return df
        except Exception as e:
            logger.error(f"Error calculating Ichimoku: {e}")
            return df
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        try:
            df = self.calculate_ichimoku(df)
            df['rsi'] = talib.RSI(df['close'], timeperiod=14)
            df['atr'] = talib.ATR(df['high'], df['low'], df['close'], timeperiod=14)
            return df
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}")
            return df
    
    def generate_signal(self, df: pd.DataFrame) -> Dict:
        if len(df) < 100:
            return {'direction': 'NEUTRAL', 'confidence': 0, 'reason': 'Insufficient data for Ichimoku'}
        
        df = self.calculate_indicators(df)
        
        if df.empty or df['tenkan_sen'].isna().all():
            return {'direction': 'NEUTRAL', 'confidence': 0, 'reason': 'Indicator calculation failed'}
        
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        call_signals = 0
        put_signals = 0
        reasons = []
        
        # 1. Price vs Cloud (35 points)
        cloud_top = max(latest['senkou_a'], latest['senkou_b']) if pd.notna(latest['senkou_a']) and pd.notna(latest['senkou_b']) else latest['close']
        cloud_bottom = min(latest['senkou_a'], latest['senkou_b']) if pd.notna(latest['senkou_a']) and pd.notna(latest['senkou_b']) else latest['close']
        
        if latest['close'] > cloud_top:
            call_signals += 35
            reasons.append("✅ Price above Ichimoku cloud")
        elif latest['close'] < cloud_bottom:
            put_signals += 35
            reasons.append("✅ Price below Ichimoku cloud")
        
        # 2. Tenkan/Kijun Crossover (35 points)
        if latest['tenkan_sen'] > latest['kijun_sen'] and prev['tenkan_sen'] <= prev['kijun_sen']:
            call_signals += 35
            reasons.append("✅ Tenkan crosses above Kijun (bullish)")
        elif latest['tenkan_sen'] < latest['kijun_sen'] and prev['tenkan_sen'] >= prev['kijun_sen']:
            put_signals += 35
            reasons.append("✅ Tenkan crosses below Kijun (bearish)")
        
        # 3. Chikou Span Position (20 points)
        # Note: Chikou is shifted back, so we compare current Chikou with past price
        if pd.notna(latest['chikou_span']):
            chikou_idx = len(df) - 27  # 26 periods back + 1
            if chikou_idx >= 0:
                past_price = df.iloc[chikou_idx]['close']
                if latest['chikou_span'] > past_price:
                    call_signals += 20
                    reasons.append("✅ Chikou above price (bullish)")
                elif latest['chikou_span'] < past_price:
                    put_signals += 20
                    reasons.append("✅ Chikou below price (bearish)")
        
        # 4. RSI Filter (5 points)
        if 40 < latest['rsi'] < 70:
            call_signals += 5
        elif 30 < latest['rsi'] < 60:
            put_signals += 5
        
        # 5. Cloud Color (5 points)
        if pd.notna(latest['senkou_a']) and pd.notna(latest['senkou_b']):
            if latest['senkou_a'] > latest['senkou_b']:  # Bullish cloud
                call_signals += 5
            elif latest['senkou_a'] < latest['senkou_b']:  # Bearish cloud
                put_signals += 5
        
        if call_signals > put_signals and call_signals >= 75:
            direction = 'CALL'
            confidence = min(call_signals, 100)
        elif put_signals > call_signals and put_signals >= 75:
            direction = 'PUT'
            confidence = min(put_signals, 100)
        else:
            direction = 'NEUTRAL'
            confidence = max(call_signals, put_signals)
            reasons.append("⚠️ Insufficient signal strength")
        
        return {
            'direction': direction,
            'confidence': confidence,
            'reason': ' | '.join(reasons),
            'strategy': self.name,
            'timeframe': self.timeframe,
            'call_score': call_signals,
            'put_score': put_signals,
            'indicators': {
                'tenkan_sen': float(latest['tenkan_sen']),
                'kijun_sen': float(latest['kijun_sen']),
                'cloud_top': float(cloud_top),
                'cloud_bottom': float(cloud_bottom),
                'rsi': float(latest['rsi'])
            }
        }


strategy_30m_ichimoku = Strategy30mIchimoku()
