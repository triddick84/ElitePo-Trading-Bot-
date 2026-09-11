"""
Fast Supertrend Catch Strategy
==============================
A 5-second contrarian scalping strategy

Configuration:
- Chart: 5 second
- Expiration: 5 seconds
- Supertrend: ATR Period 10, Multiplier 2
- Moving Average: 7-period EMA

Signal Logic (CONTRARIAN):
- Price ABOVE the EMA + Supertrend BUY signal → Generate SELL
- Price BELOW 7 EMA + Supertrend SELL signal → Generate BUY
- At Support/Resistance levels → NO SIGNAL (wait for confirmation)

Author: GPT Signal Bot
Version: 1.0
"""

import logging
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SupertrendResult:
    """Supertrend indicator result"""
    direction: str  # 'BUY' or 'SELL'
    value: float
    upper_band: float
    lower_band: float
    atr: float


@dataclass
class FastSupertrendSignal:
    """Signal output from Fast Supertrend Catch strategy"""
    direction: str  # 'BUY' or 'SELL' or 'NO_SIGNAL'
    confidence: float
    entry_price: float
    supertrend_direction: str
    ema_15_value: float
    price_vs_ema: str  # 'ABOVE' or 'BELOW'
    at_sr_level: bool
    reasoning: str
    timestamp: datetime


