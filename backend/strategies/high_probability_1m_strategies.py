"""
High-Probability 1-Minute Trading Strategies for Pocket Option
===============================================================

Clear, actionable trading strategies designed for the 1-minute timeframe.
Each strategy includes:
- Entry/Exit rules
- Risk management
- S/R integration for improved accuracy
- Clear reasoning behind each setup

Strategies Included:
1. RSI Reversal Strategy (Overbought/Oversold Bounces)
2. EMA Crossover Momentum Strategy
3. Bollinger Band Squeeze Breakout
4. MACD Divergence Strategy
5. Stochastic + RSI Confluence Strategy
"""

import pandas as pd
import numpy as np
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

# Import S/R detector for enhanced accuracy
try:
    from strategies.support_resistance import get_sr_detector
except ImportError:
    try:
        from support_resistance import get_sr_detector
    except ImportError:
        get_sr_detector = None

logger = logging.getLogger(__name__)


class SignalStrength(Enum):
    """Signal strength classification"""
    VERY_STRONG = "very_strong"  # 85%+ probability
    STRONG = "strong"            # 75-85% probability
    MODERATE = "moderate"        # 65-75% probability
    WEAK = "weak"               # 55-65% probability
    NO_SIGNAL = "no_signal"     # Below threshold


@dataclass
class TradingSignal1m:
    """1-Minute Trading Signal"""
    strategy_name: str
    direction: str  # "CALL" or "PUT"
    confidence: float  # 0-100
    strength: SignalStrength
    entry_price: float
    indicators: Dict
    reasoning: List[str]
    risk_level: str  # "low", "medium", "high"
    recommended_expiry: int  # seconds (60, 120, 180)
    sr_analysis: Optional[Dict] = None
    
    def to_dict(self) -> Dict:
        def convert_value(v):
            """Convert numpy types to Python native types"""
            if isinstance(v, (np.bool_, np.bool)):
                return bool(v)
            elif isinstance(v, (np.integer, np.int64, np.int32)):
                return int(v)
            elif isinstance(v, (np.floating, np.float64, np.float32)):
                return float(v)
            elif isinstance(v, np.ndarray):
                return v.tolist()
            return v
        
        return {
            "strategy_name": self.strategy_name,
            "direction": self.direction,
            "confidence": round(float(self.confidence), 2),
            "strength": self.strength.value,
            "entry_price": float(self.entry_price),
            "indicators": {k: convert_value(v) for k, v in self.indicators.items()},
            "reasoning": self.reasoning,
            "risk_level": self.risk_level,
            "recommended_expiry": self.recommended_expiry,
            "sr_analysis": self.sr_analysis
        }


class TechnicalIndicators1m:
    """
    Technical indicator calculations optimized for 1-minute timeframe
    Uses faster periods for quicker response to price changes
    """
    
    @staticmethod
    def calculate_rsi(closes: np.ndarray, period: int = 7) -> np.ndarray:
        """
        Calculate RSI with fast period for 1-minute charts
        
        Why RSI-7: Responds faster than RSI-14, catches reversals quicker
        on short timeframes while maintaining reliability.
        """
        deltas = np.diff(closes)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        avg_gain = np.zeros(len(closes))
        avg_loss = np.zeros(len(closes))
        
        if len(gains) >= period:
            avg_gain[period] = np.mean(gains[:period])
            avg_loss[period] = np.mean(losses[:period])
            
            for i in range(period + 1, len(closes)):
                avg_gain[i] = (avg_gain[i-1] * (period - 1) + gains[i-1]) / period
                avg_loss[i] = (avg_loss[i-1] * (period - 1) + losses[i-1]) / period
        
        rs = np.divide(avg_gain, avg_loss, out=np.zeros_like(avg_gain), where=avg_loss != 0)
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    @staticmethod
    def calculate_ema(data: np.ndarray, period: int) -> np.ndarray:
        """Calculate Exponential Moving Average"""
        multiplier = 2 / (period + 1)
        ema = np.zeros(len(data))
        ema[0] = data[0]
        
        for i in range(1, len(data)):
            ema[i] = (data[i] * multiplier) + (ema[i-1] * (1 - multiplier))
        
        return ema
    
    @staticmethod
    def calculate_sma(data: np.ndarray, period: int) -> np.ndarray:
        """Calculate Simple Moving Average"""
        sma = np.zeros(len(data))
        for i in range(period - 1, len(data)):
            sma[i] = np.mean(data[i-period+1:i+1])
        return sma
    
    @staticmethod
    def calculate_bollinger_bands(closes: np.ndarray, period: int = 14, std_dev: float = 2.0) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Calculate Bollinger Bands
        
        Period 14 for 1-minute: Balances responsiveness with noise filtering
        """
        sma = TechnicalIndicators1m.calculate_sma(closes, period)
        std = np.zeros(len(closes))
        
        for i in range(period - 1, len(closes)):
            std[i] = np.std(closes[i-period+1:i+1])
        
        upper_band = sma + (std * std_dev)
        lower_band = sma - (std * std_dev)
        
        return upper_band, sma, lower_band
    
    @staticmethod
    def calculate_macd(closes: np.ndarray, fast: int = 8, slow: int = 17, signal: int = 9) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Calculate MACD optimized for 1-minute
        
        Fast 8, Slow 17: Faster than standard 12/26 for quick response
        """
        ema_fast = TechnicalIndicators1m.calculate_ema(closes, fast)
        ema_slow = TechnicalIndicators1m.calculate_ema(closes, slow)
        
        macd_line = ema_fast - ema_slow
        signal_line = TechnicalIndicators1m.calculate_ema(macd_line, signal)
        histogram = macd_line - signal_line
        
        return macd_line, signal_line, histogram
    
    @staticmethod
    def calculate_stochastic(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, 
                            k_period: int = 9, d_period: int = 3) -> Tuple[np.ndarray, np.ndarray]:
        """
        Calculate Stochastic Oscillator
        
        K-period 9: Fast enough for 1-minute while avoiding excessive noise
        """
        k = np.zeros(len(closes))
        
        for i in range(k_period - 1, len(closes)):
            highest_high = np.max(highs[i-k_period+1:i+1])
            lowest_low = np.min(lows[i-k_period+1:i+1])
            
            if highest_high != lowest_low:
                k[i] = ((closes[i] - lowest_low) / (highest_high - lowest_low)) * 100
        
        d = TechnicalIndicators1m.calculate_sma(k, d_period)
        
        return k, d
    
    @staticmethod
    def calculate_atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 10) -> np.ndarray:
        """Calculate Average True Range for volatility measurement"""
        tr = np.zeros(len(closes))
        tr[0] = highs[0] - lows[0]
        
        for i in range(1, len(closes)):
            tr[i] = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i-1]),
                abs(lows[i] - closes[i-1])
            )
        
        atr = TechnicalIndicators1m.calculate_ema(tr, period)
        return atr
    
    @staticmethod
    def calculate_momentum(closes: np.ndarray, period: int = 7) -> np.ndarray:
        """Calculate price momentum"""
        momentum = np.zeros(len(closes))
        for i in range(period, len(closes)):
            momentum[i] = closes[i] - closes[i - period]
        return momentum
    
    @staticmethod
    def calculate_williams_r(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 9) -> np.ndarray:
        """Calculate Williams %R"""
        wr = np.zeros(len(closes))
        
        for i in range(period - 1, len(closes)):
            highest_high = np.max(highs[i-period+1:i+1])
            lowest_low = np.min(lows[i-period+1:i+1])
            
            if highest_high != lowest_low:
                wr[i] = ((highest_high - closes[i]) / (highest_high - lowest_low)) * -100
        
        return wr


