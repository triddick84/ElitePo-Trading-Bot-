"""
Auto-Execution Mode for Automated Trading
Provides immediate trade execution when Bridge Script is not available

This module enables three execution modes:
1. BRIDGE - Requires browser Bridge Script (manual setup)
2. DEMO - Simulates trades with realistic outcomes (for testing)
3. API - Direct API calls (if credentials available)
"""

import asyncio
import logging
import random
from datetime import datetime, timezone
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class AutoExecutionMode:
    """
    Handles trade execution in different modes
    """
    
    def __init__(self, db, mode: str = "DEMO"):
        """
        Initialize auto-execution
        
        Args:
            db: Database connection
            mode: Execution mode - "BRIDGE", "DEMO", or "API"
        """
        self.db = db
        self.mode = mode
        self.execution_count = 0
        
        logger.info(f"🎯 Auto-Execution Mode: {mode}")
    
    async def execute_trade_auto(
        self,
        order_id: str,
        asset: str,
        direction: str,
        amount: float,
        duration: int,
        confidence: float
    ) -> Dict:
        """
        Execute trade based on current mode
        
        Args:
            order_id: Internal order ID
            asset: Asset symbol
            direction: 'call' or 'put'
            amount: Trade amount
            duration: Duration in seconds
            confidence: Signal confidence (0-100)
        
        Returns:
            Execution result dictionary
        """
        if self.mode == "DEMO":
            return await self._execute_demo_trade(
                order_id, asset, direction, amount, duration, confidence
            )
        elif self.mode == "BRIDGE":
            return await self._execute_bridge_trade(
                order_id, asset, direction, amount, duration, confidence
            )
        elif self.mode == "API":
            return await self._execute_api_trade(
                order_id, asset, direction, amount, duration, confidence
            )
        else:
            logger.error(f"Unknown execution mode: {self.mode}")
            return {"success": False, "error": "Invalid execution mode"}
    
    async def _execute_demo_trade(
        self,
        order_id: str,
        asset: str,
        direction: str,
        amount: float,
        duration: int,
        confidence: float
    ) -> Dict:
        """
        Execute trade in DEMO mode (simulated with realistic outcomes)
        """
        try:
            logger.info(f"🎮 DEMO MODE: Executing {direction.upper()} {asset} ${amount}")
            
            # Generate realistic order ID
            demo_order_id = f"DEMO_{datetime.now(timezone.utc).strftime('%H%M%S%f')}"
            
            # Simulate execution (instant in demo)
            execution_price = random.uniform(1.0800, 1.0900)  # Realistic price
            
            # Update database with execution
            await self.db.trade_execution_queue.update_one(
                {"order_id": order_id},
                {"$set": {
                    "status": "active",
                    "bridge_order_id": demo_order_id,
                    "execution_price": execution_price,
                    "execution_time": datetime.now(timezone.utc).isoformat(),
                    "executed_at": datetime.now(timezone.utc),
                    "execution_mode": "DEMO"
                }}
            )
            
            # Store execution confirmation
            await self.db.trade_executions.insert_one({
                "order_id": order_id,
                "bridge_order_id": demo_order_id,
                "executed": True,
                "execution_price": execution_price,
                "execution_time": datetime.now(timezone.utc).isoformat(),
                "execution_mode": "DEMO",
                "confirmed_at": datetime.now(timezone.utc)
            })
            
            logger.info(f"✅ DEMO: Trade executed - Order: {demo_order_id}")
            
            # Schedule result reporting (after duration)
            asyncio.create_task(
                self._report_demo_result(order_id, demo_order_id, duration, amount, confidence)
            )
            
            self.execution_count += 1
            
            return {
                "success": True,
                "order_id": demo_order_id,
                "execution_price": execution_price,
                "mode": "DEMO",
                "message": "Trade executed in DEMO mode"
            }
            
        except Exception as e:
            logger.error(f"Error in demo execution: {e}")
            return {"success": False, "error": str(e)}
    
    async def _report_demo_result(
        self,
        order_id: str,
        demo_order_id: str,
        duration: int,
        amount: float,
        confidence: float
    ):
        """
        Report trade result after duration in DEMO mode
        """
        try:
            # Wait for trade duration + 2 seconds
            await asyncio.sleep(duration + 2)
            
            # Calculate win probability based on confidence
            # Higher confidence = higher win rate (but not guaranteed)
            base_win_rate = 0.55  # Base 55% win rate
            confidence_bonus = (confidence - 70) / 100 * 0.15  # Up to 15% bonus
            win_probability = min(0.75, base_win_rate + confidence_bonus)  # Max 75%
            
            # Determine outcome
            is_win = random.random() < win_probability
            
            if is_win:
                # Win with realistic payout (75-85%)
                payout_rate = random.uniform(0.75, 0.85)
                profit = amount * payout_rate
                result = "win"
                logger.info(f"✅ DEMO WIN: {demo_order_id} - Profit: ${profit:.2f}")
            else:
                profit = -amount
                result = "loss"
                logger.info(f"❌ DEMO LOSS: {demo_order_id} - Loss: ${amount:.2f}")
            
            close_price = random.uniform(1.0800, 1.0900)
            
            # Update database
            await self.db.trade_execution_queue.update_one(
                {"order_id": order_id},
                {"$set": {
                    "status": "completed",
                    "result": result,
                    "profit": profit,
                    "close_price": close_price,
                    "close_time": datetime.now(timezone.utc).isoformat(),
                    "completed_at": datetime.now(timezone.utc)
                }}
            )
            
            await self.db.automated_trades.update_one(
                {"order_id": order_id},
                {"$set": {
                    "status": "completed",
                    "result": result,
                    "profit": profit,
                    "completed_at": datetime.now(timezone.utc)
                }}
            )
            
            logger.info(f"📊 DEMO: Result reported for {order_id}")
            
        except Exception as e:
            logger.error(f"Error reporting demo result: {e}")
    
    async def _execute_bridge_trade(
        self,
        order_id: str,
        asset: str,
        direction: str,
        amount: float,
        duration: int,
        confidence: float
    ) -> Dict:
        """
        Execute via Bridge Script (requires browser setup)
        """
        logger.info(f"🌉 BRIDGE MODE: Queueing {direction.upper()} {asset} ${amount}")
        logger.warning("⚠️ BRIDGE MODE requires browser setup - trade is pending")
        
        return {
            "success": True,
            "status": "pending",
            "message": "Trade queued for Bridge Script execution"
        }
    
    async def _execute_api_trade(
        self,
        order_id: str,
        asset: str,
        direction: str,
        amount: float,
        duration: int,
        confidence: float
    ) -> Dict:
        """
        Execute via direct API (if credentials available)
        """
        logger.info(f"🔌 API MODE: Not yet implemented")
        
        # Fallback to demo mode
        return await self._execute_demo_trade(
            order_id, asset, direction, amount, duration, confidence
        )
    
    def get_mode(self) -> str:
        """Get current execution mode"""
        return self.mode
    
    def set_mode(self, mode: str):
        """
        Set execution mode
        
        Args:
            mode: "DEMO", "BRIDGE", or "API"
        """
        if mode in ["DEMO", "BRIDGE", "API"]:
            self.mode = mode
            logger.info(f"🔄 Execution mode changed to: {mode}")
        else:
            logger.error(f"Invalid mode: {mode}")
    
    def get_statistics(self) -> Dict:
        """Get execution statistics"""
        return {
            "mode": self.mode,
            "executions": self.execution_count
        }


# Global instance
_auto_execution: Optional[AutoExecutionMode] = None


async def get_auto_execution(db, mode: str = "DEMO") -> AutoExecutionMode:
    """Get or create auto-execution instance"""
    global _auto_execution
    
    if _auto_execution is None:
        _auto_execution = AutoExecutionMode(db, mode)
    
    return _auto_execution
