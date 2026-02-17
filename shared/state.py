#!/usr/bin/env python3
# Copyright 2026 Praetorian Security, Inc.
# SPDX-License-Identifier: Apache-2.0
"""
shared/state.py - The server's brain (global state singleton)

This holds everything static while the server runs:
- injection_text: That sneaky text we append to responses
- log_entries: Every single tool call that happened
- session_id: A unique ID for this server run
- Other metadata like start time and port

Why it exists:
- Tools need to share data (like injection text)
- Some things need to persist between tool calls
- We want one place to store logs
- Avoids circular import hell
- Makes it easy to see what can change during runtime

Everyone uses this - tools read/write to it, HTTP endpoints modify it,
and the logger dumps it to a file when we shut down.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any

# Sets static extra note text, log entries, session ID, log file, start time, and port. 
class ServerState:
    def __init__(self):
        # Extra note text appended to tool responses (set via API/config server)
        # Default is empty to avoid confusing AI agents
        self.extra_note_text = ""
        # URL for init tool to download (configurable via API/config server)
        self.init_url = "https://raw.githubusercontent.com/praetorian-inc/nebula/refs/heads/main/README.md"
        # This is a list of all the tool calls that have happened
        self.log_entries: List[Dict[str, Any]] = []
        # This is a unique ID for this server run
        self.session_id = datetime.now().isoformat().replace(':', '-').replace('.', '-')
        # Where we'll dump logs when shutting down
        # Named with session ID so we don't overwrite old logs
        # Logs are saved in the mcp_sessions folder
        from pathlib import Path
        mcp_sessions_dir = Path("mcp_sessions")
        mcp_sessions_dir.mkdir(exist_ok=True)
        self.log_file = str(mcp_sessions_dir / f"mcp-session-{self.session_id}.log")
        # tracks when server started
        self.start_time = datetime.now()
        # port is the port the server is running on
        self.port = 3000


_state = None


def get_state() -> ServerState:
    """
    Get the global server state instance.
    This is what all tools call to access shared state. 
    If state doesn't exist yet, creates it (lazy initialization).
    """
    global _state
    if _state is None:
        _state = ServerState()
    return _state


def initialize_state() -> ServerState:
    """
    Init and return the global server state.
    Called once at server startup to ensure we have fresh state.
    """
    global _state
    _state = ServerState()
    return _state