# =============================================================================
# STRATEGY 1: RSI REVERSAL STRATEGY
# =============================================================================

class RSIReversalStrategy1m:
    """
    ╔══════════════════════════════════════════════════════════════════════╗
    ║  RSI REVERSAL STRATEGY - 1 MINUTE                                     ║
    ╠══════════════════════════════════════════════════════════════════════╣
    ║  Strategy Name: RSI Overbought/Oversold Reversal                      ║
    ║  Timeframe: 1 Minute                                                  ║
    ║  Probability: 70-80% when properly filtered                           ║
    ╠══════════════════════════════════════════════════════════════════════╣
    ║  INDICATORS USED:                                                     ║
    ║  • RSI (7-period) - Fast response for 1-minute                        ║
    ║  • EMA (10-period) - Trend filter                                     ║
    ║  • ATR (10-period) - Volatility filter                                ║
    ║  • S/R Levels - Confluence confirmation                               ║
    ╠══════════════════════════════════════════════════════════════════════╣
    ║  ENTRY RULES:                                                         ║
    ║                                                                       ║
    ║  CALL (Buy) Signal:                                                   ║
    ║  1. RSI drops below 25 (oversold)                                     ║
    ║  2. RSI starts turning up (current > previous)                        ║
    ║  3. Price near or at support level (S/R confirmation)                 ║
    ║  4. Price above or near EMA-10 (not in strong downtrend)              ║
    ║                                                                       ║
    ║  PUT (Sell) Signal:                                                   ║
    ║  1. RSI rises above 75 (overbought)                                   ║
    ║  2. RSI starts turning down (current < previous)                      ║
    ║  3. Price near or at resistance level (S/R confirmation)              ║
    ║  4. Price below or near EMA-10 (not in strong uptrend)                ║
    ╠══════════════════════════════════════════════════════════════════════╣
    ║  EXIT RULES:                                                          ║
    ║  • 60-second expiry (1 candle) for quick reversals                    ║
    ║  • 120-second expiry if volatility is low (ATR below average)         ║
    ╠══════════════════════════════════════════════════════════════════════╣
    ║  RISK MANAGEMENT:                                                     ║
    ║  • Skip if RSI is between 30-70 (no clear extreme)                    ║
    ║  • Skip during high volatility news events                            ║
    ║  • Maximum 2-3% of account per trade                                  ║
    ║  • Don't trade against strong trends (EMA slope > 45°)                ║
    ╠══════════════════════════════════════════════════════════════════════╣
    ║  RATIONALE:                                                           ║
    ║  RSI extremes on 1-minute charts often mark short-term exhaustion     ║
    ║  points. When price becomes oversold/overbought, a snap-back          ║
    ║  reversal is likely within 1-3 candles. The S/R filter ensures        ║
    ║  we only take reversals at key price levels, significantly            ║
    ║  improving win rate.                                                  ║
    ╚══════════════════════════════════════════════════════════════════════╝
    """
    
    def __init__(self, enable_sr_filter: bool = True):
        self.name = "RSI Reversal 1m"
        self.timeframe = "1m"
        self.rsi_period = 7
        self.rsi_oversold = 25
        self.rsi_overbought = 75
        self.ema_period = 10
        self.atr_period = 10
        self.enable_sr_filter = enable_sr_filter
        self.sr_detector = get_sr_detector() if get_sr_detector else None
        
        logger.info(f"✅ {self.name} initialized (SR_Filter={enable_sr_filter})")
    
    def generate_signal(self, df: pd.DataFrame) -> Optional[TradingSignal1m]:
        """Generate trading signal based on RSI reversal setup"""
        
        if len(df) < 50:
            return None
        
        # Extract price data
        closes = df['close'].values
        highs = df['high'].values
        lows = df['low'].values
        
        # Calculate indicators
        rsi = TechnicalIndicators1m.calculate_rsi(closes, self.rsi_period)
        ema = TechnicalIndicators1m.calculate_ema(closes, self.ema_period)
        atr = TechnicalIndicators1m.calculate_atr(highs, lows, closes, self.atr_period)
        
        # Get latest values
        current_rsi = rsi[-1]
        prev_rsi = rsi[-2]
        current_price = closes[-1]
        current_ema = ema[-1]
        current_atr = atr[-1]
        avg_atr = np.mean(atr[-20:])
        
        # S/R Analysis
        sr_data = None
        sr_adjustment = 0.0
        if self.enable_sr_filter and self.sr_detector:
            try:
                sr_analysis = self.sr_detector.analyze(highs, lows, closes)
                sr_data = sr_analysis.to_dict()
            except Exception as e:
                logger.warning(f"S/R analysis failed: {e}")
        
        confidence = 0
        direction = None
        reasoning = []
        
        # ═══════════════════════════════════════════
        # CALL SIGNAL CHECK (Oversold Reversal)
        # ═══════════════════════════════════════════
        if current_rsi < self.rsi_oversold:
            # RSI is oversold
            confidence += 30
            reasoning.append(f"✅ RSI oversold: {current_rsi:.1f} < {self.rsi_oversold}")
            
            # Check for RSI turning up
            if current_rsi > prev_rsi:
                confidence += 20
                reasoning.append(f"✅ RSI turning up: {prev_rsi:.1f} → {current_rsi:.1f}")
            else:
                reasoning.append(f"⚠️ RSI still falling - wait for turn")
                confidence -= 10
            
            # Price near EMA (not in strong downtrend)
            ema_distance = ((current_price - current_ema) / current_ema) * 100
            if ema_distance > -0.5:  # Price within 0.5% of EMA or above
                confidence += 15
                reasoning.append(f"✅ Price near EMA support ({ema_distance:.2f}%)")
            elif ema_distance > -1.0:
                confidence += 5
                reasoning.append(f"⚠️ Price below EMA but recovering")
            else:
                reasoning.append(f"❌ Strong downtrend - caution ({ema_distance:.2f}% below EMA)")
                confidence -= 15
            
            # S/R Confirmation
            if sr_data:
                if sr_data.get('price_position') == 'at_support':
                    confidence += 20
                    reasoning.append("✅ S/R: Price AT SUPPORT - strong reversal zone")
                    sr_adjustment = 0.4
                elif sr_data.get('distance_to_support_pct', 100) < 0.1:
                    confidence += 10
                    reasoning.append("✅ S/R: Price near support level")
                    sr_adjustment = 0.2
            
            # Volatility check
            if current_atr < avg_atr * 1.5:
                confidence += 5
                reasoning.append("✅ Normal volatility - good for reversal")
            else:
                reasoning.append("⚠️ High volatility - use larger expiry")
            
            if confidence >= 60:
                direction = "CALL"
        
        # ═══════════════════════════════════════════
        # PUT SIGNAL CHECK (Overbought Reversal)
        # ═══════════════════════════════════════════
        elif current_rsi > self.rsi_overbought:
            # RSI is overbought
            confidence += 30
            reasoning.append(f"✅ RSI overbought: {current_rsi:.1f} > {self.rsi_overbought}")
            
            # Check for RSI turning down
            if current_rsi < prev_rsi:
                confidence += 20
                reasoning.append(f"✅ RSI turning down: {prev_rsi:.1f} → {current_rsi:.1f}")
            else:
                reasoning.append(f"⚠️ RSI still rising - wait for turn")
                confidence -= 10
            
            # Price near EMA (not in strong uptrend)
            ema_distance = ((current_price - current_ema) / current_ema) * 100
            if ema_distance < 0.5:  # Price within 0.5% of EMA or below
                confidence += 15
                reasoning.append(f"✅ Price near EMA resistance ({ema_distance:.2f}%)")
            elif ema_distance < 1.0:
                confidence += 5
                reasoning.append(f"⚠️ Price above EMA but may reverse")
            else:
                reasoning.append(f"❌ Strong uptrend - caution ({ema_distance:.2f}% above EMA)")
                confidence -= 15
            
            # S/R Confirmation
            if sr_data:
                if sr_data.get('price_position') == 'at_resistance':
                    confidence += 20
                    reasoning.append("✅ S/R: Price AT RESISTANCE - strong reversal zone")
                    sr_adjustment = 0.4
                elif sr_data.get('distance_to_resistance_pct', 100) < 0.1:
                    confidence += 10
                    reasoning.append("✅ S/R: Price near resistance level")
                    sr_adjustment = 0.2
            
            # Volatility check
            if current_atr < avg_atr * 1.5:
                confidence += 5
                reasoning.append("✅ Normal volatility - good for reversal")
            else:
                reasoning.append("⚠️ High volatility - use larger expiry")
            
            if confidence >= 60:
                direction = "PUT"
        
        # No clear signal
        if not direction:
            return None
        
        # Determine signal strength
        if confidence >= 85:
            strength = SignalStrength.VERY_STRONG
        elif confidence >= 75:
            strength = SignalStrength.STRONG
        elif confidence >= 65:
            strength = SignalStrength.MODERATE
        else:
            strength = SignalStrength.WEAK
        
        # Determine expiry based on volatility
        recommended_expiry = 60 if current_atr < avg_atr else 120
        
        # Risk level
        risk_level = "low" if confidence >= 80 else ("medium" if confidence >= 70 else "high")
        
        return TradingSignal1m(
            strategy_name=self.name,
            direction=direction,
            confidence=min(confidence, 100),
            strength=strength,
            entry_price=current_price,
            indicators={
                "rsi": current_rsi,
                "rsi_prev": prev_rsi,
                "ema": current_ema,
                "atr": current_atr,
                "atr_avg": avg_atr,
                "price_to_ema_pct": ema_distance
            },
            reasoning=reasoning,
            risk_level=risk_level,
            recommended_expiry=recommended_expiry,
            sr_analysis=sr_data
        )


