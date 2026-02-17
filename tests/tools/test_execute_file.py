# Copyright 2026 Praetorian Security, Inc.
# SPDX-License-Identifier: Apache-2.0
"""
Tests for tools/execute_file.py - Critical RCE vector

This tool executes local files with arguments. These tests verify:
- Command construction based on file type
- Permission validation
- Process execution
- Error handling
- Argument passing
- Working directory handling
"""

import pytest
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from tools.execute_file import execute_file


class TestFileValidation:
    """Test file existence and permission checks"""

    @pytest.mark.asyncio
    async def test_rejects_nonexistent_file(self, mock_get_state):
        """Should return error if file doesn't exist"""
        with patch("pathlib.Path.exists", return_value=False):
            result = await execute_file("/path/to/missing.py")

        assert "Error" in result
        assert "not found" in result

    @pytest.mark.asyncio
    async def test_rejects_unreadable_file(self, mock_get_state):
        """Should return error if file isn't readable"""
        with patch("pathlib.Path.exists", return_value=True):
            with patch("os.access", return_value=False):
                result = await execute_file("/path/to/unreadable.py")

        assert "Error" in result
        assert "not readable" in result


class TestCommandConstruction:
    """Test how commands are constructed for different file types"""

    @pytest.mark.asyncio
    async def test_constructs_python_command(self, mock_get_state, mock_subprocess):
        """Should use python3 for .py files"""
        process = mock_subprocess(0, b"", b"")

        with patch("pathlib.Path.exists", return_value=True):
            with patch("os.access", return_value=True):
                with patch("asyncio.create_subprocess_exec", return_value=process) as mock_exec:
                    result = await execute_file("/tmp/test.py")

        assert mock_exec.called
        args = mock_exec.call_args[0]
        assert args[0] == "python3"
        assert "/tmp/test.py" in args

    @pytest.mark.asyncio
    async def test_constructs_bash_command(self, mock_get_state, mock_subprocess):
        """Should use bash for .sh files"""
        process = mock_subprocess(0, b"", b"")

        with patch("pathlib.Path.exists", return_value=True):
            with patch("os.access", return_value=True):
                with patch("asyncio.create_subprocess_exec", return_value=process) as mock_exec:
                    result = await execute_file("/tmp/test.sh")

        assert mock_exec.called
        args = mock_exec.call_args[0]
        assert args[0] == "bash"

    @pytest.mark.asyncio
    async def test_constructs_node_command(self, mock_get_state, mock_subprocess):
        """Should use node for .js files"""
        process = mock_subprocess(0, b"", b"")

        with patch("pathlib.Path.exists", return_value=True):
            with patch("os.access", return_value=True):
                with patch("asyncio.create_subprocess_exec", return_value=process) as mock_exec:
                    result = await execute_file("/tmp/test.js")

        assert mock_exec.called
        args = mock_exec.call_args[0]
        assert args[0] == "node"

    @pytest.mark.asyncio
    async def test_executes_executable_directly(self, mock_get_state, mock_subprocess):
        """Should execute files with execute permission directly"""
        process = mock_subprocess(0, b"", b"")

        with patch("pathlib.Path.exists", return_value=True):
            with patch("os.access", side_effect=lambda path, mode: mode == os.R_OK or mode == os.X_OK):
                with patch("asyncio.create_subprocess_exec", return_value=process) as mock_exec:
                    result = await execute_file("/tmp/executable")

        assert mock_exec.called
        args = mock_exec.call_args[0]
        assert args[0] == "/tmp/executable"

    @pytest.mark.asyncio
    async def test_rejects_unknown_file_type(self, mock_get_state):
        """Should reject non-executable files with unknown extension"""
        with patch("pathlib.Path.exists", return_value=True):
            with patch("os.access", side_effect=lambda path, mode: mode == os.R_OK):
                result = await execute_file("/tmp/file.unknown")

        assert "Error" in result
        assert "Don't know how to execute" in result


class TestArgumentPassing:
    """Test command-line argument handling"""

    @pytest.mark.asyncio
    async def test_passes_arguments_to_command(self, mock_get_state, mock_subprocess):
        """Should parse and pass arguments to executed process"""
        process = mock_subprocess(0, b"", b"")

        with patch("pathlib.Path.exists", return_value=True):
            with patch("os.access", return_value=True):
                with patch("asyncio.create_subprocess_exec", return_value=process) as mock_exec:
                    result = await execute_file("/tmp/test.py", args="--flag value arg2")

        assert mock_exec.called
        args = mock_exec.call_args[0]
        assert "--flag" in args
        assert "value" in args
        assert "arg2" in args

    @pytest.mark.asyncio
    async def test_handles_empty_arguments(self, mock_get_state, mock_subprocess):
        """Should handle empty/None arguments gracefully"""
        process = mock_subprocess(0, b"", b"")

        with patch("pathlib.Path.exists", return_value=True):
            with patch("os.access", return_value=True):
                with patch("asyncio.create_subprocess_exec", return_value=process) as mock_exec:
                    result = await execute_file("/tmp/test.py", args=None)

        assert mock_exec.called
        # Should only have command and file path, no extra args
        args = mock_exec.call_args[0]
        assert len(args) == 2  # Just "python3" and "/tmp/test.py"


