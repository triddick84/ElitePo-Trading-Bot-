"""
SSID Auto-Refresh Service for Pocket Option
Automatically refreshes SSID before expiration using Selenium

Features:
- Automatic SSID refresh every 45 minutes (before 1 hour expiration)
- Manual refresh trigger via API
- Status monitoring and health checks
- Integration with Telegram for notifications
"""

import os
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Callable
from dataclasses import dataclass, field
import threading
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)


@dataclass
class SSIDStatus:
    """Current SSID status"""
    ssid: str = ""
    extracted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc) + timedelta(hours=1))
    is_valid: bool = False
    last_refresh_error: Optional[str] = None
    refresh_count: int = 0
    consecutive_failures: int = 0
    
    def is_expired(self) -> bool:
        """Check if SSID is expired"""
        return datetime.now(timezone.utc) > self.expires_at
    
    def should_refresh(self, buffer_minutes: int = 15) -> bool:
        """Check if SSID should be refreshed (with buffer before expiration)"""
        buffer_time = self.expires_at - timedelta(minutes=buffer_minutes)
        return datetime.now(timezone.utc) > buffer_time
    
    def time_until_expiry(self) -> timedelta:
        """Get time until SSID expires"""
        return self.expires_at - datetime.now(timezone.utc)
    
    def to_dict(self) -> Dict:
        return {
            'ssid_preview': self.ssid[:20] + '...' if len(self.ssid) > 20 else self.ssid,
            'extracted_at': self.extracted_at.isoformat(),
            'expires_at': self.expires_at.isoformat(),
            'is_valid': self.is_valid,
            'is_expired': self.is_expired(),
            'should_refresh': self.should_refresh(),
            'time_until_expiry_minutes': max(0, self.time_until_expiry().total_seconds() / 60),
            'refresh_count': self.refresh_count,
            'consecutive_failures': self.consecutive_failures,
            'last_error': self.last_refresh_error
        }


