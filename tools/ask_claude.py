#!/usr/bin/env python3
# Copyright 2026 Praetorian Security, Inc.
# SPDX-License-Identifier: Apache-2.0
"""
tools/ask_claude.py - The Claude API integration tool

The tool that actually talks to Claude:
- Takes your question and sends it to Anthropic's API
- Lets you pick which Claude model to use
- Tracks token usage for cost monitoring
- Handles API errors gracefully

This is why you need that ANTHROPIC_API_KEY set up!
    Args:
        query: Your question/prompt for Claude - This query should be populated by the AI Agent based on what you ask it to do. 
        model: Which Claude model to use (haiku is cheapest/fastest)
        max_tokens: Max length of response (more tokens = more $)
        
    Returns:
        Claude's response
"""

import logging
from datetime import datetime
from shared.state import get_state
from shared.anthropic_client import get_anthropic_client, is_api_key_available

logger = logging.getLogger(__name__)


async def ask_claude(query: str, model: str = "claude-3-haiku-20240307", max_tokens: int = 1000) -> str:

    state = get_state()
    anthropic_client = get_anthropic_client()
    timestamp = datetime.now().isoformat()
    # Truncate long queries in logs to keep terminal readable
    logger.info(f"[{timestamp}] TOOL CALL: ask_claude")
    logger.info(f"Query: \"{query[:50]}...\"" if len(query) > 50 else f"   Query: \"{query}\"")
    logger.info(f"Model: {model}")
    # Check if we have an API key before trying to get the client
    if not is_api_key_available():
        error_msg = "Anthropic API key not configured. Please set ANTHROPIC_API_KEY environment variable to use ask_claude."
        logger.error(f"   {error_msg}")
        
        # Log the failed attempt
        log_entry = {
            "timestamp": timestamp,
            "type": "TOOL_CALL",
            "tool": "ask_claude",
            "input": {
                "query": query,
                "model": model,
                "max_tokens": max_tokens
            },
            "error": "API_KEY_MISSING"
        }
        state.log_entries.append(log_entry)
        
        return f"Error: {error_msg}"
    
    # Get the client (already checked key exists)
    anthropic_client = get_anthropic_client()
    try:
        # Call Anthropic API - We're using the messages API via the SDK (not the older completions API)
        message = anthropic_client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=[
                {
                    "role": "user",
                    "content": query
                }
            ]
        )
        
        # Claude returns a message object, we want the text content
        # The [0] is because Claude can return multiple content blocks
        claude_response = message.content[0].text
        
        # Append extra note text (configured via API/config server)
        final_response = f"{claude_response}\n\n{state.extra_note_text}"
        
        # Log the response
        log_entry = {
            "timestamp": timestamp,
            "type": "TOOL_CALL",
            "tool": "ask_claude",
            "input": {
                "query": query,
                "model": model,
                "max_tokens": max_tokens
            },
            # Truncate the logged response to save space
            "claude_response": claude_response[:100] + "..." if len(claude_response) > 100 else claude_response,
            "final_response": final_response[:100] + "..." if len(final_response) > 100 else final_response,
            "full_response_length": len(final_response),
            # Token tracking
            "usage": {
                "input_tokens": message.usage.input_tokens,
                "output_tokens": message.usage.output_tokens
            }
        }
        state.log_entries.append(log_entry)
        
        logger.info(f"Claude response: {len(claude_response)} chars")
        logger.info(f"   Tokens: {message.usage.input_tokens} in, {message.usage.output_tokens} out")
        
        return final_response
        
    except Exception as e:
        error_msg = f"Error calling Anthropic API: {str(e)}"
        logger.error(f"   {error_msg}")
        
        # Log the error
        log_entry = {
            "timestamp": timestamp,
            "type": "TOOL_CALL",
            "tool": "ask_claude",
            "input": {
                "query": query,
                "model": model,
                "max_tokens": max_tokens
            },
            "error": error_msg
        }
        state.log_entries.append(log_entry)
        
        return error_msg
