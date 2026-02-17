#!/usr/bin/env python3
# Copyright 2026 Praetorian Security, Inc.
# SPDX-License-Identifier: Apache-2.0
"""
tools/hello_world.py - The simplest tool that could possibly work

Does exactly what it says:
- Takes your text, returns "hello world {your text}"
- Logs what it did

This is basically the template for how all tools work:
1. Get global state
2. Do the thing
3. Log it
4. Return result

    Args:
        text: Whatever text you want after "hello world" - this should be populated by the AI Agent sending the tool call.
        
    Returns:
        String like "hello world {text}"
"""

import logging
from datetime import datetime
from shared.state import get_state

logger = logging.getLogger(__name__)


async def hello_world(text: str) -> str:

    # Grab shared state
    state = get_state()
    timestamp = datetime.now().isoformat()

    # The actual business logic
    core_response = f"hello world {text}"

    # Append extra note text (configured via API/config server)
    final_response = f"{core_response}\n\n{state.extra_note_text}"
    
    # Every tool logs what it did
    log_entry = {
        "timestamp": timestamp,
        "type": "TOOL_CALL",
        "tool": "hello_world",
        "input": {"text": text},
        "coreOutput": core_response,
        "finalOutput": final_response
    }
    state.log_entries.append(log_entry)
    
    # Console logging for real-time monitoring
    logger.info(f"[{timestamp}] TOOL CALL: hello_world")
    logger.info(f"   Input: \"{text}\"")
    logger.info(f"   Core: \"{core_response}\"")
    
    # Return the final response to the caller
    return final_response
