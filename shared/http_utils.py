# Copyright 2026 Praetorian Security, Inc.
# SPDX-License-Identifier: Apache-2.0
"""
Shared HTTP utilities for MCP tools.

Provides SSL context creation for environments with certificate issues.
"""

import ssl
import aiohttp


def create_insecure_ssl_context() -> ssl.SSLContext:
    """
    Create SSL context that bypasses certificate verification.

    WARNING: This is for PoC/testing environments only!
    Disables certificate validation which can be a security risk.

    Returns:
        SSL context with verification disabled
    """
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    return ssl_context


def create_insecure_session(**kwargs) -> aiohttp.ClientSession:
    """
    Create aiohttp session with SSL verification disabled.

    WARNING: For PoC/testing environments only!

    Args:
        **kwargs: Additional keyword arguments for ClientSession

    Returns:
        ClientSession configured to ignore SSL errors
    """
    ssl_context = create_insecure_ssl_context()
    connector = aiohttp.TCPConnector(ssl=ssl_context)
    return aiohttp.ClientSession(connector=connector, **kwargs)
