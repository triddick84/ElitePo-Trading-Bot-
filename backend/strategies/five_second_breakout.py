"""
Five-Second Breakout Strategy
Complete integration of Enhanced Breakout Predictor optimized for 5s trading

Features:
- Ultra-fast breakout detection (<100ms)
- Multi-confirmation system
- S/R level integration
- Probability scoring
- Alert system integration
"""

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timezone
from typing import Dict, Optional, List, Any
import logging
import time
import asyncio

# Import breakout predictor components
import sys
sys.path.insert(0, '/app/backend')

from indicators.breakout_predictor import (
    BreakoutPredictor5s,
    get_breakout_predictor_5s,
    generate_breakout_signal,
    BreakoutSettings,
    BreakoutSignal
)
from alerts.breakout_alerts import (
    get_alert_manager,
    send_breakout_alert
)

logger = logging.getLogger(__name__)


class FiveSecondBreakoutStrategy:
    """
    Complete 5-second breakout trading strategy
    
    Combines:
    - Enhanced Breakout Predictor
    - Probability Scoring Engine
    - S/R Level Analysis
    - Alert Integration
    - Multi-timeframe confirmation (optional)
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or self._default_config()
        
        # Initialize components
        self.breakout_predictor = get_breakout_predictor_5s()
        self.alert_manager = get_alert_manager()
        
        # Strategy settings
        self.timeframe = "5s"
        self.min_confidence = self.config.get('min_confidence', 75)
        self.enable_alerts = self.config.get('enable_alerts', True)
        self.enable_multi_timeframe = self.config.get('multi_timeframe_confirmation', False)
        
        # Performance tracking
        self.signals_generated = 0
        self.processing_times: List[float] = []
        
        logger.info("⚡ Five-Second Breakout Strategy initialized")
        logger.info(f"   Min Confidence: {self.min_confidence}%")
        logger.info(f"   Alerts: {'Enabled' if self.enable_alerts else 'Disabled'}")
    
    def _default_config(self) -> Dict:
        """Default strategy configuration"""
        return {
            'min_confidence': 75,
            'enable_alerts': True,
            'multi_timeframe_confirmation': False,
            'lookback_period': 15,
            'percentage_step': 0.5,
            'number_of_lines': 3,
            'min_breakout_strength': 0.4,
            'webhook_enabled': False,
            'webhook_url': '',
            'alert_formats': ['json']
        }
    
    def fetch_market_data(self, symbol: str, periods: int = 100) -> Optional[pd.DataFrame]:
        """
        Fetch market data for analysis
        
        Args:
            symbol: Trading symbol
            periods: Number of bars to fetch
        
        Returns:
            DataFrame with OHLCV data or None
        """
        try:
            # Clean symbol for yfinance
            yf_symbol = symbol.replace('_OTC', '').replace('_regular', '').replace('_otc', '')
            
            # Add forex suffix if needed
            if len(yf_symbol) == 6 and yf_symbol.isalpha():
                yf_symbol = f"{yf_symbol}=X"
            elif yf_symbol in ['BTCUSD', 'ETHUSD', 'LTCUSD']:
                yf_symbol = yf_symbol.replace('USD', '-USD')
            
            ticker = yf.Ticker(yf_symbol)
            df = ticker.history(period="2d", interval="1m")
            
            if df.empty or len(df) < 50:
                logger.warning(f"Insufficient data for {symbol}: {len(df) if not df.empty else 0} candles")
                return None
            
            # Normalize columns
            df = df.rename(columns={
                'Open': 'open', 'High': 'high',
                'Low': 'low', 'Close': 'close', 'Volume': 'volume'
            })
            
            return df.tail(periods)
            
        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}")
            return None
    
    def analyze_breakout(self, df: pd.DataFrame, symbol: str) -> Optional[Dict]:
        """
        Analyze for breakout signals
        
        Args:
            df: OHLCV DataFrame
            symbol: Trading symbol
        
        Returns:
            Signal dict or None
        """
        start_time = time.time()
        
        # Use breakout predictor
        signal = self.breakout_predictor.generate_signal(symbol, df)
        
        if signal is None:
            return None
        
        # Check confidence threshold
        if signal.get('confidence', 0) < self.min_confidence:
            logger.debug(f"Signal confidence {signal['confidence']} below threshold {self.min_confidence}")
            return None
        
        # Add processing time
        signal['strategy_processing_time_ms'] = round((time.time() - start_time) * 1000, 2)
        
        return signal
    
    def apply_multi_timeframe_filter(self, signal: Dict, symbol: str) -> Dict:
        """
        Apply multi-timeframe confirmation filter
        
        Checks 1m timeframe trend alignment
        """
        if not self.enable_multi_timeframe:
            return signal
        
        try:
            # Fetch 1m data for trend confirmation
            df_1m = self.fetch_market_data(symbol, 50)
            
            if df_1m is None or len(df_1m) < 20:
                return signal
            
            # Simple trend detection on 1m
            close = df_1m['close'].values
            sma_fast = pd.Series(close).rolling(5).mean().iloc[-1]
            sma_slow = pd.Series(close).rolling(20).mean().iloc[-1]
            
            trend_bullish = sma_fast > sma_slow
            trend_bearish = sma_fast < sma_slow
            
            signal_direction = signal.get('direction', signal.get('signal', ''))
            
            # Boost confidence if aligned
            if (signal_direction == 'BUY' and trend_bullish) or \
               (signal_direction == 'SELL' and trend_bearish):
                signal['confidence'] = min(signal['confidence'] + 5, 95)
                signal['multi_timeframe_aligned'] = True
                logger.info(f"✅ Multi-timeframe aligned: +5% confidence boost")
            else:
                signal['multi_timeframe_aligned'] = False
                # Optional: reduce confidence for counter-trend
                # signal['confidence'] = max(signal['confidence'] - 3, 50)
            
        except Exception as e:
            logger.warning(f"Multi-timeframe filter error: {e}")
        
        return signal
    
    async def generate_signal_async(self, symbol: str, 
                                     chart_type: str = "japanese_candles") -> Optional[Dict]:
        """
        Async signal generation with alert integration
        
        Args:
            symbol: Trading symbol
            chart_type: Chart type for display
        
        Returns:
            Signal dict with full analysis
        """
        start_time = time.time()
        
        # Fetch data
        df = self.fetch_market_data(symbol)
        
        if df is None:
            return None
        
        # Analyze for breakout
        signal = self.analyze_breakout(df, symbol)
        
        if signal is None:
            return None
        
        # Apply multi-timeframe filter
        signal = self.apply_multi_timeframe_filter(signal, symbol)
        
        # Re-check confidence after filter
        if signal.get('confidence', 0) < self.min_confidence:
            return None
        
        # Track performance
        self.signals_generated += 1
        total_time = (time.time() - start_time) * 1000
        self.processing_times.append(total_time)
        signal['total_processing_time_ms'] = round(total_time, 2)
        
        # Send alert if enabled
        if self.enable_alerts:
            try:
                alert_result = await send_breakout_alert(signal)
                signal['alert_sent'] = alert_result.get('success', False)
                signal['alert_id'] = alert_result.get('alert_id', '')
            except Exception as e:
                logger.warning(f"Alert sending failed: {e}")
                signal['alert_sent'] = False
        
        logger.info(f"🎯 BREAKOUT SIGNAL: {symbol} {signal.get('direction')} @ {signal.get('confidence')}%")
        logger.info(f"   Type: {signal.get('breakout_type')}, Strength: {signal.get('strength')}")
        logger.info(f"   Processing: {total_time:.2f}ms (target <100ms: {'✅' if total_time < 100 else '⚠️'})")
        
        return signal
    
    def generate_signal(self, symbol: str, 
                        chart_type: str = "japanese_candles",
                        user_timeframes: List[str] = None) -> Optional[Dict]:
        """
        Synchronous signal generation (for compatibility)
        
        Args:
            symbol: Trading symbol
            chart_type: Chart type
            user_timeframes: User-selected timeframes
        
        Returns:
            Signal dict or None
        """
        start_time = time.time()
        
        # Fetch data
        df = self.fetch_market_data(symbol)
        
        if df is None:
            return None
        
        # Analyze for breakout
        signal = self.analyze_breakout(df, symbol)
        
        if signal is None:
            return None
        
        # Apply multi-timeframe filter (sync version)
        signal = self.apply_multi_timeframe_filter(signal, symbol)
        
        # Re-check confidence after filter
        if signal.get('confidence', 0) < self.min_confidence:
            return None
        
        # Track performance
        self.signals_generated += 1
        total_time = (time.time() - start_time) * 1000
        self.processing_times.append(total_time)
        signal['total_processing_time_ms'] = round(total_time, 2)
        
        return signal
    
    def get_performance_metrics(self) -> Dict:
        """Get strategy performance metrics"""
        predictor_metrics = self.breakout_predictor.get_performance_metrics()
        alert_stats = self.alert_manager.get_statistics()
        
        avg_time = sum(self.processing_times) / len(self.processing_times) if self.processing_times else 0
        
        return {
            "signals_generated": self.signals_generated,
            "avg_processing_time_ms": round(avg_time, 2),
            "max_processing_time_ms": round(max(self.processing_times), 2) if self.processing_times else 0,
            "latency_target_met": avg_time < 100,  # <100ms target
            "predictor_metrics": predictor_metrics,
            "alert_statistics": alert_stats,
            "config": self.config
        }
    
    def update_config(self, new_config: Dict) -> bool:
        """Update strategy configuration"""
        for key, value in new_config.items():
            if key in self.config:
                self.config[key] = value
        
        # Update component configs
        self.min_confidence = self.config.get('min_confidence', 75)
        self.enable_alerts = self.config.get('enable_alerts', True)
        self.enable_multi_timeframe = self.config.get('multi_timeframe_confirmation', False)
        
        logger.info(f"📝 Strategy config updated: {new_config}")
        return True


# ============================================================================
# INTEGRATION FUNCTIONS
# ============================================================================

# Global strategy instance
_breakout_strategy: Optional[FiveSecondBreakoutStrategy] = None


def get_breakout_strategy() -> FiveSecondBreakoutStrategy:
    """Get singleton breakout strategy instance"""
    global _breakout_strategy
    if _breakout_strategy is None:
        _breakout_strategy = FiveSecondBreakoutStrategy()
    return _breakout_strategy


def generate_5s_breakout_signal(symbol: str, 
                                 chart_type: str = "japanese_candles",
                                 user_timeframes: List[str] = None) -> Optional[Dict]:
    """
    Convenience function for signal generation
    Compatible with existing strategy interface
    """
    strategy = get_breakout_strategy()
    return strategy.generate_signal(symbol, chart_type, user_timeframes)


async def generate_5s_breakout_signal_async(symbol: str,
                                             chart_type: str = "japanese_candles") -> Optional[Dict]:
    """Async version for signal generation with alerts"""
    strategy = get_breakout_strategy()
    return await strategy.generate_signal_async(symbol, chart_type)


# ============================================================================
# CONFIGURATION YAML GENERATOR
# ============================================================================

def generate_config_yaml() -> str:
    """Generate YAML configuration template"""
    return """# Enhanced Breakout Predictor Configuration
