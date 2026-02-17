#!/usr/bin/env python3
"""
Command decoder for extracting C2 commands from Slack messages

WARNING: This module contains command decoding capabilities for security research only.
"""
import base64
import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


class CommandDecoder:
    """Decodes commands from Slack messages"""

    @staticmethod
    def encode(command: str) -> str:
        """
        Encode command for Slack message (for testing/demo purposes)

        Args:
            command: Shell command to encode

        Returns:
            Base64 encoded command without padding
        """
        encoded = base64.b64encode(command.encode()).decode()
        # Remove padding to be less obvious
        encoded = encoded.rstrip('=')
        return encoded

    @staticmethod
    def decode(text: str) -> Optional[str]:
        """
        Extract and decode command from Slack message text

        Args:
            text: Slack message text content

        Returns:
            Decoded command if found, None otherwise
        """
        if not text:
            return None

        try:
            # Pattern matches: project-XXX, deployment-XXX, client-XXX, status-XXX, etc.
            pattern = r'(?:project|deployment|client|status|update|check)-([A-Za-z0-9+/]+)'
            match = re.search(pattern, text, re.IGNORECASE)

            if not match:
                return None

            encoded = match.group(1)

            # Re-add padding if needed
            padding = (4 - len(encoded) % 4) % 4
            encoded += '=' * padding

            try:
                decoded = base64.b64decode(encoded).decode()
                logger.debug(f"Decoded command from Slack: {decoded[:20]}...")
                return decoded
            except Exception as e:
                logger.debug(f"Base64 decode failed: {e}")
                return None

        except Exception as e:
            logger.error(f"Error decoding command: {e}")
            return None

    @staticmethod
    def is_potential_command(text: str) -> bool:
        """
        Check if text might contain an encoded command

        Args:
            text: Text to check

        Returns:
            True if text might contain a command
        """
        if not text:
            return False

        # Look for the encoding patterns
        pattern = r'(?:project|deployment|client|status|update|check)-[A-Za-z0-9+/]+'
        return bool(re.search(pattern, text, re.IGNORECASE))

    @staticmethod
    def extract_all_commands(text: str) -> list[str]:
        """
        Extract all potential commands from text

        Args:
            text: Text to search

        Returns:
            List of decoded commands
        """
        commands = []

        if not text:
            return commands

        try:
            # Find all potential command patterns
            pattern = r'(?:project|deployment|client|status|update|check)-([A-Za-z0-9+/]+)'
            matches = re.finditer(pattern, text, re.IGNORECASE)

            for match in matches:
                encoded = match.group(1)

                # Re-add padding if needed
                padding = (4 - len(encoded) % 4) % 4
                encoded += '=' * padding

                try:
                    decoded = base64.b64decode(encoded).decode()
                    commands.append(decoded)
                    logger.debug(f"Found command: {decoded[:20]}...")
                except:
                    # Skip invalid base64
                    continue

        except Exception as e:
            logger.error(f"Error extracting commands: {e}")

        return commands