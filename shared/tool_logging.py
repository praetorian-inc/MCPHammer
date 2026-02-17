# Copyright 2026 Praetorian Security, Inc.
# SPDX-License-Identifier: Apache-2.0
"""
Shared logging utilities for MCP tools.

Provides centralized logging functions to eliminate duplication across tools.
All tools should use these functions for consistent logging format.
"""

import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from shared.state import get_state

logger = logging.getLogger(__name__)


def log_tool_call(
    tool_name: str,
    input_data: Dict[str, Any],
    output: str,
    **kwargs
) -> None:
    """
    Log a tool call to state and console with consistent formatting.

    This function eliminates the ~200 lines of duplicated logging code
    across 6 tools by providing a single source of truth for logging format.

    Args:
        tool_name: Name of the tool being called
        input_data: Dictionary of input parameters
        output: String output from the tool (will be truncated if > 500 chars)
        **kwargs: Additional fields to add to log entry (e.g., download={}, execution={})
    """
    state = get_state()
    timestamp = datetime.now().isoformat()

    # Truncate output for log entry
    truncated_output = output[:500] + "..." if len(output) > 500 else output

    # Build log entry
    log_entry = {
        "timestamp": timestamp,
        "type": "TOOL_CALL",
        "tool": tool_name,
        "input": input_data,
        "coreOutput": truncated_output
    }

    # Add any additional fields (download stats, execution info, etc.)
    log_entry.update(kwargs)

    # Append to state
    state.log_entries.append(log_entry)

    # Console logging
    logger.info(f"[{timestamp}] TOOL CALL: {tool_name}")
    logger.info(f"   Input: {json.dumps(input_data)[:100]}")
    logger.info(f"   Output: {len(output)} chars")


def log_tool_error(
    tool_name: str,
    input_data: Dict[str, Any],
    error_msg: str,
    **kwargs
) -> None:
    """
    Log a tool error to state and console with consistent formatting.

    Args:
        tool_name: Name of the tool that failed
        input_data: Dictionary of input parameters
        error_msg: Error message describing the failure
        **kwargs: Additional fields to add to log entry
    """
    state = get_state()
    timestamp = datetime.now().isoformat()

    # Build error log entry
    log_entry = {
        "timestamp": timestamp,
        "type": "TOOL_CALL",
        "tool": tool_name,
        "input": input_data,
        "error": error_msg
    }

    # Add any additional fields
    log_entry.update(kwargs)

    # Append to state
    state.log_entries.append(log_entry)

    # Console logging
    logger.error(f"[{timestamp}] ERROR: {error_msg}")
