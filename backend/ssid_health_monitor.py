"""
SSID Health Monitor & Alert System
====================================

Monitors SSID connection health and sends alerts when:
- SSID is about to expire
- Connection is lost
- Trading errors occur
- Reconnection attempts fail

Supports multiple notification channels:
- Console logging
- Webhook notifications
- Email alerts (via configured SMTP)
- Browser notifications (via frontend)
"""

import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
import json
import os
import aiohttp

logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    """Alert severity levels"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    ERROR = "error"


class AlertType(Enum):
    """Types of alerts"""
    SSID_EXPIRING = "ssid_expiring"
    SSID_EXPIRED = "ssid_expired"
    CONNECTION_LOST = "connection_lost"
    CONNECTION_RESTORED = "connection_restored"
    TRADE_ERROR = "trade_error"
    TRADE_SUCCESS = "trade_success"
    RECONNECT_FAILED = "reconnect_failed"
    SYSTEM_ERROR = "system_error"


@dataclass
class Alert:
    """Alert data structure"""
    alert_type: AlertType
    level: AlertLevel
    message: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    details: Dict = field(default_factory=dict)
    acknowledged: bool = False
    
    def to_dict(self) -> Dict:
        return {
            "alert_type": self.alert_type.value,
            "level": self.level.value,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "details": self.details,
            "acknowledged": self.acknowledged
        }


class SSIDHealthMonitor:
    """
    Monitors SSID health and connection status
    Sends alerts through configured channels
    """
    
    def __init__(
        self,
        check_interval: int = 60,  # Check every 60 seconds
        expiry_warning_minutes: int = 30,  # Warn 30 min before expiry
        max_reconnect_attempts: int = 3,
        webhook_url: Optional[str] = None,
        db=None
    ):
        self.check_interval = check_interval
        self.expiry_warning_minutes = expiry_warning_minutes
        self.max_reconnect_attempts = max_reconnect_attempts
        self.webhook_url = webhook_url or os.environ.get('ALERT_WEBHOOK_URL')
        self.db = db
        
        # State tracking
        self.is_running = False
        self.last_check: Optional[datetime] = None
        self.last_connected: Optional[datetime] = None
        self.ssid_set_time: Optional[datetime] = None
        self.estimated_expiry: Optional[datetime] = None
        self.reconnect_attempts = 0
        self.connection_status = False
        
        # Alert history
        self.alerts: List[Alert] = []
        self.max_alert_history = 100
        
        # Callbacks
        self._alert_callbacks: List[Callable] = []
        self._status_callbacks: List[Callable] = []
        
        # Background task
        self._monitor_task: Optional[asyncio.Task] = None
        
        logger.info("🔔 SSID Health Monitor initialized")
    
    def on_alert(self, callback: Callable):
        """Register callback for alerts"""
        self._alert_callbacks.append(callback)
    
    def on_status_change(self, callback: Callable):
        """Register callback for status changes"""
        self._status_callbacks.append(callback)
    
    async def start(self):
        """Start the health monitoring loop"""
        if self.is_running:
            logger.warning("Monitor already running")
            return
        
        self.is_running = True
        self._monitor_task = asyncio.create_task(self._monitoring_loop())
        logger.info("✅ SSID Health Monitor started")
        
        await self._send_alert(Alert(
            alert_type=AlertType.SYSTEM_ERROR,
            level=AlertLevel.INFO,
            message="SSID Health Monitor started",
            details={"check_interval": self.check_interval}
        ))
    
    async def stop(self):
        """Stop the health monitoring loop"""
        self.is_running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("⏹️ SSID Health Monitor stopped")
    
    async def _monitoring_loop(self):
        """Main monitoring loop"""
        while self.is_running:
            try:
                await self._check_health()
                self.last_check = datetime.now(timezone.utc)
            except Exception as e:
                logger.error(f"Health check error: {e}")
                await self._send_alert(Alert(
                    alert_type=AlertType.SYSTEM_ERROR,
                    level=AlertLevel.ERROR,
                    message=f"Health check failed: {str(e)}"
                ))
            
            await asyncio.sleep(self.check_interval)
    
    async def _check_health(self):
        """Perform health check"""
        try:
            # Import here to avoid circular imports
            from pocket_option_api_v2 import get_pocket_option_client
            
            client = get_pocket_option_client()
            
            if client is None:
                # No client configured
                if self.connection_status:
                    self.connection_status = False
                    await self._send_alert(Alert(
                        alert_type=AlertType.CONNECTION_LOST,
                        level=AlertLevel.CRITICAL,
                        message="⚠️ Pocket Option client not configured - SSID required",
                        details={"action_required": "Update SSID from browser"}
                    ))
                return
            
            # Check connection
            is_connected = await client.check_connection()
            
            if is_connected and not self.connection_status:
                # Connection restored
                self.connection_status = True
                self.last_connected = datetime.now(timezone.utc)
                self.reconnect_attempts = 0
                await self._send_alert(Alert(
                    alert_type=AlertType.CONNECTION_RESTORED,
                    level=AlertLevel.INFO,
                    message="✅ Connection to Pocket Option restored",
                    details={"connected_at": self.last_connected.isoformat()}
                ))
                await self._notify_status_change(True)
            
            elif not is_connected and self.connection_status:
                # Connection lost
                self.connection_status = False
                await self._send_alert(Alert(
                    alert_type=AlertType.CONNECTION_LOST,
                    level=AlertLevel.CRITICAL,
                    message="❌ Connection to Pocket Option LOST",
                    details={
                        "last_connected": self.last_connected.isoformat() if self.last_connected else None,
                        "action_required": "SSID may have expired - refresh from browser"
                    }
                ))
                await self._notify_status_change(False)
                
                # Attempt reconnection
                await self._attempt_reconnect()
            
            # Check SSID expiry warning
            if self.ssid_set_time and self.estimated_expiry:
                time_to_expiry = self.estimated_expiry - datetime.now(timezone.utc)
                if time_to_expiry <= timedelta(minutes=self.expiry_warning_minutes):
                    await self._send_alert(Alert(
                        alert_type=AlertType.SSID_EXPIRING,
                        level=AlertLevel.WARNING,
                        message=f"⏰ SSID expiring in {int(time_to_expiry.total_seconds() / 60)} minutes",
                        details={
                            "estimated_expiry": self.estimated_expiry.isoformat(),
                            "action_required": "Prepare new SSID from browser"
                        }
                    ))
        
        except Exception as e:
            logger.error(f"Health check error: {e}")
            raise
    
    async def _attempt_reconnect(self):
        """Attempt to reconnect with existing SSID"""
        if self.reconnect_attempts >= self.max_reconnect_attempts:
            await self._send_alert(Alert(
                alert_type=AlertType.RECONNECT_FAILED,
                level=AlertLevel.CRITICAL,
                message="❌ All reconnection attempts failed",
                details={
                    "attempts": self.reconnect_attempts,
                    "action_required": "Manual SSID refresh required from browser"
                }
            ))
            return
        
        self.reconnect_attempts += 1
        logger.info(f"🔄 Reconnection attempt {self.reconnect_attempts}/{self.max_reconnect_attempts}")
        
        try:
            from pocket_option_api_v2 import get_pocket_option_client
            client = get_pocket_option_client()
            
            if client:
                result = await client.reconnect()
                if result.get('success'):
                    self.connection_status = True
                    self.reconnect_attempts = 0
                    await self._send_alert(Alert(
                        alert_type=AlertType.CONNECTION_RESTORED,
                        level=AlertLevel.INFO,
                        message="✅ Reconnection successful",
                        details={"attempt": self.reconnect_attempts}
                    ))
        except Exception as e:
            logger.error(f"Reconnection attempt failed: {e}")
    
    async def _send_alert(self, alert: Alert):
        """Send alert through all configured channels"""
        # Add to history
        self.alerts.append(alert)
        if len(self.alerts) > self.max_alert_history:
            self.alerts = self.alerts[-self.max_alert_history:]
        
        # Store in database
        if self.db:
            try:
                await self.db.ssid_alerts.insert_one(alert.to_dict())
            except Exception as e:
                logger.error(f"Failed to store alert: {e}")
        
        # Log
        log_msg = f"[{alert.level.value.upper()}] {alert.alert_type.value}: {alert.message}"
        if alert.level == AlertLevel.CRITICAL:
            logger.critical(log_msg)
        elif alert.level == AlertLevel.ERROR:
            logger.error(log_msg)
        elif alert.level == AlertLevel.WARNING:
            logger.warning(log_msg)
        else:
            logger.info(log_msg)
        
        # Call registered callbacks
        for callback in self._alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(alert)
                else:
                    callback(alert)
            except Exception as e:
                logger.error(f"Alert callback error: {e}")
        
        # Send webhook notification
        if self.webhook_url and alert.level in [AlertLevel.CRITICAL, AlertLevel.WARNING]:
            await self._send_webhook(alert)
    
    async def _send_webhook(self, alert: Alert):
        """Send alert to webhook URL"""
        try:
            async with aiohttp.ClientSession() as session:
                payload = {
                    "text": f"🚨 *{alert.level.value.upper()}*: {alert.message}",
                    "alert": alert.to_dict()
                }
                async with session.post(self.webhook_url, json=payload, timeout=10) as resp:
                    if resp.status != 200:
                        logger.warning(f"Webhook notification failed: {resp.status}")
        except Exception as e:
            logger.error(f"Webhook error: {e}")
    
    async def _notify_status_change(self, connected: bool):
        """Notify status change callbacks"""
        for callback in self._status_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(connected)
                else:
                    callback(connected)
            except Exception as e:
                logger.error(f"Status callback error: {e}")
    
    def set_ssid_time(self, set_time: datetime, estimated_expiry_hours: float = 4):
        """Record when SSID was set and estimate expiry"""
        self.ssid_set_time = set_time
        self.estimated_expiry = set_time + timedelta(hours=estimated_expiry_hours)
        logger.info(f"📅 SSID set at {set_time}, estimated expiry: {self.estimated_expiry}")
    
    def get_status(self) -> Dict:
        """Get current monitor status"""
        return {
            "is_running": self.is_running,
            "connection_status": self.connection_status,
            "last_check": self.last_check.isoformat() if self.last_check else None,
            "last_connected": self.last_connected.isoformat() if self.last_connected else None,
            "ssid_set_time": self.ssid_set_time.isoformat() if self.ssid_set_time else None,
            "estimated_expiry": self.estimated_expiry.isoformat() if self.estimated_expiry else None,
            "reconnect_attempts": self.reconnect_attempts,
            "recent_alerts": [a.to_dict() for a in self.alerts[-10:]],
            "check_interval": self.check_interval
        }
    
    def get_alerts(self, limit: int = 50, level: Optional[AlertLevel] = None) -> List[Dict]:
        """Get recent alerts"""
        alerts = self.alerts
        if level:
            alerts = [a for a in alerts if a.level == level]
        return [a.to_dict() for a in alerts[-limit:]]
    
    def acknowledge_alert(self, index: int) -> bool:
        """Acknowledge an alert"""
        if 0 <= index < len(self.alerts):
            self.alerts[index].acknowledged = True
            return True
        return False


# Global monitor instance
_health_monitor: Optional[SSIDHealthMonitor] = None


def get_health_monitor(db=None) -> SSIDHealthMonitor:
    """Get or create the global health monitor"""
    global _health_monitor
    if _health_monitor is None:
        _health_monitor = SSIDHealthMonitor(db=db)
    return _health_monitor


async def start_health_monitor(db=None):
    """Start the global health monitor"""
    monitor = get_health_monitor(db)
    await monitor.start()
    return monitor
