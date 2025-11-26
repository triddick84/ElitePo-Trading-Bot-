"""
Adaptive Strategy Configuration Service
Manages user preferences for adaptive market condition strategies
"""

import logging
from typing import Dict, List, Optional
from motor.motor_asyncio import AsyncIOMotorClient
import os
from datetime import datetime, timezone
from models import AdaptiveStrategyConfig

logger = logging.getLogger(__name__)


class AdaptiveStrategyService:
    """Manages adaptive strategy configuration for users"""
    
    # Available indicators for users to choose from
    AVAILABLE_INDICATORS = [
        "MACD",
        "Parabolic_SAR",
        "EMA",
        "RSI",
        "Volume",
        "Bollinger_Bands",
        "Stochastic"
    ]
    
    # Default configurations
    DEFAULT_TRENDING_INDICATORS = ["MACD", "Parabolic_SAR", "EMA"]
    DEFAULT_RANGING_INDICATORS = ["RSI", "Volume", "Bollinger_Bands", "EMA"]
    
    def __init__(self, db):
        self.db = db
        self.collection = self.db.adaptive_strategy_config
        logger.info("🎯 Adaptive Strategy Service initialized")
    
    async def get_config(self, user_id: str = "default_user") -> AdaptiveStrategyConfig:
        """
        Get user's adaptive strategy configuration
        Returns default if no configuration exists
        """
        try:
            config_doc = await self.collection.find_one({'user_id': user_id})
            
            if config_doc:
                # Remove MongoDB _id field
                config_doc.pop('_id', None)
                return AdaptiveStrategyConfig(**config_doc)
            
            # Return default configuration
            default_config = AdaptiveStrategyConfig(
                user_id=user_id,
                enabled=True,
                adx_trending_threshold=25.0,
                adx_ranging_threshold=20.0,
                trending_indicators=self.DEFAULT_TRENDING_INDICATORS,
                ranging_indicators=self.DEFAULT_RANGING_INDICATORS,
                trending_execution_delay=3.0,
                ranging_execution_delay=1.5,
                ranging_signal_threshold=80.0
            )
            
            # Save default config
            await self.save_config(default_config)
            logger.info(f"✅ Created default adaptive strategy config for user {user_id}")
            
            return default_config
            
        except Exception as e:
            logger.error(f"Error getting adaptive strategy config: {e}")
            # Return safe default
            return AdaptiveStrategyConfig(user_id=user_id)
    
    async def save_config(self, config: AdaptiveStrategyConfig) -> bool:
        """Save or update adaptive strategy configuration"""
        try:
            config.updated_at = datetime.now(timezone.utc)
            config_dict = config.dict()
            
            # Upsert configuration
            await self.collection.update_one(
                {'user_id': config.user_id},
                {'$set': config_dict},
                upsert=True
            )
            
            logger.info(f"✅ Saved adaptive strategy config for user {config.user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving adaptive strategy config: {e}")
            return False
    
    async def update_config(self, user_id: str, updates: Dict) -> Optional[AdaptiveStrategyConfig]:
        """
        Update specific fields of adaptive strategy configuration
        """
        try:
            # Get current config
            current_config = await self.get_config(user_id)
            
            # Validate and update only provided fields
            if 'enabled' in updates:
                current_config.enabled = updates['enabled']
            
            if 'adx_trending_threshold' in updates:
                threshold = updates['adx_trending_threshold']
                if 15.0 <= threshold <= 50.0:
                    current_config.adx_trending_threshold = threshold
            
            if 'adx_ranging_threshold' in updates:
                threshold = updates['adx_ranging_threshold']
                if 10.0 <= threshold <= 30.0:
                    current_config.adx_ranging_threshold = threshold
            
            if 'trending_indicators' in updates:
                indicators = updates['trending_indicators']
                # Validate indicators
                if all(ind in self.AVAILABLE_INDICATORS for ind in indicators):
                    current_config.trending_indicators = indicators
                else:
                    logger.warning(f"Invalid trending indicators: {indicators}")
            
            if 'ranging_indicators' in updates:
                indicators = updates['ranging_indicators']
                # Validate indicators
                if all(ind in self.AVAILABLE_INDICATORS for ind in indicators):
                    current_config.ranging_indicators = indicators
                else:
                    logger.warning(f"Invalid ranging indicators: {indicators}")
            
            if 'trending_execution_delay' in updates:
                delay = updates['trending_execution_delay']
                if 0.5 <= delay <= 10.0:
                    current_config.trending_execution_delay = delay
            
            if 'ranging_execution_delay' in updates:
                delay = updates['ranging_execution_delay']
                if 0.5 <= delay <= 10.0:
                    current_config.ranging_execution_delay = delay
            
            if 'ranging_signal_threshold' in updates:
                threshold = updates['ranging_signal_threshold']
                if 70.0 <= threshold <= 95.0:
                    current_config.ranging_signal_threshold = threshold
            
            # Save updated config
            await self.save_config(current_config)
            logger.info(f"✅ Updated adaptive strategy config for user {user_id}")
            
            return current_config
            
        except Exception as e:
            logger.error(f"Error updating adaptive strategy config: {e}")
            return None
    
    def get_available_indicators(self) -> List[str]:
        """Get list of all available indicators"""
        return self.AVAILABLE_INDICATORS.copy()
    
    def validate_indicators(self, indicators: List[str]) -> bool:
        """Validate if all indicators in the list are available"""
        return all(ind in self.AVAILABLE_INDICATORS for ind in indicators)


# Create singleton instance - will be initialized in server.py
adaptive_strategy_service = None
