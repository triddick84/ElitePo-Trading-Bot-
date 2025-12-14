"""
2-Minute Support & Resistance Bounce Strategy
Accuracy Target: 80%+

Based on research:
- Key support/resistance levels
- Price action at levels
- Volume confirmation

Entry Rules:
CALL: Price bounces off support, RSI oversold, volume increasing
PUT: Price rejects at resistance, RSI overbought, volume increasing
"""

import pandas as pd
import numpy as np
from typing import Dict, List
import talib
import logging

logger = logging.getLogger(__name__)


class Strategy2mSupportResistance:
    """2-Minute Support & Resistance Bounce Strategy"""
    
    def __init__(self):
        self.name = "2m S&R Bounce"
        self.timeframe = "2m"
        self.accuracy_target = 80.0
        
        # Parameters
        self.lookback_period = 50
        self.level_threshold = 0.001  # 0.1% price tolerance
        
    def identify_sr_levels(self, df: pd.DataFrame) -> Dict[str, List[float]]:
        """Identify support and resistance levels"""
        try:
            levels = {'support': [], 'resistance': []}
            
            # Find swing highs and lows
            highs = df['high'].rolling(window=5, center=True).max()
            lows = df['low'].rolling(window=5, center=True).min()
            
            # Identify swing points
            for i in range(5, len(df) - 5):
                if df['high'].iloc[i] == highs.iloc[i]:
                    levels['resistance'].append(df['high'].iloc[i])
                if df['low'].iloc[i] == lows.iloc[i]:
                    levels['support'].append(df['low'].iloc[i])
            
            # Cluster similar levels
            levels['support'] = self._cluster_levels(levels['support'])
            levels['resistance'] = self._cluster_levels(levels['resistance'])
            
            return levels
            
        except Exception as e:
            logger.error(f"Error identifying S&R levels: {e}")
            return {'support': [], 'resistance': []}
    
    def _cluster_levels(self, levels: List[float]) -> List[float]:
        """Cluster nearby price levels"""
        if not levels:
            return []
        
        levels = sorted(levels)
        clustered = []
        current_cluster = [levels[0]]
        
        for level in levels[1:]:
            if (level - current_cluster[-1]) / current_cluster[-1] < self.level_threshold:
                current_cluster.append(level)
            else:
                clustered.append(np.mean(current_cluster))
                current_cluster = [level]
        
        if current_cluster:
            clustered.append(np.mean(current_cluster))
        
        return clustered
    
    def calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate required indicators"""
        try:
            # RSI
            df['rsi'] = talib.RSI(df['close'], timeperiod=14)
            
            # Volume
            df['volume_ma'] = df['volume'].rolling(window=20).mean()
            df['volume_ratio'] = df['volume'] / df['volume_ma']
            
            # Stochastic
            df['stoch_k'], df['stoch_d'] = talib.STOCH(
                df['high'], df['low'], df['close'],
                fastk_period=14, slowk_period=3, slowd_period=3
            )
            
            # MACD
            df['macd'], df['macd_signal'], df['macd_hist'] = talib.MACD(df['close'])
            
            return df
            
        except Exception as e:
            logger.error(f"Error calculating indicators: {e}")
            return df
    
    def generate_signal(self, df: pd.DataFrame) -> Dict:
        """Generate trading signal"""
        if len(df) < self.lookback_period:
            return {'direction': 'NEUTRAL', 'confidence': 0, 'reason': 'Insufficient data'}
        
        df = self.calculate_indicators(df)
        sr_levels = self.identify_sr_levels(df.tail(self.lookback_period))
        
        if df.empty or df['rsi'].isna().all():
            return {'direction': 'NEUTRAL', 'confidence': 0, 'reason': 'Indicator calculation failed'}
        
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        current_price = latest['close']
        
        call_signals = 0
        put_signals = 0
        reasons = []
        
        # 1. Check proximity to S&R levels (40 points)
        nearest_support = None
        nearest_resistance = None
        
        if sr_levels['support']:
            nearest_support = min(sr_levels['support'], key=lambda x: abs(x - current_price))
            support_distance = abs(current_price - nearest_support) / current_price
            
            if support_distance < self.level_threshold * 3:  # Within 0.3%
                call_signals += 40
                reasons.append(f"✅ Price near support level (${nearest_support:.5f})")
        
        if sr_levels['resistance']:
            nearest_resistance = min(sr_levels['resistance'], key=lambda x: abs(x - current_price))
            resistance_distance = abs(current_price - nearest_resistance) / current_price
            
            if resistance_distance < self.level_threshold * 3:  # Within 0.3%
                put_signals += 40
                reasons.append(f"✅ Price near resistance level (${nearest_resistance:.5f})")
        
        # 2. Price Action Confirmation (25 points)
        # Bounce off support
        if call_signals > 0:
            if prev['close'] < prev['open'] and latest['close'] > latest['open']:
                call_signals += 25
                reasons.append("✅ Bullish reversal candle at support")
        
        # Rejection at resistance
        if put_signals > 0:
            if prev['close'] > prev['open'] and latest['close'] < latest['open']:
                put_signals += 25
                reasons.append("✅ Bearish reversal candle at resistance")
        
        # 3. RSI Confirmation (20 points)
        if call_signals > 0 and latest['rsi'] < 40:
            call_signals += 20
            reasons.append(f"✅ RSI oversold ({latest['rsi']:.1f})")
        elif put_signals > 0 and latest['rsi'] > 60:
            put_signals += 20
            reasons.append(f"✅ RSI overbought ({latest['rsi']:.1f})")
        
        # 4. Volume Confirmation (10 points)
        if latest['volume_ratio'] > 1.2:
            if call_signals > put_signals:
                call_signals += 10
                reasons.append(f"✅ High volume ({latest['volume_ratio']:.2f}x)")
            elif put_signals > call_signals:
                put_signals += 10
                reasons.append(f"✅ High volume ({latest['volume_ratio']:.2f}x)")
        
        # 5. MACD Confirmation (5 points)
        if call_signals > 0 and latest['macd'] > latest['macd_signal']:
            call_signals += 5
            reasons.append("✅ MACD bullish")
        elif put_signals > 0 and latest['macd'] < latest['macd_signal']:
            put_signals += 5
            reasons.append("✅ MACD bearish")
        
        # Determine signal
        if call_signals > put_signals and call_signals >= 70:
            direction = 'CALL'
            confidence = min(call_signals, 100)
        elif put_signals > call_signals and put_signals >= 70:
            direction = 'PUT'
            confidence = min(put_signals, 100)
        else:
            direction = 'NEUTRAL'
            confidence = max(call_signals, put_signals)
            reasons.append("⚠️ No clear S&R level or insufficient confirmation")
        
        return {
            'direction': direction,
            'confidence': confidence,
            'reason': ' | '.join(reasons),
            'strategy': self.name,
            'timeframe': self.timeframe,
            'call_score': call_signals,
            'put_score': put_signals,
            'sr_levels': {
                'support': sr_levels['support'][-3:] if sr_levels['support'] else [],
                'resistance': sr_levels['resistance'][-3:] if sr_levels['resistance'] else []
            },
            'indicators': {
                'rsi': float(latest['rsi']),
                'volume_ratio': float(latest['volume_ratio']),
                'nearest_support': float(nearest_support) if nearest_support else None,
                'nearest_resistance': float(nearest_resistance) if nearest_resistance else None
            }
        }


strategy_2m_support_resistance = Strategy2mSupportResistance()
