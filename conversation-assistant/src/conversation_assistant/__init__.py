#!/usr/bin/env python3
"""
Conversation Assistant MCP Server

A Model Context Protocol server that provides:
- Current time/date/timezone context
- Persistent user rules and preferences
- Conversation summarization
"""

__version__ = "1.0.0"
__author__ = "Domenic Lo Iacono"

from .config import Config
from .server import main

__all__ = ["Config", "main"]