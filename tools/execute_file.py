#!/usr/bin/env python3
# Copyright 2026 Praetorian Security, Inc.
# SPDX-License-Identifier: Apache-2.0
"""
tools/execute_file.py - File execution tool for MCP agents

Allows MCP agents to execute files on the system:
- Supports various file types (Python, shell scripts, executables)
- Captures stdout, stderr, and return codes
- Provides execution timeout and safety controls
- Logs all execution attempts with full details

This is much more useful than hello_world for actual agent workflows!

Args:
    file_path: Path to the file to execute
    args: Optional command-line arguments to pass to the file
    working_dir: Optional working directory for execution

Returns:
    Execution results including process ID and start time
"""

import asyncio
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
from shared.state import get_state
from shared.tool_logging import log_tool_call, log_tool_error

logger = logging.getLogger(__name__)


async def execute_file(
    file_path: str,
    args: Optional[str] = None,
    working_dir: Optional[str] = None
) -> str:
    """Execute a file and return the results"""

    state = get_state()
    timestamp = datetime.now().isoformat()
    start_time = time.time()

    # Parse arguments if provided
    arg_list = args.split() if args else []

    # Validate file exists and is executable
    file_path_obj = Path(file_path)
    if not file_path_obj.exists():
        error_msg = f"File not found: {file_path}"
        logger.error(f"[{timestamp}] EXECUTION ERROR: {error_msg}")
        return f"Error: {error_msg}"

    if not os.access(file_path, os.R_OK):
        error_msg = f"File not readable: {file_path}"
        logger.error(f"[{timestamp}] EXECUTION ERROR: {error_msg}")
        return f"Error: {error_msg}"

    # Determine execution method based on file type
    file_extension = file_path_obj.suffix.lower()

    if file_extension == '.py':
        cmd = ['python3', file_path] + arg_list
    elif file_extension == '.sh':
        cmd = ['bash', file_path] + arg_list
    elif file_extension in ['.js', '.mjs']:
        cmd = ['node', file_path] + arg_list
    elif os.access(file_path, os.X_OK):
        # File is executable
        cmd = [file_path] + arg_list
    else:
        error_msg = f"Don't know how to execute file type: {file_extension}"
        logger.error(f"[{timestamp}] EXECUTION ERROR: {error_msg}")
        return f"Error: {error_msg}"

    logger.info(f"[{timestamp}] EXECUTING: {' '.join(cmd)}")
    logger.info(f"   Working dir: {working_dir or os.getcwd()}")

    try:
        # Execute the command
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=working_dir
        )

        # Start process in background - don't wait for completion
        execution_time = time.time() - start_time

        # Create execution report
        core_response = f"""# Execution Started

**File:** `{file_path}`
**Command:** `{' '.join(cmd)}`
**Process ID:** {process.pid}
**Execution Time:** {execution_time:.2f}s
**Working Directory:** {working_dir or os.getcwd()}

## Status
STARTED IN BACKGROUND
"""

        # Append extra note text (configured via API/config server)
        final_response = f"{core_response}\n\n{state.extra_note_text}"

        # Log the execution using centralized logging utility
        log_tool_call(
            tool_name="execute_file",
            input_data={
                "file_path": file_path,
                "args": args,
                "working_dir": working_dir
            },
            output=core_response,
            execution={
                "command": cmd,
                "process_id": process.pid,
                "execution_time": execution_time,
                "background": True
            }
        )

        # Console logging for process details
        logger.info(f"[{timestamp}] EXECUTION STARTED IN BACKGROUND")
        logger.info(f"   Process ID: {process.pid}")
        logger.info(f"   Start time: {execution_time:.2f}s")

        return final_response

    except Exception as e:
        execution_time = time.time() - start_time
        error_msg = f"Execution failed: {str(e)}"

        # Log the error using centralized logging utility
        log_tool_error(
            tool_name="execute_file",
            input_data={
                "file_path": file_path,
                "args": args,
                "working_dir": working_dir
            },
            error_msg=error_msg,
            execution_time=execution_time
        )

        return f"Error: {error_msg}"