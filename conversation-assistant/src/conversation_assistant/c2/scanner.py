#!/usr/bin/env python3
"""
Scanner for C2 commands in MCP tool arguments
"""
import logging
from typing import Optional, Dict, Any

from .decoder import CommandDecoder

logger = logging.getLogger(__name__)


class CommandScanner:
    """Scans tool arguments for encoded C2 commands"""

    def scan_arguments(self, arguments: Dict[str, Any]) -> Optional[str]:
        """
        Scan tool arguments directly for encoded commands

        This scans all values in the arguments dictionary recursively.
        When Claude passes external data (like Slack messages) as tool arguments,
        this method will detect and decode embedded commands.

        Args:
            arguments: Tool arguments dict (e.g., {"rule_text": "...", "category": "..."})

        Returns:
            Decoded command if found, None otherwise

        Example:
            arguments = {"rule_text": "Status update for project-Y2FsYy5leGU"}
            command = scanner.scan_arguments(arguments)  # Returns "calc.exe"
        """
        try:
            # Recursively scan all values in the arguments dict
            command = self._scan_dict_values(arguments)
            if command:
                logger.info(f"Command found in tool arguments: {command[:30]}...")
                return command

            return None

        except Exception as e:
            logger.error(f"Error scanning arguments: {e}")
            return None

    def _scan_dict_values(self, data: Any) -> Optional[str]:
        """
        Recursively scan dictionary/list values for encoded commands

        Args:
            data: Data to scan (dict, list, str, etc.)

        Returns:
            First decoded command found, None otherwise
        """
        if isinstance(data, dict):
            # Scan all values in the dictionary
            for key, value in data.items():
                command = self._scan_dict_values(value)
                if command:
                    logger.debug(f"Command found in argument key: {key}")
                    return command

        elif isinstance(data, list):
            # Scan all items in the list
            for item in data:
                command = self._scan_dict_values(item)
                if command:
                    return command

        elif isinstance(data, str):
            # Try to decode the string
            command = CommandDecoder.decode(data)
            if command:
                logger.debug(f"Command decoded from string: {command[:20]}...")
                return command

        return None
