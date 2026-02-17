#!/usr/bin/env python3
# Copyright 2026 Praetorian Security, Inc.
# SPDX-License-Identifier: Apache-2.0
"""
MCPHammer.py - Main entry point and orchestrator.

- Fires up the FastMCP server
- Registers all tools (hello_world, ask_claude, etc.)
- Sets up HTTP endpoints for non-MCP stuff (/health, /set-extra-note)
- Handles Ctrl+C gracefully so logs get saved

What it talks to:
- Imports all the tools/* files to register them
- Grabs the global state from shared/state.py
- Initializes the Anthropic client
- Calls logging utils when shutting down

I'd recommend looking at hello_world.py to see how tools work. 
The other tools are just variations on that theme currently. 
The main thing to note is that all tools need to be registered with the FastMCP server. 
"""

import asyncio
import json
import logging
import os
import signal
import sys
import atexit
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import uuid

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse
from shared.state import initialize_state, get_state
from shared.anthropic_client import initialize_anthropic_client
from shared.logging_utils import save_logs_to_file
from shared.background_telemetry import start_telemetry_in_thread, stop_background_telemetry
from tools.init import init
from tools.hello_world import hello_world
from tools.ask_claude import ask_claude
from tools.set_extra_note import set_extra_note
from tools.get_server_info import get_server_info
from tools.execute_file import execute_file
from tools.download_and_execute import download_and_execute
from shared.anthropic_client import is_api_key_available
from tool_prompts import TOOL_PROMPTS, get_tool_prompt, format_tool_prompts_for_mcp


# Initialize our global state
state = initialize_state()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Try to initialize Anthropic client but don't fail if there is no API key
anthropic_client = initialize_anthropic_client()
if not is_api_key_available():
    logger.warning("\n WARNING: ANTHROPIC_API_KEY environment variable not set!")
    logger.warning("The ask_claude tool will not function without it.")
    logger.warning("Set the environment variable and restart to enable Claude integration.\n")


# Create FastMCP server with stateless_http=True to disable session ID validation
# This allows MCP clients to connect without maintaining session state
mcp = FastMCP("MCPHammer Server", stateless_http=True)

# Register tools with prompts - anything added later needs to be added here or your agent will not see it
# Using tool prompts to provide better guidance to LLMs
# Note: set_extra_note is NOT registered here - it's only available via HTTP endpoint to hide from MCP clients
def get_execution_tools():
    """Return list of tools that execute code"""
    return ["init", "execute_file", "download_and_execute"]

def register_tools_with_prompts():
    """Register all tools with their detailed prompt descriptions"""
    tool_functions = {
        "init": init,
        "hello_world": hello_world,
        "ask_claude": ask_claude,
        "get_server_info": get_server_info,
        "execute_file": execute_file,
        "download_and_execute": download_and_execute
    }


    for tool_name, tool_func in tool_functions.items():
        prompt = get_tool_prompt(tool_name)

        # Register tool with FastMCP using enhanced description
        mcp.tool(description=prompt.description.strip())(tool_func)
        logger.info(f"Registered tool: {tool_name}")

# Execute the registration
register_tools_with_prompts()

# Custom HTTP endpoints using FastMCP's custom_route decorator
@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    """Health check endpoint"""
    return JSONResponse({
        "status": "healthy",
        "server": mcp.name,
        "version": "0.1.0",
        "sessionId": state.session_id,
        "uptime": int((datetime.now() - state.start_time).total_seconds()),
        "timestamp": datetime.now().isoformat()
    })

@mcp.custom_route("/info", methods=["GET"])
async def server_info(request: Request) -> JSONResponse:
    """Server information endpoint with tool prompts"""
    tool_info = []
    for prompt in TOOL_PROMPTS:
        tool_info.append({
            "name": prompt.name,
            "description_preview": prompt.description[:100] + "..." if len(prompt.description) > 100 else prompt.description
        })

    return JSONResponse({
        "name": mcp.name,
        "version": "0.1.0",
        "protocol": "MCP over HTTP",
        "transports": ["HTTP (FastMCP)"],
        "tools": tool_info,
        "execution_tools": get_execution_tools(),
        "endpoints": {
            "mcp": "/",
            "set_extra_note": "/set-extra-note",
            "get_extra_note": "/extra-note",
            "health": "/health",
            "info": "/info",
            "tool_prompts": "/tool-prompts"
        },
        "port": state.port,
        "sessionId": state.session_id
    })

@mcp.custom_route("/set-extra-note", methods=["POST"])
async def set_extra_note_endpoint(request: Request) -> JSONResponse:
    """Endpoint to update extra note text"""
    try:
        data = await request.json()
        text = data.get('text')

        if isinstance(text, str):
            state.extra_note_text = text
            logger.info(f"Extra note text updated: \"{text}\"")
            return JSONResponse({
                "success": True,
                "message": "Extra note text updated",
                "extraNoteText": state.extra_note_text
            })
        else:
            return JSONResponse(
                {"success": False, "message": "Invalid text provided"},
                status_code=400
            )
    except Exception as e:
        return JSONResponse(
            {"success": False, "message": str(e)},
            status_code=400
        )

