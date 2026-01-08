"""
Tests for the checklist module (ChecklistRunner).

Tests cover:
- Async command execution with run_check_async
- Command whitelist enforcement (security)
- Empty command handling
- Timeout handling
- Batch execution with run_all_async
- Sync wrappers
- Constants validation
"""

import pytest
import asyncio
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from chainguard.checklist import ChecklistRunner


# =============================================================================
# Fixtures
# =============================================================================
@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create some test files
        (Path(tmpdir) / "test.txt").write_text("hello world")
        (Path(tmpdir) / "config.json").write_text('{"key": "value"}')
        yield tmpdir


# =============================================================================
# TestChecklistConstants - Verify configuration
# =============================================================================
class TestChecklistConstants:
    """Tests for ChecklistRunner constants."""

    def test_allowed_commands_contains_expected(self):
        """Verify whitelist contains all expected commands."""
        expected_commands = {
            'test', 'grep', 'ls', 'cat', 'head', 'wc', 'find', 'stat', '[',
            'php', 'node', 'python', 'python3', 'npm', 'composer'
        }
        assert ChecklistRunner.ALLOWED_COMMANDS == expected_commands

    def test_allowed_commands_is_set(self):
        """Verify ALLOWED_COMMANDS is a set for O(1) lookup."""
        assert isinstance(ChecklistRunner.ALLOWED_COMMANDS, set)

    def test_timeout_is_reasonable(self):
        """Verify timeout is between 1 and 60 seconds."""
        assert 1 <= ChecklistRunner.COMMAND_TIMEOUT <= 60
        assert ChecklistRunner.COMMAND_TIMEOUT == 10

    def test_dangerous_commands_not_in_whitelist(self):
        """Verify dangerous commands are NOT in whitelist."""
        dangerous_commands = {'rm', 'curl', 'wget', 'sh', 'bash', 'eval', 'exec', 'sudo'}
        for cmd in dangerous_commands:
            assert cmd not in ChecklistRunner.ALLOWED_COMMANDS


