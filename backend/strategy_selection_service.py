"""
Strategy Selection Service
Manages user strategy preferences for each timeframe
"""

import logging
from typing import Dict, List, Optional
from motor.motor_asyncio import AsyncIOMotorClient
import os

logger = logging.getLogger(__name__)


class StrategySelectionService:
    """Manages strategy selection for different timeframes"""
    
    # Available strategies per timeframe
    AVAILABLE_STRATEGIES = {
        '5s': [
            {'id': 'default', 'name': 'Default 5s Strategy', 'description': 'Ultra Precision V2 with Bollinger Bands'},
            {'id': 'ema20_pullback_reversal', 'name': 'EMA 20 Pullback Reversal', 'description': 'EMA 20 trend + RSI-2 + BB(5,2.5) + Stoch(3,1,1) pullback reversal. Best for 5s expiry on volatile OTC pairs.', 'win_rate': '80-90%'},
            {'id': 'holly_crossover_5s', 'name': 'Holly Crossover 5s', 'description': 'EMA(12) x WMA(23) reversal crossover with S/R confirmation. Catches trend reversals.', 'win_rate': '75-85%'},
            {'id': 'turbo_precision_5s', 'name': 'Turbo Precision 5s', 'description': 'RSI + Stochastic RSI + EMA Ribbon. 4+ confirmations. Highest accuracy.', 'win_rate': '75-85%'},
            {'id': 'micro_compression_burst', 'name': 'Micro Compression Burst', 'description': 'BB breakout after 4-6 tight candles. 30s expiry. Best for calm/OTC markets.', 'win_rate': '75-85%'},
            {'id': 'keltner_breakout', 'name': 'Keltner Channel Breakout', 'description': 'EMA(20) + ATR(10) bands. Enter on breakout with volume.', 'win_rate': '70-80%'},
            {'id': 'candlestick_patterns', 'name': 'Candlestick Patterns', 'description': 'Engulfing, Hammer, Doji, Morning/Evening Star patterns', 'win_rate': '65-75%'},
            {'id': 'rsi_bb_scalp', 'name': 'RSI + Bollinger Scalp', 'description': 'RSI oversold/overbought with BB for quick scalps', 'win_rate': '70-80%'},
            {'id': 'proven_supertrend', 'name': 'ProvenSignals SuperTrend', 'description': 'ATR 10, Multiplier 5 - Trend following'},
        ],
        '15s': [
            {'id': 'default', 'name': 'Default 15s Strategy', 'description': 'Fractal-based reversal strategy'},
            {'id': 'holly_crossover_15s', 'name': '⭐⭐⭐ Holly Crossover 15s', 'description': 'EMA(12) x WMA(23) reversal crossover with S/R confirmation. Catches trend reversals.', 'win_rate': '75-85%'},
            {'id': 'momentum_buster_15s', 'name': '⭐⭐⭐ Momentum Buster 15s', 'description': 'Momentum(3) green/red bars with reversal detection. Ultra-fast scalping.', 'win_rate': '70-80%'},
            {'id': 'starc_cci_reversal', 'name': '⭐ STARC Bands + CCI Reversal', 'description': 'STARC(15,5,1.3) + CCI(10). 1m expiry. Smooth rhythmic markets.', 'win_rate': '70-80%'},
            {'id': 'macd_histogram', 'name': '⭐ MACD Histogram Reversal', 'description': 'MACD(12,26,9) histogram color change + divergence', 'win_rate': '70-80%'},
            {'id': 'candlestick_patterns', 'name': '⭐ Candlestick Patterns', 'description': 'Engulfing, Hammer, Doji, Morning/Evening Star patterns', 'win_rate': '65-75%'},
            {'id': 'rsi_bb_scalp', 'name': '⭐ RSI + Bollinger Scalp', 'description': 'RSI oversold/overbought with BB for quick scalps', 'win_rate': '70-80%'},
            {'id': 'stochastic_rsi_combo', 'name': '⭐ Stochastic + RSI Combo', 'description': 'Double confirmation with Stochastic and RSI', 'win_rate': '70-80%'},
            {'id': 'rsi_volume', 'name': 'RSI + Volume Reversal', 'description': 'RSI(14) oversold/overbought with volume spikes'},
            {'id': 'bollinger_ema', 'name': 'Bollinger + EMA Breakout', 'description': 'BB(20,2) breakouts confirmed by EMA(20)'},
            {'id': 'macd_rsi', 'name': 'MACD + RSI Trend', 'description': 'MACD(12,26,9) with RSI trend confirmation'},
            {'id': 'proven_rsi', 'name': 'ProvenSignals RSI', 'description': 'RSI Period 5 with divergence - Catches trend reversals'},
        ],
        '30s': [
            {'id': 'default', 'name': 'Default 30s Strategy', 'description': 'SuperTrend + MA Crossover'},
            {'id': 'holly_crossover_30s', 'name': '⭐⭐⭐ Holly Crossover 30s', 'description': 'EMA(12) x WMA(23) reversal crossover with S/R confirmation. Catches trend reversals.', 'win_rate': '75-85%'},
            {'id': 'golden_one_moment', 'name': '⭐⭐⭐ Golden One Moment', 'description': 'RSI(2) + Stochastic(4,3,3) mean reversion crossover. Precise 30s entries.', 'win_rate': '75-85%'},
            {'id': 'dynamic_ema_rsi', 'name': '⭐ Dynamic EMA + RSI Zone', 'description': 'EMA(13)/EMA(50) with RSI(14) 45-55 zone. 1m expiry.', 'win_rate': '75-85%'},
            {'id': 'otc_reverse', 'name': '⭐ OTC Market Reverse', 'description': 'RSI(7) + EMA(21) for OTC markets. Inverse signals on 3 losses.', 'win_rate': '70-80%'},
            {'id': 'keltner_breakout', 'name': '⭐ Keltner Channel Breakout', 'description': 'EMA(20) + ATR(10) bands. Enter on breakout.', 'win_rate': '70-80%'},
            {'id': 'rsi_bb_scalp', 'name': '⭐ RSI + Bollinger Scalp', 'description': 'RSI oversold/overbought with BB for quick scalps', 'win_rate': '70-80%'},
            {'id': 'stochastic_rsi_combo', 'name': '⭐ Stochastic + RSI Combo', 'description': 'Double confirmation with Stochastic and RSI', 'win_rate': '70-80%'},
            {'id': 'psar_fractals', 'name': 'Parabolic SAR + Fractals', 'description': 'SAR trend with fractal breakouts'},
            {'id': 'stochastic_adx', 'name': 'Stochastic + ADX', 'description': 'Stochastic(8,3,3) with ADX(14) momentum'},
            {'id': 'psar_stochastic', 'name': 'SAR + Stochastic', 'description': 'Combined SAR and Stochastic signals'},
        ],
        '1m': [
            {'id': 'default', 'name': 'Default 1m Strategy', 'description': 'High Accuracy strategies (Triple Confirmation, Williams/MACD, Smart Money)'},
            {'id': 'turbo_precision_1m', 'name': '⭐⭐⭐ Turbo Precision 1m', 'description': 'RSI + Stochastic RSI + EMA Ribbon. 4+ confirmations. Highest accuracy.', 'win_rate': '75-85%'},
            {'id': '1m_momentum_exhaustion', 'name': '⭐⭐⭐ Momentum Exhaustion Reversal', 'description': 'RSI-2 + Stochastic + BB + Candlestick patterns. Catches reversals at momentum extremes.', 'win_rate': '70-75%'},
            {'id': '1m_quad_crossover', 'name': '⭐⭐ Quad SMA/EMA Crossover', 'description': '2/5/10 SMA + 20 EMA crossovers. 4 rule system with trend/counter-trend signals.', 'win_rate': '80-85%'},
            {'id': 'zigzag_double_ma', 'name': '⭐ ZigZag + Double MA', 'description': 'ZigZag(5,4,3) + SMA(3)/SMA(6). Clear swings without spikes.', 'win_rate': '75-85%'},
            {'id': 'triple_supertrend', 'name': '⭐ Triple SuperTrend Confirmation', 'description': '3 SuperTrends + Heikin Ashi. 5m expiry. London/NY overlap.', 'win_rate': '80-90%'},
            {'id': 'ema_pullback', 'name': '⭐ EMA Pullback Strategy', 'description': 'EMA(8)/EMA(21) pullback entries. Strong trend continuation.', 'win_rate': '75-85%'},
            {'id': 'rsi_sr_reversal', 'name': '⭐ RSI + Support/Resistance Reversal', 'description': 'RSI(14) at 30/70 + S/R zones with doji confirmation', 'win_rate': '75-85%'},
            {'id': 'triple_confirmation', 'name': 'Triple Confirmation', 'description': '90%+ accuracy with 5 indicator confirmation'},
            {'id': 'smart_money', 'name': 'Smart Money ICT', 'description': 'Order blocks, FVGs, liquidity sweeps'},
        ],
        '2m': [
            {'id': 'default', 'name': 'Default 2m Strategy', 'description': 'Combined trend and momentum analysis'},
            {'id': 'ema_pullback', 'name': '⭐ EMA Pullback Strategy', 'description': 'EMA(8)/EMA(21) pullback entries. Strong trend continuation.', 'win_rate': '75-85%'},
            {'id': 'ema_macd_trend', 'name': '⭐ EMA + MACD Trend', 'description': 'EMA(9)/EMA(21) crossover with MACD confirmation', 'win_rate': '75-85%'},
            {'id': 'stochastic_rsi_combo', 'name': '⭐ Stochastic + RSI Combo', 'description': 'Double confirmation with Stochastic and RSI', 'win_rate': '70-80%'},
            {'id': 'triple_confirmation', 'name': 'Triple Confirmation', 'description': '90%+ accuracy with 5 indicator confirmation'},
        ],
        '3m': [
            {'id': 'default', 'name': 'Default 3m Strategy', 'description': 'Combined RSI + BB + MACD'},
            {'id': 'ema_pullback', 'name': '⭐ EMA Pullback Strategy', 'description': 'EMA(8)/EMA(21) pullback entries. Strong trend continuation.', 'win_rate': '75-85%'},
            {'id': 'ema_macd_trend', 'name': '⭐ EMA + MACD Trend', 'description': 'EMA(9)/EMA(21) crossover with MACD confirmation', 'win_rate': '75-85%'},
            {'id': 'ichimoku_cci', 'name': 'Ichimoku + CCI', 'description': 'Ichimoku Cloud with CCI momentum'},
            {'id': 'atr_sr', 'name': 'ATR + Support/Resistance', 'description': 'Volatility-based with key levels'},
            {'id': 'cci_rsi', 'name': 'CCI + RSI', 'description': 'Dual momentum confirmation'},
        ],
        '5m': [
            {'id': 'default', 'name': 'Default 5m Strategy', 'description': 'Combined RSI + BB + MACD'},
            {'id': 'ema_pullback', 'name': '⭐ EMA Pullback Strategy', 'description': 'EMA(8)/EMA(21) pullback entries. Strong trend continuation.', 'win_rate': '75-85%'},
            {'id': 'ema_macd_trend', 'name': '⭐ EMA + MACD Trend', 'description': 'EMA(9)/EMA(21) crossover with MACD confirmation', 'win_rate': '75-85%'},
            {'id': 'vwap_momentum', 'name': '⭐ VWAP Momentum', 'description': 'Volume-weighted momentum with EMA(9)', 'win_rate': '70-75%'},
            {'id': 'ichimoku_cci', 'name': 'Ichimoku + CCI', 'description': 'Ichimoku Cloud with CCI momentum'},
            {'id': 'atr_sr', 'name': 'ATR + Support/Resistance', 'description': 'Volatility-based with key levels'},
            {'id': 'cci_rsi', 'name': 'CCI + RSI', 'description': 'Dual momentum confirmation'},
        ],
    }
    
    def __init__(self):
        mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
        db_name = os.environ.get('DB_NAME', 'trading_bot_db')
        self.client = AsyncIOMotorClient(mongo_url)
        self.db = self.client[db_name]
        self.collection = self.db.strategy_selections
        
    async def get_selected_strategies(self) -> Dict[str, str]:
        """
        Get user's selected strategies for all timeframes
        Returns dict of {timeframe: strategy_id}
        """
        try:
            config = await self.collection.find_one({'type': 'strategy_selection'})
            
            if config:
                return config.get('selections', {})
            
            # Return defaults if no selection exists
            return {
                '5s': 'default',
                '15s': 'default',
                '30s': 'default',
                '1m': 'default',
                '3m': 'default',
                '5m': 'default',
            }
            
        except Exception as e:
            logger.error(f"Error getting selected strategies: {e}")
            return {}
    
    async def update_strategy_selection(self, timeframe: str, strategy_id: str) -> bool:
        """Update strategy selection for a specific timeframe"""
        try:
            # Validate timeframe and strategy
            if timeframe not in self.AVAILABLE_STRATEGIES:
                logger.error(f"Invalid timeframe: {timeframe}")
                return False
            
            available_ids = [s['id'] for s in self.AVAILABLE_STRATEGIES[timeframe]]
            if strategy_id not in available_ids:
                logger.error(f"Invalid strategy ID {strategy_id} for timeframe {timeframe}")
                return False
            
            # Update or create selection
            await self.collection.update_one(
                {'type': 'strategy_selection'},
                {'$set': {f'selections.{timeframe}': strategy_id}},
                upsert=True
            )
            
            logger.info(f"Updated strategy for {timeframe} to {strategy_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating strategy selection: {e}")
            return False
    
    async def get_strategy_details(self, timeframe: str, strategy_id: str) -> Optional[Dict]:
        """Get details for a specific strategy"""
        try:
            if timeframe not in self.AVAILABLE_STRATEGIES:
                return None
            
            for strategy in self.AVAILABLE_STRATEGIES[timeframe]:
                if strategy['id'] == strategy_id:
                    return strategy
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting strategy details: {e}")
            return None
    
    def get_available_strategies(self, timeframe: str) -> List[Dict]:
        """Get all available strategies for a timeframe"""
        return self.AVAILABLE_STRATEGIES.get(timeframe, [])
    
    def get_all_available_strategies(self) -> Dict[str, List[Dict]]:
        """Get all available strategies for all timeframes"""
        return self.AVAILABLE_STRATEGIES


# Global instance
strategy_selection_service = StrategySelectionService()