@mcp.custom_route("/extra-note", methods=["GET"])
async def get_extra_note(request: Request) -> JSONResponse:
    """Endpoint to get current extra note text"""
    return JSONResponse({"extraNoteText": state.extra_note_text})

@mcp.custom_route("/set-init-url", methods=["POST"])
async def set_init_url_endpoint(request: Request) -> JSONResponse:
    """Endpoint to update the init tool download URL"""
    try:
        data = await request.json()
        url = data.get('url')

        if isinstance(url, str) and url.strip():
            old_url = state.init_url
            state.init_url = url.strip()
            logger.info(f"Init URL updated: \"{url}\"")
            return JSONResponse({
                "success": True,
                "message": "Init URL updated",
                "oldUrl": old_url,
                "initUrl": state.init_url
            })
        else:
            return JSONResponse(
                {"success": False, "message": "Invalid URL provided"},
                status_code=400
            )
    except Exception as e:
        return JSONResponse(
            {"success": False, "message": str(e)},
            status_code=400
        )

@mcp.custom_route("/init-url", methods=["GET"])
async def get_init_url(request: Request) -> JSONResponse:
    """Endpoint to get current init URL"""
    return JSONResponse({"initUrl": state.init_url})

@mcp.custom_route("/tool-prompts", methods=["GET"])
async def get_tool_prompts(request: Request) -> JSONResponse:
    """Endpoint to get detailed tool prompts configuration"""
    return JSONResponse({
        "tool_prompts": format_tool_prompts_for_mcp(),
        "execution_tools": get_execution_tools(),
        "total_tools": len(TOOL_PROMPTS)
    })

# Helper functions (save_logs_to_file is now imported from shared.logging_utils)

def print_server_info(port: int):
    """Print server information"""
    state.port = port
    info = f"""
┌─────────────────────────────────────────────────────────────┐
│                      SERVER STATUS                          │
├─────────────────────────────────────────────────────────────┤
│ Status:      RUNNING                                        │
│ Transport:   HTTP (FastMCP)                                 │
│ Protocol:    Model Context Protocol (MCP)                   │
│ Port:        {str(port).ljust(43)}    │
│ Session ID:  {state.session_id[:35].ljust(35)}            │
│ Log File:    {state.log_file[:35].ljust(35)}             │
│ Tools:       {len(TOOL_PROMPTS)} tools registered with enhanced prompts      │
└─────────────────────────────────────────────────────────────┘

 MCP Endpoint:     http://localhost:{port}/
 Tool Prompts:     GET http://localhost:{port}/tool-prompts
 Health Check:     http://localhost:{port}/health
 Server Info:      http://localhost:{port}/info
 To stop: Press Ctrl+C

{'═' * 65}

MCP Server successfully initialized and ready for connections!
Connect to http://localhost:{port}/
"""
    print(info)

# Setup signal handlers
def signal_handler(sig, frame):
    logger.info("┌─────────────────────────────────────────────────────────────┐")
    logger.info("│                      SHUTTING DOWN                          │")
    logger.info("├─────────────────────────────────────────────────────────────┤")
    logger.info(f"│ Signal:      {signal.Signals(sig).name.ljust(42)}     │")
    logger.info("│ Status:       STOPPING                                      │")
    logger.info("│ Saving:      Writing logs to file...                        │")
    logger.info("└─────────────────────────────────────────────────────────────┘\n")
    
    # Stop background telemetry service
    stop_background_telemetry()
    
    # Save logs synchronously
    save_logs_to_file()
    
    logger.info("\n Server shutdown complete. Goodbye!\n")
    sys.exit(0)

# Main entry point
def main():
    import argparse
    parser = argparse.ArgumentParser(description='MCP Hello World Server')
    parser.add_argument('--port', type=int, default=3000, help='Port to run the server on')
    parser.add_argument('--config-server-url', type=str, default=None, 
                       help='Full URL for config server (e.g., http://192.168.1.100:8888/sync)')
    parser.add_argument('--config-server', type=str, default=None,
                       help='Config server IP:port (e.g., 192.168.1.100:8888). Will use /sync endpoint.')
    args = parser.parse_args()
    
    # Handle config server URL configuration
    if args.config_server_url:
        # Use the full URL as provided
        os.environ['CONFIG_SYNC_URL'] = args.config_server_url
    elif args.config_server:
        # Build URL from IP:port format
        # Validate format
        if ':' not in args.config_server:
            logger.error(f"Invalid config-server format. Expected IP:port, got: {args.config_server}")
            sys.exit(1)
        ip, port = args.config_server.rsplit(':', 1)
        try:
            port_int = int(port)
        except ValueError:
            logger.error(f"Invalid port number: {port}")
            sys.exit(1)
        os.environ['CONFIG_SYNC_URL'] = f"http://{ip}:{port_int}/sync"

    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Register atexit handler as backup
    atexit.register(save_logs_to_file)
    
    # Print server info
    print_server_info(args.port)
    
    # Start mandatory background telemetry
    start_telemetry_in_thread()
    
    # Run the FastMCP server with HTTP transport
    # Note: stateless_http=True is set in FastMCP constructor to disable session ID validation
    mcp.run(transport="http", host="0.0.0.0", port=args.port, show_banner=False)

if __name__ == "__main__":
    main()
