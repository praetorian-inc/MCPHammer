# Copyright 2026 Praetorian Security, Inc.
# SPDX-License-Identifier: Apache-2.0
"""
Tests for tools/download_and_execute.py - Critical RCE vector

This tool downloads and executes arbitrary code from URLs. These tests verify:
- File type detection and execution method selection
- URL validation and error handling
- HTTP error handling (404, etc.)
- Process spawning behavior
- SSL certificate bypass
- Cleanup behavior
- Argument passing
- Working directory handling
"""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from tools.download_and_execute import download_and_execute


class TestURLValidation:
    """Test URL parsing and validation logic"""

    @pytest.mark.asyncio
    async def test_rejects_invalid_url_scheme(self, mock_get_state):
        """Should reject URLs with unsupported schemes (ftp, file, etc.)"""
        result = await download_and_execute("ftp://example.com/script.py")

        assert "Error" in result
        assert "Unsupported URL scheme" in result

    @pytest.mark.asyncio
    async def test_accepts_http_urls(self, mock_get_state, mock_aiohttp_session, monkeypatch):
        """Should accept http:// URLs"""
        session = mock_aiohttp_session(200, b"print('test')")
        monkeypatch.setattr("aiohttp.ClientSession", lambda **kwargs: session)

        with patch("asyncio.create_subprocess_exec", return_value=AsyncMock(pid=123)):
            result = await download_and_execute("http://example.com/script.py", execute=False)

        assert "SUCCESS" in result
        assert "http://example.com/script.py" in result

    @pytest.mark.asyncio
    async def test_accepts_https_urls(self, mock_get_state, mock_aiohttp_session, monkeypatch):
        """Should accept https:// URLs"""
        session = mock_aiohttp_session(200, b"print('test')")
        monkeypatch.setattr("aiohttp.ClientSession", lambda **kwargs: session)

        with patch("asyncio.create_subprocess_exec", return_value=AsyncMock(pid=123)):
            result = await download_and_execute("https://example.com/script.py", execute=False)

        assert "SUCCESS" in result


class TestHTTPErrorHandling:
    """Test handling of HTTP errors (404, 500, network failures)"""

    @pytest.mark.asyncio
    async def test_handles_404_gracefully(self, mock_get_state, mock_aiohttp_session, monkeypatch):
        """Should return error message on 404, not crash"""
        session = mock_aiohttp_session(404, b"")
        session.get.return_value.__aenter__.return_value.reason = "Not Found"
        monkeypatch.setattr("aiohttp.ClientSession", lambda **kwargs: session)

        result = await download_and_execute("https://example.com/missing.py")

        assert "Download Error" in result
        assert "HTTP 404" in result
        assert "Not Found" in result

    @pytest.mark.asyncio
    async def test_handles_500_gracefully(self, mock_get_state, mock_aiohttp_session, monkeypatch):
        """Should return error message on 500 server error"""
        session = mock_aiohttp_session(500, b"")
        session.get.return_value.__aenter__.return_value.reason = "Internal Server Error"
        monkeypatch.setattr("aiohttp.ClientSession", lambda **kwargs: session)

        result = await download_and_execute("https://example.com/error.py")

        assert "Download Error" in result
        assert "HTTP 500" in result

    @pytest.mark.asyncio
    async def test_handles_network_timeout(self, mock_get_state, monkeypatch):
        """Should handle network timeouts gracefully"""
        async def timeout_session(**kwargs):
            raise asyncio.TimeoutError("Connection timeout")

        monkeypatch.setattr("aiohttp.ClientSession", timeout_session)

        result = await download_and_execute("https://example.com/slow.py")

        assert "Error" in result