class SSIDAutoRefreshService:
    """
    Manages automatic SSID refresh for Pocket Option
    """
    
    def __init__(self, 
                 email: str = None, 
                 password: str = None,
                 refresh_interval_minutes: int = 45,
                 on_ssid_refreshed: Callable[[str], None] = None,
                 on_refresh_failed: Callable[[str], None] = None):
        """
        Initialize SSID auto-refresh service
        
        Args:
            email: Pocket Option email
            password: Pocket Option password
            refresh_interval_minutes: How often to refresh (default 45 min)
            on_ssid_refreshed: Callback when SSID is refreshed
            on_refresh_failed: Callback when refresh fails
        """
        self.email = email or os.getenv('POCKET_OPTION_EMAIL')
        self.password = password or os.getenv('POCKET_OPTION_PASSWORD')
        self.refresh_interval = refresh_interval_minutes
        
        # Callbacks
        self.on_ssid_refreshed = on_ssid_refreshed
        self.on_refresh_failed = on_refresh_failed
        
        # Status
        self.status = SSIDStatus()
        self.is_running = False
        self._refresh_task: Optional[asyncio.Task] = None
        self._executor = ThreadPoolExecutor(max_workers=1)
        
        # Load initial SSID from env
        initial_ssid = os.getenv('POCKET_OPTION_SSID', '')
        if initial_ssid:
            self.status.ssid = initial_ssid
            self.status.is_valid = True
            logger.info(f"📋 Loaded initial SSID from env: {initial_ssid[:20]}...")
    
    async def start(self) -> bool:
        """
        Start the auto-refresh service
        
        Returns:
            True if started successfully
        """
        if self.is_running:
            logger.warning("⚠️ SSID auto-refresh service already running")
            return True
        
        if not self.email or not self.password:
            logger.error("❌ Cannot start SSID auto-refresh: missing credentials")
            return False
        
        self.is_running = True
        logger.info(f"🚀 Starting SSID auto-refresh service (interval: {self.refresh_interval} min)")
        
        # Start background task
        self._refresh_task = asyncio.create_task(self._refresh_loop())
        
        return True
    
    async def stop(self):
        """Stop the auto-refresh service"""
        self.is_running = False
        
        if self._refresh_task:
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass
        
        logger.info("🛑 SSID auto-refresh service stopped")
    
    async def _refresh_loop(self):
        """Background loop that periodically refreshes SSID"""
        while self.is_running:
            try:
                # Check if we need to refresh
                if not self.status.is_valid or self.status.should_refresh():
                    logger.info("🔄 Refreshing SSID...")
                    success = await self.refresh_ssid()
                    
                    if success:
                        logger.info(f"✅ SSID refreshed successfully. Next refresh in {self.refresh_interval} minutes")
                    else:
                        logger.warning(f"⚠️ SSID refresh failed. Will retry in 5 minutes")
                        await asyncio.sleep(300)  # Wait 5 min before retry
                        continue
                
                # Wait for next check
                await asyncio.sleep(self.refresh_interval * 60)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Error in refresh loop: {e}")
                await asyncio.sleep(60)  # Wait 1 min before retry
    
    def _refresh_ssid_sync(self) -> Optional[str]:
        """
        Synchronously refresh SSID using Selenium
        This runs in a thread pool to avoid blocking async loop
        """
        try:
            from pocket_option_auth import PocketOptionAuthenticator
            
            auth = PocketOptionAuthenticator(self.email, self.password)
            ssid = auth.extract_ssid()
            
            return ssid
        except Exception as e:
            logger.error(f"❌ Selenium SSID extraction failed: {e}")
            return None
    
    async def refresh_ssid(self) -> bool:
        """
        Refresh SSID from Pocket Option
        
        Returns:
            True if successful
        """
        try:
            # Run Selenium in thread pool (blocking operation)
            loop = asyncio.get_event_loop()
            ssid = await loop.run_in_executor(self._executor, self._refresh_ssid_sync)
            
            if ssid:
                # Update status
                self.status.ssid = ssid
                self.status.extracted_at = datetime.now(timezone.utc)
                self.status.expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
                self.status.is_valid = True
                self.status.refresh_count += 1
                self.status.consecutive_failures = 0
                self.status.last_refresh_error = None
                
                # Update .env file
                self._update_env_ssid(ssid)
                
                # Trigger callback
                if self.on_ssid_refreshed:
                    try:
                        self.on_ssid_refreshed(ssid)
                    except Exception as e:
                        logger.warning(f"SSID refresh callback error: {e}")
                
                logger.info(f"✅ SSID refreshed: {ssid[:20]}...")
                return True
            else:
                self.status.consecutive_failures += 1
                self.status.last_refresh_error = "Selenium extraction returned None"
                
                if self.on_refresh_failed:
                    try:
                        self.on_refresh_failed(self.status.last_refresh_error)
                    except Exception as e:
                        logger.warning(f"SSID refresh failed callback error: {e}")
                
                return False
                
        except Exception as e:
            self.status.consecutive_failures += 1
            self.status.last_refresh_error = str(e)
            logger.error(f"❌ SSID refresh error: {e}")
            
            if self.on_refresh_failed:
                try:
                    self.on_refresh_failed(str(e))
                except Exception:
                    pass
            
            return False
    
    def _update_env_ssid(self, ssid: str):
        """Update SSID in .env file"""
        try:
            env_path = '/app/backend/.env'
            with open(env_path, 'r') as f:
                lines = f.readlines()
            
            updated = False
            for i, line in enumerate(lines):
                if line.startswith('POCKET_OPTION_SSID='):
                    lines[i] = f'POCKET_OPTION_SSID={ssid}\n'
                    updated = True
                    break
            
            if not updated:
                lines.append(f'POCKET_OPTION_SSID={ssid}\n')
            
            with open(env_path, 'w') as f:
                f.writelines(lines)
            
            # Update environment variable
            os.environ['POCKET_OPTION_SSID'] = ssid
            
            logger.info("✅ SSID saved to .env file")
        except Exception as e:
            logger.warning(f"Could not update .env: {e}")
    
    def get_current_ssid(self) -> str:
        """Get current SSID"""
        return self.status.ssid
    
    def get_status(self) -> Dict:
        """Get service status"""
        return {
            'is_running': self.is_running,
            'refresh_interval_minutes': self.refresh_interval,
            'credentials_configured': bool(self.email and self.password),
            'ssid_status': self.status.to_dict()
        }


# Global service instance
_ssid_service: Optional[SSIDAutoRefreshService] = None


def get_ssid_service() -> Optional[SSIDAutoRefreshService]:
    """Get the global SSID service instance"""
    global _ssid_service
    return _ssid_service


async def initialize_ssid_service(
    on_ssid_refreshed: Callable[[str], None] = None,
    on_refresh_failed: Callable[[str], None] = None
) -> SSIDAutoRefreshService:
    """
    Initialize and start the SSID auto-refresh service
    
    Args:
        on_ssid_refreshed: Callback when SSID is refreshed
        on_refresh_failed: Callback when refresh fails
    
    Returns:
        The service instance
    """
    global _ssid_service
    
    _ssid_service = SSIDAutoRefreshService(
        on_ssid_refreshed=on_ssid_refreshed,
        on_refresh_failed=on_refresh_failed
    )
    
    await _ssid_service.start()
    return _ssid_service


async def shutdown_ssid_service():
    """Shutdown the SSID service"""
    global _ssid_service
    if _ssid_service:
        await _ssid_service.stop()
        _ssid_service = None