# Optimized for 5-second timeframe trading

breakout_predictor:
  default_timeframe: "5s"
  enabled: true
  
  # Detection settings
  lookback_period: 15
  percentage_step: 0.5
  number_of_lines: 3
  min_breakout_strength: 0.4
  confirmation_bars: 1
  
  # Alert settings
  alerts:
    enabled: true
    sound: true
    popup: true
    
  # Webhook integration
  webhook:
    enabled: false
    url: ""
    format: "json"  # json, mt4, tradingview
    timeout_ms: 100
    retry_attempts: 3
    
  # MT4/MT5 Integration
  mt_integration:
    enabled: false
    bridge_port: 5555
    
  # Performance optimization
  optimization:
    buffer_size: 3000
    max_bars: 5000
    processing_delay_ms: 100
    
  # Multi-timeframe settings
  multi_timeframe:
    enabled: false
    confirmation_timeframe: "1m"
    
  # Confidence thresholds
  thresholds:
    min_confidence: 75
    high_confidence: 85
    ultra_confidence: 90
"""


# Save config template
def save_config_template():
    """Save configuration template to file"""
    config_path = "/app/backend/config/breakout_config.yaml"
    try:
        with open(config_path, 'w') as f:
            f.write(generate_config_yaml())
        logger.info(f"📄 Config template saved to {config_path}")
    except Exception as e:
        logger.error(f"Failed to save config template: {e}")
