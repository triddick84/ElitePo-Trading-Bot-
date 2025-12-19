"""
Breakout Alert Service
Handles webhook integration, MT4/MT5 format, and real-time alert delivery
Optimized for ultra-low latency (<100ms)
"""

import asyncio
import aiohttp
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Optional, List, Any
from dataclasses import dataclass, asdict
import time
from collections import deque

logger = logging.getLogger(__name__)


@dataclass
class AlertPayload:
    """Standard alert payload structure"""
    alert_id: str
    ticker: str
    signal: str
    price: float
    timestamp: str
    message: str
    timeframe: str
    breakout_level: float
    confidence_score: float
    breakout_type: str
    strength: float
    support_levels: List[float]
    resistance_levels: List[float]
    
    def to_json(self) -> str:
        return json.dumps(asdict(self))
    
    def to_mt4_format(self) -> str:
        """Format compatible with MT4/MT5 Expert Advisors"""
        return (
            f"SIGNAL|{self.signal}|"
            f"SYMBOL|{self.ticker}|"
            f"PRICE|{self.price}|"
            f"BREAKOUT|{self.breakout_level}|"
            f"CONF|{self.confidence_score}|"
            f"TYPE|{self.breakout_type}|"
            f"TIME|{self.timestamp}"
        )
    
    def to_tradingview_format(self) -> Dict:
        """Format compatible with TradingView webhooks"""
        return {
            "strategy": "EnhancedBreakoutPredictor",
            "order": {
                "symbol": self.ticker,
                "side": "buy" if self.signal == "BUY" else "sell",
                "price": self.price,
                "confidence": self.confidence_score / 100
            },
            "position": {
                "breakout_level": self.breakout_level,
                "support": self.support_levels,
                "resistance": self.resistance_levels
            },
            "alert": {
                "message": self.message,
                "timestamp": self.timestamp,
                "type": self.breakout_type
            }
        }