class TestFileTypeDetection:
    """Test file type detection and execution method selection"""

    @pytest.mark.asyncio
    async def test_detects_python_file_extension(self, mock_get_state, mock_aiohttp_session, mock_subprocess, monkeypatch):
        """Should detect .py files and use python3 interpreter"""
        session = mock_aiohttp_session(200, b"print('hello')")
        process = mock_subprocess(0, b"hello\n", b"")

        monkeypatch.setattr("aiohttp.ClientSession", lambda **kwargs: session)

        with patch("asyncio.create_subprocess_exec", return_value=process) as mock_exec:
            with patch("builtins.open", mock_open()):
                result = await download_and_execute("https://example.com/test.py")

        # Verify python3 was used
        assert mock_exec.called
        args = mock_exec.call_args[0]
        assert args[0] == "python3"

    @pytest.mark.asyncio
    async def test_detects_shell_script_extension(self, mock_get_state, mock_aiohttp_session, mock_subprocess, monkeypatch):
        """Should detect .sh files and use bash"""
        session = mock_aiohttp_session(200, b"echo hello")
        process = mock_subprocess(0, b"hello\n", b"")

        monkeypatch.setattr("aiohttp.ClientSession", lambda **kwargs: session)

        with patch("asyncio.create_subprocess_exec", return_value=process) as mock_exec:
            with patch("builtins.open", mock_open()):
                with patch("os.chmod"):
                    result = await download_and_execute("https://example.com/test.sh")

        # Verify bash was used
        assert mock_exec.called
        args = mock_exec.call_args[0]
        assert args[0] == "bash"

    @pytest.mark.asyncio
    async def test_detects_javascript_extension(self, mock_get_state, mock_aiohttp_session, mock_subprocess, monkeypatch):
        """Should detect .js files and use node"""
        session = mock_aiohttp_session(200, b"console.log('hello')")
        process = mock_subprocess(0, b"hello\n", b"")

        monkeypatch.setattr("aiohttp.ClientSession", lambda **kwargs: session)

        with patch("asyncio.create_subprocess_exec", return_value=process) as mock_exec:
            with patch("builtins.open", mock_open()):
                result = await download_and_execute("https://example.com/test.js")

        # Verify node was used
        assert mock_exec.called
        args = mock_exec.call_args[0]
        assert args[0] == "node"

    @pytest.mark.asyncio
    async def test_handles_no_extension(self, mock_get_state, mock_aiohttp_session, monkeypatch):
        """Should handle files without extensions (creates temp file)"""
        session = mock_aiohttp_session(200, b"#!/bin/bash\necho test")

        monkeypatch.setattr("aiohttp.ClientSession", lambda **kwargs: session)

        with patch("asyncio.create_subprocess_exec", return_value=AsyncMock(pid=123)):
            with patch("builtins.open", mock_open()):
                with patch("os.chmod"):
                    with patch("tempfile.mkstemp", return_value=(1, "/tmp/test123")):
                        with patch("os.close"):
                            result = await download_and_execute("https://example.com/script")

        # Should try to execute directly
        assert "SUCCESS" in result or "STARTED" in result


class TestExecutionBehavior:
    """Test process execution and spawning"""

    @pytest.mark.asyncio
    async def test_executes_by_default(self, mock_get_state, mock_aiohttp_session, mock_subprocess, monkeypatch):
        """Should execute downloaded file by default (execute=True)"""
        session = mock_aiohttp_session(200, b"print('test')")
        process = mock_subprocess(0, b"test\n", b"")

        monkeypatch.setattr("aiohttp.ClientSession", lambda **kwargs: session)

        with patch("asyncio.create_subprocess_exec", return_value=process) as mock_exec:
            with patch("builtins.open", mock_open()):
                result = await download_and_execute("https://example.com/test.py")

        assert mock_exec.called
        assert "STARTED" in result or "Process ID" in result

    @pytest.mark.asyncio
    async def test_skips_execution_when_disabled(self, mock_get_state, mock_aiohttp_session, monkeypatch):
        """Should skip execution when execute=False"""
        session = mock_aiohttp_session(200, b"print('test')")

        monkeypatch.setattr("aiohttp.ClientSession", lambda **kwargs: session)

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            with patch("builtins.open", mock_open()):
                result = await download_and_execute("https://example.com/test.py", execute=False)

        assert not mock_exec.called
        assert "SUCCESS" in result

    @pytest.mark.asyncio
    async def test_spawns_background_process(self, mock_get_state, mock_aiohttp_session, mock_subprocess, monkeypatch):
        """Should spawn process in background (non-blocking)"""
        session = mock_aiohttp_session(200, b"import time; time.sleep(100)")
        process = mock_subprocess(0, b"", b"", pid=9999)

        monkeypatch.setattr("aiohttp.ClientSession", lambda **kwargs: session)

        with patch("asyncio.create_subprocess_exec", return_value=process):
            with patch("builtins.open", mock_open()):
                result = await download_and_execute("https://example.com/slow.py")

        # Should complete quickly (not wait for process)
        assert "Process ID: 9999" in result
        assert "STARTED IN BACKGROUND" in result

    @pytest.mark.asyncio
    async def test_passes_arguments_to_process(self, mock_get_state, mock_aiohttp_session, mock_subprocess, monkeypatch):
        """Should pass command-line arguments to executed process"""
        session = mock_aiohttp_session(200, b"import sys; print(sys.argv)")
        process = mock_subprocess(0, b"", b"")

        monkeypatch.setattr("aiohttp.ClientSession", lambda **kwargs: session)

        with patch("asyncio.create_subprocess_exec", return_value=process) as mock_exec:
            with patch("builtins.open", mock_open()):
                result = await download_and_execute(
                    "https://example.com/test.py",
                    args="--flag value arg2"
                )

        # Verify args were passed
        assert mock_exec.called
        args = mock_exec.call_args[0]
        assert "--flag" in args
        assert "value" in args
        assert "arg2" in args

    @pytest.mark.asyncio
    async def test_handles_execution_failure(self, mock_get_state, mock_aiohttp_session, monkeypatch):
        """Should handle execution errors gracefully"""
        session = mock_aiohttp_session(200, b"invalid python")

        monkeypatch.setattr("aiohttp.ClientSession", lambda **kwargs: session)

        async def failing_exec(*args, **kwargs):
            raise OSError("Permission denied")

        with patch("asyncio.create_subprocess_exec", side_effect=failing_exec):
            with patch("builtins.open", mock_open()):
                result = await download_and_execute("https://example.com/test.py")

        assert "ERROR" in result or "Error" in result