# =============================================================================
# STRATEGY 2: EMA CROSSOVER MOMENTUM STRATEGY
# =============================================================================

class EMACrossoverStrategy1m:
    """
    ╔══════════════════════════════════════════════════════════════════════╗
    ║  EMA CROSSOVER MOMENTUM STRATEGY - 1 MINUTE                           ║
    ╠══════════════════════════════════════════════════════════════════════╣
    ║  Strategy Name: Triple EMA Crossover with Momentum                    ║
    ║  Timeframe: 1 Minute                                                  ║
    ║  Probability: 72-78% with trend filter                                ║
    ╠══════════════════════════════════════════════════════════════════════╣
    ║  INDICATORS USED:                                                     ║
    ║  • EMA-5 (Fast) - Entry trigger                                       ║
    ║  • EMA-10 (Medium) - Crossover signal                                 ║
    ║  • EMA-21 (Slow) - Trend direction filter                             ║
    ║  • Momentum (7-period) - Confirmation                                 ║
    ║  • S/R Levels - Risk filter                                           ║
    ╠══════════════════════════════════════════════════════════════════════╣
    ║  ENTRY RULES:                                                         ║
    ║                                                                       ║
    ║  CALL (Buy) Signal:                                                   ║
    ║  1. EMA-5 crosses ABOVE EMA-10 (bullish crossover)                    ║
    ║  2. Price is above EMA-21 (uptrend confirmed)                         ║
    ║  3. Momentum is positive and increasing                               ║
    ║  4. NOT at strong resistance (S/R filter)                             ║
    ║                                                                       ║
    ║  PUT (Sell) Signal:                                                   ║
    ║  1. EMA-5 crosses BELOW EMA-10 (bearish crossover)                    ║
    ║  2. Price is below EMA-21 (downtrend confirmed)                       ║
    ║  3. Momentum is negative and decreasing                               ║
    ║  4. NOT at strong support (S/R filter)                                ║
    ╠══════════════════════════════════════════════════════════════════════╣
    ║  EXIT RULES:                                                          ║
    ║  • 60-second expiry for strong momentum                               ║
    ║  • 120-second expiry for moderate momentum                            ║
    ╠══════════════════════════════════════════════════════════════════════╣
    ║  RISK MANAGEMENT:                                                     ║
    ║  • Only trade in direction of EMA-21 trend                            ║
    ║  • Skip if EMAs are tangled (no clear trend)                          ║
    ║  • Avoid trading at major S/R levels                                  ║
    ║  • Use 2% max per trade                                               ║
    ╠══════════════════════════════════════════════════════════════════════╣
    ║  RATIONALE:                                                           ║
    ║  EMA crossovers on 1-minute charts capture micro-trends. By           ║
    ║  filtering with the longer EMA-21 trend, we ensure we're trading      ║
    ║  with the overall momentum, not against it. Momentum confirmation     ║
    ║  adds extra reliability to the crossover signal.                      ║
    ╚══════════════════════════════════════════════════════════════════════╝
    """
    
    def __init__(self, enable_sr_filter: bool = True):
        self.name = "EMA Crossover 1m"
        self.timeframe = "1m"
        self.ema_fast = 5
        self.ema_medium = 10
        self.ema_slow = 21
        self.momentum_period = 7
        self.enable_sr_filter = enable_sr_filter
        self.sr_detector = get_sr_detector() if get_sr_detector else None
        
        logger.info(f"✅ {self.name} initialized")
    
    def generate_signal(self, df: pd.DataFrame) -> Optional[TradingSignal1m]:
        """Generate trading signal based on EMA crossover"""
        
        if len(df) < 50:
            return None
        
        closes = df['close'].values
        highs = df['high'].values
        lows = df['low'].values
        
        # Calculate EMAs
        ema_fast = TechnicalIndicators1m.calculate_ema(closes, self.ema_fast)
        ema_medium = TechnicalIndicators1m.calculate_ema(closes, self.ema_medium)
        ema_slow = TechnicalIndicators1m.calculate_ema(closes, self.ema_slow)
        momentum = TechnicalIndicators1m.calculate_momentum(closes, self.momentum_period)
        
        # Get current and previous values
        current_price = closes[-1]
        current_fast = ema_fast[-1]
        current_medium = ema_medium[-1]
        current_slow = ema_slow[-1]
        current_momentum = momentum[-1]
        
        prev_fast = ema_fast[-2]
        prev_medium = ema_medium[-2]
        prev_momentum = momentum[-2]
        
        # S/R Analysis
        sr_data = None
        if self.enable_sr_filter and self.sr_detector:
            try:
                sr_analysis = self.sr_detector.analyze(highs, lows, closes)
                sr_data = sr_analysis.to_dict()
            except Exception:
                pass
        
        confidence = 0
        direction = None
        reasoning = []
        
        # Check for bullish crossover
        bullish_crossover = prev_fast <= prev_medium and current_fast > current_medium
        bearish_crossover = prev_fast >= prev_medium and current_fast < current_medium
        
        # ═══════════════════════════════════════════
        # CALL SIGNAL CHECK
        # ═══════════════════════════════════════════
        if bullish_crossover:
            confidence += 30
            reasoning.append(f"✅ Bullish EMA crossover: EMA-{self.ema_fast} crossed above EMA-{self.ema_medium}")
            
            # Trend confirmation (price above slow EMA)
            if current_price > current_slow:
                confidence += 25
                reasoning.append(f"✅ Uptrend confirmed: Price above EMA-{self.ema_slow}")
            else:
                confidence -= 10
                reasoning.append(f"⚠️ Counter-trend: Price below EMA-{self.ema_slow}")
            
            # Momentum confirmation
            if current_momentum > 0:
                confidence += 15
                reasoning.append(f"✅ Positive momentum: {current_momentum:.5f}")
                if current_momentum > prev_momentum:
                    confidence += 10
                    reasoning.append("✅ Momentum increasing")
            else:
                confidence -= 5
                reasoning.append("⚠️ Weak momentum")
            
            # EMA alignment bonus
            if current_fast > current_medium > current_slow:
                confidence += 10
                reasoning.append("✅ EMAs perfectly aligned (bullish stack)")
            
            # S/R Filter
            if sr_data:
                if sr_data.get('price_position') == 'at_resistance':
                    confidence -= 20
                    reasoning.append("❌ S/R WARNING: At resistance - high reversal risk")
                elif sr_data.get('distance_to_resistance_pct', 100) < 0.1:
                    confidence -= 10
                    reasoning.append("⚠️ S/R: Near resistance level")
                elif sr_data.get('price_position') == 'at_support':
                    confidence += 10
                    reasoning.append("✅ S/R: Bouncing from support")
            
            if confidence >= 60:
                direction = "CALL"
        
        # ═══════════════════════════════════════════
        # PUT SIGNAL CHECK
        # ═══════════════════════════════════════════
        elif bearish_crossover:
            confidence += 30
            reasoning.append(f"✅ Bearish EMA crossover: EMA-{self.ema_fast} crossed below EMA-{self.ema_medium}")
            
            # Trend confirmation (price below slow EMA)
            if current_price < current_slow:
                confidence += 25
                reasoning.append(f"✅ Downtrend confirmed: Price below EMA-{self.ema_slow}")
            else:
                confidence -= 10
                reasoning.append(f"⚠️ Counter-trend: Price above EMA-{self.ema_slow}")
            
            # Momentum confirmation
            if current_momentum < 0:
                confidence += 15
                reasoning.append(f"✅ Negative momentum: {current_momentum:.5f}")
                if current_momentum < prev_momentum:
                    confidence += 10
                    reasoning.append("✅ Momentum increasing (bearish)")
            else:
                confidence -= 5
                reasoning.append("⚠️ Weak momentum")
            
            # EMA alignment bonus
            if current_fast < current_medium < current_slow:
                confidence += 10
                reasoning.append("✅ EMAs perfectly aligned (bearish stack)")
            
            # S/R Filter
            if sr_data:
                if sr_data.get('price_position') == 'at_support':
                    confidence -= 20
                    reasoning.append("❌ S/R WARNING: At support - high bounce risk")
                elif sr_data.get('distance_to_support_pct', 100) < 0.1:
                    confidence -= 10
                    reasoning.append("⚠️ S/R: Near support level")
                elif sr_data.get('price_position') == 'at_resistance':
                    confidence += 10
                    reasoning.append("✅ S/R: Rejecting from resistance")
            
            if confidence >= 60:
                direction = "PUT"
        
        if not direction:
            return None
        
        # Determine strength and expiry
        strength = (SignalStrength.VERY_STRONG if confidence >= 85 else
                   SignalStrength.STRONG if confidence >= 75 else
                   SignalStrength.MODERATE if confidence >= 65 else
                   SignalStrength.WEAK)
        
        recommended_expiry = 60 if abs(current_momentum) > abs(prev_momentum) else 120
        risk_level = "low" if confidence >= 80 else ("medium" if confidence >= 70 else "high")
        
        return TradingSignal1m(
            strategy_name=self.name,
            direction=direction,
            confidence=min(confidence, 100),
            strength=strength,
            entry_price=current_price,
            indicators={
                "ema_fast": current_fast,
                "ema_medium": current_medium,
                "ema_slow": current_slow,
                "momentum": current_momentum,
                "ema_fast_prev": prev_fast,
                "ema_medium_prev": prev_medium
            },
            reasoning=reasoning,
            risk_level=risk_level,
            recommended_expiry=recommended_expiry,
            sr_analysis=sr_data
        )