class WebhookService:
    """
    Async webhook service for sending breakout alerts
    Supports JSON, MT4, and custom formats
    """
    
    def __init__(self, timeout_ms: int = 100, max_retries: int = 3):
        self.timeout_ms = timeout_ms
        self.max_retries = max_retries
        self.sent_alerts: deque = deque(maxlen=1000)
        self.failed_alerts: deque = deque(maxlen=100)
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Performance tracking
        self.total_sent = 0
        self.total_failed = 0
        self.avg_latency_ms = 0
        self.latency_samples: deque = deque(maxlen=100)
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=self.timeout_ms / 1000)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session
    
    async def send_webhook(self, url: str, payload: AlertPayload, 
                            format_type: str = "json") -> Dict:
        """
        Send webhook alert
        
        Args:
            url: Webhook URL
            payload: AlertPayload instance
            format_type: "json", "mt4", or "tradingview"
        
        Returns:
            Dict with success status and details
        """
        start_time = time.time()
        
        try:
            session = await self._get_session()
            
            # Format payload based on type
            if format_type == "mt4":
                data = payload.to_mt4_format()
                headers = {"Content-Type": "text/plain"}
            elif format_type == "tradingview":
                data = json.dumps(payload.to_tradingview_format())
                headers = {"Content-Type": "application/json"}
            else:  # json
                data = payload.to_json()
                headers = {"Content-Type": "application/json"}
            
            # Send request with retries
            for attempt in range(self.max_retries):
                try:
                    async with session.post(url, data=data, headers=headers) as response:
                        latency = (time.time() - start_time) * 1000
                        self.latency_samples.append(latency)
                        self.avg_latency_ms = sum(self.latency_samples) / len(self.latency_samples)
                        
                        if response.status == 200:
                            self.total_sent += 1
                            self.sent_alerts.append({
                                "alert_id": payload.alert_id,
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "latency_ms": round(latency, 2)
                            })
                            
                            return {
                                "success": True,
                                "status_code": response.status,
                                "latency_ms": round(latency, 2),
                                "attempt": attempt + 1
                            }
                        
                except asyncio.TimeoutError:
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(0.01)  # 10ms delay between retries
                        continue
                    raise
            
            # All retries failed
            self.total_failed += 1
            return {
                "success": False,
                "error": "Max retries exceeded",
                "latency_ms": round((time.time() - start_time) * 1000, 2)
            }
            
        except Exception as e:
            self.total_failed += 1
            self.failed_alerts.append({
                "alert_id": payload.alert_id,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            
            return {
                "success": False,
                "error": str(e),
                "latency_ms": round((time.time() - start_time) * 1000, 2)
            }
    
    async def close(self):
        """Close the session"""
        if self.session and not self.session.closed:
            await self.session.close()
    
    def get_statistics(self) -> Dict:
        """Get webhook service statistics"""
        return {
            "total_sent": self.total_sent,
            "total_failed": self.total_failed,
            "success_rate": self.total_sent / (self.total_sent + self.total_failed) 
                           if (self.total_sent + self.total_failed) > 0 else 1.0,
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "recent_sent": len(self.sent_alerts),
            "recent_failed": len(self.failed_alerts)
        }


class BreakoutAlertManager:
    """
    Main alert manager for breakout signals
    Handles multiple alert channels and formats
    """
    
    def __init__(self):
        self.webhook_service = WebhookService()
        self.alert_queue: asyncio.Queue = asyncio.Queue()
        self.registered_webhooks: List[Dict] = []
        self.alert_history: deque = deque(maxlen=500)
        
        # Alert configuration
        self.config = {
            "enabled": True,
            "sound_alert": True,
            "popup_alert": True,
            "webhook_enabled": False,
            "mt4_enabled": False,
            "telegram_enabled": False
        }
        
        logger.info("🔔 Breakout Alert Manager initialized")
    
    def register_webhook(self, url: str, format_type: str = "json", 
                          name: str = "default") -> bool:
        """Register a webhook URL for alerts"""
        webhook = {
            "name": name,
            "url": url,
            "format": format_type,
            "enabled": True,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        self.registered_webhooks.append(webhook)
        logger.info(f"📝 Registered webhook: {name} ({format_type})")
        return True
    
    def create_alert_payload(self, signal_data: Dict) -> AlertPayload:
        """Create AlertPayload from signal dictionary"""
        alert_id = f"BRK_{signal_data.get('ticker', 'UNKNOWN')}_{int(time.time() * 1000)}"
        
        return AlertPayload(
            alert_id=alert_id,
            ticker=signal_data.get('ticker', signal_data.get('symbol', '')),
            signal=signal_data.get('signal', signal_data.get('direction', '')),
            price=signal_data.get('price', signal_data.get('current_price', 0)),
            timestamp=signal_data.get('timestamp', datetime.now(timezone.utc).isoformat()),
            message=signal_data.get('message', signal_data.get('reasoning', '')),
            timeframe=signal_data.get('timeframe', '5s'),
            breakout_level=signal_data.get('breakout_level', 0),
            confidence_score=signal_data.get('confidence_score', signal_data.get('confidence', 0)),
            breakout_type=signal_data.get('breakout_type', ''),
            strength=signal_data.get('strength', 0),
            support_levels=signal_data.get('support_levels', []),
            resistance_levels=signal_data.get('resistance_levels', [])
        )
    
    async def generate_alert(self, signal_data: Dict) -> Dict:
        """
        Generate and dispatch breakout alert
        
        Args:
            signal_data: Signal dictionary from breakout predictor
        
        Returns:
            Dict with alert status and delivery results
        """
        if not self.config["enabled"]:
            return {"success": False, "reason": "Alerts disabled"}
        
        start_time = time.time()
        
        # Create payload
        payload = self.create_alert_payload(signal_data)
        
        # Store in history
        self.alert_history.append({
            "alert_id": payload.alert_id,
            "signal": payload.signal,
            "ticker": payload.ticker,
            "confidence": payload.confidence_score,
            "timestamp": payload.timestamp
        })
        
        results = {
            "alert_id": payload.alert_id,
            "webhook_results": [],
            "processing_time_ms": 0
        }
        
        # Send to registered webhooks
        if self.config["webhook_enabled"] and self.registered_webhooks:
            for webhook in self.registered_webhooks:
                if webhook["enabled"]:
                    result = await self.webhook_service.send_webhook(
                        webhook["url"],
                        payload,
                        webhook["format"]
                    )
                    results["webhook_results"].append({
                        "name": webhook["name"],
                        **result
                    })
        
        results["processing_time_ms"] = round((time.time() - start_time) * 1000, 2)
        
        logger.info(f"🔔 Alert generated: {payload.alert_id}")
        logger.info(f"   Signal: {payload.signal} {payload.ticker} @ {payload.price}")
        logger.info(f"   Confidence: {payload.confidence_score}%, Latency: {results['processing_time_ms']}ms")
        
        return results
    
    def get_alert_history(self, limit: int = 50) -> List[Dict]:
        """Get recent alert history"""
        return list(self.alert_history)[-limit:]
    
    def get_statistics(self) -> Dict:
        """Get alert manager statistics"""
        return {
            "config": self.config,
            "registered_webhooks": len(self.registered_webhooks),
            "alert_history_count": len(self.alert_history),
            "webhook_stats": self.webhook_service.get_statistics()
        }
    
    def update_config(self, config: Dict) -> bool:
        """Update alert configuration"""
        for key, value in config.items():
            if key in self.config:
                self.config[key] = value
        logger.info(f"📝 Alert config updated: {config}")
        return True
    
    async def cleanup(self):
        """Cleanup resources"""
        await self.webhook_service.close()


# Global instance
_alert_manager: Optional[BreakoutAlertManager] = None


def get_alert_manager() -> BreakoutAlertManager:
    """Get singleton alert manager instance"""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = BreakoutAlertManager()
    return _alert_manager


async def send_breakout_alert(signal_data: Dict) -> Dict:
    """Convenience function to send breakout alert"""
    manager = get_alert_manager()
    return await manager.generate_alert(signal_data)
