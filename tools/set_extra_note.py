#!/usr/bin/env python3
# Copyright 2026 Praetorian Security, Inc.
# SPDX-License-Identifier: Apache-2.0
"""
tools/set_extra_note.py - The extra note text setter

Dead simple tool that:
- Updates the global extra note text
- Shows you what changed (old vs new)
- That's it!

This is how you change what gets appended to hello_world and ask_claude responses
without restarting the server.
    Args:
        extra_note_text: The new text to append to responses

    Returns:
        Confirmation message showing old and new values
"""

import logging
from datetime import datetime
from shared.state import get_state

logger = logging.getLogger(__name__)


async def set_extra_note(extra_note_text: str) -> str:
    state = get_state()
    timestamp = datetime.now().isoformat()
    # Remember the old value so we can show what changed
    old_extra_note = state.extra_note_text
    # Sets extra note text
    state.extra_note_text = extra_note_text
    # Log the change for our records
    log_entry = {
        "timestamp": timestamp,
        "type": "TOOL_CALL",
        "tool": "set_extra_note",
        "input": {"extra_note_text": extra_note_text},
        "oldValue": old_extra_note,
        "newValue": extra_note_text
    }
    state.log_entries.append(log_entry)

    logger.info(f"  [{timestamp}] TOOL CALL: set_extra_note")
    logger.info(f"   Old extra note: \"{old_extra_note}\"")
    logger.info(f"   New extra note: \"{extra_note_text}\"")

    return f"Extra note text updated!\n\n**Previous:** \"{old_extra_note}\"\n**New:** \"{extra_note_text}\"\n\nAll future tool calls will append this new text."

