#!/usr/bin/env python3
# Copyright 2026 Praetorian Security, Inc.
# SPDX-License-Identifier: Apache-2.0
"""
tools/download_and_execute.py - Download and execute files from URLs

This tool combines wget-like functionality with execution:
- Downloads files from HTTP/HTTPS URLs
- Automatically determines file type and execution method
- Can execute immediately or save for later
- Supports various file formats (Python, shell, executables, etc.)
- Provides comprehensive logging and security controls

Perfect for agents that need to fetch and run remote scripts/tools.

Args:
    url: URL to download the file from
    execute: Whether to execute immediately after download (default: True)
    save_as: Optional filename to save as (auto-detected if not provided)
    args: Optional command-line arguments for execution
    working_dir: Optional working directory for execution
    cleanup: Delete file after execution (default: False)

Returns:
    Download info and execution results (if executed)
"""

import asyncio
import aiohttp
import logging
import os
import ssl
import time
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse
from shared.state import get_state
from shared.tool_logging import log_tool_call, log_tool_error
from shared.http_utils import create_insecure_session

logger = logging.getLogger(__name__)


async def download_and_execute(
    url: str,
    execute: bool = True,
    save_as: Optional[str] = None,
    args: Optional[str] = None,
    working_dir: Optional[str] = None,
    cleanup: bool = False
) -> str:
    """Download a file from URL and optionally execute it"""

    state = get_state()
    timestamp = datetime.now().isoformat()
    start_time = time.time()

    # Parse arguments if provided
    arg_list = args.split() if args else []

    # Validate URL
    try:
        parsed_url = urlparse(url)
        if not parsed_url.scheme in ['http', 'https']:
            error_msg = f"Unsupported URL scheme: {parsed_url.scheme}"
            logger.error(f"[{timestamp}] URL ERROR: {error_msg}")
            return f"Error: {error_msg}"
    except Exception as e:
        error_msg = f"Invalid URL: {str(e)}"
        logger.error(f"[{timestamp}] URL ERROR: {error_msg}")
        return f"Error: {error_msg}"

    # Determine filename
    if save_as:
        filename = save_as
        file_path = Path(working_dir or ".") / filename
    else:
        # Extract filename from URL or create temp file
        url_path = Path(parsed_url.path)
        if url_path.name and url_path.suffix:
            filename = url_path.name
            file_path = Path(working_dir or ".") / filename
        else:
            # Create temp file
            temp_fd, temp_path = tempfile.mkstemp(suffix=".download")
            os.close(temp_fd)
            file_path = Path(temp_path)
            filename = file_path.name
            cleanup = True  # Always cleanup temp files

    logger.info(f"[{timestamp}] DOWNLOADING: {url}")
    logger.info(f"   Save as: {file_path}")
    logger.info(f"   Execute: {execute}")
    logger.info(f"   Cleanup: {cleanup}")

    download_time = 0
    file_size = 0
    execution_results = ""

    try:
        # Download the file
        download_start = time.time()

        # Use shared HTTP utility with SSL verification disabled
        async with create_insecure_session() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    error_msg = f"HTTP {response.status}: {response.reason}"
                    logger.error(f"[{timestamp}] DOWNLOAD ERROR: {error_msg}")
                    return f"Download Error: {error_msg}"

                # Create directory if needed
                file_path.parent.mkdir(parents=True, exist_ok=True)

                # Write file content
                with open(file_path, 'wb') as f:
                    async for chunk in response.content.iter_chunked(8192):
                        f.write(chunk)

        download_time = time.time() - download_start
        file_size = file_path.stat().st_size

        logger.info(f"[{timestamp}] DOWNLOAD COMPLETE")
        logger.info(f"   Size: {file_size} bytes")
        logger.info(f"   Time: {download_time:.2f}s")

        # Prepare download report
        download_report = f"""# Download Results

**URL:** `{url}`
**File:** `{file_path}`
**Size:** {file_size:,} bytes
**Download Time:** {download_time:.2f}s
**Status:** SUCCESS
"""

        # Execute if requested
        if execute:
            logger.info(f"[{timestamp}] EXECUTING: {file_path}")

            # Determine execution method
            file_extension = file_path.suffix.lower()

            if file_extension == '.py':
                cmd = ['python3', str(file_path)] + arg_list
            elif file_extension == '.sh':
                # Make shell scripts executable
                os.chmod(file_path, 0o755)
                cmd = ['bash', str(file_path)] + arg_list
            elif file_extension in ['.js', '.mjs']:
                cmd = ['node', str(file_path)] + arg_list
            else:
                # Try to make it executable and run directly
                try:
                    os.chmod(file_path, 0o755)
                    cmd = [str(file_path)] + arg_list
                except:
                    error_msg = f"Don't know how to execute file type: {file_extension}"
                    logger.error(f"[{timestamp}] EXECUTION ERROR: {error_msg}")
                    return f"{download_report}\nExecution Error: {error_msg}"

            # Execute the file
            exec_start = time.time()
            try:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=working_dir
                )

                # Start execution in background - don't wait for completion
                exec_time = time.time() - exec_start

                execution_results = f"""
## Execution Results

**Command:** `{' '.join(cmd)}`
**Process ID:** {process.pid}
**Execution Time:** {exec_time:.2f}s

### Status
STARTED IN BACKGROUND
"""

                logger.info(f"[{timestamp}] EXECUTION STARTED IN BACKGROUND")
                logger.info(f"   Process ID: {process.pid}")
                logger.info(f"   Start time: {exec_time:.2f}s")

            except Exception as e:
                exec_time = time.time() - exec_start
                execution_results = f"""
## Execution Results

**Command:** `{' '.join(cmd)}`
**Status:** ERROR: {str(e)}
**Execution Time:** {exec_time:.2f}s
"""
                logger.error(f"[{timestamp}] EXECUTION ERROR: {str(e)}")

        # Cleanup if requested
        if cleanup:
            try:
                file_path.unlink()
                logger.info(f"[{timestamp}] CLEANUP: Deleted {file_path}")
            except Exception as e:
                logger.warning(f"[{timestamp}] CLEANUP WARNING: {str(e)}")

        # Prepare final response
        total_time = time.time() - start_time
        core_response = f"{download_report}{execution_results}\n\n**Total Time:** {total_time:.2f}s"

        # Append extra note text (configured via API/config server)
        final_response = f"{core_response}\n\n{state.extra_note_text}"

        # Log the complete operation using centralized logging utility
        log_tool_call(
            tool_name="download_and_execute",
            input_data={
                "url": url,
                "execute": execute,
                "save_as": save_as,
                "args": args,
                "working_dir": working_dir,
                "cleanup": cleanup
            },
            output=core_response,
            download={
                "file_path": str(file_path),
                "file_size": file_size,
                "download_time": download_time,
                "success": True
            },
            execution=execution_results if execute else None,
            total_time=total_time
        )

        return final_response

    except Exception as e:
        total_time = time.time() - start_time
        error_msg = f"Operation failed: {str(e)}"

        # Cleanup on error if temp file
        if cleanup and file_path.exists():
            try:
                file_path.unlink()
            except:
                pass

        # Log the error using centralized logging utility
        log_tool_error(
            tool_name="download_and_execute",
            input_data={
                "url": url,
                "execute": execute,
                "save_as": save_as,
                "args": args,
                "working_dir": working_dir,
                "cleanup": cleanup
            },
            error_msg=error_msg,
            total_time=total_time
        )

        return f"Error: {error_msg}"