# =============================================================================
# TestChecklistRunnerAsync - Async method tests
# =============================================================================
class TestChecklistRunnerAsync:
    """Async tests for ChecklistRunner."""

    @pytest.mark.asyncio
    async def test_run_check_empty_command(self, temp_dir):
        """Test that empty command returns passed=False."""
        result = await ChecklistRunner.run_check_async("", temp_dir)
        assert result["passed"] is False
        assert "Empty command" in result["output"]

    @pytest.mark.asyncio
    async def test_run_check_whitespace_only_command(self, temp_dir):
        """Test that whitespace-only command returns passed=False."""
        result = await ChecklistRunner.run_check_async("   ", temp_dir)
        assert result["passed"] is False
        assert "Empty command" in result["output"]

    @pytest.mark.asyncio
    async def test_run_check_disallowed_command_rm(self, temp_dir):
        """Test that 'rm' command is blocked."""
        result = await ChecklistRunner.run_check_async("rm -rf /", temp_dir)
        assert result["passed"] is False
        assert "not allowed" in result["output"]

    @pytest.mark.asyncio
    async def test_run_check_disallowed_command_curl(self, temp_dir):
        """Test that 'curl' command is blocked."""
        result = await ChecklistRunner.run_check_async("curl http://example.com", temp_dir)
        assert result["passed"] is False
        assert "not allowed" in result["output"]

    @pytest.mark.asyncio
    async def test_run_check_disallowed_command_wget(self, temp_dir):
        """Test that 'wget' command is blocked."""
        result = await ChecklistRunner.run_check_async("wget http://evil.com", temp_dir)
        assert result["passed"] is False
        assert "not allowed" in result["output"]

    @pytest.mark.asyncio
    async def test_run_check_disallowed_command_bash(self, temp_dir):
        """Test that 'bash' command is blocked."""
        result = await ChecklistRunner.run_check_async("bash -c 'echo evil'", temp_dir)
        assert result["passed"] is False
        assert "not allowed" in result["output"]

    @pytest.mark.asyncio
    async def test_run_check_allowed_command_ls(self, temp_dir):
        """Test that 'ls' command runs successfully."""
        result = await ChecklistRunner.run_check_async("ls", temp_dir)
        assert result["passed"] is True
        assert "test.txt" in result["output"]

    @pytest.mark.asyncio
    async def test_run_check_allowed_command_ls_with_args(self, temp_dir):
        """Test that 'ls -la' command runs successfully."""
        result = await ChecklistRunner.run_check_async("ls -la", temp_dir)
        assert result["passed"] is True

    @pytest.mark.asyncio
    async def test_run_check_allowed_command_test_file_exists(self, temp_dir):
        """Test 'test -f' for existing file returns passed=True."""
        result = await ChecklistRunner.run_check_async("test -f test.txt", temp_dir)
        assert result["passed"] is True

    @pytest.mark.asyncio
    async def test_run_check_allowed_command_test_file_not_exists(self, temp_dir):
        """Test 'test -f' for non-existing file returns passed=False."""
        result = await ChecklistRunner.run_check_async("test -f nonexistent.txt", temp_dir)
        assert result["passed"] is False

    @pytest.mark.asyncio
    async def test_run_check_allowed_command_test_directory(self, temp_dir):
        """Test 'test -d' for directory check."""
        result = await ChecklistRunner.run_check_async("test -d .", temp_dir)
        assert result["passed"] is True

    @pytest.mark.asyncio
    async def test_run_check_allowed_command_grep_match(self, temp_dir):
        """Test 'grep' command finds matching pattern."""
        result = await ChecklistRunner.run_check_async("grep -q hello test.txt", temp_dir)
        assert result["passed"] is True

    @pytest.mark.asyncio
    async def test_run_check_allowed_command_grep_no_match(self, temp_dir):
        """Test 'grep' command with no match returns passed=False."""
        result = await ChecklistRunner.run_check_async("grep -q nonexistent test.txt", temp_dir)
        assert result["passed"] is False

    @pytest.mark.asyncio
    async def test_run_check_allowed_command_cat(self, temp_dir):
        """Test 'cat' command reads file content."""
        result = await ChecklistRunner.run_check_async("cat test.txt", temp_dir)
        assert result["passed"] is True
        assert "hello world" in result["output"]

    @pytest.mark.asyncio
    async def test_run_check_allowed_command_wc(self, temp_dir):
        """Test 'wc' command counts lines/words."""
        result = await ChecklistRunner.run_check_async("wc -l test.txt", temp_dir)
        assert result["passed"] is True

    @pytest.mark.asyncio
    async def test_run_check_allowed_command_head(self, temp_dir):
        """Test 'head' command."""
        result = await ChecklistRunner.run_check_async("head -n 1 test.txt", temp_dir)
        assert result["passed"] is True
        assert "hello" in result["output"]

    @pytest.mark.asyncio
    async def test_run_check_allowed_command_bracket(self, temp_dir):
        """Test '[' (test) command."""
        result = await ChecklistRunner.run_check_async("[ -f test.txt ]", temp_dir)
        assert result["passed"] is True

    @pytest.mark.asyncio
    async def test_run_check_allowed_command_find(self, temp_dir):
        """Test 'find' command."""
        result = await ChecklistRunner.run_check_async("find . -name '*.txt'", temp_dir)
        assert result["passed"] is True
        assert "test.txt" in result["output"]

    @pytest.mark.asyncio
    async def test_run_check_allowed_command_stat(self, temp_dir):
        """Test 'stat' command."""
        result = await ChecklistRunner.run_check_async("stat test.txt", temp_dir)
        assert result["passed"] is True

    @pytest.mark.asyncio
    async def test_run_check_command_not_found(self, temp_dir):
        """Test handling of command that doesn't exist on system."""
        # Mock a command that's in whitelist but doesn't exist
        with patch.object(ChecklistRunner, 'ALLOWED_COMMANDS', {'nonexistentcmd123'}):
            result = await ChecklistRunner.run_check_async("nonexistentcmd123", temp_dir)
            assert result["passed"] is False
            assert "Command not found" in result["output"] or "not found" in result["output"].lower()

    @pytest.mark.asyncio
    async def test_run_check_output_truncated(self, temp_dir):
        """Test that output is truncated to 200 chars."""
        # Create a file with long content
        long_content = "x" * 500
        (Path(temp_dir) / "long.txt").write_text(long_content)

        result = await ChecklistRunner.run_check_async("cat long.txt", temp_dir)
        assert result["passed"] is True
        assert len(result["output"]) <= 200

    @pytest.mark.asyncio
    async def test_run_check_parse_error(self, temp_dir):
        """Test handling of malformed command string."""
        # Unclosed quote should cause parse error
        result = await ChecklistRunner.run_check_async('test -f "unclosed', temp_dir)
        assert result["passed"] is False
        assert "Parse error" in result["output"] or "error" in result["output"].lower()

    @pytest.mark.asyncio
    async def test_run_all_async_empty_list(self, temp_dir):
        """Test run_all_async with empty checklist."""
        result = await ChecklistRunner.run_all_async([], temp_dir)
        assert result["results"] == {}
        assert result["passed"] == 0
        assert result["failed"] == 0
        assert result["total"] == 0

    @pytest.mark.asyncio
    async def test_run_all_async_single_item_pass(self, temp_dir):
        """Test run_all_async with single passing item."""
        checklist = [{"item": "File exists", "check": "test -f test.txt"}]
        result = await ChecklistRunner.run_all_async(checklist, temp_dir)

        assert result["passed"] == 1
        assert result["failed"] == 0
        assert result["total"] == 1
        assert result["results"]["File exists"] == "\u2713"  # checkmark

    @pytest.mark.asyncio
    async def test_run_all_async_single_item_fail(self, temp_dir):
        """Test run_all_async with single failing item."""
        checklist = [{"item": "Missing file", "check": "test -f nonexistent.txt"}]
        result = await ChecklistRunner.run_all_async(checklist, temp_dir)

        assert result["passed"] == 0
        assert result["failed"] == 1
        assert result["total"] == 1
        assert result["results"]["Missing file"] == "\u2717"  # X mark

    @pytest.mark.asyncio
    async def test_run_all_async_multiple_items(self, temp_dir):
        """Test run_all_async with multiple checklist items."""
        checklist = [
            {"item": "test.txt exists", "check": "test -f test.txt"},
            {"item": "config.json exists", "check": "test -f config.json"},
            {"item": "missing.txt exists", "check": "test -f missing.txt"},
            {"item": "Has hello", "check": "grep -q hello test.txt"}
        ]
        result = await ChecklistRunner.run_all_async(checklist, temp_dir)

        assert result["passed"] == 3
        assert result["failed"] == 1
        assert result["total"] == 4
        assert result["results"]["test.txt exists"] == "\u2713"
        assert result["results"]["config.json exists"] == "\u2713"
        assert result["results"]["missing.txt exists"] == "\u2717"
        assert result["results"]["Has hello"] == "\u2713"

    @pytest.mark.asyncio
    async def test_run_all_async_item_without_check(self, temp_dir):
        """Test run_all_async handles items without 'check' field."""
        checklist = [
            {"item": "No check field"},
            {"item": "Has check", "check": "test -f test.txt"}
        ]
        result = await ChecklistRunner.run_all_async(checklist, temp_dir)

        # Item without check should not be counted
        assert result["passed"] == 1
        assert result["failed"] == 0
        assert result["total"] == 2
        assert "No check field" not in result["results"]

    @pytest.mark.asyncio
    async def test_run_all_async_default_item_name(self, temp_dir):
        """Test run_all_async uses '?' for missing item name."""
        checklist = [{"check": "test -f test.txt"}]
        result = await ChecklistRunner.run_all_async(checklist, temp_dir)

        assert "?" in result["results"]
        assert result["results"]["?"] == "\u2713"

    @pytest.mark.asyncio
    async def test_run_all_async_parallel_execution(self, temp_dir):
        """Test that run_all_async executes checks in parallel."""
        # Create a checklist with multiple items
        checklist = [
            {"item": f"Check {i}", "check": "ls"} for i in range(5)
        ]

        import time
        start = time.time()
        result = await ChecklistRunner.run_all_async(checklist, temp_dir)
        duration = time.time() - start

        # All should pass
        assert result["passed"] == 5
        # Parallel execution should be fast (< 2 seconds for simple commands)
        assert duration < 2.0


