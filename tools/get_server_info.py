#!/usr/bin/env python3
# Copyright 2026 Praetorian Security, Inc.
# SPDX-License-Identifier: Apache-2.0
"""
tools/get_server_info.py - Server status reporter

Tells you what's going on:
- Reports server version, uptime, session ID
- Can include usage stats (how many times each tool was called)
- Basically a runtime health check

Reads from global state to see what all the other tools have been up to. 
    Args:
        include_stats: Set True to include usage statistics and call counts
        
    Returns:
        Markdown-formatted server information report
"""

import logging
from datetime import datetime
from shared.state import get_state

logger = logging.getLogger(__name__)


async def get_server_info(include_stats: bool = False) -> str:
    """Returns information about this MCP server"""
    state = get_state()
    timestamp = datetime.now().isoformat()
    
    log_entry = {
        "timestamp": timestamp,
        "type": "TOOL_CALL",
        "tool": "get_server_info",
        "input": {"include_stats": include_stats},
        "output": "server info returned"
    }
    
    state.log_entries.append(log_entry)
    logger.info(f"[{timestamp}] TOOL CALL: get_server_info")
    
    uptime = int((datetime.now() - state.start_time).total_seconds())
    
    info = f"""# MCP Server Information

**Name:** MCPHammer Server
**Version:** 0.1.0
**Session ID:** {state.session_id}
**Port:** {state.port}
**Uptime:** {uptime} seconds"""
    
    if include_stats:
        info += f"""

## Usage Statistics

- **Total Tool Calls:** {len(state.log_entries)}
- **Session Start:** {state.log_entries[0]['timestamp'] if state.log_entries else 'No calls yet'}
- **Last Activity:** {timestamp}
- **Log File:** {state.log_file}"""
        
        # Tool usage breakdown
        tool_counts = {}
        for entry in state.log_entries:
            if entry.get('type') == 'TOOL_CALL':
                tool = entry.get('tool')
                tool_counts[tool] = tool_counts.get(tool, 0) + 1
        
        if tool_counts:
            info += "\n\n## Tool Usage Breakdown\n"
            for tool, count in tool_counts.items():
                info += f"\n- **{tool}:** {count} calls"
    
    return info
