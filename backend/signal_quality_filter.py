"""
Signal Quality Filter - Ultra-Strict Validation for 90%+ Accuracy

PHILOSOPHY: "Better no signal than wrong signal"

Implements multiple layers of quality checks to ensure only the highest
probability signals are generated. Targets 90-95% win rate by aggressive filtering.
"""

import pandas as pd
import numpy as np
from typing import Dict, Optional, List, Tuple
import logging

logger = logging.getLogger(__name__)

class SignalQualityFilter:
    """
    Ultra-strict signal quality validation
    
    REJECTS signals that don't meet institutional-grade standards
    Target: 90-95% accuracy by filtering 80%+ of potential signals
    """
    
    def __init__(self):
        # STRICT thresholds for 90%+ accuracy
        self.min_confidence = 85.0  # Absolute minimum (was 75)
        self.min_indicator_agreement = 0.75  # 75% of indicators must agree
        self.max_spread_ratio = 0.002  # Max 0.2% spread (tight liquidity)
        self.min_order_flow = 0.25  # Minimum OFI for directional conviction
        self.max_volatility_ratio = 0.005  # Max 0.5% volatility (manageable)
        
        # Market condition thresholds
        self.min_volume_ratio = 0.7  # Current volume vs average
        self.max_ranging_ratio = 0.6  # Max ratio of price in middle 60% of range
        
        logger.info("🔒 Signal Quality Filter initialized - STRICT MODE for 90%+ accuracy")
    
    def validate_signal(
        self,
        signal: str,
        confidence: float,
        technical_analysis: Dict,
        features: Dict = None
    ) -> Tuple[bool, float, List[str]]:
        """
        Ultra-strict signal validation
        
        Returns:
            Tuple of (is_valid, adjusted_confidence, rejection_reasons)
        """
        rejection_reasons = []
        confidence_penalties = []
        
        # RULE 1: MINIMUM CONFIDENCE THRESHOLD (CRITICAL)
        if confidence < self.min_confidence:
            rejection_reasons.append(f"❌ Confidence too low: {confidence:.1f}% < {self.min_confidence}%")
            return False, confidence, rejection_reasons
        
        # RULE 2: INDICATOR ALIGNMENT (CRITICAL)
        alignment_score = self._check_indicator_alignment(signal, technical_analysis)
        if alignment_score < self.min_indicator_agreement:
            rejection_reasons.append(f"❌ Poor indicator alignment: {alignment_score:.1%} < {self.min_indicator_agreement:.1%}")
            return False, confidence, rejection_reasons
        
        # RULE 3: LIQUIDITY CHECK (spread)
        if features:
            spread = features.get('spread', 0)
            if spread > self.max_spread_ratio:
                rejection_reasons.append(f"❌ Wide spread (low liquidity): {spread:.4f} > {self.max_spread_ratio:.4f}")
                return False, confidence, rejection_reasons
        
        # RULE 4: ORDER FLOW CONVICTION
        if features:
            ofi = features.get('ofi', 0)
            if signal == 'CALL' and ofi < self.min_order_flow:
                rejection_reasons.append(f"❌ Weak buy pressure: OFI {ofi:.3f} < {self.min_order_flow}")
                return False, confidence, rejection_reasons
            elif signal == 'PUT' and ofi > -self.min_order_flow:
                rejection_reasons.append(f"❌ Weak sell pressure: OFI {ofi:.3f} > -{self.min_order_flow}")
                return False, confidence, rejection_reasons
        
        # RULE 5: VOLATILITY CHECK
        volatility = technical_analysis.get('volatility', 0)
        if volatility > self.max_volatility_ratio:
            rejection_reasons.append(f"⚠️ High volatility: {volatility:.4f} - reducing confidence")
            confidence_penalties.append(-5)
        
        # RULE 6: EXTREME INDICATOR VALUES (better confidence)
        rsi = technical_analysis.get('rsi_2') or technical_analysis.get('rsi_14', 50)
        if signal == 'CALL' and rsi < 20:
            confidence_penalties.append(+3)  # Extreme oversold
        elif signal == 'PUT' and rsi > 80:
            confidence_penalties.append(+3)  # Extreme overbought
        
        # RULE 7: TREND ALIGNMENT
        ema_distance = technical_analysis.get('ema_distance', 0)
        if signal == 'CALL' and ema_distance < -0.002:  # Below EMA
            confidence_penalties.append(+2)  # Upward bounce potential
        elif signal == 'PUT' and ema_distance > 0.002:  # Above EMA
            confidence_penalties.append(+2)  # Downward reversal potential
        
        # RULE 8: SUPPORT/RESISTANCE CONFIRMATION
        if technical_analysis.get('reversal_detected'):
            confidence_penalties.append(+5)  # Strong reversal setup
        
        # Apply confidence adjustments
        final_confidence = confidence + sum(confidence_penalties)
        
        # FINAL CHECK: After adjustments, still above minimum?
        if final_confidence < self.min_confidence:
            rejection_reasons.append(f"❌ Final confidence below minimum: {final_confidence:.1f}%")
            return False, final_confidence, rejection_reasons
        
        # CAP at 98% (never overconfident)
        final_confidence = min(final_confidence, 98.0)
        
        logger.info(f"✅ Signal APPROVED: {signal} at {final_confidence:.1f}% confidence")
        return True, final_confidence, []
    
    def _check_indicator_alignment(self, signal: str, technical_analysis: Dict) -> float:
        """
        Check what % of indicators agree with the signal
        
        Returns: Alignment score (0.0 to 1.0)
        """
        indicators_voting = []
        
        # RSI vote
        rsi = technical_analysis.get('rsi_2') or technical_analysis.get('rsi_14', 50)
        if rsi < 40:
            indicators_voting.append('CALL')
        elif rsi > 60:
            indicators_voting.append('PUT')
        else:
            indicators_voting.append('NEUTRAL')
        
        # EMA trend vote
        ema_distance = technical_analysis.get('ema_distance', 0)
        if ema_distance > 0.001:
            indicators_voting.append('PUT')  # Above EMA, pullback expected
        elif ema_distance < -0.001:
            indicators_voting.append('CALL')  # Below EMA, bounce expected
        else:
            indicators_voting.append('NEUTRAL')
        
        # Stochastic vote
        stoch = technical_analysis.get('stoch_k', 50)
        if stoch < 30:
            indicators_voting.append('CALL')
        elif stoch > 70:
            indicators_voting.append('PUT')
        else:
            indicators_voting.append('NEUTRAL')
        
        # Bollinger Band vote
        bb_position = technical_analysis.get('bb_position', 0.5)
        if bb_position < 0.2:
            indicators_voting.append('CALL')  # Near lower band
        elif bb_position > 0.8:
            indicators_voting.append('PUT')  # Near upper band
        else:
            indicators_voting.append('NEUTRAL')
        
        # MACD vote (if available)
        macd_hist = technical_analysis.get('macd_histogram')
        if macd_hist is not None:
            if macd_hist > 0:
                indicators_voting.append('CALL')
            elif macd_hist < 0:
                indicators_voting.append('PUT')
            else:
                indicators_voting.append('NEUTRAL')
        
        # Count agreements
        agreements = sum(1 for vote in indicators_voting if vote == signal)
        total_votes = len(indicators_voting)
        
        if total_votes == 0:
            return 0.5
        
        alignment_score = agreements / total_votes
        logger.debug(f"Indicator alignment: {agreements}/{total_votes} = {alignment_score:.1%}")
        
        return alignment_score
    
    def check_market_conditions(self, df: pd.DataFrame) -> Tuple[bool, str]:
        """
        Check if market conditions are suitable for trading
        
        Returns:
            Tuple of (is_suitable, reason)
        """
        try:
            if len(df) < 30:
                return False, "Insufficient data for market analysis"
            
            recent = df.tail(30)
            close = recent['close']
            
            # Check for ranging market (price stuck in middle of range)
            price_range = close.max() - close.min()
            if price_range == 0:
                return False, "No price movement (flat market)"
            
            current_price = close.iloc[-1]
            position_in_range = (current_price - close.min()) / price_range
            
            # If price is stuck in middle 60% of range, likely ranging
            if 0.2 < position_in_range < 0.8:
                # Check if price has been ranging
                std_dev = close.std()
                mean_price = close.mean()
                cv = std_dev / mean_price if mean_price > 0 else 0
                
                if cv < 0.002:  # Very low coefficient of variation
                    return False, "Ranging market detected (choppy conditions)"
            
            # Check volume (if available)
            if 'volume' in recent.columns:
                avg_volume = recent['volume'].mean()
                current_volume = recent['volume'].iloc[-5:].mean()
                volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1
                
                if volume_ratio < self.min_volume_ratio:
                    return False, f"Low volume: {volume_ratio:.1%} of average"
            
            # Passed all checks
            return True, "Market conditions suitable"
            
        except Exception as e:
            logger.error(f"Error checking market conditions: {e}")
            return False, f"Error analyzing market: {str(e)}"

# Create singleton instance
signal_quality_filter = SignalQualityFilter()
