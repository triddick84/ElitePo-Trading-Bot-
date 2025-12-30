"""
Pocket Option Trade Execution Module
Integrates with Browser Bridge Script for real order execution
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Any
from collections import deque
import json

logger = logging.getLogger(__name__)


class PocketOptionTradeExecutor:
    """
    Handles real trade execution via Browser Bridge Script
    
    Flow:
    1. Automated trading service calls execute_trade()
    2. This creates a trade request and stores it
    3. Frontend bridge script picks up pending trades
    4. Bridge executes trade in browser
    5. Bridge sends result back
    6. We update order status
    """
    
    def __init__(self, db):
        self.db = db
        self.pending_trades = {}  # order_id -> trade_request
        self.active_trades = {}   # order_id -> trade_info
        self.completed_trades = deque(maxlen=500)
        
        logger.info("📊 Trade Executor initialized")
    
    async def execute_trade(
        self,
        asset: str,
        direction: str,
        amount: float,
        duration: int,
        strategy: str = "unknown",
        confidence: float = 0.0
    ) -> Dict:
        """
        Execute a trade (now with AUTO-EXECUTION mode)
        
        Args:
            asset: Asset symbol (e.g., 'EURUSD_otc')
            direction: 'call' or 'put'
            amount: Trade amount in dollars
            duration: Trade duration in seconds
            strategy: Strategy name
            confidence: Signal confidence
        
        Returns:
            Trade execution result
        """
        try:
            # Create order ID
            order_id = f"LIVE_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')}"
            
            # Create trade request
            trade_request = {
                "order_id": order_id,
                "asset": asset,
                "direction": direction,
                "amount": amount,
                "duration": duration,
                "strategy": strategy,
                "confidence": confidence,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "status": "pending",
                "execution_type": "auto"
            }
            
            # Store in pending trades
            self.pending_trades[order_id] = trade_request
            
            # Save to database
            await self.db.trade_execution_queue.insert_one({
                **trade_request,
                "user_id": "default_user",
                "created_at": datetime.now(timezone.utc)
            })
            
            logger.info(f"📤 Trade created: {order_id} - {direction.upper()} {asset} ${amount}")
            
            # AUTO-EXECUTE based on current execution mode
            from auto_execution_mode import get_auto_execution
            
            # Get existing auto_execution instance (preserves current mode)
            auto_exec = await get_auto_execution(self.db)
            current_mode = auto_exec.get_mode()
            
            logger.info(f"🔄 Executing trade in {current_mode} mode")
            
            execution_result = await auto_exec.execute_trade_auto(
                order_id=order_id,
                asset=asset,
                direction=direction,
                amount=amount,
                duration=duration,
                confidence=confidence
            )
            
            if execution_result.get('success'):
                # Move from pending to active
                if order_id in self.pending_trades:
                    trade = self.pending_trades[order_id]
                    trade['status'] = 'active'
                    trade['bridge_order_id'] = execution_result.get('order_id')
                    trade['execution_mode'] = current_mode
                    self.active_trades[order_id] = trade
                    del self.pending_trades[order_id]
                
                return {
                    "success": True,
                    "order_id": order_id,
                    "status": "executed",
                    "execution_mode": current_mode,
                    "bridge_order_id": execution_result.get('order_id'),
                    "message": f"Trade executed in {current_mode} mode"
                }
            else:
                return {
                    "success": True,
                    "order_id": order_id,
                    "status": "pending",
                    "execution_mode": current_mode,
                    "message": "Trade queued for execution"
                }
            
        except Exception as e:
            logger.error(f"Error executing trade: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _check_execution_status(self, order_id: str, timeout: int = 5) -> Dict:
        """
        Check if bridge has executed a pending trade
        
        Args:
            order_id: Order ID to check
            timeout: Timeout in seconds
        
        Returns:
            Execution status dictionary
        """
        start_time = datetime.now(timezone.utc)
        
        while (datetime.now(timezone.utc) - start_time).total_seconds() < timeout:
            # Check database for execution confirmation
            execution = await self.db.trade_executions.find_one(
                {"order_id": order_id},
                {"_id": 0}
            )
            
            if execution and execution.get('executed'):
                return execution
            
            await asyncio.sleep(0.5)
        
        return {"executed": False}
    
    async def get_pending_trades(self) -> list:
        """
        Get list of pending trades waiting for bridge execution
        
        Returns:
            List of pending trade requests
        """
        try:
            pending = list(self.pending_trades.values())
            
            # Also check database for any orphaned pending trades
            db_pending = await self.db.trade_execution_queue.find(
                {
                    "status": "pending",
                    "user_id": "default_user"
                },
                {"_id": 0}
            ).to_list(length=100)
            
            # Merge
            all_pending = {t['order_id']: t for t in pending + db_pending}
            
            return list(all_pending.values())
            
        except Exception as e:
            logger.error(f"Error getting pending trades: {e}")
            return []
    
    async def confirm_execution(
        self,
        order_id: str,
        bridge_order_id: str,
        execution_price: float,
        execution_time: str
    ) -> Dict:
        """
        Confirm that bridge has executed a trade
        
        Called by bridge API endpoint when trade is executed
        
        Args:
            order_id: Our internal order ID
            bridge_order_id: Pocket Option's order ID
            execution_price: Price at execution
            execution_time: ISO timestamp of execution
        
        Returns:
            Confirmation result
        """
        try:
            # Move from pending to active
            if order_id in self.pending_trades:
                trade = self.pending_trades[order_id]
                trade['status'] = 'active'
                trade['bridge_order_id'] = bridge_order_id
                trade['execution_price'] = execution_price
                trade['execution_time'] = execution_time
                
                self.active_trades[order_id] = trade
                del self.pending_trades[order_id]
            
            # Update database
            await self.db.trade_execution_queue.update_one(
                {"order_id": order_id},
                {"$set": {
                    "status": "active",
                    "bridge_order_id": bridge_order_id,
                    "execution_price": execution_price,
                    "execution_time": execution_time,
                    "executed_at": datetime.now(timezone.utc)
                }}
            )
            
            # Store execution confirmation
            await self.db.trade_executions.insert_one({
                "order_id": order_id,
                "bridge_order_id": bridge_order_id,
                "executed": True,
                "execution_price": execution_price,
                "execution_time": execution_time,
                "confirmed_at": datetime.now(timezone.utc)
            })
            
            logger.info(f"✅ Trade execution confirmed: {order_id} -> {bridge_order_id}")
            
            return {
                "success": True,
                "message": "Execution confirmed"
            }
            
        except Exception as e:
            logger.error(f"Error confirming execution: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def report_trade_result(
        self,
        order_id: str,
        result: str,
        profit: float,
        close_price: float,
        close_time: str
    ) -> Dict:
        """
        Report trade result from bridge
        
        Called by bridge when trade expires
        
        Args:
            order_id: Our internal order ID
            result: 'win', 'loss', or 'draw'
            profit: Profit amount (can be negative)
            close_price: Closing price
            close_time: ISO timestamp of close
        
        Returns:
            Result confirmation
        """
        try:
            # Move from active to completed
            if order_id in self.active_trades:
                trade = self.active_trades[order_id]
                trade['status'] = 'completed'
                trade['result'] = result
                trade['profit'] = profit
                trade['close_price'] = close_price
                trade['close_time'] = close_time
                
                self.completed_trades.append(trade)
                del self.active_trades[order_id]
            
            # Update database
            await self.db.trade_execution_queue.update_one(
                {"order_id": order_id},
                {"$set": {
                    "status": "completed",
                    "result": result,
                    "profit": profit,
                    "close_price": close_price,
                    "close_time": close_time,
                    "completed_at": datetime.now(timezone.utc)
                }}
            )
            
            # Also update automated_trades if it exists there
            await self.db.automated_trades.update_one(
                {"order_id": order_id},
                {"$set": {
                    "status": "completed",
                    "result": result,
                    "profit": profit,
                    "completed_at": datetime.now(timezone.utc)
                }}
            )
            
            logger.info(f"📊 Trade result reported: {order_id} - {result.upper()} - ${profit:.2f}")
            
            return {
                "success": True,
                "message": "Result recorded"
            }
            
        except Exception as e:
            logger.error(f"Error reporting trade result: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def cancel_pending_trade(self, order_id: str) -> Dict:
        """Cancel a pending trade"""
        try:
            if order_id in self.pending_trades:
                del self.pending_trades[order_id]
            
            await self.db.trade_execution_queue.update_one(
                {"order_id": order_id},
                {"$set": {
                    "status": "cancelled",
                    "cancelled_at": datetime.now(timezone.utc)
                }}
            )
            
            logger.info(f"❌ Trade cancelled: {order_id}")
            
            return {
                "success": True,
                "message": "Trade cancelled"
            }
            
        except Exception as e:
            logger.error(f"Error cancelling trade: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_statistics(self) -> Dict:
        """Get executor statistics"""
        completed = list(self.completed_trades)
        
        total = len(completed)
        wins = sum(1 for t in completed if t.get('result') == 'win')
        losses = sum(1 for t in completed if t.get('result') == 'loss')
        
        total_profit = sum(t.get('profit', 0) for t in completed)
        
        return {
            "pending_count": len(self.pending_trades),
            "active_count": len(self.active_trades),
            "completed_count": total,
            "wins": wins,
            "losses": losses,
            "win_rate": (wins / total * 100) if total > 0 else 0,
            "total_profit": total_profit
        }


# Global instance
_trade_executor: Optional[PocketOptionTradeExecutor] = None


async def get_trade_executor(db) -> PocketOptionTradeExecutor:
    """Get or create global trade executor instance"""
    global _trade_executor
    
    if _trade_executor is None:
        _trade_executor = PocketOptionTradeExecutor(db)
    
    return _trade_executor
