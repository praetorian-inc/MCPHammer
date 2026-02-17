# Copyright 2026 Praetorian Security, Inc.
# SPDX-License-Identifier: Apache-2.0
"""
Shared test fixtures for MCPHammer test suite.

This file provides common fixtures and test utilities:
- Mock state objects
- Temp file/directory management
- Mock HTTP responses
- Process execution mocks
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock
from typing import Dict, Any, List


@pytest.fixture
def mock_state():
    """Mock ServerState object for testing tools without side effects"""
    state = MagicMock()
    state.extra_note_text = ""
    state.init_url = "https://example.com/test.txt"
    state.log_entries = []
    state.session_id = "test-session-123"
    state.start_time = MagicMock()
    state.port = 3000
    state.log_file = "/tmp/test-log.log"
    return state


@pytest.fixture
def mock_get_state(monkeypatch, mock_state):
    """Patch shared.state.get_state() to return mock state"""
    def _mock_get_state():
        return mock_state

    monkeypatch.setattr("shared.state.get_state", _mock_get_state)
    return mock_state


@pytest.fixture
def temp_file():
    """Create a temporary file that's cleaned up after the test"""
    temp_fd, temp_path = tempfile.mkstemp()
    temp_path_obj = Path(temp_path)
    yield temp_path_obj

    # Cleanup
    try:
        if temp_path_obj.exists():
            temp_path_obj.unlink()
    except:
        pass


@pytest.fixture
def temp_dir():
    """Create a temporary directory that's cleaned up after the test"""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def mock_http_response():
    """Factory for creating mock aiohttp response objects"""
    def _create_response(status=200, content=b"test content", reason="OK"):
        response = AsyncMock()
        response.status = status
        response.reason = reason

        # Mock content.iter_chunked() for file downloads
        async def iter_chunked(chunk_size):
            yield content

        response.content.iter_chunked = iter_chunked
        return response

    return _create_response


@pytest.fixture
def mock_aiohttp_session(mock_http_response):
    """Mock aiohttp.ClientSession for HTTP requests"""
    def _create_session(response_status=200, response_content=b"test content"):
        # Create a proper mock that supports async context manager
        response = mock_http_response(response_status, response_content)

        # Mock the get() method's return value (which is an async context manager)
        get_result = AsyncMock()
        get_result.__aenter__.return_value = response
        get_result.__aexit__.return_value = None

        # Create the session mock
        session = MagicMock()
        session.get = MagicMock(return_value=get_result)

        # Make the session itself an async context manager
        async def session_aenter(self):
            return session

        async def session_aexit(self, *args):
            return None

        session.__aenter__ = session_aenter
        session.__aexit__ = session_aexit

        return session

    return _create_session


@pytest.fixture
def mock_subprocess():
    """Mock asyncio.create_subprocess_exec for process execution"""
    def _create_process(returncode=0, stdout=b"", stderr=b"", pid=12345):
        process = AsyncMock()
        process.returncode = returncode
        process.pid = pid
        process.communicate.return_value = (stdout, stderr)
        return process

    return _create_process


@pytest.fixture(autouse=True)
def reset_state():
    """Reset global state between tests to prevent test pollution"""
    # This runs before each test
    yield
    # This runs after each test
    # Clear any cached state
    import shared.state
    shared.state._state = None