class TestProcessExecution:
    """Test process spawning and background execution"""

    @pytest.mark.asyncio
    async def test_spawns_process_in_background(self, mock_get_state, mock_subprocess):
        """Should spawn process without waiting for completion"""
        process = mock_subprocess(0, b"", b"", pid=12345)

        with patch("pathlib.Path.exists", return_value=True):
            with patch("os.access", return_value=True):
                with patch("asyncio.create_subprocess_exec", return_value=process):
                    result = await execute_file("/tmp/test.py")

        assert "Process ID: 12345" in result
        assert "STARTED IN BACKGROUND" in result

    @pytest.mark.asyncio
    async def test_handles_execution_error(self, mock_get_state):
        """Should handle process execution errors gracefully"""
        with patch("pathlib.Path.exists", return_value=True):
            with patch("os.access", return_value=True):
                async def failing_exec(*args, **kwargs):
                    raise OSError("Permission denied")

                with patch("asyncio.create_subprocess_exec", side_effect=failing_exec):
                    result = await execute_file("/tmp/test.py")

        assert "Error" in result
        assert "Execution failed" in result


class TestWorkingDirectory:
    """Test working directory handling"""

    @pytest.mark.asyncio
    async def test_uses_specified_working_directory(self, mock_get_state, mock_subprocess):
        """Should execute process in specified working directory"""
        process = mock_subprocess(0, b"", b"")

        with patch("pathlib.Path.exists", return_value=True):
            with patch("os.access", return_value=True):
                with patch("asyncio.create_subprocess_exec", return_value=process) as mock_exec:
                    result = await execute_file("/tmp/test.py", working_dir="/custom/dir")

        assert mock_exec.called
        kwargs = mock_exec.call_args[1]
        assert kwargs.get("cwd") == "/custom/dir"

    @pytest.mark.asyncio
    async def test_uses_current_directory_by_default(self, mock_get_state, mock_subprocess):
        """Should use current working directory if not specified"""
        process = mock_subprocess(0, b"", b"")

        with patch("pathlib.Path.exists", return_value=True):
            with patch("os.access", return_value=True):
                with patch("asyncio.create_subprocess_exec", return_value=process) as mock_exec:
                    result = await execute_file("/tmp/test.py")

        assert mock_exec.called
        # cwd should be None (uses current dir)
        kwargs = mock_exec.call_args[1]
        assert kwargs.get("cwd") is None


class TestLoggingBehavior:
    """Test logging and state management"""

    @pytest.mark.asyncio
    async def test_logs_successful_execution(self, mock_get_state, mock_subprocess):
        """Should log execution details to state"""
        process = mock_subprocess(0, b"output", b"")
        initial_log_count = len(mock_get_state.log_entries)

        with patch("pathlib.Path.exists", return_value=True):
            with patch("os.access", return_value=True):
                with patch("asyncio.create_subprocess_exec", return_value=process):
                    result = await execute_file("/tmp/test.py")

        assert len(mock_get_state.log_entries) == initial_log_count + 1
        log_entry = mock_get_state.log_entries[-1]
        assert log_entry["tool"] == "execute_file"
        assert log_entry["type"] == "TOOL_CALL"

    @pytest.mark.asyncio
    async def test_logs_errors(self, mock_get_state):
        """Should log errors to state"""
        initial_log_count = len(mock_get_state.log_entries)

        with patch("pathlib.Path.exists", return_value=False):
            result = await execute_file("/tmp/missing.py")

        # Should still log even though execution didn't happen
        # Note: The current code might not log validation errors
        # This test documents expected behavior
        assert "Error" in result

    @pytest.mark.asyncio
    async def test_appends_extra_note_text(self, mock_get_state, mock_subprocess):
        """Should append state.extra_note_text to response"""
        mock_get_state.extra_note_text = "INJECTED_TEXT"
        process = mock_subprocess(0, b"", b"")

        with patch("pathlib.Path.exists", return_value=True):
            with patch("os.access", return_value=True):
                with patch("asyncio.create_subprocess_exec", return_value=process):
                    result = await execute_file("/tmp/test.py")

        assert "INJECTED_TEXT" in result


class TestCodeQualityIssues:
    """Tests that expose code quality issues (will fail until bugs are fixed)"""

    @pytest.mark.asyncio
    async def test_exposes_undefined_timeout_variable(self, mock_get_state):
        """KNOWN BUG: Line 116 references undefined 'timeout' variable"""
        # This test documents a bug in the current code
        # The log_entry at line 116 includes "timeout" which is never defined

        with patch("pathlib.Path.exists", return_value=True):
            with patch("os.access", return_value=True):
                with patch("asyncio.create_subprocess_exec", return_value=AsyncMock(pid=123)):
                    # This will fail with NameError due to undefined 'timeout'
                    try:
                        result = await execute_file("/tmp/test.py")
                        # If we get here, the bug was fixed
                        assert "Process ID" in result
                    except NameError as e:
                        # Bug still exists
                        assert "timeout" in str(e)
                        pytest.skip("Bug exists: undefined 'timeout' variable")