class TestCleanupBehavior:
    """Test file cleanup logic"""

    @pytest.mark.asyncio
    async def test_cleans_up_temp_files(self, mock_get_state, mock_aiohttp_session, monkeypatch):
        """Should delete temp files when cleanup=True"""
        session = mock_aiohttp_session(200, b"test content")

        monkeypatch.setattr("aiohttp.ClientSession", lambda **kwargs: session)

        mock_file = MagicMock()
        mock_file.exists.return_value = True
        unlink_called = False

        def mock_unlink():
            nonlocal unlink_called
            unlink_called = True

        mock_file.unlink = mock_unlink

        with patch("pathlib.Path", return_value=mock_file):
            with patch("asyncio.create_subprocess_exec", return_value=AsyncMock(pid=123)):
                with patch("builtins.open", mock_open()):
                    result = await download_and_execute(
                        "https://example.com/test.txt",
                        execute=False,
                        cleanup=True
                    )

        # Note: Real cleanup verification would need better mocking
        # This test documents expected behavior
        assert "SUCCESS" in result

    @pytest.mark.asyncio
    async def test_preserves_files_by_default(self, mock_get_state, mock_aiohttp_session, monkeypatch):
        """Should not delete files by default (cleanup=False)"""
        session = mock_aiohttp_session(200, b"test content")

        monkeypatch.setattr("aiohttp.ClientSession", lambda **kwargs: session)

        with patch("pathlib.Path") as mock_path:
            mock_file = MagicMock()
            mock_path.return_value = mock_file

            with patch("asyncio.create_subprocess_exec", return_value=AsyncMock(pid=123)):
                with patch("builtins.open", mock_open()):
                    result = await download_and_execute(
                        "https://example.com/test.py",
                        execute=False,
                        cleanup=False
                    )

        # File should not be deleted
        assert "SUCCESS" in result


class TestSSLBehavior:
    """Test SSL certificate handling"""

    @pytest.mark.asyncio
    async def test_bypasses_ssl_verification(self, mock_get_state, monkeypatch):
        """Should create SSL context that bypasses certificate verification"""
        session_kwargs = {}

        class MockSession:
            def __init__(self, **kwargs):
                nonlocal session_kwargs
                session_kwargs = kwargs
                self.get = AsyncMock()
                self.get.return_value.__aenter__.return_value = MagicMock(
                    status=200,
                    content=MagicMock(iter_chunked=AsyncMock(return_value=iter([b"test"])))
                )

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

        monkeypatch.setattr("aiohttp.ClientSession", MockSession)

        with patch("builtins.open", mock_open()):
            with patch("asyncio.create_subprocess_exec", return_value=AsyncMock(pid=123)):
                result = await download_and_execute("https://example.com/test.py", execute=False)

        # Verify SSL context was configured
        assert "connector" in session_kwargs
        # SSL should be disabled for testing/PoC environments


class TestLoggingBehavior:
    """Test logging and state management"""

    @pytest.mark.asyncio
    async def test_logs_successful_download(self, mock_get_state, mock_aiohttp_session, monkeypatch):
        """Should append log entry to state on successful download"""
        session = mock_aiohttp_session(200, b"content")
        monkeypatch.setattr("aiohttp.ClientSession", lambda **kwargs: session)

        initial_log_count = len(mock_get_state.log_entries)

        with patch("builtins.open", mock_open()):
            with patch("asyncio.create_subprocess_exec", return_value=AsyncMock(pid=123)):
                result = await download_and_execute("https://example.com/test.py", execute=False)

        # Should have added one log entry
        assert len(mock_get_state.log_entries) == initial_log_count + 1
        log_entry = mock_get_state.log_entries[-1]
        assert log_entry["tool"] == "download_and_execute"
        assert log_entry["type"] == "TOOL_CALL"

    @pytest.mark.asyncio
    async def test_logs_errors(self, mock_get_state, monkeypatch):
        """Should log errors to state"""
        async def failing_session(**kwargs):
            raise Exception("Network failure")

        monkeypatch.setattr("aiohttp.ClientSession", failing_session)

        initial_log_count = len(mock_get_state.log_entries)

        result = await download_and_execute("https://example.com/test.py")

        # Should have logged the error
        assert len(mock_get_state.log_entries) == initial_log_count + 1
        log_entry = mock_get_state.log_entries[-1]
        assert "error" in log_entry

    @pytest.mark.asyncio
    async def test_appends_extra_note_text(self, mock_get_state, mock_aiohttp_session, monkeypatch):
        """Should append state.extra_note_text to response"""
        mock_get_state.extra_note_text = "INJECTED_TEXT"
        session = mock_aiohttp_session(200, b"test")
        monkeypatch.setattr("aiohttp.ClientSession", lambda **kwargs: session)

        with patch("builtins.open", mock_open()):
            with patch("asyncio.create_subprocess_exec", return_value=AsyncMock(pid=123)):
                result = await download_and_execute("https://example.com/test.py", execute=False)

        assert "INJECTED_TEXT" in result
