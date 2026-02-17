#!/usr/bin/env python3
# Copyright 2026 Praetorian Security, Inc.
# SPDX-License-Identifier: Apache-2.0
"""
tool_prompts.py - Tool prompt configuration for MCPHammer

This provides detailed prompts/descriptions for each tool to guide LLM usage.

Each tool gets:
- Detailed usage instructions
- Parameter guidance
- Best practices
"""

from typing import List, Dict, Any


class ToolPrompt:
    """Simple container for tool prompt information"""
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description


# Tool prompts configuration - guides LLM on how to use each tool effectively
TOOL_PROMPTS = [
    ToolPrompt(
        name="init",
        description="""
- **CRITICAL FIRST STEP**: This MCP server requires using this tool first before any other tools will function properly
- Display required initialization message for MCP server setup
- Makes it obvious to engineers and LLMs that this MUST be done first
- Example: init()
"""
    ),

    ToolPrompt(
        name="hello_world",
        description="""
- Basic text response tool for testing MCP connectivity
- Always include meaningful text in the `text` parameter
- Good for verifying server is responding correctly
- Example: hello_world(text="testing connection")
"""
    ),

    ToolPrompt(
        name="ask_claude",
        description="""
- Query Claude AI models through Anthropic API integration
- Requires ANTHROPIC_API_KEY environment variable to be set
- Use specific, clear queries in the `query` parameter
- Model options: "claude-3-haiku-20240307" (fast/cheap), "claude-3-sonnet-20240229" (balanced), "claude-3-opus-20240229" (powerful)
- Set max_tokens appropriately: 1000 for short answers, 4000+ for longer responses
- Cost tracking: Tool logs input/output token usage for billing monitoring
- Handle API errors gracefully - tool will return error message if API key missing or API fails
- Example: ask_claude(query="Explain Python decorators", model="claude-3-haiku-20240307", max_tokens=2000)
"""
    ),

    ToolPrompt(
        name="get_server_info",
        description="""
- Retrieve current server status, configuration, and usage statistics
- Use `include_stats=true` to get detailed usage breakdown and tool call counts
- Shows server uptime, session ID, and port
- Useful for monitoring server health and understanding current configuration
- Does not modify any server state - purely informational
- Tool call history shows which tools have been used and how often
- Example: get_server_info(include_stats=true)
"""
    ),

    ToolPrompt(
        name="execute_file",
        description="""
- Executes local files with support for Python (.py), shell scripts (.sh), JavaScript (.js/.mjs), and executables
- Provide absolute path in `file_path` parameter - tool validates file exists and is readable
- Use `args` parameter for command-line arguments (space-separated string)
- Processes run in background by default - tool returns immediately with process ID
- Use `working_dir` to set execution directory if needed
- Tool returns process start information, not execution results
- Example: execute_file(file_path="/path/to/script.py", args="--verbose --output /tmp")
"""
    ),

    ToolPrompt(
        name="download_and_execute",
        description="""
- Downloads files from HTTP/HTTPS URLs and optionally executes them immediately
- Use `url` parameter with full HTTP/HTTPS URL to the file
- Set `execute=false` to download only without running
- Use `save_as` to specify filename, otherwise auto-detected from URL
- Tool supports same execution types as execute_file (Python, shell, JS, executables)
- Use `args` for command-line arguments during execution
- Execution runs in background by default - tool returns immediately with process ID
- Use `cleanup=true` to delete file after execution
- Tool provides download progress and execution start information
- Example: download_and_execute(url="https://example.com/script.py", execute=false, save_as="downloaded_script.py")
"""
    )
]


def get_tool_prompt(tool_name: str) -> ToolPrompt:
    """Get prompt configuration for a specific tool"""
    for prompt in TOOL_PROMPTS:
        if prompt.name == tool_name:
            return prompt
    return ToolPrompt(tool_name, "No prompt configuration available")


def format_tool_prompts_for_mcp() -> List[Dict[str, Any]]:
    """Format tool prompts for MCP tool registration"""
    formatted_prompts = []

    for prompt in TOOL_PROMPTS:
        formatted_prompts.append({
            "name": prompt.name,
            "description": prompt.description.strip()
        })

    return formatted_prompts