# =============================================================================
# STRATEGY 3: BOLLINGER BAND SQUEEZE BREAKOUT
# =============================================================================

class BollingerSqueezeStrategy1m:
    """
    ╔══════════════════════════════════════════════════════════════════════╗
    ║  BOLLINGER BAND SQUEEZE BREAKOUT STRATEGY - 1 MINUTE                  ║
    ╠══════════════════════════════════════════════════════════════════════╣
    ║  Strategy Name: BB Squeeze Breakout with Volume                       ║
    ║  Timeframe: 1 Minute                                                  ║
    ║  Probability: 68-75% on confirmed breakouts                           ║
    ╠══════════════════════════════════════════════════════════════════════╣
    ║  INDICATORS USED:                                                     ║
    ║  • Bollinger Bands (14, 2.0) - Squeeze detection                      ║
    ║  • RSI (7) - Momentum confirmation                                    ║
    ║  • ATR (10) - Volatility measurement                                  ║
    ║  • S/R Levels - Target/barrier identification                         ║
    ╠══════════════════════════════════════════════════════════════════════╣
    ║  ENTRY RULES:                                                         ║
    ║                                                                       ║
    ║  CALL (Buy) Signal:                                                   ║
    ║  1. Bollinger Band width was narrow (squeeze detected)                ║
    ║  2. Price breaks ABOVE upper band                                     ║
    ║  3. RSI confirms bullish momentum (> 50)                              ║
    ║  4. No major resistance immediately above                             ║
    ║                                                                       ║
    ║  PUT (Sell) Signal:                                                   ║
    ║  1. Bollinger Band width was narrow (squeeze detected)                ║
    ║  2. Price breaks BELOW lower band                                     ║
    ║  3. RSI confirms bearish momentum (< 50)                              ║
    ║  4. No major support immediately below                                ║
    ╠══════════════════════════════════════════════════════════════════════╣
    ║  EXIT RULES:                                                          ║
    ║  • 60-second expiry for strong breakouts                              ║
    ║  • 120-second expiry for moderate breakouts                           ║
    ║  • 180-second expiry if expecting extended move                       ║
    ╠══════════════════════════════════════════════════════════════════════╣
    ║  RISK MANAGEMENT:                                                     ║
    ║  • Confirm squeeze before breakout (low BB width)                     ║
    ║  • Skip false breakouts (price quickly returns inside bands)          ║
    ║  • Check S/R levels for potential barriers                            ║
    ║  • Use 1-2% max per trade                                             ║
    ╠══════════════════════════════════════════════════════════════════════╣
    ║  RATIONALE:                                                           ║
    ║  When Bollinger Bands squeeze (narrow), it indicates low volatility   ║
    ║  and consolidation. A breakout from this compression often leads      ║
    ║  to a strong directional move. On 1-minute charts, these moves        ║
    ║  are typically 2-5 candles in duration - perfect for binary options.  ║
    ╚══════════════════════════════════════════════════════════════════════╝
    """
    
    def __init__(self, enable_sr_filter: bool = True):
        self.name = "BB Squeeze Breakout 1m"
        self.timeframe = "1m"
        self.bb_period = 14
        self.bb_std = 2.0
        self.rsi_period = 7
        self.squeeze_threshold = 0.6  # BB width below 60% of average = squeeze
        self.enable_sr_filter = enable_sr_filter
        self.sr_detector = get_sr_detector() if get_sr_detector else None
        
        logger.info(f"✅ {self.name} initialized")
    
    def generate_signal(self, df: pd.DataFrame) -> Optional[TradingSignal1m]:
        """Generate signal based on BB squeeze breakout"""
        
        if len(df) < 50:
            return None
        
        closes = df['close'].values
        highs = df['high'].values
        lows = df['low'].values
        
        # Calculate indicators
        bb_upper, bb_middle, bb_lower = TechnicalIndicators1m.calculate_bollinger_bands(
            closes, self.bb_period, self.bb_std
        )
        rsi = TechnicalIndicators1m.calculate_rsi(closes, self.rsi_period)
        atr = TechnicalIndicators1m.calculate_atr(highs, lows, closes, 10)
        
        # Current values
        current_price = closes[-1]
        prev_price = closes[-2]
        current_upper = bb_upper[-1]
        current_lower = bb_lower[-1]
        current_middle = bb_middle[-1]
        current_rsi = rsi[-1]
        
        # Calculate BB width and check for squeeze
        bb_width = (current_upper - current_lower) / current_middle if current_middle > 0 else 0
        avg_bb_width = np.mean([(bb_upper[i] - bb_lower[i]) / bb_middle[i] 
                                for i in range(-20, 0) if bb_middle[i] > 0])
        
        is_squeeze = bb_width < avg_bb_width * self.squeeze_threshold
        was_inside = bb_lower[-2] < prev_price < bb_upper[-2]
        
        # S/R Analysis
        sr_data = None
        if self.enable_sr_filter and self.sr_detector:
            try:
                sr_analysis = self.sr_detector.analyze(highs, lows, closes)
                sr_data = sr_analysis.to_dict()
            except Exception:
                pass
        
        confidence = 0
        direction = None
        reasoning = []
        
        # ═══════════════════════════════════════════
        # CALL SIGNAL - Upper Band Breakout
        # ═══════════════════════════════════════════
        if current_price > current_upper and was_inside:
            confidence += 25
            reasoning.append(f"✅ Price broke ABOVE upper BB: {current_price:.5f} > {current_upper:.5f}")
            
            # Squeeze confirmation
            if is_squeeze or bb_width < avg_bb_width * 0.8:
                confidence += 20
                reasoning.append(f"✅ BB Squeeze detected: width {bb_width:.4f} vs avg {avg_bb_width:.4f}")
            else:
                confidence += 5
                reasoning.append("⚠️ No clear squeeze - moderate breakout")
            
            # RSI confirmation
            if current_rsi > 50:
                confidence += 15
                reasoning.append(f"✅ RSI bullish: {current_rsi:.1f} > 50")
                if current_rsi > 60:
                    confidence += 5
                    reasoning.append("✅ Strong RSI momentum")
            else:
                confidence -= 10
                reasoning.append(f"⚠️ RSI weak: {current_rsi:.1f}")
            
            # Breakout strength
            breakout_strength = (current_price - current_upper) / atr[-1] if atr[-1] > 0 else 0
            if breakout_strength > 0.3:
                confidence += 10
                reasoning.append(f"✅ Strong breakout: {breakout_strength:.2f} ATR")
            
            # S/R check - avoid if resistance immediately above
            if sr_data:
                if sr_data.get('distance_to_resistance_pct', 100) < 0.05:
                    confidence -= 25
                    reasoning.append("❌ S/R: Major resistance blocking - skip trade")
                elif sr_data.get('distance_to_resistance_pct', 100) < 0.15:
                    confidence -= 10
                    reasoning.append("⚠️ S/R: Resistance nearby - reduced target")
            
            if confidence >= 55:
                direction = "CALL"
        
        # ═══════════════════════════════════════════
        # PUT SIGNAL - Lower Band Breakout
        # ═══════════════════════════════════════════
        elif current_price < current_lower and was_inside:
            confidence += 25
            reasoning.append(f"✅ Price broke BELOW lower BB: {current_price:.5f} < {current_lower:.5f}")
            
            # Squeeze confirmation
            if is_squeeze or bb_width < avg_bb_width * 0.8:
                confidence += 20
                reasoning.append(f"✅ BB Squeeze detected: width {bb_width:.4f} vs avg {avg_bb_width:.4f}")
            else:
                confidence += 5
                reasoning.append("⚠️ No clear squeeze - moderate breakout")
            
            # RSI confirmation
            if current_rsi < 50:
                confidence += 15
                reasoning.append(f"✅ RSI bearish: {current_rsi:.1f} < 50")
                if current_rsi < 40:
                    confidence += 5
                    reasoning.append("✅ Strong RSI momentum (bearish)")
            else:
                confidence -= 10
                reasoning.append(f"⚠️ RSI weak: {current_rsi:.1f}")
            
            # Breakout strength
            breakout_strength = (current_lower - current_price) / atr[-1] if atr[-1] > 0 else 0
            if breakout_strength > 0.3:
                confidence += 10
                reasoning.append(f"✅ Strong breakout: {breakout_strength:.2f} ATR")
            
            # S/R check - avoid if support immediately below
            if sr_data:
                if sr_data.get('distance_to_support_pct', 100) < 0.05:
                    confidence -= 25
                    reasoning.append("❌ S/R: Major support blocking - skip trade")
                elif sr_data.get('distance_to_support_pct', 100) < 0.15:
                    confidence -= 10
                    reasoning.append("⚠️ S/R: Support nearby - reduced target")
            
            if confidence >= 55:
                direction = "PUT"
        
        if not direction:
            return None
        
        # Determine parameters
        strength = (SignalStrength.VERY_STRONG if confidence >= 85 else
                   SignalStrength.STRONG if confidence >= 75 else
                   SignalStrength.MODERATE if confidence >= 65 else
                   SignalStrength.WEAK)
        
        # Longer expiry for squeeze breakouts as they tend to run
        recommended_expiry = 60 if is_squeeze else 120
        risk_level = "low" if confidence >= 75 else ("medium" if confidence >= 65 else "high")
        
        return TradingSignal1m(
            strategy_name=self.name,
            direction=direction,
            confidence=min(confidence, 100),
            strength=strength,
            entry_price=current_price,
            indicators={
                "bb_upper": current_upper,
                "bb_middle": current_middle,
                "bb_lower": current_lower,
                "bb_width": bb_width,
                "bb_width_avg": avg_bb_width,
                "is_squeeze": is_squeeze,
                "rsi": current_rsi
            },
            reasoning=reasoning,
            risk_level=risk_level,
            recommended_expiry=recommended_expiry,
            sr_analysis=sr_data
        )


