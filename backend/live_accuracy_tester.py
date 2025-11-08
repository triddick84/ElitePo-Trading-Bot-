"""
Live Accuracy Testing System for Trading Strategies
Tracks real-time signal performance and calculates win rates
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging
from timezone_utils import get_chicago_time
from models import SignalDirection

logger = logging.getLogger(__name__)

class LiveAccuracyTester:
    """
    Tracks signals and their outcomes to calculate real accuracy
    """
    
    def __init__(self, db=None):
        self.db = db
        self.tracked_signals = {}  # signal_id -> signal data
        self.test_results = []
        
        logger.info("📊 Live Accuracy Tester initialized")
    
    async def register_signal(self, signal_id: str, signal_data: Dict) -> None:
        """
        Register a signal for tracking
        
        Args:
            signal_id: Unique signal identifier
            signal_data: Signal information including:
                - direction: BUY/SELL
                - entry_price: Entry price
                - entry_time: When signal was generated
                - expiration_minutes: How long to track
                - timeframe: Trading timeframe
                - strategy: Strategy name
                - confidence: Predicted confidence
        """
        try:
            self.tracked_signals[signal_id] = {
                **signal_data,
                'registered_at': get_chicago_time(),
                'status': 'pending',
                'outcome': None,
                'exit_price': None,
                'profit_loss': None
            }
            
            logger.info(f"📝 Registered signal {signal_id[:8]}... for tracking")
            
            # Schedule outcome check
            expiration_seconds = signal_data.get('expiration_minutes', 1) * 60
            asyncio.create_task(
                self._check_signal_outcome(signal_id, expiration_seconds)
            )
            
        except Exception as e:
            logger.error(f"Error registering signal: {e}")
    
    async def _check_signal_outcome(self, signal_id: str, wait_seconds: int) -> None:
        """
        Wait for expiration and check if signal was correct
        """
        try:
            # Wait for signal expiration
            await asyncio.sleep(wait_seconds)
            
            signal = self.tracked_signals.get(signal_id)
            if not signal:
                return
            
            # Get current market price (would need real market data service)
            # For now, we'll mark as needs_verification
            signal['status'] = 'needs_verification'
            signal['checked_at'] = get_chicago_time()
            
            logger.info(f"⏰ Signal {signal_id[:8]}... expired - Ready for verification")
            
            # Store result in database
            if self.db:
                await self.db.signal_tracking.update_one(
                    {'signal_id': signal_id},
                    {'$set': signal},
                    upsert=True
                )
            
        except Exception as e:
            logger.error(f"Error checking signal outcome: {e}")
    
    async def verify_signal_outcome(self, signal_id: str, exit_price: float) -> Dict:
        """
        Manually verify a signal's outcome with actual exit price
        
        Args:
            signal_id: Signal identifier
            exit_price: Actual price at expiration
            
        Returns:
            Updated signal data with outcome
        """
        try:
            signal = self.tracked_signals.get(signal_id)
            if not signal:
                return {'error': 'Signal not found'}
            
            entry_price = signal['entry_price']
            direction = signal['direction']
            
            # Determine if signal was correct
            price_change = exit_price - entry_price
            
            if direction == 'BUY' or direction == SignalDirection.BUY:
                won = price_change > 0
            else:  # SELL
                won = price_change < 0
            
            # Update signal data
            signal['status'] = 'verified'
            signal['outcome'] = 'WIN' if won else 'LOSS'
            signal['exit_price'] = exit_price
            signal['profit_loss'] = price_change
            signal['verified_at'] = get_chicago_time()
            
            # Store in test results
            self.test_results.append(signal)
            
            # Save to database
            if self.db:
                await self.db.signal_tracking.update_one(
                    {'signal_id': signal_id},
                    {'$set': signal},
                    upsert=True
                )
            
            logger.info(f"✅ Signal {signal_id[:8]}... verified: {signal['outcome']}")
            
            return signal
            
        except Exception as e:
            logger.error(f"Error verifying signal outcome: {e}")
            return {'error': str(e)}
    
    def calculate_accuracy_stats(self, strategy: Optional[str] = None, 
                                 timeframe: Optional[str] = None,
                                 time_range_hours: int = 24) -> Dict:
        """
        Calculate accuracy statistics
        
        Args:
            strategy: Filter by strategy name
            timeframe: Filter by timeframe
            time_range_hours: Only include signals from last N hours
            
        Returns:
            Accuracy statistics
        """
        try:
            # Filter results
            cutoff_time = get_chicago_time() - timedelta(hours=time_range_hours)
            
            filtered_results = [
                r for r in self.test_results
                if r.get('verified_at') and r.get('verified_at') > cutoff_time
                and r.get('status') == 'verified'
            ]
            
            if strategy:
                filtered_results = [r for r in filtered_results if r.get('strategy') == strategy]
            
            if timeframe:
                filtered_results = [r for r in filtered_results if r.get('timeframe') == timeframe]
            
            if not filtered_results:
                return {
                    'total_signals': 0,
                    'message': 'No verified signals in this period'
                }
            
            # Calculate stats
            total_signals = len(filtered_results)
            wins = len([r for r in filtered_results if r['outcome'] == 'WIN'])
            losses = len([r for r in filtered_results if r['outcome'] == 'LOSS'])
            
            win_rate = (wins / total_signals * 100) if total_signals > 0 else 0
            
            # Average confidence for wins vs losses
            win_confidences = [r['confidence'] for r in filtered_results if r['outcome'] == 'WIN']
            loss_confidences = [r['confidence'] for r in filtered_results if r['outcome'] == 'LOSS']
            
            avg_win_confidence = sum(win_confidences) / len(win_confidences) if win_confidences else 0
            avg_loss_confidence = sum(loss_confidences) / len(loss_confidences) if loss_confidences else 0
            
            # Performance by confidence level
            high_conf_signals = [r for r in filtered_results if r['confidence'] >= 80]
            high_conf_wins = len([r for r in high_conf_signals if r['outcome'] == 'WIN'])
            high_conf_rate = (high_conf_wins / len(high_conf_signals) * 100) if high_conf_signals else 0
            
            return {
                'total_signals': total_signals,
                'wins': wins,
                'losses': losses,
                'win_rate': round(win_rate, 2),
                'loss_rate': round(100 - win_rate, 2),
                'average_win_confidence': round(avg_win_confidence, 2),
                'average_loss_confidence': round(avg_loss_confidence, 2),
                'high_confidence_signals': len(high_conf_signals),
                'high_confidence_win_rate': round(high_conf_rate, 2),
                'time_range_hours': time_range_hours,
                'strategy': strategy or 'all',
                'timeframe': timeframe or 'all',
                'timestamp': get_chicago_time().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error calculating accuracy stats: {e}")
            return {'error': str(e)}
    
    def get_pending_signals(self) -> List[Dict]:
        """Get all signals awaiting verification"""
        return [
            {**s, 'signal_id': sid}
            for sid, s in self.tracked_signals.items()
            if s.get('status') == 'needs_verification'
        ]
    
    def get_recent_results(self, limit: int = 20) -> List[Dict]:
        """Get recent verified results"""
        sorted_results = sorted(
            self.test_results,
            key=lambda x: x.get('verified_at', datetime.min),
            reverse=True
        )
        return sorted_results[:limit]


# Global instance
live_accuracy_tester = LiveAccuracyTester()
