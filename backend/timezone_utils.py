"""
Timezone utility module for Chicago Central Time synchronization
All signals must be synchronized with Pocket Option's platform timezone (America/Chicago)
"""
import pytz
from datetime import datetime, timezone

# Pocket Option uses Chicago/Central timezone
CHICAGO_TZ = pytz.timezone('America/Chicago')

def get_chicago_time() -> datetime:
    """Get current time in Chicago/Central timezone"""
    return datetime.now(CHICAGO_TZ)

def utc_to_chicago(utc_time: datetime) -> datetime:
    """Convert UTC time to Chicago timezone"""
    if utc_time.tzinfo is None:
        # Assume UTC if no timezone info
        utc_time = utc_time.replace(tzinfo=timezone.utc)
    return utc_time.astimezone(CHICAGO_TZ)

def chicago_to_utc(chicago_time: datetime) -> datetime:
    """Convert Chicago time to UTC"""
    if chicago_time.tzinfo is None:
        # Assume Chicago timezone
        chicago_time = CHICAGO_TZ.localize(chicago_time)
    return chicago_time.astimezone(timezone.utc)

def format_chicago_time(dt: datetime) -> str:
    """Format datetime in Chicago timezone for display"""
    chicago_dt = utc_to_chicago(dt) if dt.tzinfo == timezone.utc else dt
    return chicago_dt.strftime('%Y-%m-%d %H:%M:%S %Z')

def get_chicago_timestamp_str() -> str:
    """Get current Chicago time as formatted string"""
    return format_chicago_time(get_chicago_time())
