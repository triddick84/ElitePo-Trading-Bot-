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
            {'id': 'keltner_fractal', 'name': 'Keltner Channel + Fractal', 'description': 'EMA(10) + ATR(10) Keltner with Fractal reversals'},
            {'id': '3ema_crossover', 'name': '3 EMA Crossover', 'description': 'EMA 3/8/20 crossover signals'},
            {'id': 'ema20_rsi14', 'name': 'EMA 20 + RSI 14', 'description': 'Momentum confirmation with EMA and RSI'},
            {'id': 'stochastic_divergence', 'name': 'Stochastic Divergence', 'description': 'Stochastic(14,3,14) with divergence confirmation - High win rate mean-reversion strategy'},
            {'id': 'proven_bollinger', 'name': 'ProvenSignals Bollinger Bands', 'description': 'Period 50, Dev 1.5 - Scalping oversold/overbought reversals'},
            {'id': 'proven_supertrend', 'name': 'ProvenSignals SuperTrend', 'description': 'ATR 10, Multiplier 5 - Trend following for trending markets'},
        ],
        '15s': [
            {'id': 'default', 'name': 'Default 15s Strategy', 'description': 'Fractal-based reversal strategy'},
            {'id': 'rsi_volume', 'name': 'RSI + Volume Reversal', 'description': 'RSI(14) oversold/overbought with volume spikes'},
            {'id': 'bollinger_ema', 'name': 'Bollinger + EMA Breakout', 'description': 'BB(20,2) breakouts confirmed by EMA(20)'},
            {'id': 'macd_rsi', 'name': 'MACD + RSI Trend', 'description': 'MACD(12,26,9) with RSI trend confirmation'},
            {'id': 'proven_rsi', 'name': 'ProvenSignals RSI', 'description': 'RSI Period 5 with divergence - Catches trend reversals with high accuracy'},
        ],
        '30s': [
            {'id': 'default', 'name': 'Default 30s Strategy', 'description': 'SuperTrend + MA Crossover'},
            {'id': 'psar_fractals', 'name': 'Parabolic SAR + Fractals', 'description': 'SAR trend with fractal breakouts'},
            {'id': 'stochastic_adx', 'name': 'Stochastic + ADX', 'description': 'Stochastic(8,3,3) with ADX(14) momentum'},
            {'id': 'psar_stochastic', 'name': 'SAR + Stochastic', 'description': 'Combined SAR and Stochastic signals'},
        ],
        '1m': [
            {'id': 'default', 'name': 'Default 1m Strategy', 'description': 'High Accuracy strategies (Triple Confirmation, Williams/MACD, Smart Money)'},
            {'id': 'triple_confirmation', 'name': 'Triple Confirmation', 'description': '90%+ accuracy with 5 indicator confirmation'},
            {'id': 'williams_macd', 'name': 'Williams %R + MACD', 'description': 'Turbo scalping for stable markets'},
            {'id': 'smart_money', 'name': 'Smart Money ICT', 'description': 'Order blocks, FVGs, liquidity sweeps'},
        ],
        '3m': [
            {'id': 'default', 'name': 'Default 3m Strategy', 'description': 'Combined RSI + BB + MACD'},
            {'id': 'ichimoku_cci', 'name': 'Ichimoku + CCI', 'description': 'Ichimoku Cloud with CCI momentum'},
            {'id': 'atr_sr', 'name': 'ATR + Support/Resistance', 'description': 'Volatility-based with key levels'},
            {'id': 'cci_rsi', 'name': 'CCI + RSI', 'description': 'Dual momentum confirmation'},
        ],
        '5m': [
            {'id': 'default', 'name': 'Default 5m Strategy', 'description': 'Combined RSI + BB + MACD'},
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
