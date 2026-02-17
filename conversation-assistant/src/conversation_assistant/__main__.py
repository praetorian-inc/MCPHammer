#!/usr/bin/env python3
"""
Entry point for running conversation-assistant as a module
"""

if __name__ == "__main__":
    from .server import main
    import asyncio

    asyncio.run(main())