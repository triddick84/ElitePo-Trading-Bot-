"""
Automated Trading Service
Connects signal generation with automated order execution via Bridge Script
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from collections import deque

logger = logging.getLogger(__name__)


class AutomatedTradingService:
    """
    Automated trading service that:
    1. Receives signals from strategy engines
    2. Applies risk management (money management system)
    3. Executes trades via Pocket Option Bridge Script
    4. Tracks results and performance
    """
    
    def __init__(self, db):
        self.db = db
        self.is_enabled = False
        self.is_running = False
        
        # Trading state
        self.pending_orders = {}
        self.active_orders = {}
        self.completed_orders = deque(maxlen=500)
        
        # Statistics
        self.total_trades = 0
        self.wins = 0
        self.losses = 0
        self.draws = 0
        
        # Configuration
        self.default_stake = 1.0
        self.max_concurrent_trades = 5
        self.min_confidence = 70.0
        self.use_money_management = True
        self.use_risk_rules = True
        
        logger.info("🤖 Automated Trading Service initialized")
    
    async def load_config(self):
        """Load configuration from database"""
        try:
            config = await self.db.automated_trading_config.find_one(
                {"user_id": "default_user"},
                {"_id": 0}
            )
            
            if config:
                self.is_enabled = config.get('enabled', False)
                self.default_stake = config.get('default_stake', 1.0)
                self.max_concurrent_trades = config.get('max_concurrent_trades', 5)
                self.min_confidence = config.get('min_confidence', 70.0)
                self.use_money_management = config.get('use_money_management', True)
                self.use_risk_rules = config.get('use_risk_rules', True)
                
                logger.info(f"✅ Loaded config: Enabled={self.is_enabled}, MinConf={self.min_confidence}%")
            else:
                await self.save_config()
                
        except Exception as e:
            logger.error(f"Error loading config: {e}")
    
    async def save_config(self):
        """Save configuration to database"""
        try:
            config = {
                "user_id": "default_user",
                "enabled": self.is_enabled,
                "default_stake": self.default_stake,
                "max_concurrent_trades": self.max_concurrent_trades,
                "min_confidence": self.min_confidence,
                "use_money_management": self.use_money_management,
                "use_risk_rules": self.use_risk_rules,
                "updated_at": datetime.now(timezone.utc)
            }
            
            await self.db.automated_trading_config.replace_one(
                {"user_id": "default_user"},
                config,
                upsert=True
            )
            
        except Exception as e:
            logger.error(f"Error saving config: {e}")
    
    async def process_signal(self, signal: Dict[str, Any]) -> Optional[Dict]:
        """
        Process a trading signal and potentially execute a trade
        
        Args:
            signal: Trading signal with asset, direction, confidence, etc.
        
        Returns:
            Trade execution result or None if not executed
        """
        if not self.is_enabled:
            logger.debug("Automated trading disabled - signal ignored")
            return None
        
        try:
            # Extract signal details
            asset = signal.get('symbol', 'EURUSD_OTC')
            direction = signal.get('direction', 'call')
            confidence = signal.get('probability', 0)
            timeframe = signal.get('timeframe', 60)
            strategy = signal.get('strategy', 'unknown')
            
            # Validate confidence
            if confidence < self.min_confidence:
                logger.debug(f"Signal confidence {confidence}% below minimum {self.min_confidence}%")
                return None
            
            # Check concurrent trades limit
            if len(self.active_orders) >= self.max_concurrent_trades:
                logger.warning(f"Max concurrent trades ({self.max_concurrent_trades}) reached")
                return None
            
            # Calculate stake
            stake = await self._calculate_stake(confidence, asset)
            
            if not stake or stake <= 0:
                logger.warning("Stake calculation returned 0 or None")
                return None
            
            # Check risk rules
            if self.use_risk_rules:
                can_trade = await self._check_risk_rules(asset, stake)
                if not can_trade:
                    logger.info(f"Risk rules prevented trade on {asset}")
                    return None
            
            # Execute trade
            result = await self._execute_trade(
                asset=asset,
                direction=direction,
                amount=stake,
                duration=timeframe,
                confidence=confidence,
                strategy=strategy
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing signal: {e}")
            return None
    
    async def _calculate_stake(self, confidence: float, asset: str) -> float:
        """Calculate stake using money management system"""
        try:
            if not self.use_money_management:
                return self.default_stake
            
            # Import money management system
            from money_management_system import MoneyManagementSystem
            
            # Get balance (from bridge or API)
            balance = await self._get_current_balance()
            
            # Calculate stake
            mm_system = MoneyManagementSystem(initial_balance=balance)
            await mm_system.load_state()
            
            result = await mm_system.calculate_stake(
                confidence=confidence,
                balance=balance
            )
            
            if result.get('can_trade'):
                return result.get('stake', self.default_stake)
            else:
                logger.warning("Money management system blocked trade")
                return 0.0
                
        except Exception as e:
            logger.error(f"Error calculating stake: {e}")
            return self.default_stake
    
    async def _check_risk_rules(self, asset: str, stake: float) -> bool:
        """Check risk management rules"""
        try:
            # Time-based filter: Max 3 trades per 5 minutes
            recent_trades = [
                order for order in self.completed_orders
                if (datetime.now(timezone.utc) - order['timestamp']).total_seconds() < 300
            ]
            
            if len(recent_trades) >= 3:
                logger.warning("Time-based limit: 3 trades in last 5 minutes")
                return False
            
            # Asset concentration: No more than 2 trades on same asset
            asset_trades = [
                order for order in self.active_orders.values()
                if order['asset'] == asset
            ]
            
            if len(asset_trades) >= 2:
                logger.warning(f"Asset concentration limit: 2 active trades on {asset}")
                return False
            
            # Daily limit check
            today_trades = [
                order for order in self.completed_orders
                if order['timestamp'].date() == datetime.now(timezone.utc).date()
            ]
            
            if len(today_trades) >= 100:
                logger.warning("Daily trade limit reached (100)")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking risk rules: {e}")
            return False
    
    async def _execute_trade(
        self,
        asset: str,
        direction: str,
        amount: float,
        duration: int,
        confidence: float,
        strategy: str
    ) -> Optional[Dict]:
        """Execute trade via Bridge Script (REAL EXECUTION)"""
        try:
            logger.info(f"🚀 Executing REAL trade: {direction.upper()} {asset} ${amount} for {duration}s (confidence: {confidence}%)")
            
            # Import trade executor
            from trade_executor import get_trade_executor
            
            executor = await get_trade_executor(self.db)
            
            # Execute trade via Bridge Script
            result = await executor.execute_trade(
                asset=asset,
                direction=direction,
                amount=amount,
                duration=duration,
                strategy=strategy,
                confidence=confidence
            )
            
            if not result.get('success'):
                logger.error(f"Trade execution failed: {result.get('error')}")
                return None
            
            order_id = result['order_id']
            
            # Create order record
            order = {
                "order_id": order_id,
                "asset": asset,
                "direction": direction,
                "amount": amount,
                "duration": duration,
                "confidence": confidence,
                "strategy": strategy,
                "timestamp": datetime.now(timezone.utc),
                "status": result.get('status', 'pending'),
                "execution_type": "bridge_script",
                "result": None,
                "profit": 0.0
            }
            
            # Store in active orders
            self.active_orders[order_id] = order
            
            # Save to database
            await self.db.automated_trades.insert_one({
                **order,
                "user_id": "default_user"
            })
            
            logger.info(f"✅ Order created: {order_id} - Status: {result.get('status')}")
            
            self.total_trades += 1
            
            # Schedule order result check
            asyncio.create_task(self._check_order_result_from_bridge(order_id, duration))
            
            return order
            
        except Exception as e:
            logger.error(f"Error executing trade: {e}")
            return None
    
    async def _check_order_expiration(self, order_id: str, duration: int):
        """Check order result after duration expires"""
        try:
            # Wait for the trade duration + buffer
            await asyncio.sleep(duration + 5)
            
            if order_id not in self.active_orders:
                return
            
            order = self.active_orders[order_id]
            
            # TODO: Query Bridge Script or API for actual result
            # For now, simulate result based on confidence
            import random
            confidence = order['confidence']
            
            # Higher confidence = higher win probability
            win_probability = min(confidence / 100, 0.9)
            is_win = random.random() < win_probability
            
            if is_win:
                order['result'] = 'win'
                order['profit'] = order['amount'] * 0.8  # 80% payout
                self.wins += 1
                logger.info(f"✅ WIN: Order {order_id} - Profit: ${order['profit']:.2f}")
            else:
                order['result'] = 'loss'
                order['profit'] = -order['amount']
                self.losses += 1
                logger.info(f"❌ LOSS: Order {order_id} - Loss: ${order['amount']:.2f}")
            
            order['status'] = 'completed'
            
            # Move to completed
            self.completed_orders.append(order)
            del self.active_orders[order_id]
            
            # Update database
            await self.db.automated_trades.update_one(
                {"order_id": order_id},
                {"$set": {
                    "status": order['status'],
                    "result": order['result'],
                    "profit": order['profit'],
                    "completed_at": datetime.now(timezone.utc)
                }}
            )
            
        except Exception as e:
            logger.error(f"Error checking order expiration: {e}")
    
    async def _get_current_balance(self) -> float:
        """Get current account balance"""
        try:
            # Try to get from database
            balance_doc = await self.db.account_balance.find_one(
                {"user_id": "default_user"},
                {"_id": 0}
            )
            
            if balance_doc:
                return balance_doc.get('balance', 1000.0)
            
            return 1000.0  # Default balance
            
        except Exception as e:
            logger.error(f"Error getting balance: {e}")
            return 1000.0
    
    def get_statistics(self) -> Dict:
        """Get trading statistics"""
        win_rate = (self.wins / self.total_trades * 100) if self.total_trades > 0 else 0.0
        
        total_profit = sum(
            order['profit'] for order in self.completed_orders
            if order.get('profit')
        )
        
        return {
            "is_enabled": self.is_enabled,
            "total_trades": self.total_trades,
            "wins": self.wins,
            "losses": self.losses,
            "draws": self.draws,
            "win_rate": win_rate,
            "active_orders": len(self.active_orders),
            "pending_orders": len(self.pending_orders),
            "total_profit": total_profit,
            "config": {
                "default_stake": self.default_stake,
                "max_concurrent_trades": self.max_concurrent_trades,
                "min_confidence": self.min_confidence,
                "use_money_management": self.use_money_management,
                "use_risk_rules": self.use_risk_rules
            }
        }
    
    async def enable(self):
        """Enable automated trading"""
        self.is_enabled = True
        await self.save_config()
        logger.info("✅ Automated trading ENABLED")
    
    async def disable(self):
        """Disable automated trading"""
        self.is_enabled = False
        await self.save_config()
        logger.info("⏸️ Automated trading DISABLED")
    
    async def update_config(self, config: Dict):
        """Update configuration"""
        if 'default_stake' in config:
            self.default_stake = float(config['default_stake'])
        
        if 'max_concurrent_trades' in config:
            self.max_concurrent_trades = int(config['max_concurrent_trades'])
        
        if 'min_confidence' in config:
            self.min_confidence = float(config['min_confidence'])
        
        if 'use_money_management' in config:
            self.use_money_management = bool(config['use_money_management'])
        
        if 'use_risk_rules' in config:
            self.use_risk_rules = bool(config['use_risk_rules'])
        
        await self.save_config()
        logger.info("✅ Configuration updated")


# Global instance
_automated_trading_service: Optional[AutomatedTradingService] = None


async def get_automated_trading_service(db) -> AutomatedTradingService:
    """Get or create the global automated trading service"""
    global _automated_trading_service
    
    if _automated_trading_service is None:
        _automated_trading_service = AutomatedTradingService(db)
        await _automated_trading_service.load_config()
    
    return _automated_trading_service
