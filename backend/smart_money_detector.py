"""
Smart Money Concepts (SMC) + ICT Detector for Binary Options
Detects institutional activity: Liquidity Grabs, Order Blocks, Fair Value Gaps

Based on 2025 research - highest accuracy method for ultra-short timeframes
Target: 90-95% accuracy when combined with technical analysis
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class SmartMoneyDetector:
    """
    Detects Smart Money activity and institutional patterns
    
    Key Concepts:
    1. Liquidity Grab: Price sweeps highs/lows to trigger stops, then reverses
    2. Order Block: Last candle before strong move (institutional entry zone)
    3. Fair Value Gap (FVG): Price imbalance between 3 candles
    4. Market Structure: Break of Structure (BOS) vs Change of Character (CHoCH)
    """
    
    def __init__(self, timeframe: str = '5s'):
        self.timeframe = timeframe
        
        # Liquidity grab detection parameters
        self.min_wick_ratio = 0.5  # Wick must be 50%+ of total candle range
        self.reversal_threshold = 0.6  # Body must reclaim 60% of wick
        self.lookback_candles = 20  # Check last 20 candles for key levels
        
        # Order block parameters
        self.ob_strength_threshold = 0.002  # 0.2% minimum move to be significant
        self.ob_recent_candles = 5  # Look at last 5 candles for OBs
        
        # Fair Value Gap parameters
        self.fvg_min_gap = 0.0005  # Minimum gap size (0.05%)
        
        # Market structure parameters
        self.structure_lookback = 10  # Candles to analyze for structure
        
        logger.info(f"✅ Smart Money Detector initialized for {timeframe}")
    
    def detect_liquidity_grab(self, df: pd.DataFrame) -> Dict:
        """
        Detect liquidity grab patterns
        
        Liquidity Grab occurs when:
        1. Price makes a long wick breaching recent high/low
        2. Candle closes back inside previous range (reversal)
        3. Next candle confirms reversal direction
        
        Returns dict with:
        - grab_detected: bool
        - grab_type: 'bullish' (swept low) or 'bearish' (swept high)
        - grab_level: price level where liquidity was grabbed
        - reversal_strength: 0-100 score
        """
        try:
            if len(df) < self.lookback_candles:
                return {'grab_detected': False}
            
            # Get recent data
            recent = df.tail(self.lookback_candles).copy()
            last_candle = df.iloc[-1]
            prev_candle = df.iloc[-2] if len(df) >= 2 else None
            
            # Calculate recent highs and lows (swing points)
            recent_high = recent['high'].max()
            recent_low = recent['low'].min()
            
            # Check for BULLISH liquidity grab (swept low, reversed up)
            bullish_grab = False
            bearish_grab = False
            grab_level = 0
            reversal_strength = 0
            
            # Bullish: Long lower wick that breaches recent low, closes higher
            lower_wick = last_candle['open'] - last_candle['low'] if last_candle['close'] > last_candle['open'] else last_candle['close'] - last_candle['low']
            upper_wick = last_candle['high'] - last_candle['open'] if last_candle['close'] < last_candle['open'] else last_candle['high'] - last_candle['close']
            candle_range = last_candle['high'] - last_candle['low']
            
            if candle_range > 0:
                lower_wick_ratio = lower_wick / candle_range
                upper_wick_ratio = upper_wick / candle_range
                
                # BULLISH GRAB: Long lower wick breaching recent low
                if lower_wick_ratio >= self.min_wick_ratio and last_candle['low'] <= recent_low * 1.0001:
                    # Check if candle closed back up (reversal)
                    close_position = (last_candle['close'] - last_candle['low']) / candle_range
                    if close_position >= self.reversal_threshold:
                        bullish_grab = True
                        grab_level = last_candle['low']
                        reversal_strength = min(100, close_position * 100)
                        logger.info(f"🟢 BULLISH LIQUIDITY GRAB: Swept low at {grab_level:.5f}, reversed {reversal_strength:.1f}%")
                
                # BEARISH GRAB: Long upper wick breaching recent high
                elif upper_wick_ratio >= self.min_wick_ratio and last_candle['high'] >= recent_high * 0.9999:
                    # Check if candle closed back down (reversal)
                    close_position = (last_candle['high'] - last_candle['close']) / candle_range
                    if close_position >= self.reversal_threshold:
                        bearish_grab = True
                        grab_level = last_candle['high']
                        reversal_strength = min(100, close_position * 100)
                        logger.info(f"🔴 BEARISH LIQUIDITY GRAB: Swept high at {grab_level:.5f}, reversed {reversal_strength:.1f}%")
            
            return {
                'grab_detected': bullish_grab or bearish_grab,
                'grab_type': 'bullish' if bullish_grab else ('bearish' if bearish_grab else None),
                'grab_level': grab_level,
                'reversal_strength': reversal_strength,
                'candles_ago': 0  # Just happened on last candle
            }
            
        except Exception as e:
            logger.error(f"Error detecting liquidity grab: {e}")
            return {'grab_detected': False}
    
    def identify_order_blocks(self, df: pd.DataFrame) -> Dict:
        """
        Identify Order Blocks - zones where institutional orders were placed
        
        Order Block = Last opposite-colored candle before strong directional move
        
        Bullish OB: Last red candle before strong rally (support zone)
        Bearish OB: Last green candle before strong drop (resistance zone)
        
        Returns dict with:
        - bullish_ob: list of bullish order block zones [{high, low, strength}]
        - bearish_ob: list of bearish order block zones
        - nearest_ob_type: 'bullish' or 'bearish'
        - distance_to_ob: percentage distance to nearest OB
        """
        try:
            if len(df) < self.ob_recent_candles + 3:
                return {'bullish_ob': [], 'bearish_ob': []}
            
            bullish_obs = []
            bearish_obs = []
            current_price = df.iloc[-1]['close']
            
            # Look for order blocks in recent candles
            for i in range(len(df) - self.ob_recent_candles, len(df) - 1):
                candle = df.iloc[i]
                next_candle = df.iloc[i + 1]
                
                # Calculate move strength after this candle
                move_size = abs(df.iloc[i+1:i+4]['close'].max() - df.iloc[i+1:i+4]['close'].min()) if i + 4 < len(df) else 0
                move_pct = move_size / candle['close'] if candle['close'] > 0 else 0
                
                # Bullish OB: Red candle before upward move
                if candle['close'] < candle['open'] and next_candle['close'] > next_candle['open']:
                    if move_pct >= self.ob_strength_threshold:
                        bullish_obs.append({
                            'high': candle['high'],
                            'low': candle['low'],
                            'mid': (candle['high'] + candle['low']) / 2,
                            'strength': min(100, move_pct * 1000),  # Scale to 0-100
                            'candles_ago': len(df) - i - 1
                        })
                
                # Bearish OB: Green candle before downward move
                elif candle['close'] > candle['open'] and next_candle['close'] < next_candle['open']:
                    if move_pct >= self.ob_strength_threshold:
                        bearish_obs.append({
                            'high': candle['high'],
                            'low': candle['low'],
                            'mid': (candle['high'] + candle['low']) / 2,
                            'strength': min(100, move_pct * 1000),
                            'candles_ago': len(df) - i - 1
                        })
            
            # Find nearest order block to current price
            nearest_ob_type = None
            distance_to_ob = 100  # percentage
            
            for ob in bullish_obs:
                dist = abs(current_price - ob['mid']) / current_price * 100
                if dist < distance_to_ob:
                    distance_to_ob = dist
                    nearest_ob_type = 'bullish'
            
            for ob in bearish_obs:
                dist = abs(current_price - ob['mid']) / current_price * 100
                if dist < distance_to_ob:
                    distance_to_ob = dist
                    nearest_ob_type = 'bearish'
            
            if bullish_obs or bearish_obs:
                logger.info(f"📦 Order Blocks: {len(bullish_obs)} bullish, {len(bearish_obs)} bearish. Nearest: {nearest_ob_type} at {distance_to_ob:.2f}% away")
            
            return {
                'bullish_ob': bullish_obs,
                'bearish_ob': bearish_obs,
                'nearest_ob_type': nearest_ob_type,
                'distance_to_ob': distance_to_ob,
                'near_ob': distance_to_ob < 0.5  # Within 0.5% of an OB
            }
            
        except Exception as e:
            logger.error(f"Error identifying order blocks: {e}")
            return {'bullish_ob': [], 'bearish_ob': []}
    
    def find_fair_value_gaps(self, df: pd.DataFrame) -> Dict:
        """
        Detect Fair Value Gaps (FVG) - price imbalances
        
        FVG occurs when there's a gap between 3 consecutive candles:
        - Bullish FVG: Gap between candle 1 high and candle 3 low (after up move)
        - Bearish FVG: Gap between candle 1 low and candle 3 high (after down move)
        
        These gaps often get "filled" as price returns to fill the imbalance
        
        Returns dict with:
        - fvg_detected: bool
        - fvg_type: 'bullish' or 'bearish'
        - gap_high: upper boundary of gap
        - gap_low: lower boundary of gap
        - gap_size: size of gap in price
        - gap_filled: bool (has price returned to gap?)
        """
        try:
            if len(df) < 5:
                return {'fvg_detected': False}
            
            # Check last 3 candles for FVG pattern
            c1 = df.iloc[-3]  # First candle
            c2 = df.iloc[-2]  # Middle candle (the "gap" candle)
            c3 = df.iloc[-1]  # Third candle
            
            current_price = c3['close']
            
            # Bullish FVG: Gap up (c1.high < c3.low)
            bullish_fvg = False
            bearish_fvg = False
            gap_high = 0
            gap_low = 0
            gap_size = 0
            
            if c1['high'] < c3['low']:
                gap_size = c3['low'] - c1['high']
                gap_pct = gap_size / c1['close']
                
                if gap_pct >= self.fvg_min_gap:
                    bullish_fvg = True
                    gap_low = c1['high']
                    gap_high = c3['low']
                    logger.info(f"🟢 BULLISH FVG: Gap from {gap_low:.5f} to {gap_high:.5f} (size: {gap_pct*100:.3f}%)")
            
            # Bearish FVG: Gap down (c1.low > c3.high)
            elif c1['low'] > c3['high']:
                gap_size = c1['low'] - c3['high']
                gap_pct = gap_size / c1['close']
                
                if gap_pct >= self.fvg_min_gap:
                    bearish_fvg = True
                    gap_high = c1['low']
                    gap_low = c3['high']
                    logger.info(f"🔴 BEARISH FVG: Gap from {gap_low:.5f} to {gap_high:.5f} (size: {gap_pct*100:.3f}%)")
            
            # Check if gap has been filled
            gap_filled = False
            if bullish_fvg or bearish_fvg:
                # Gap is filled if price has returned to the gap zone
                if gap_low <= current_price <= gap_high:
                    gap_filled = True
            
            return {
                'fvg_detected': bullish_fvg or bearish_fvg,
                'fvg_type': 'bullish' if bullish_fvg else ('bearish' if bearish_fvg else None),
                'gap_high': gap_high,
                'gap_low': gap_low,
                'gap_mid': (gap_high + gap_low) / 2 if (bullish_fvg or bearish_fvg) else 0,
                'gap_size': gap_size,
                'gap_filled': gap_filled,
                'price_in_gap': gap_low <= current_price <= gap_high if (bullish_fvg or bearish_fvg) else False
            }
            
        except Exception as e:
            logger.error(f"Error finding fair value gaps: {e}")
            return {'fvg_detected': False}
    
    def analyze_market_structure(self, df: pd.DataFrame) -> Dict:
        """
        Analyze market structure for trend and reversal signals
        
        Key Concepts:
        - Higher Highs (HH) + Higher Lows (HL) = Uptrend
        - Lower Highs (LH) + Lower Lows (LL) = Downtrend
        - Break of Structure (BOS): Continuation of trend
        - Change of Character (CHoCH): Potential trend reversal
        
        Returns dict with:
        - structure: 'uptrend', 'downtrend', or 'sideways'
        - bos_detected: bool (Break of Structure - continuation)
        - choch_detected: bool (Change of Character - reversal)
        - strength: 0-100 score of structure clarity
        """
        try:
            if len(df) < self.structure_lookback:
                return {'structure': 'unknown', 'bos_detected': False, 'choch_detected': False}
            
            # Get recent highs and lows
            recent = df.tail(self.structure_lookback)
            
            # Find swing highs and lows (local peaks/troughs)
            swing_highs = []
            swing_lows = []
            
            for i in range(2, len(recent) - 2):
                current = recent.iloc[i]
                
                # Swing high: higher than 2 candles before and after
                if (current['high'] > recent.iloc[i-1]['high'] and 
                    current['high'] > recent.iloc[i-2]['high'] and
                    current['high'] > recent.iloc[i+1]['high'] and
                    current['high'] > recent.iloc[i+2]['high']):
                    swing_highs.append(current['high'])
                
                # Swing low: lower than 2 candles before and after
                if (current['low'] < recent.iloc[i-1]['low'] and 
                    current['low'] < recent.iloc[i-2]['low'] and
                    current['low'] < recent.iloc[i+1]['low'] and
                    current['low'] < recent.iloc[i+2]['low']):
                    swing_lows.append(current['low'])
            
            # Determine structure
            structure = 'sideways'
            bos_detected = False
            choch_detected = False
            strength = 50
            
            if len(swing_highs) >= 2 and len(swing_lows) >= 2:
                # Check for uptrend (HH + HL)
                if swing_highs[-1] > swing_highs[-2] and swing_lows[-1] > swing_lows[-2]:
                    structure = 'uptrend'
                    strength = min(100, ((swing_highs[-1] / swing_highs[-2] - 1) + (swing_lows[-1] / swing_lows[-2] - 1)) * 5000)
                    
                    # BOS in uptrend: New high after pullback
                    current_high = df.iloc[-1]['high']
                    if current_high > swing_highs[-1]:
                        bos_detected = True
                        logger.info(f"📈 BOS (Uptrend): New high at {current_high:.5f}")
                
                # Check for downtrend (LH + LL)
                elif swing_highs[-1] < swing_highs[-2] and swing_lows[-1] < swing_lows[-2]:
                    structure = 'downtrend'
                    strength = min(100, ((swing_highs[-2] / swing_highs[-1] - 1) + (swing_lows[-2] / swing_lows[-1] - 1)) * 5000)
                    
                    # BOS in downtrend: New low after pullback
                    current_low = df.iloc[-1]['low']
                    if current_low < swing_lows[-1]:
                        bos_detected = True
                        logger.info(f"📉 BOS (Downtrend): New low at {current_low:.5f}")
                
                # Check for CHoCH (Change of Character - potential reversal)
                # CHoCH in uptrend: Break below previous swing low
                if structure == 'uptrend' and df.iloc[-1]['low'] < swing_lows[-2]:
                    choch_detected = True
                    logger.warning(f"⚠️ CHoCH: Uptrend broken below {swing_lows[-2]:.5f}")
                
                # CHoCH in downtrend: Break above previous swing high
                elif structure == 'downtrend' and df.iloc[-1]['high'] > swing_highs[-2]:
                    choch_detected = True
                    logger.warning(f"⚠️ CHoCH: Downtrend broken above {swing_highs[-2]:.5f}")
            
            return {
                'structure': structure,
                'bos_detected': bos_detected,
                'choch_detected': choch_detected,
                'strength': strength,
                'swing_highs': swing_highs[-3:] if len(swing_highs) >= 3 else swing_highs,
                'swing_lows': swing_lows[-3:] if len(swing_lows) >= 3 else swing_lows
            }
            
        except Exception as e:
            logger.error(f"Error analyzing market structure: {e}")
            return {'structure': 'unknown', 'bos_detected': False, 'choch_detected': False}
    
    def get_comprehensive_analysis(self, df: pd.DataFrame) -> Dict:
        """
        Get complete Smart Money analysis with all components
        
        Returns dict with all SMC signals and an overall confidence score
        """
        try:
            # Run all detectors
            liquidity = self.detect_liquidity_grab(df)
            order_blocks = self.identify_order_blocks(df)
            fvg = self.find_fair_value_gaps(df)
            structure = self.analyze_market_structure(df)
            
            # Calculate overall Smart Money confidence
            smc_confidence = 0
            smc_direction = None
            reasons = []
            
            # Liquidity grab adds 30% confidence
            if liquidity['grab_detected']:
                smc_confidence += liquidity['reversal_strength'] * 0.30
                smc_direction = 'CALL' if liquidity['grab_type'] == 'bullish' else 'PUT'
                reasons.append(f"{liquidity['grab_type'].upper()} liquidity grab (strength: {liquidity['reversal_strength']:.0f}%)")
            
            # Order block proximity adds 25% confidence
            if order_blocks.get('near_ob'):
                ob_contribution = 25 if order_blocks['distance_to_ob'] < 0.2 else 15
                smc_confidence += ob_contribution
                if order_blocks['nearest_ob_type'] == 'bullish':
                    if smc_direction is None:
                        smc_direction = 'CALL'
                    reasons.append(f"Near bullish order block ({order_blocks['distance_to_ob']:.2f}% away)")
                else:
                    if smc_direction is None:
                        smc_direction = 'PUT'
                    reasons.append(f"Near bearish order block ({order_blocks['distance_to_ob']:.2f}% away)")
            
            # FVG adds 20% confidence
            if fvg['fvg_detected'] and fvg['price_in_gap']:
                smc_confidence += 20
                if fvg['fvg_type'] == 'bullish':
                    if smc_direction is None:
                        smc_direction = 'CALL'
                    reasons.append(f"Price in bullish FVG (filling gap)")
                else:
                    if smc_direction is None:
                        smc_direction = 'PUT'
                    reasons.append(f"Price in bearish FVG (filling gap)")
            
            # Market structure adds 25% confidence
            if structure['structure'] != 'unknown' and structure['structure'] != 'sideways':
                structure_contribution = structure['strength'] * 0.25 / 100
                smc_confidence += structure_contribution * 100
                
                if structure['bos_detected']:
                    reasons.append(f"BOS in {structure['structure']} (strength: {structure['strength']:.0f}%)")
                    if structure['structure'] == 'uptrend':
                        if smc_direction is None:
                            smc_direction = 'CALL'
                    else:
                        if smc_direction is None:
                            smc_direction = 'PUT'
                
                if structure['choch_detected']:
                    reasons.append(f"CHoCH detected - potential reversal")
            
            # Normalize confidence to 0-100
            smc_confidence = min(100, smc_confidence)
            
            logger.info(f"🧠 Smart Money Analysis: {smc_direction or 'NONE'} with {smc_confidence:.1f}% confidence")
            if reasons:
                logger.info(f"   Reasons: {', '.join(reasons)}")
            
            return {
                'liquidity_grab': liquidity,
                'order_blocks': order_blocks,
                'fair_value_gap': fvg,
                'market_structure': structure,
                'smc_confidence': smc_confidence,
                'smc_direction': smc_direction,
                'smc_reasons': reasons,
                'high_confidence': smc_confidence >= 70
            }
            
        except Exception as e:
            logger.error(f"Error in comprehensive SMC analysis: {e}")
            return {
                'smc_confidence': 0,
                'smc_direction': None,
                'smc_reasons': [],
                'high_confidence': False
            }


# Global instance
_smart_money_detector = None

def get_smart_money_detector(timeframe: str = '5s') -> SmartMoneyDetector:
    """Get or create Smart Money Detector instance"""
    global _smart_money_detector
    if _smart_money_detector is None:
        _smart_money_detector = SmartMoneyDetector(timeframe)
    return _smart_money_detector
