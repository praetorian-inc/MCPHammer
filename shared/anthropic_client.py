#!/usr/bin/env python3
# Copyright 2026 Praetorian Security, Inc.
# SPDX-License-Identifier: Apache-2.0
"""
Super simple file that:
- Creates one Anthropic client and reuses it
- Reads your API key from the environment
- Yells at you if you forgot to set ANTHROPIC_API_KEY
- Lazy loads (only creates client when first needed)

Used by: ask_claude tool (and any future Claude-powered tools)
    Returns:
        Anthropic client if API key is set, None otherwise
"""

import os
from anthropic import Anthropic
from typing import Optional


def is_api_key_available() -> bool:
    #Check if API key is available 
    return ANTHROPIC_API_KEY is not None

# Set API key - uses environment variable. 
# In the future this should probably be passed by the user or the AI Agent
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

_anthropic_client = None
_warned_about_missing_key = False

def get_anthropic_client() -> Optional[Anthropic]:

    global _anthropic_client, _warned_about_missing_key
    
    # No API key? Return None instead of crashing
    if not ANTHROPIC_API_KEY:
        if not _warned_about_missing_key:
            # Only warn once to avoid spam
            _warned_about_missing_key = True
            print("\nWARNING: ANTHROPIC_API_KEY not set - ask_claude tool will not work!")
        return None
    
    # First time with valid key? Create the client
    if _anthropic_client is None:
        _anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)
    
    return _anthropic_client


def initialize_anthropic_client() -> Optional[Anthropic]:
    """
    Initialize and return the global Anthropic client.
    
    No longer raises on missing API key - just returns None.
    This allows the server to start without Claude functionality.
    """
    global _anthropic_client
    
    if not ANTHROPIC_API_KEY:
        return None
    
    # Create fresh client instance
    _anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)
    return _anthropic_client