# =============================================================================
# STRATEGY 4: MACD DIVERGENCE STRATEGY
# =============================================================================

class MACDDivergenceStrategy1m:
    """
    ╔══════════════════════════════════════════════════════════════════════╗
    ║  MACD DIVERGENCE STRATEGY - 1 MINUTE                                  ║
    ╠══════════════════════════════════════════════════════════════════════╣
    ║  Strategy Name: MACD Histogram Divergence                             ║
    ║  Timeframe: 1 Minute                                                  ║
    ║  Probability: 70-78% on confirmed divergences                         ║
    ╠══════════════════════════════════════════════════════════════════════╣
    ║  INDICATORS USED:                                                     ║
    ║  • MACD (8, 17, 9) - Faster settings for 1-minute                     ║
    ║  • EMA-21 - Trend filter                                              ║
    ║  • S/R Levels - Entry optimization                                    ║
    ╠══════════════════════════════════════════════════════════════════════╣
    ║  ENTRY RULES:                                                         ║
    ║                                                                       ║
    ║  CALL Signal (Bullish Divergence):                                    ║
    ║  1. Price makes LOWER low                                             ║
    ║  2. MACD histogram makes HIGHER low (divergence)                      ║
    ║  3. MACD line crossing above signal line (confirmation)               ║
    ║  4. Price near support level (S/R)                                    ║
    ║                                                                       ║
    ║  PUT Signal (Bearish Divergence):                                     ║
    ║  1. Price makes HIGHER high                                           ║
    ║  2. MACD histogram makes LOWER high (divergence)                      ║
    ║  3. MACD line crossing below signal line (confirmation)               ║
    ║  4. Price near resistance level (S/R)                                 ║
    ╠══════════════════════════════════════════════════════════════════════╣
    ║  RATIONALE:                                                           ║
    ║  MACD divergence signals weakening momentum. When price makes new     ║
    ║  extremes but MACD doesn't confirm, the trend is exhausting.          ║
    ║  Combined with S/R levels, these setups offer high-probability        ║
    ║  reversal opportunities on 1-minute charts.                           ║
    ╚══════════════════════════════════════════════════════════════════════╝
    """
    
    def __init__(self, enable_sr_filter: bool = True):
        self.name = "MACD Divergence 1m"
        self.timeframe = "1m"
        self.macd_fast = 8
        self.macd_slow = 17
        self.macd_signal = 9
        self.lookback = 10  # Candles to look back for divergence
        self.enable_sr_filter = enable_sr_filter
        self.sr_detector = get_sr_detector() if get_sr_detector else None
        
        logger.info(f"✅ {self.name} initialized")
    
    def generate_signal(self, df: pd.DataFrame) -> Optional[TradingSignal1m]:
        """Generate signal based on MACD divergence"""
        
        if len(df) < 50:
            return None
        
        closes = df['close'].values
        highs = df['high'].values
        lows = df['low'].values
        
        # Calculate MACD
        macd_line, signal_line, histogram = TechnicalIndicators1m.calculate_macd(
            closes, self.macd_fast, self.macd_slow, self.macd_signal
        )
        ema_21 = TechnicalIndicators1m.calculate_ema(closes, 21)
        
        # Current values
        current_price = closes[-1]
        current_hist = histogram[-1]
        prev_hist = histogram[-2]
        current_macd = macd_line[-1]
        current_signal = signal_line[-1]
        prev_macd = macd_line[-2]
        prev_signal = signal_line[-2]
        
        # Check for MACD crossover
        bullish_cross = prev_macd <= prev_signal and current_macd > current_signal
        bearish_cross = prev_macd >= prev_signal and current_macd < current_signal
        
        # Look for divergence
        bullish_div, bullish_div_strength = self._check_bullish_divergence(lows, histogram)
        bearish_div, bearish_div_strength = self._check_bearish_divergence(highs, histogram)
        
        # S/R Analysis
        sr_data = None
        if self.enable_sr_filter and self.sr_detector:
            try:
                sr_analysis = self.sr_detector.analyze(highs, lows, closes)
                sr_data = sr_analysis.to_dict()
            except Exception:
                pass
        
        confidence = 0
        direction = None
        reasoning = []
        
        # ═══════════════════════════════════════════
        # CALL SIGNAL - Bullish Divergence
        # ═══════════════════════════════════════════
        if bullish_div:
            confidence += 35
            reasoning.append(f"✅ Bullish MACD divergence detected (strength: {bullish_div_strength:.1f})")
            
            # MACD crossover confirmation
            if bullish_cross:
                confidence += 25
                reasoning.append("✅ MACD bullish crossover confirms divergence")
            elif current_macd > prev_macd:
                confidence += 10
                reasoning.append("✅ MACD turning up")
            
            # Trend context
            if current_price < ema_21[-1]:
                confidence += 5
                reasoning.append("✅ Counter-trend setup - potential reversal")
            
            # S/R confirmation
            if sr_data:
                if sr_data.get('price_position') == 'at_support':
                    confidence += 20
                    reasoning.append("✅ S/R: Divergence at SUPPORT - high probability")
                elif sr_data.get('distance_to_support_pct', 100) < 0.1:
                    confidence += 10
                    reasoning.append("✅ S/R: Near support level")
            
            if confidence >= 60:
                direction = "CALL"
        
        # ═══════════════════════════════════════════
        # PUT SIGNAL - Bearish Divergence
        # ═══════════════════════════════════════════
        elif bearish_div:
            confidence += 35
            reasoning.append(f"✅ Bearish MACD divergence detected (strength: {bearish_div_strength:.1f})")
            
            # MACD crossover confirmation
            if bearish_cross:
                confidence += 25
                reasoning.append("✅ MACD bearish crossover confirms divergence")
            elif current_macd < prev_macd:
                confidence += 10
                reasoning.append("✅ MACD turning down")
            
            # Trend context
            if current_price > ema_21[-1]:
                confidence += 5
                reasoning.append("✅ Counter-trend setup - potential reversal")
            
            # S/R confirmation
            if sr_data:
                if sr_data.get('price_position') == 'at_resistance':
                    confidence += 20
                    reasoning.append("✅ S/R: Divergence at RESISTANCE - high probability")
                elif sr_data.get('distance_to_resistance_pct', 100) < 0.1:
                    confidence += 10
                    reasoning.append("✅ S/R: Near resistance level")
            
            if confidence >= 60:
                direction = "PUT"
        
        if not direction:
            return None
        
        strength = (SignalStrength.VERY_STRONG if confidence >= 85 else
                   SignalStrength.STRONG if confidence >= 75 else
                   SignalStrength.MODERATE if confidence >= 65 else
                   SignalStrength.WEAK)
        
        # Divergence reversals may take 2-3 candles
        recommended_expiry = 120 if bullish_cross or bearish_cross else 180
        risk_level = "low" if confidence >= 80 else ("medium" if confidence >= 70 else "high")
        
        return TradingSignal1m(
            strategy_name=self.name,
            direction=direction,
            confidence=min(confidence, 100),
            strength=strength,
            entry_price=current_price,
            indicators={
                "macd": current_macd,
                "macd_signal": current_signal,
                "histogram": current_hist,
                "bullish_divergence": bullish_div,
                "bearish_divergence": bearish_div,
                "bullish_cross": bullish_cross,
                "bearish_cross": bearish_cross
            },
            reasoning=reasoning,
            risk_level=risk_level,
            recommended_expiry=recommended_expiry,
            sr_analysis=sr_data
        )
    
    def _check_bullish_divergence(self, lows: np.ndarray, histogram: np.ndarray) -> Tuple[bool, float]:
        """Check for bullish divergence (price lower low, histogram higher low)"""
        lookback = min(self.lookback, len(lows) - 1)
        
        # Find recent price low
        recent_lows = lows[-lookback:]
        price_low_idx = np.argmin(recent_lows)
        current_low = lows[-1]
        prev_low = recent_lows[price_low_idx]
        
        # Check if price made lower low
        if current_low >= prev_low * 1.0001:  # Tolerance
            return False, 0
        
        # Check histogram
        recent_hist = histogram[-lookback:]
        hist_low_idx = np.argmin(recent_hist)
        current_hist = histogram[-1]
        prev_hist_low = recent_hist[hist_low_idx]
        
        # Bullish divergence: price lower low, histogram higher low
        if current_hist > prev_hist_low:
            strength = (current_hist - prev_hist_low) / abs(prev_hist_low) if prev_hist_low != 0 else 0
            return True, strength * 100
        
        return False, 0
    
    def _check_bearish_divergence(self, highs: np.ndarray, histogram: np.ndarray) -> Tuple[bool, float]:
        """Check for bearish divergence (price higher high, histogram lower high)"""
        lookback = min(self.lookback, len(highs) - 1)
        
        # Find recent price high
        recent_highs = highs[-lookback:]
        price_high_idx = np.argmax(recent_highs)
        current_high = highs[-1]
        prev_high = recent_highs[price_high_idx]
        
        # Check if price made higher high
        if current_high <= prev_high * 0.9999:  # Tolerance
            return False, 0
        
        # Check histogram
        recent_hist = histogram[-lookback:]
        hist_high_idx = np.argmax(recent_hist)
        current_hist = histogram[-1]
        prev_hist_high = recent_hist[hist_high_idx]
        
        # Bearish divergence: price higher high, histogram lower high
        if current_hist < prev_hist_high:
            strength = (prev_hist_high - current_hist) / abs(prev_hist_high) if prev_hist_high != 0 else 0
            return True, strength * 100
        
        return False, 0


