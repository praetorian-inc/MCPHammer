#!/usr/bin/env python3
# Copyright 2026 Praetorian Security, Inc.
# SPDX-License-Identifier: Apache-2.0
"""
Just one main job: 
- Takes all the logs from state.log_entries
- Dumps them to a JSON file when server shuts down
- Formats it nicely with session info and timestamps

Gets called during shutdown (Ctrl+C or crashes) to make sure
we don't lose our session history.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from .state import get_state

logger = logging.getLogger(__name__)


def save_logs_to_file():
    """Save session logs to file (synchronous version)"""
    state = get_state()
    try:
        # Ensure mcp_sessions directory exists
        log_path = Path(state.log_file)
        log_path.parent.mkdir(exist_ok=True)

        log_data = {
            "sessionId": state.session_id,
            "startTime": state.log_entries[0]['timestamp'] if state.log_entries else datetime.now().isoformat(),
            "endTime": datetime.now().isoformat(),
            "totalEntries": len(state.log_entries),
            "transport": "HTTP (FastMCP)",
            "port": state.port,
            "logs": state.log_entries
        }
        
        with open(state.log_file, 'w') as f:
            json.dump(log_data, f, indent=2)
        
        logger.info(f"Session logs saved to: {state.log_file}")
        logger.info(f"Total log entries: {len(state.log_entries)}")
    except Exception as e:
        logger.error(f"Failed to write logs to file: {e}")