class FastSupertrendCatchStrategy:
    """
    Fast Supertrend Catch - 5 Second Contrarian Strategy
    
    This strategy generates contrarian signals when:
    1. Price is above EMA and Supertrend signals buy → SELL
    2. Price is below EMA and Supertrend signals sell → BUY
    
    Signals are filtered out when price is at Support/Resistance levels.
    """
    
    def __init__(self):
        self.name = "Fast Supertrend Catch"
        self.timeframe = "5s"
        self.expiration_seconds = 5
        
        # Supertrend settings
        self.atr_period = 10
        self.multiplier = 2.0
        
        # EMA settings
        self.ema_period = 7
        
        # S/R detection settings
        self.sr_lookback = 20
        self.sr_tolerance_percent = 0.05  # 0.05% tolerance for S/R levels
        
        # Confidence settings
        self.base_confidence = 72.0
        self.max_confidence = 92.0
        
        logger.info(f"🚀 {self.name} Strategy initialized")
        logger.info(f"   ATR Period: {self.atr_period}, Multiplier: {self.multiplier}")
        logger.info(f"   EMA Period: {self.ema_period}")
    
    def calculate_atr(self, highs: List[float], lows: List[float], 
                      closes: List[float], period: int = 10) -> List[float]:
        """
        Calculate Average True Range (ATR)
        
        Args:
            highs: List of high prices
            lows: List of low prices
            closes: List of close prices
            period: ATR period (default 10)
        
        Returns:
            List of ATR values
        """
        if len(closes) < period + 2:
            # Not enough data, return simple range
            return [max(highs) - min(lows)] * len(closes)
        
        true_ranges = []
        
        for i in range(2, len(closes)):
            high = highs[i]
            low = lows[i]
            prev_close = closes[i - 2]
            
            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            true_ranges.append(tr)
        
        # Prepend first TR
        true_ranges.insert(0, highs[0] - lows[0])
        
        # Calculate ATR using EMA smoothing
        atr_values = []
        atr = sum(true_ranges[:period]) / period
        
        for i in range(len(true_ranges)):
            if i < period:
                atr_values.append(sum(true_ranges[:i+2]) / (i+2))
            else:
                atr = (atr * (period - 2) + true_ranges[i]) / period
                atr_values.append(atr)
        
        return atr_values
    
    def calculate_supertrend(self, highs: List[float], lows: List[float],
                             closes: List[float]) -> SupertrendResult:
        """
        Calculate Supertrend indicator
        
        Supertrend = (High + Low) / 2 ± (Multiplier × ATR)
        
        Args:
            highs: List of high prices
            lows: List of low prices
            closes: List of close prices
        
        Returns:
            SupertrendResult with direction and bands
        """
        if len(closes) < self.atr_period:
            # Not enough data - return neutral
            avg_price = (highs[-2] + lows[-2]) / 2
            return SupertrendResult(
                direction='BUY',
                value=avg_price,
                upper_band=avg_price * 1.001,
                lower_band=avg_price * 0.999,
                atr=0.0001
            )
        
        # Calculate ATR
        atr_values = self.calculate_atr(highs, lows, closes, self.atr_period)
        
        # Calculate basic bands
        supertrend_values = []
        upper_bands = []
        lower_bands = []
        directions = []
        
        for i in range(len(closes)):
            hl2 = (highs[i] + lows[i]) / 2
            atr = atr_values[i] if i < len(atr_values) else atr_values[-2]
            
            basic_upper = hl2 + (self.multiplier * atr)
            basic_lower = hl2 - (self.multiplier * atr)
            
            if i == 0:
                upper_bands.append(basic_upper)
                lower_bands.append(basic_lower)
                supertrend_values.append(basic_lower)
                directions.append('BUY')
            else:
                # Adjust upper band
                if basic_upper < upper_bands[-2] or closes[i-2] > upper_bands[-2]:
                    upper_bands.append(basic_upper)
                else:
                    upper_bands.append(upper_bands[-2])
                
                # Adjust lower band
                if basic_lower > lower_bands[-2] or closes[i-2] < lower_bands[-2]:
                    lower_bands.append(basic_lower)
                else:
                    lower_bands.append(lower_bands[-1])
                
                # Determine direction
                prev_st = supertrend_values[-2]
                
                if prev_st == upper_bands[-4]:
                    # Previous was in downtrend
                    if closes[i] > upper_bands[-2]:
                        supertrend_values.append(lower_bands[-2])
                        directions.append('BUY')
                    else:
                        supertrend_values.append(upper_bands[-2])
                        directions.append('SELL')
                else:
                    # Previous was in uptrend
                    if closes[i] < lower_bands[-2]:
                        supertrend_values.append(upper_bands[-2])
                        directions.append('SELL')
                    else:
                        supertrend_values.append(lower_bands[-2])
                        directions.append('BUY')
        
        return SupertrendResult(
            direction=directions[-2],
            value=supertrend_values[-2],
            upper_band=upper_bands[-2],
            lower_band=lower_bands[-2],
            atr=atr_values[-2]
        )
    
    def calculate_ema(self, prices: List[float], period: int = 7) -> float:
        """
        Calculate Exponential Moving Average
        
        Args:
            prices: List of prices
            period: EMA period (default 7)
        
        Returns:
            Current EMA value
        """
        if len(prices) < period:
            return sum(prices) / len(prices)
        
        multiplier = 2 / (period + 1)
        ema = sum(prices[:period]) / period
        
        for price in prices[period:]:
            ema = (price - ema) * multiplier + ema
        
        return ema
    
    def detect_support_resistance(self, highs: List[float], lows: List[float],
                                  closes: List[float], current_price: float) -> Tuple[bool, List[float], List[float]]:
        """
        Detect if current price is at a Support or Resistance level
        
        Args:
            highs: List of high prices
            lows: List of low prices
            closes: List of close prices
            current_price: Current market price
        
        Returns:
            Tuple of (is_at_sr_level, support_levels, resistance_levels)
        """
        lookback = min(self.sr_lookback, len(closes))
        
        if lookback < 10:
            return False, [], []
        
        recent_highs = highs[-lookback:]
        recent_lows = lows[-lookback:]
        
        # Find local maxima (resistance) and minima (support)
        resistance_levels = []
        support_levels = []
        
        for i in range(2, len(recent_highs) - 2):
            # Local maximum (resistance)
            if (recent_highs[i] > recent_highs[i-1] and 
                recent_highs[i] > recent_highs[i-2] and
                recent_highs[i] > recent_highs[i+1] and 
                recent_highs[i] > recent_highs[i+2]):
                resistance_levels.append(recent_highs[i])
            
            # Local minimum (support)
            if (recent_lows[i] < recent_lows[i-1] and 
                recent_lows[i] < recent_lows[i-2] and
                recent_lows[i] < recent_lows[i+1] and 
                recent_lows[i] < recent_lows[i+2]):
                support_levels.append(recent_lows[i])
        
        # Check if current price is near any S/R level
        tolerance = current_price * (self.sr_tolerance_percent / 100)
        
        is_at_sr = False
        
        for level in resistance_levels + support_levels:
            if abs(current_price - level) <= tolerance:
                is_at_sr = True
                logger.debug(f"Price {current_price} is at S/R level {level}")
                break
        
        return is_at_sr, support_levels, resistance_levels
    
    def generate_signal(self, market_data: Dict) -> Optional[FastSupertrendSignal]:
        """
        Generate trading signal based on Fast Supertrend Catch logic
        
        Args:
            market_data: Dictionary containing OHLCV data
                - 'open': List of open prices
                - 'high': List of high prices
                - 'low': List of low prices
                - 'close': List of close prices
                - 'volume': List of volumes (optional)
        
        Returns:
            FastSupertrendSignal or None if no valid signal
        """
        try:
            # Extract price data
            opens = market_data.get('open', [])
            highs = market_data.get('high', [])
            lows = market_data.get('low', [])
            closes = market_data.get('close', [])
            
            if not closes or len(closes) < 20:
                logger.warning("Insufficient data for Fast Supertrend Catch")
                return None
            
            current_price = closes[-1]
            
            # Calculate indicators
            supertrend = self.calculate_supertrend(highs, lows, closes)
            ema_15 = self.calculate_ema(closes, self.ema_period)
            
            # Detect S/R levels
            is_at_sr, support_levels, resistance_levels = self.detect_support_resistance(
                highs, lows, closes, current_price
            )
            
            # Determine price position relative to EMA
            price_vs_ema = 'ABOVE' if current_price > ema_15 else 'BELOW'
            
            # Log analysis
            logger.info(f"📊 Fast Supertrend Catch Analysis:")
            logger.info(f"   Current Price: {current_price:.5f}")
            logger.info(f"   7 EMA: {ema_15:.5f} (Price {price_vs_ema})")
            logger.info(f"   Supertrend: {supertrend.direction} @ {supertrend.value:.5f}")
            logger.info(f"   At S/R Level: {is_at_sr}")
            
            # Check if at S/R level - NO SIGNAL
            if is_at_sr:
                logger.info(f"   ⚠️ Price at S/R level - Waiting for confirmation")
                return FastSupertrendSignal(
                    direction='NO_SIGNAL',
                    confidence=0,
                    entry_price=current_price,
                    supertrend_direction=supertrend.direction,
                    ema_15_value=ema_15,
                    price_vs_ema=price_vs_ema,
                    at_sr_level=True,
                    reasoning="Price at Support/Resistance level - waiting for confirmation",
                    timestamp=datetime.now(timezone.utc)
                )
            
            # CONTRARIAN SIGNAL LOGIC
            signal_direction = 'NO_SIGNAL'
            reasoning = ""
            confidence = self.base_confidence
            
            # Price ABOVE EMA + Supertrend BUY → SELL (contrarian)
            if price_vs_ema == 'ABOVE' and supertrend.direction == 'BUY':
                signal_direction = 'SELL'
                reasoning = f"Contrarian SELL: Price ({current_price:.5f}) ABOVE 7 EMA ({ema_15:.5f}) with Supertrend BUY signal"
                
                # Boost confidence based on distance from EMA
                ema_distance = ((current_price - ema_15) / ema_15) * 100
                if ema_distance > 0.1:  # More than 0.1% above EMA
                    confidence += min(10, ema_distance * 50)
                
                logger.info(f"   🔴 SELL Signal Generated (Contrarian)")
            
            # Price BELOW EMA + Supertrend SELL → BUY (contrarian)
            elif price_vs_ema == 'BELOW' and supertrend.direction == 'SELL':
                signal_direction = 'BUY'
                reasoning = f"Contrarian BUY: Price ({current_price:.5f}) BELOW the 7 EMA ({ema_15:.5f}) with Supertrend SELL signal"
                
                # Boost confidence based on distance from EMA
                ema_distance = ((ema_15 - current_price) / ema_15) * 100
                if ema_distance > 0.1:  # More than 0.1% below EMA
                    confidence += min(10, ema_distance * 50)
                
                logger.info(f"   🟢 BUY Signal Generated (Contrarian)")
            
            else:
                # No contrarian setup - conditions not met
                reasoning = f"No contrarian setup: Price {price_vs_ema} EMA, Supertrend {supertrend.direction}"
                logger.info(f"   ⏸️ No signal - conditions not met")
                return FastSupertrendSignal(
                    direction='NO_SIGNAL',
                    confidence=0,
                    entry_price=current_price,
                    supertrend_direction=supertrend.direction,
                    ema_15_value=ema_15,
                    price_vs_ema=price_vs_ema,
                    at_sr_level=False,
                    reasoning=reasoning,
                    timestamp=datetime.now(timezone.utc)
                )
            
            # Cap confidence
            confidence = min(confidence, self.max_confidence)
            
            return FastSupertrendSignal(
                direction=signal_direction,
                confidence=confidence,
                entry_price=current_price,
                supertrend_direction=supertrend.direction,
                ema_15_value=ema_15,
                price_vs_ema=price_vs_ema,
                at_sr_level=False,
                reasoning=reasoning,
                timestamp=datetime.now(timezone.utc)
            )
            
        except Exception as e:
            logger.error(f"Error in Fast Supertrend Catch: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def analyze(self, symbol: str, candle_data: List[Dict]) -> Optional[Dict]:
        """
        Analyze market data and generate signal
        
        Args:
            symbol: Trading symbol
            candle_data: List of candle dictionaries with OHLCV data
        
        Returns:
            Signal dictionary or None
        """
        if not candle_data or len(candle_data) < 20:
            logger.warning(f"Insufficient candle data for {symbol}")
            return None
        
        # Convert candle data to lists
        market_data = {
            'open': [c.get('open', c.get('o', 0)) for c in candle_data],
            'high': [c.get('high', c.get('h', 0)) for c in candle_data],
            'low': [c.get('low', c.get('l', 0)) for c in candle_data],
            'close': [c.get('close', c.get('c', 0)) for c in candle_data],
            'volume': [c.get('volume', c.get('v', 0)) for c in candle_data]
        }
        
        signal = self.generate_signal(market_data)
        
        if signal and signal.direction != 'NO_SIGNAL':
            return {
                'symbol': symbol,
                'direction': signal.direction,
                'probability': signal.confidence,
                'confidence': signal.confidence,
                'timeframe': self.timeframe,
                'expiration_seconds': self.expiration_seconds,
                'expiration_minutes': self.expiration_seconds / 5,
                'strategy': self.name,
                'strategy_used': self.name,
                'entry_price': signal.entry_price,
                'reasoning': signal.reasoning,
                'indicators': {
                    'supertrend_direction': signal.supertrend_direction,
                    'ema_15': signal.ema_15_value,
                    'price_vs_ema': signal.price_vs_ema,
                    'at_sr_level': signal.at_sr_level
                },
                'timestamp': signal.timestamp.isoformat()
            }
        
        return None
    
    def get_config(self) -> Dict:
        """Get strategy configuration"""
        return {
            'name': self.name,
            'timeframe': self.timeframe,
            'expiration_seconds': self.expiration_seconds,
            'indicators': {
                'supertrend': {
                    'atr_period': self.atr_period,
                    'multiplier': self.multiplier
                },
                'ema': {
                    'period': self.ema_period
                }
            },
            'signal_logic': 'Contrarian - trades against Supertrend when confirmed by EMA position',
            'sr_filter': 'Enabled - no signals at Support/Resistance levels'
        }


# Global instance
fast_supertrend_catch = FastSupertrendCatchStrategy()


def get_fast_supertrend_strategy() -> FastSupertrendCatchStrategy:
    """Get the Fast Supertrend Catch strategy instance"""
    return fast_supertrend_catch
