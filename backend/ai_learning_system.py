"""
AI Learning System - Self-improving signal generation
Analyzes validation results and adjusts strategies to improve accuracy
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from motor.motor_asyncio import AsyncIOMotorClient
from collections import defaultdict
import numpy as np
import os
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

class AILearningSystem:
    """
    Self-learning AI that improves signal generation based on validation results
    """
    
    def __init__(self):
        self.mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
        self.db_name = os.environ.get('DB_NAME', 'trading_bot')
        self.client = None
        self.db = None
        
        # Learning parameters
        self.min_samples_for_learning = 10  # Minimum signals before adjusting
        self.learning_rate = 0.1  # How aggressive adjustments are (0.0-1.0)
        self.confidence_threshold = 0.65  # Target minimum win rate
        
        # Current strategy adjustments (loaded from DB or defaults)
        self.strategy_adjustments = {
            'indicator_weights': {
                'rsi': 1.0,
                'ema': 1.0,
                'macd': 1.0,
                'bollinger': 1.0,
                'volume': 0.8,
                'stochastic': 0.9
            },
            'thresholds': {
                'rsi_oversold': 30,
                'rsi_overbought': 70,
                'probability_boost': 1.0,
                'confidence_boost': 1.0
            },
            'strategy_preferences': {
                'trending_market_weight': 1.0,
                'ranging_market_weight': 1.0,
                'volatility_adjustment': 1.0
            }
        }
        
    async def initialize(self):
        """Initialize MongoDB connection and load saved adjustments"""
        try:
            self.client = AsyncIOMotorClient(self.mongo_url)
            self.db = self.client[self.db_name]
            
            # Load saved adjustments
            saved_adjustments = await self.db.ai_learning_state.find_one({'_id': 'current'})
            if saved_adjustments:
                self.strategy_adjustments = saved_adjustments.get('adjustments', self.strategy_adjustments)
                logger.info("📚 Loaded AI learning state from database")
            else:
                # Save initial state
                await self._save_adjustments()
                logger.info("🆕 Initialized new AI learning state")
            
            logger.info("✅ AI Learning System initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize AI Learning System: {e}")
    
    async def analyze_and_learn(self):
        """
        Main learning loop - analyzes recent validations and adjusts strategies
        Should be called periodically (e.g., every hour or after N validations)
        """
        try:
            logger.info("🧠 AI Learning System: Starting analysis...")
            
            # Fetch recent validations
            validations = await self._fetch_recent_validations(hours=24, min_count=self.min_samples_for_learning)
            
            if len(validations) < self.min_samples_for_learning:
                logger.info(f"📊 Insufficient data for learning ({len(validations)} < {self.min_samples_for_learning})")
                return
            
            # Calculate current performance
            current_performance = self._calculate_performance(validations)
            logger.info(f"📈 Current Performance: {current_performance['win_rate']:.1f}% win rate")
            
            # Analyze patterns in winning vs losing signals
            patterns = await self._analyze_patterns(validations)
            
            # Generate adjustments based on patterns
            adjustments_made = await self._generate_adjustments(patterns, current_performance)
            
            if adjustments_made:
                # Save adjustments
                await self._save_adjustments()
                logger.info(f"✅ AI Learning: Applied {adjustments_made} adjustments")
            else:
                logger.info("✅ AI Learning: No adjustments needed - performance is good")
                
        except Exception as e:
            logger.error(f"❌ Error in AI learning cycle: {e}")
    
    async def _fetch_recent_validations(self, hours: int = 24, min_count: int = 10) -> List[Dict]:
        """Fetch recent validated signals"""
        try:
            query = {
                'validated_at': {
                    '$gte': (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
                }
            }
            
            validations = await self.db.signal_validations.find(query).to_list(1000)
            return validations
        except Exception as e:
            logger.error(f"❌ Error fetching validations: {e}")
            return []
    
    def _calculate_performance(self, validations: List[Dict]) -> Dict:
        """Calculate overall performance metrics"""
        total = len(validations)
        wins = sum(1 for v in validations if v['result'] == 'WIN')
        losses = total - wins
        win_rate = (wins / total) if total > 0 else 0
        
        # Calculate by direction
        buy_signals = [v for v in validations if v['direction'] in ['BUY', 'CALL']]
        sell_signals = [v for v in validations if v['direction'] in ['SELL', 'PUT']]
        
        buy_win_rate = sum(1 for v in buy_signals if v['result'] == 'WIN') / len(buy_signals) if buy_signals else 0
        sell_win_rate = sum(1 for v in sell_signals if v['result'] == 'WIN') / len(sell_signals) if sell_signals else 0
        
        # Calculate average price change
        avg_change = np.mean([v['price_change_percent'] for v in validations])
        
        return {
            'total': total,
            'wins': wins,
            'losses': losses,
            'win_rate': win_rate,
            'buy_win_rate': buy_win_rate,
            'sell_win_rate': sell_win_rate,
            'avg_change': avg_change
        }
    
    async def _analyze_patterns(self, validations: List[Dict]) -> Dict:
        """
        Analyze patterns in winning vs losing signals
        Identifies what makes winning signals different from losing ones
        """
        try:
            winning_signals = [v for v in validations if v['result'] == 'WIN']
            losing_signals = [v for v in validations if v['result'] == 'LOSS']
            
            patterns = {
                'direction_performance': self._analyze_direction_performance(winning_signals, losing_signals),
                'timeframe_performance': self._analyze_timeframe_performance(winning_signals, losing_signals),
                'price_movement': self._analyze_price_movements(winning_signals, losing_signals),
                'market_conditions': await self._analyze_market_conditions(validations)
            }
            
            return patterns
        except Exception as e:
            logger.error(f"❌ Error analyzing patterns: {e}")
            return {}
    
    def _analyze_direction_performance(self, wins: List[Dict], losses: List[Dict]) -> Dict:
        """Analyze BUY vs SELL performance"""
        buy_wins = sum(1 for v in wins if v['direction'] in ['BUY', 'CALL'])
        sell_wins = sum(1 for v in wins if v['direction'] in ['SELL', 'PUT'])
        
        buy_losses = sum(1 for v in losses if v['direction'] in ['BUY', 'CALL'])
        sell_losses = sum(1 for v in losses if v['direction'] in ['SELL', 'PUT'])
        
        buy_total = buy_wins + buy_losses
        sell_total = sell_wins + sell_losses
        
        return {
            'buy_win_rate': (buy_wins / buy_total) if buy_total > 0 else 0.5,
            'sell_win_rate': (sell_wins / sell_total) if sell_total > 0 else 0.5,
            'buy_bias': buy_wins - buy_losses,
            'sell_bias': sell_wins - sell_losses
        }
    
    def _analyze_timeframe_performance(self, wins: List[Dict], losses: List[Dict]) -> Dict:
        """Analyze performance per timeframe"""
        timeframe_stats = defaultdict(lambda: {'wins': 0, 'losses': 0})
        
        for v in wins:
            tf = self._minutes_to_timeframe(v['expiration_minutes'])
            timeframe_stats[tf]['wins'] += 1
            
        for v in losses:
            tf = self._minutes_to_timeframe(v['expiration_minutes'])
            timeframe_stats[tf]['losses'] += 1
        
        # Calculate win rates
        results = {}
        for tf, stats in timeframe_stats.items():
            total = stats['wins'] + stats['losses']
            win_rate = stats['wins'] / total if total > 0 else 0.5
            results[tf] = {
                'win_rate': win_rate,
                'total': total
            }
        
        return results
    
    def _analyze_price_movements(self, wins: List[Dict], losses: List[Dict]) -> Dict:
        """Analyze typical price movements in wins vs losses"""
        win_changes = [abs(v['price_change_percent']) for v in wins]
        loss_changes = [abs(v['price_change_percent']) for v in losses]
        
        return {
            'avg_win_movement': np.mean(win_changes) if win_changes else 0,
            'avg_loss_movement': np.mean(loss_changes) if loss_changes else 0,
            'win_volatility': np.std(win_changes) if len(win_changes) > 1 else 0,
            'loss_volatility': np.std(loss_changes) if len(loss_changes) > 1 else 0
        }
    
    async def _analyze_market_conditions(self, validations: List[Dict]) -> Dict:
        """Analyze which market conditions produce better results"""
        # Group by symbol and time of day
        symbol_performance = defaultdict(lambda: {'wins': 0, 'total': 0})
        hour_performance = defaultdict(lambda: {'wins': 0, 'total': 0})
        
        for v in validations:
            symbol = v['symbol']
            is_win = v['result'] == 'WIN'
            
            symbol_performance[symbol]['total'] += 1
            if is_win:
                symbol_performance[symbol]['wins'] += 1
            
            # Time of day
            try:
                hour = datetime.fromisoformat(v['validated_at'].replace('Z', '+00:00')).hour
                hour_performance[hour]['total'] += 1
                if is_win:
                    hour_performance[hour]['wins'] += 1
            except:
                pass
        
        # Calculate win rates
        best_symbols = {sym: stats['wins'] / stats['total'] 
                       for sym, stats in symbol_performance.items() if stats['total'] >= 3}
        best_hours = {hour: stats['wins'] / stats['total']
                     for hour, stats in hour_performance.items() if stats['total'] >= 3}
        
        return {
            'symbol_performance': best_symbols,
            'hour_performance': best_hours
        }
    
    async def _generate_adjustments(self, patterns: Dict, performance: Dict) -> int:
        """
        Generate strategy adjustments based on identified patterns
        Returns number of adjustments made
        """
        adjustments_made = 0
        
        # If overall win rate is good, make minimal adjustments
        if performance['win_rate'] >= 0.75:
            logger.info("✅ Performance is excellent (≥75%), maintaining current settings")
            return 0
        
        # Adjust based on direction performance
        if 'direction_performance' in patterns:
            dir_perf = patterns['direction_performance']
            
            # If BUY signals performing poorly, increase confidence threshold for BUY
            if dir_perf['buy_win_rate'] < self.confidence_threshold:
                adjustment = (self.confidence_threshold - dir_perf['buy_win_rate']) * self.learning_rate
                self.strategy_adjustments['thresholds']['probability_boost'] *= (1 - adjustment)
                logger.info(f"🔧 Adjusting BUY signal threshold: {adjustment:.2%} stricter")
                adjustments_made += 1
            
            # If SELL signals performing poorly
            if dir_perf['sell_win_rate'] < self.confidence_threshold:
                adjustment = (self.confidence_threshold - dir_perf['sell_win_rate']) * self.learning_rate
                self.strategy_adjustments['thresholds']['probability_boost'] *= (1 - adjustment)
                logger.info(f"🔧 Adjusting SELL signal threshold: {adjustment:.2%} stricter")
                adjustments_made += 1
        
        # Adjust indicator weights based on performance
        if performance['win_rate'] < 0.65:
            # Increase RSI weight if win rate is low
            self.strategy_adjustments['indicator_weights']['rsi'] *= 1.05
            logger.info("🔧 Increased RSI weight by 5%")
            adjustments_made += 1
            
            # Adjust confidence boost
            self.strategy_adjustments['thresholds']['confidence_boost'] *= 1.1
            logger.info("🔧 Increased confidence boost by 10%")
            adjustments_made += 1
        
        # Adjust timeframe preferences
        if 'timeframe_performance' in patterns:
            for tf, stats in patterns['timeframe_performance'].items():
                if stats['total'] >= 5 and stats['win_rate'] < 0.6:
                    logger.info(f"⚠️ Timeframe {tf} underperforming: {stats['win_rate']:.1%}")
                    # Could reduce weighting for this timeframe
        
        return adjustments_made
    
    def get_current_adjustments(self) -> Dict:
        """Get current strategy adjustments to apply to signal generation"""
        return self.strategy_adjustments
    
    async def _save_adjustments(self):
        """Save current adjustments to database"""
        try:
            await self.db.ai_learning_state.update_one(
                {'_id': 'current'},
                {
                    '$set': {
                        'adjustments': self.strategy_adjustments,
                        'updated_at': datetime.now(timezone.utc).isoformat()
                    }
                },
                upsert=True
            )
            logger.info("💾 Saved AI learning adjustments")
        except Exception as e:
            logger.error(f"❌ Error saving adjustments: {e}")
    
    def _minutes_to_timeframe(self, minutes: float) -> str:
        """Convert minutes to timeframe string"""
        if minutes < 0.1:
            return '5s'
        elif minutes < 0.3:
            return '15s'
        elif minutes < 0.6:
            return '30s'
        elif minutes < 1.5:
            return '1m'
        elif minutes < 2.5:
            return '2m'
        elif minutes < 4:
            return '3m'
        else:
            return '5m'
    
    async def generate_learning_report(self) -> Dict:
        """Generate a detailed learning report"""
        try:
            validations = await self._fetch_recent_validations(hours=168)  # Last week
            
            if not validations:
                return {
                    'status': 'insufficient_data',
                    'message': 'Not enough validation data to generate report'
                }
            
            performance = self._calculate_performance(validations)
            patterns = await self._analyze_patterns(validations)
            
            return {
                'status': 'success',
                'period': '7 days',
                'performance': performance,
                'patterns': patterns,
                'current_adjustments': self.strategy_adjustments,
                'recommendations': self._generate_recommendations(performance, patterns)
            }
        except Exception as e:
            logger.error(f"❌ Error generating report: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def _generate_recommendations(self, performance: Dict, patterns: Dict) -> List[str]:
        """Generate human-readable recommendations"""
        recommendations = []
        
        if performance['win_rate'] < 0.65:
            recommendations.append("⚠️ Overall win rate below target (65%). System will adjust thresholds.")
        
        if performance['buy_win_rate'] < performance['sell_win_rate'] - 0.15:
            recommendations.append("📊 BUY signals underperforming vs SELL. Increasing BUY signal requirements.")
        elif performance['sell_win_rate'] < performance['buy_win_rate'] - 0.15:
            recommendations.append("📊 SELL signals underperforming vs BUY. Increasing SELL signal requirements.")
        
        if performance['win_rate'] >= 0.75:
            recommendations.append("✅ Excellent performance! Maintaining current strategy parameters.")
        
        return recommendations
    
    async def cleanup(self):
        """Cleanup resources"""
        if self.client:
            self.client.close()
            logger.info("✅ AI Learning System cleaned up")

# Global instance
ai_learning_system = AILearningSystem()