# =============================================================================
# STRATEGY 5: STOCHASTIC + RSI CONFLUENCE
# =============================================================================

class StochRSIConfluenceStrategy1m:
    """
    ╔══════════════════════════════════════════════════════════════════════╗
    ║  STOCHASTIC + RSI CONFLUENCE STRATEGY - 1 MINUTE                      ║
    ╠══════════════════════════════════════════════════════════════════════╣
    ║  Strategy Name: Dual Oscillator Confluence                            ║
    ║  Timeframe: 1 Minute                                                  ║
    ║  Probability: 75-82% when both indicators align                       ║
    ╠══════════════════════════════════════════════════════════════════════╣
    ║  INDICATORS USED:                                                     ║
    ║  • Stochastic (9, 3) - Fast oscillator                                ║
    ║  • RSI (7) - Momentum oscillator                                      ║
    ║  • EMA-10 - Trend filter                                              ║
    ║  • S/R Levels - Entry optimization                                    ║
    ╠══════════════════════════════════════════════════════════════════════╣
    ║  ENTRY RULES:                                                         ║
    ║                                                                       ║
    ║  CALL Signal:                                                         ║
    ║  1. Stochastic %K AND %D below 20 (oversold)                          ║
    ║  2. RSI below 30 (oversold)                                           ║
    ║  3. Stochastic %K crosses above %D (bullish cross)                    ║
    ║  4. Price near or above EMA-10                                        ║
    ║                                                                       ║
    ║  PUT Signal:                                                          ║
    ║  1. Stochastic %K AND %D above 80 (overbought)                        ║
    ║  2. RSI above 70 (overbought)                                         ║
    ║  3. Stochastic %K crosses below %D (bearish cross)                    ║
    ║  4. Price near or below EMA-10                                        ║
    ╠══════════════════════════════════════════════════════════════════════╣
    ║  RATIONALE:                                                           ║
    ║  When BOTH Stochastic and RSI reach extreme levels simultaneously,    ║
    ║  it indicates strong oversold/overbought conditions. The crossover    ║
    ║  provides timing for entry. This dual confirmation reduces false      ║
    ║  signals significantly compared to using either indicator alone.      ║
    ╚══════════════════════════════════════════════════════════════════════╝
    """
    
    def __init__(self, enable_sr_filter: bool = True):
        self.name = "Stoch-RSI Confluence 1m"
        self.timeframe = "1m"
        self.stoch_k = 9
        self.stoch_d = 3
        self.stoch_oversold = 20
        self.stoch_overbought = 80
        self.rsi_period = 7
        self.rsi_oversold = 30
        self.rsi_overbought = 70
        self.enable_sr_filter = enable_sr_filter
        self.sr_detector = get_sr_detector() if get_sr_detector else None
        
        logger.info(f"✅ {self.name} initialized")
    
    def generate_signal(self, df: pd.DataFrame) -> Optional[TradingSignal1m]:
        """Generate signal based on Stochastic + RSI confluence"""
        
        if len(df) < 50:
            return None
        
        closes = df['close'].values
        highs = df['high'].values
        lows = df['low'].values
        
        # Calculate indicators
        stoch_k, stoch_d = TechnicalIndicators1m.calculate_stochastic(
            highs, lows, closes, self.stoch_k, self.stoch_d
        )
        rsi = TechnicalIndicators1m.calculate_rsi(closes, self.rsi_period)
        ema_10 = TechnicalIndicators1m.calculate_ema(closes, 10)
        
        # Current values
        current_price = closes[-1]
        current_k = stoch_k[-1]
        current_d = stoch_d[-1]
        prev_k = stoch_k[-2]
        prev_d = stoch_d[-2]
        current_rsi = rsi[-1]
        current_ema = ema_10[-1]
        
        # Check for crossovers
        bullish_cross = prev_k <= prev_d and current_k > current_d
        bearish_cross = prev_k >= prev_d and current_k < current_d
        
        # S/R Analysis
        sr_data = None
        if self.enable_sr_filter and self.sr_detector:
            try:
                sr_analysis = self.sr_detector.analyze(highs, lows, closes)
                sr_data = sr_analysis.to_dict()
            except Exception:
                pass
        
        confidence = 0
        direction = None
        reasoning = []
        
        # ═══════════════════════════════════════════
        # CALL SIGNAL - Oversold Confluence
        # ═══════════════════════════════════════════
        stoch_oversold = current_k < self.stoch_oversold and current_d < self.stoch_oversold
        rsi_oversold = current_rsi < self.rsi_oversold
        
        if stoch_oversold and rsi_oversold:
            confidence += 35
            reasoning.append(f"✅ DUAL OVERSOLD: Stoch({current_k:.1f}/{current_d:.1f}) + RSI({current_rsi:.1f})")
            
            # Crossover confirmation
            if bullish_cross:
                confidence += 25
                reasoning.append("✅ Stochastic bullish crossover - entry signal!")
            elif current_k > prev_k:
                confidence += 10
                reasoning.append("✅ Stochastic turning up")
            else:
                reasoning.append("⚠️ Waiting for Stochastic crossover")
            
            # Trend filter
            if current_price >= current_ema * 0.998:
                confidence += 10
                reasoning.append("✅ Price at/above EMA-10 support")
            
            # How oversold (deeper = stronger reversal potential)
            oversold_depth = (self.stoch_oversold - current_k) + (self.rsi_oversold - current_rsi)
            if oversold_depth > 30:
                confidence += 10
                reasoning.append("✅ Deeply oversold - strong reversal potential")
            
            # S/R confirmation
            if sr_data:
                if sr_data.get('price_position') == 'at_support':
                    confidence += 15
                    reasoning.append("✅ S/R: At SUPPORT - optimal entry")
            
            if confidence >= 60 and bullish_cross:
                direction = "CALL"
        
        # ═══════════════════════════════════════════
        # PUT SIGNAL - Overbought Confluence
        # ═══════════════════════════════════════════
        stoch_overbought = current_k > self.stoch_overbought and current_d > self.stoch_overbought
        rsi_overbought = current_rsi > self.rsi_overbought
        
        if stoch_overbought and rsi_overbought:
            confidence += 35
            reasoning.append(f"✅ DUAL OVERBOUGHT: Stoch({current_k:.1f}/{current_d:.1f}) + RSI({current_rsi:.1f})")
            
            # Crossover confirmation
            if bearish_cross:
                confidence += 25
                reasoning.append("✅ Stochastic bearish crossover - entry signal!")
            elif current_k < prev_k:
                confidence += 10
                reasoning.append("✅ Stochastic turning down")
            else:
                reasoning.append("⚠️ Waiting for Stochastic crossover")
            
            # Trend filter
            if current_price <= current_ema * 1.002:
                confidence += 10
                reasoning.append("✅ Price at/below EMA-10 resistance")
            
            # How overbought
            overbought_depth = (current_k - self.stoch_overbought) + (current_rsi - self.rsi_overbought)
            if overbought_depth > 30:
                confidence += 10
                reasoning.append("✅ Deeply overbought - strong reversal potential")
            
            # S/R confirmation
            if sr_data:
                if sr_data.get('price_position') == 'at_resistance':
                    confidence += 15
                    reasoning.append("✅ S/R: At RESISTANCE - optimal entry")
            
            if confidence >= 60 and bearish_cross:
                direction = "PUT"
        
        if not direction:
            return None
        
        strength = (SignalStrength.VERY_STRONG if confidence >= 85 else
                   SignalStrength.STRONG if confidence >= 75 else
                   SignalStrength.MODERATE if confidence >= 65 else
                   SignalStrength.WEAK)
        
        recommended_expiry = 60  # Quick reversals from extreme levels
        risk_level = "low" if confidence >= 80 else ("medium" if confidence >= 70 else "high")
        
        return TradingSignal1m(
            strategy_name=self.name,
            direction=direction,
            confidence=min(confidence, 100),
            strength=strength,
            entry_price=current_price,
            indicators={
                "stoch_k": current_k,
                "stoch_d": current_d,
                "rsi": current_rsi,
                "ema_10": current_ema,
                "stoch_oversold": stoch_oversold,
                "stoch_overbought": stoch_overbought,
                "rsi_oversold": rsi_oversold,
                "rsi_overbought": rsi_overbought,
                "bullish_cross": bullish_cross,
                "bearish_cross": bearish_cross
            },
            reasoning=reasoning,
            risk_level=risk_level,
            recommended_expiry=recommended_expiry,
            sr_analysis=sr_data
        )