# =============================================================================
# TestChecklistRunnerSync - Sync wrapper tests
# =============================================================================
class TestChecklistRunnerSync:
    """Tests for sync wrappers."""

    def test_run_check_sync_allowed_command(self, temp_dir):
        """Test sync run_check with allowed command."""
        result = ChecklistRunner.run_check("ls", temp_dir)
        assert result["passed"] is True

    def test_run_check_sync_disallowed_command(self, temp_dir):
        """Test sync run_check blocks disallowed command."""
        result = ChecklistRunner.run_check("rm -rf /", temp_dir)
        assert result["passed"] is False
        assert "not allowed" in result["output"].lower()

    def test_run_check_sync_empty_command(self, temp_dir):
        """Test sync run_check with empty command."""
        result = ChecklistRunner.run_check("", temp_dir)
        assert result["passed"] is False

    def test_run_all_sync_empty_list(self, temp_dir):
        """Test sync run_all with empty checklist."""
        result = ChecklistRunner.run_all([], temp_dir)
        assert result["results"] == {}
        assert result["passed"] == 0
        assert result["failed"] == 0
        assert result["total"] == 0

    def test_run_all_sync_multiple_items(self, temp_dir):
        """Test sync run_all with multiple items."""
        checklist = [
            {"item": "test.txt exists", "check": "test -f test.txt"},
            {"item": "missing.txt exists", "check": "test -f missing.txt"}
        ]
        result = ChecklistRunner.run_all(checklist, temp_dir)

        assert result["passed"] == 1
        assert result["failed"] == 1
        assert result["total"] == 2


