"""
Strategy Registry
Central registry for all trading strategies

Manages strategy selection, execution, and integration
"""

import logging
from typing import Dict, Optional, List
import pandas as pd

logger = logging.getLogger(__name__)


class StrategyRegistry:
    """
    Central registry for all trading strategies
    Provides strategy lookup, execution, and management
    """
    
    def __init__(self):
        self.strategies = {}
        self._load_strategies()
    
    def _load_strategies(self):
        """Load all available strategies"""
        try:
            # 5-second strategies
            from strategies.strategy_5s_momentum_breakout import strategy_5s_momentum_breakout
            from strategies.strategy_5s_price_action import strategy_5s_price_action
            self.strategies['5s_momentum_breakout'] = strategy_5s_momentum_breakout
            self.strategies['5s_price_action'] = strategy_5s_price_action
            
            # Fast Supertrend Catch - 5s contrarian strategy
            try:
                from strategies.fast_supertrend_catch import get_fast_supertrend_strategy
                self.strategies['5s_fast_supertrend_catch'] = get_fast_supertrend_strategy()
                logger.info("✅ Loaded Fast Supertrend Catch Strategy for 5s")
            except Exception as e:
                logger.warning(f"Could not load Fast Supertrend Catch: {e}")
            
            # Enhanced Breakout Predictor - 5s optimized
            try:
                from strategies.five_second_breakout import get_breakout_strategy
                self.strategies['5s_enhanced_breakout'] = get_breakout_strategy()
                logger.info("Loaded Enhanced Breakout Predictor for 5s")
            except Exception as e:
                logger.warning(f"Could not load Enhanced Breakout Predictor: {e}")
            
            # EMA 20 Pullback Reversal - 5s optimized
            try:
                from strategies.strategy_5s_ema20_pullback_reversal import strategy_5s_ema20_pullback_reversal
                self.strategies['5s_ema20_pullback_reversal'] = strategy_5s_ema20_pullback_reversal
                logger.info("Loaded EMA 20 Pullback Reversal Strategy for 5s")
            except Exception as e:
                logger.warning(f"Could not load EMA 20 Pullback Reversal: {e}")
            
            # 15-second strategies
            from strategies.strategy_15s_ema_crossover import strategy_15s_ema_crossover
            from strategies.strategy_15s_rsi_stochastic import strategy_15s_rsi_stochastic
            self.strategies['15s_ema_crossover'] = strategy_15s_ema_crossover
            self.strategies['15s_rsi_stochastic'] = strategy_15s_rsi_stochastic
            
            # NEW: 15s Triple Confluence (High Accuracy - 85%+ target)
            try:
                from strategies.strategy_15s_triple_confluence import strategy_15s_triple_confluence
                self.strategies['15s_triple_confluence'] = strategy_15s_triple_confluence
                logger.info("✅ Loaded 15s Triple Confluence Strategy (RSI+Stoch+BB)")
            except Exception as e:
                logger.warning(f"Could not load 15s Triple Confluence: {e}")
            
            # NEW: 15s EMA Cascade (3-5-8-13)
            try:
                from strategies.strategy_15s_ema_cascade import strategy_15s_ema_cascade
                self.strategies['15s_ema_cascade'] = strategy_15s_ema_cascade
                logger.info("✅ Loaded 15s EMA Cascade Strategy (3-5-8-13)")
            except Exception as e:
                logger.warning(f"Could not load 15s EMA Cascade: {e}")
            
            # 30-second strategies
            from strategies.strategy_30s_bollinger_rsi import strategy_30s_bollinger_rsi
            from strategies.strategy_30s_macd_keltner import strategy_30s_macd_keltner
            self.strategies['30s_bollinger_rsi'] = strategy_30s_bollinger_rsi
            self.strategies['30s_macd_keltner'] = strategy_30s_macd_keltner
            
            # NEW: 30s Williams %R + ADX + ATR (High Accuracy - 83%+ target)
            try:
                from strategies.strategy_30s_williams_adx_atr import strategy_30s_williams_adx_atr
                self.strategies['30s_williams_adx_atr'] = strategy_30s_williams_adx_atr
                logger.info("✅ Loaded 30s Williams+ADX+ATR Strategy")
            except Exception as e:
                logger.warning(f"Could not load 30s Williams+ADX+ATR: {e}")
            
            # NEW: 30s VWAP Momentum
            try:
                from strategies.strategy_30s_vwap_momentum import strategy_30s_vwap_momentum
                self.strategies['30s_vwap_momentum'] = strategy_30s_vwap_momentum
                logger.info("✅ Loaded 30s VWAP Momentum Strategy")
            except Exception as e:
                logger.warning(f"Could not load 30s VWAP Momentum: {e}")
            
            # 1-minute strategies
            from strategies.strategy_1m_rsi_divergence import strategy_1m_rsi_divergence
            from strategies.strategy_1m_triple_ema import strategy_1m_triple_ema
            self.strategies['1m_rsi_divergence'] = strategy_1m_rsi_divergence
            self.strategies['1m_triple_ema'] = strategy_1m_triple_ema
            
            # NEW: 1m Quad SMA/EMA Crossover Strategy (High Accuracy - 80%+ target)
            try:
                from strategies.strategy_1m_quad_crossover import strategy_1m_quad_crossover
                self.strategies['1m_quad_crossover'] = strategy_1m_quad_crossover
                logger.info("✅ Loaded 1m Quad SMA/EMA Crossover Strategy (2/5/10 SMA + 20 EMA)")
            except Exception as e:
                logger.warning(f"Could not load 1m Quad Crossover: {e}")
            
            # NEW: 1m Momentum Exhaustion Reversal Strategy (70-75% target)
            try:
                from strategies.strategy_1m_momentum_exhaustion import momentum_exhaustion_strategy
                self.strategies['1m_momentum_exhaustion'] = momentum_exhaustion_strategy
                logger.info("✅ Loaded 1m Momentum Exhaustion Strategy (RSI-2, Stochastic, BB, Candles)")
            except Exception as e:
                logger.warning(f"Could not load 1m Momentum Exhaustion: {e}")
            
            # NEW: Turbo Precision Strategy (75-85% target) - Works for both 5s and 1m
            try:
                from strategies.strategy_turbo_precision import turbo_precision_5s, turbo_precision_1m
                self.strategies['turbo_precision_5s'] = turbo_precision_5s
                self.strategies['turbo_precision_1m'] = turbo_precision_1m
                logger.info("✅ Loaded Turbo Precision Strategy (5s + 1m, 4+ confirmations)")
            except Exception as e:
                logger.warning(f"Could not load Turbo Precision: {e}")
            
            # 2-minute strategies
            from strategies.strategy_2m_support_resistance import strategy_2m_support_resistance
            from strategies.strategy_2m_trend_momentum import strategy_2m_trend_momentum
            self.strategies['2m_support_resistance'] = strategy_2m_support_resistance
            self.strategies['2m_trend_momentum'] = strategy_2m_trend_momentum
            
            # 3-minute strategies
            from strategies.strategy_3m_volume_profile import strategy_3m_volume_profile
            from strategies.strategy_3m_price_action import strategy_3m_price_action
            self.strategies['3m_volume_profile'] = strategy_3m_volume_profile
            self.strategies['3m_price_action'] = strategy_3m_price_action
            
            # 5-minute strategies
            from strategies.strategy_5m_trend_following import strategy_5m_trend_following
            from strategies.strategy_5m_breakout import strategy_5m_breakout
            self.strategies['5m_trend_following'] = strategy_5m_trend_following
            self.strategies['5m_breakout'] = strategy_5m_breakout
            
            # 15-minute strategies
            from strategies.strategy_15m_multi_timeframe import strategy_15m_multi_timeframe
            from strategies.strategy_15m_swing_trading import strategy_15m_swing_trading
            self.strategies['15m_multi_timeframe'] = strategy_15m_multi_timeframe
            self.strategies['15m_swing_trading'] = strategy_15m_swing_trading
            
            # 30-minute strategies
            from strategies.strategy_30m_ichimoku import strategy_30m_ichimoku
            from strategies.strategy_30m_position_trading import strategy_30m_position_trading
            self.strategies['30m_ichimoku'] = strategy_30m_ichimoku
            self.strategies['30m_position_trading'] = strategy_30m_position_trading
            
            # 1-hour strategies
            from strategies.strategy_1h_wyckoff import strategy_1h_wyckoff
            from strategies.strategy_1h_daily_bias import strategy_1h_daily_bias
            self.strategies['1h_wyckoff'] = strategy_1h_wyckoff
            self.strategies['1h_daily_bias'] = strategy_1h_daily_bias

            # 1m 21-Second Reversal (timing-based contrarian, paired with Tampermonkey)
            try:
                from strategies.strategy_1m_21s_reversal import strategy_1m_21s_reversal
                self.strategies['1m_21s_reversal'] = strategy_1m_21s_reversal
                logger.info("✅ Loaded 1m 21s Reversal Strategy (timing contrarian)")
            except Exception as e:
                logger.warning(f"Could not load 1m 21s Reversal: {e}")

            # NEW (BETA): Fibonacci Confluence — 30s / 1m / 5m
            try:
                from strategies.strategy_fibonacci_confluence import (
                    strategy_fibonacci_confluence_30s,
                    strategy_fibonacci_confluence_1m,
                    strategy_fibonacci_confluence_5m,
                )
                self.strategies['30s_fibonacci_confluence'] = strategy_fibonacci_confluence_30s
                self.strategies['1m_fibonacci_confluence'] = strategy_fibonacci_confluence_1m
                self.strategies['5m_fibonacci_confluence'] = strategy_fibonacci_confluence_5m
                logger.info("✅ Loaded Fibonacci Confluence Strategy (30s/1m/5m, BETA)")
            except Exception as e:
                logger.warning(f"Could not load Fibonacci Confluence: {e}")

            # NEW (BETA): Triple Confirmation — 30s / 1m / 5m
            try:
                from strategies.strategy_triple_confirmation import (
                    strategy_triple_confirmation_30s,
                    strategy_triple_confirmation_1m,
                    strategy_triple_confirmation_5m,
                )
                self.strategies['30s_triple_confirmation'] = strategy_triple_confirmation_30s
                self.strategies['1m_triple_confirmation'] = strategy_triple_confirmation_1m
                self.strategies['5m_triple_confirmation'] = strategy_triple_confirmation_5m
                logger.info("✅ Loaded Triple Confirmation Strategy (30s/1m/5m, BETA)")
            except Exception as e:
                logger.warning(f"Could not load Triple Confirmation: {e}")
            
            # Legacy strategies (keep for backward compatibility)
            self.strategies['enhanced_rsi_bb_volume'] = None  # Placeholder
            self.strategies['enhanced_stoch_macd_pattern'] = None  # Placeholder
            
            logger.info(f"✅ Loaded {len(self.strategies)} strategies into registry")
            
        except Exception as e:
            logger.error(f"❌ Error loading strategies: {e}")
    
    def get_strategy(self, strategy_name: str):
        """Get strategy by name"""
        strategy = self.strategies.get(strategy_name)
        if strategy is None:
            logger.warning(f"Strategy '{strategy_name}' not found in registry")
        return strategy
    
    def list_strategies(self, timeframe: Optional[str] = None) -> List[Dict]:
        """
        List all available strategies
        
        Args:
            timeframe: Filter by timeframe (optional)
        
        Returns:
            List of strategy info dicts
        """
        strategy_list = []
        
        for name, strategy in self.strategies.items():
            if strategy is None:
                continue
            
            # Filter by timeframe if specified
            if timeframe and hasattr(strategy, 'timeframe'):
                if strategy.timeframe != timeframe:
                    continue
            
            strategy_info = {
                'name': name,
                'display_name': strategy.name if hasattr(strategy, 'name') else name,
                'timeframe': strategy.timeframe if hasattr(strategy, 'timeframe') else 'unknown',
                'accuracy_target': strategy.accuracy_target if hasattr(strategy, 'accuracy_target') else 0,
                'beta': bool(getattr(strategy, 'beta', False)),
            }
            strategy_list.append(strategy_info)
        
        return strategy_list
    
    def execute_strategy(self, strategy_name: str, df: pd.DataFrame) -> Dict:
        """
        Execute a strategy on given data
        
        Args:
            strategy_name: Name of strategy to execute
            df: DataFrame with OHLCV data
        
        Returns:
            Signal result dict
        """
        strategy = self.get_strategy(strategy_name)
        
        if strategy is None:
            return {
                'direction': 'NEUTRAL',
                'confidence': 0,
                'reason': f'Strategy "{strategy_name}" not found',
                'strategy': strategy_name
            }
        
        try:
            result = strategy.generate_signal(df)
            return result
            
        except Exception as e:
            logger.error(f"Error executing strategy '{strategy_name}': {e}")
            return {
                'direction': 'NEUTRAL',
                'confidence': 0,
                'reason': f'Strategy execution error: {str(e)}',
                'strategy': strategy_name
            }
    
    def get_strategies_by_timeframe(self) -> Dict[str, List[str]]:
        """
        Group strategies by timeframe
        
        Returns:
            Dict mapping timeframe to list of strategy names
        """
        grouped = {}
        
        for name, strategy in self.strategies.items():
            if strategy is None:
                continue
            
            timeframe = strategy.timeframe if hasattr(strategy, 'timeframe') else 'unknown'
            
            if timeframe not in grouped:
                grouped[timeframe] = []
            
            grouped[timeframe].append(name)
        
        return grouped


# Global instance
strategy_registry = StrategyRegistry()