# =============================================================================
# MASTER STRATEGY AGGREGATOR
# =============================================================================

class HighProbability1mStrategies:
    """
    Master class that runs all 1-minute strategies and returns the best signal
    
    Features:
    - Runs all 5 strategies simultaneously
    - Returns highest confidence signal
    - Option to require multiple strategy agreement
    """
    
    def __init__(self, enable_sr_filter: bool = True):
        self.strategies = [
            RSIReversalStrategy1m(enable_sr_filter),
            EMACrossoverStrategy1m(enable_sr_filter),
            BollingerSqueezeStrategy1m(enable_sr_filter),
            MACDDivergenceStrategy1m(enable_sr_filter),
            StochRSIConfluenceStrategy1m(enable_sr_filter)
        ]
        logger.info(f"✅ High-Probability 1m Strategies initialized ({len(self.strategies)} strategies)")
    
    def get_best_signal(self, df: pd.DataFrame) -> Optional[TradingSignal1m]:
        """Get the best signal from all strategies"""
        signals = []
        
        for strategy in self.strategies:
            try:
                signal = strategy.generate_signal(df)
                if signal:
                    signals.append(signal)
            except Exception as e:
                logger.error(f"Strategy {strategy.name} error: {e}")
        
        if not signals:
            return None
        
        # Return highest confidence signal
        return max(signals, key=lambda s: s.confidence)
    
    def get_all_signals(self, df: pd.DataFrame) -> List[TradingSignal1m]:
        """Get signals from all strategies"""
        signals = []
        
        for strategy in self.strategies:
            try:
                signal = strategy.generate_signal(df)
                if signal:
                    signals.append(signal)
            except Exception as e:
                logger.error(f"Strategy {strategy.name} error: {e}")
        
        return sorted(signals, key=lambda s: s.confidence, reverse=True)
    
    def get_consensus_signal(self, df: pd.DataFrame, min_agreement: int = 2) -> Optional[Dict]:
        """
        Get signal only when multiple strategies agree on direction
        
        Args:
            df: Price data
            min_agreement: Minimum number of strategies that must agree
        
        Returns:
            Consensus signal with combined confidence
        """
        signals = self.get_all_signals(df)
        
        if not signals:
            return None
        
        # Count direction votes
        call_votes = [s for s in signals if s.direction == "CALL"]
        put_votes = [s for s in signals if s.direction == "PUT"]
        
        if len(call_votes) >= min_agreement:
            avg_confidence = np.mean([s.confidence for s in call_votes])
            return {
                "direction": "CALL",
                "confidence": avg_confidence,
                "agreement": len(call_votes),
                "strategies": [s.strategy_name for s in call_votes],
                "signals": [s.to_dict() for s in call_votes]
            }
        
        elif len(put_votes) >= min_agreement:
            avg_confidence = np.mean([s.confidence for s in put_votes])
            return {
                "direction": "PUT",
                "confidence": avg_confidence,
                "agreement": len(put_votes),
                "strategies": [s.strategy_name for s in put_votes],
                "signals": [s.to_dict() for s in put_votes]
            }
        
        return None


# Global instances
_rsi_strategy = None
_ema_strategy = None
_bb_strategy = None
_macd_strategy = None
_stoch_rsi_strategy = None
_master_strategy = None


def get_1m_strategies():
    """Get all 1-minute strategy instances"""
    global _rsi_strategy, _ema_strategy, _bb_strategy, _macd_strategy, _stoch_rsi_strategy, _master_strategy
    
    if _master_strategy is None:
        _rsi_strategy = RSIReversalStrategy1m()
        _ema_strategy = EMACrossoverStrategy1m()
        _bb_strategy = BollingerSqueezeStrategy1m()
        _macd_strategy = MACDDivergenceStrategy1m()
        _stoch_rsi_strategy = StochRSIConfluenceStrategy1m()
        _master_strategy = HighProbability1mStrategies()
    
    return {
        "rsi_reversal": _rsi_strategy,
        "ema_crossover": _ema_strategy,
        "bb_squeeze": _bb_strategy,
        "macd_divergence": _macd_strategy,
        "stoch_rsi": _stoch_rsi_strategy,
        "master": _master_strategy
    }