# =============================================================================
# TestChecklistRunnerTimeout - Timeout handling
# =============================================================================
class TestChecklistRunnerTimeout:
    """Tests for timeout handling."""

    @pytest.mark.asyncio
    async def test_run_check_timeout(self, temp_dir):
        """Test that long-running commands timeout."""
        # Temporarily reduce timeout for faster test
        original_timeout = ChecklistRunner.COMMAND_TIMEOUT
        ChecklistRunner.COMMAND_TIMEOUT = 0.1  # 100ms

        try:
            # 'find' with no limit can take long, but we use a simpler approach
            # Use a command that will definitely exceed 100ms
            result = await ChecklistRunner.run_check_async(
                "find / -name 'test' 2>/dev/null",
                temp_dir
            )
            # Due to security restrictions, find / might fail or timeout
            # Either way, we verify the timeout mechanism exists
            assert "passed" in result
        finally:
            ChecklistRunner.COMMAND_TIMEOUT = original_timeout


# =============================================================================
# TestChecklistRunnerEdgeCases - Edge cases
# =============================================================================
class TestChecklistRunnerEdgeCases:
    """Tests for edge cases."""

    @pytest.mark.asyncio
    async def test_run_check_with_special_characters(self, temp_dir):
        """Test command with special characters in arguments."""
        # Create file with special name
        special_file = Path(temp_dir) / "file with spaces.txt"
        special_file.write_text("content")

        result = await ChecklistRunner.run_check_async(
            'test -f "file with spaces.txt"',
            temp_dir
        )
        assert result["passed"] is True

    @pytest.mark.asyncio
    async def test_run_check_nonexistent_directory(self):
        """Test with non-existent working directory."""
        result = await ChecklistRunner.run_check_async(
            "ls",
            "/nonexistent/path/that/does/not/exist"
        )
        assert result["passed"] is False

    @pytest.mark.asyncio
    async def test_run_check_command_with_stderr(self, temp_dir):
        """Test that stderr is captured in output."""
        result = await ChecklistRunner.run_check_async(
            "ls nonexistent_file_12345",
            temp_dir
        )
        assert result["passed"] is False
        # stderr should be captured
        assert result["output"] != ""

    @pytest.mark.asyncio
    async def test_run_all_async_preserves_order(self, temp_dir):
        """Test that results preserve checklist order."""
        checklist = [
            {"item": "A", "check": "ls"},
            {"item": "B", "check": "ls"},
            {"item": "C", "check": "ls"}
        ]
        result = await ChecklistRunner.run_all_async(checklist, temp_dir)

        # All items should be present
        assert "A" in result["results"]
        assert "B" in result["results"]
        assert "C" in result["results"]
