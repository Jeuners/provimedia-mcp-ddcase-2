"""
Tests for the history module (Error Memory System).

Tests cover:
- HistoryEntry and ErrorEntry dataclasses
- HistoryManager methods
- Pattern extraction and matching
- Auto-suggest formatting
"""

import pytest
import json
import tempfile
import asyncio
from pathlib import Path
from datetime import datetime, timedelta

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from chainguard.history import (
    HistoryEntry,
    ErrorEntry,
    HistoryManager,
    format_auto_suggest,
    HISTORY_MAX_ENTRIES,
    ERROR_INDEX_MAX_ENTRIES,
    SIMILARITY_THRESHOLD
)


# =============================================================================
# HistoryEntry Tests
# =============================================================================
class TestHistoryEntry:
    """Tests for HistoryEntry dataclass."""

    def test_create_basic(self):
        """Test basic creation."""
        entry = HistoryEntry(
            ts="2025-01-04T10:30:00",
            file="test.php",
            action="edit",
            validation="PASS"
        )
        assert entry.ts == "2025-01-04T10:30:00"
        assert entry.file == "test.php"
        assert entry.action == "edit"
        assert entry.validation == "PASS"

    def test_to_dict_excludes_empty(self):
        """Test that to_dict excludes empty fields."""
        entry = HistoryEntry(
            ts="2025-01-04T10:30:00",
            file="test.php",
            action="edit",
            validation="PASS",
            scope_id="",
            scope_desc="",
            fix_applied=None
        )
        d = entry.to_dict()
        assert "scope_id" not in d
        assert "scope_desc" not in d
        assert "fix_applied" not in d

    def test_from_dict(self):
        """Test creation from dict."""
        data = {
            "ts": "2025-01-04T10:30:00",
            "file": "test.php",
            "action": "edit",
            "validation": "PASS",
            "extra_field": "ignored"
        }
        entry = HistoryEntry.from_dict(data)
        assert entry.file == "test.php"
        assert entry.validation == "PASS"

    def test_with_error(self):
        """Test entry with validation error."""
        entry = HistoryEntry(
            ts="2025-01-04T10:30:00",
            file="Controller.php",
            action="edit",
            validation="FAIL:PHP Syntax:unexpected }"
        )
        assert entry.validation.startswith("FAIL")


# =============================================================================
# ErrorEntry Tests
# =============================================================================
class TestErrorEntry:
    """Tests for ErrorEntry dataclass."""

    def test_create_basic(self):
        """Test basic creation."""
        entry = ErrorEntry(
            ts="2025-01-04T10:30:00",
            file_pattern="*Controller.php",
            error_type="PHP Syntax",
            error_msg="unexpected }",
            resolution="Missing semicolon before }",
            scope_desc="Auth feature",
            project_id="abc123"
        )
        assert entry.file_pattern == "*Controller.php"
        assert entry.error_type == "PHP Syntax"
        assert entry.resolution == "Missing semicolon before }"

    def test_matches_exact_type(self):
        """Test matching by error type."""
        entry = ErrorEntry(
            ts="2025-01-04T10:30:00",
            file_pattern="*Controller.php",
            error_type="PHP Syntax",
            error_msg="unexpected }",
            resolution=None,
            scope_desc="",
            project_id="abc123"
        )
        score = entry.matches("php syntax")
        assert score >= 0.3

    def test_matches_file_pattern(self):
        """Test matching by file pattern."""
        entry = ErrorEntry(
            ts="2025-01-04T10:30:00",
            file_pattern="*Controller.php",
            error_type="PHP Syntax",
            error_msg="unexpected }",
            resolution=None,
            scope_desc="",
            project_id="abc123"
        )
        score = entry.matches("Controller")
        assert score >= 0.3

    def test_matches_combined(self):
        """Test combined matching."""
        entry = ErrorEntry(
            ts="2025-01-04T10:30:00",
            file_pattern="*Controller.php",
            error_type="PHP Syntax",
            error_msg="unexpected }",
            scope_desc="Auth feature",
            project_id="abc123",
            resolution=None
        )
        score = entry.matches("php Controller")
        # Both words match (php in error_type, Controller in file_pattern)
        # Score = (0.3 + 0.3) / 2 = 0.3
        assert score >= 0.3

    def test_matches_no_match(self):
        """Test no match scenario."""
        entry = ErrorEntry(
            ts="2025-01-04T10:30:00",
            file_pattern="*Controller.php",
            error_type="PHP Syntax",
            error_msg="unexpected }",
            resolution=None,
            scope_desc="",
            project_id="abc123"
        )
        score = entry.matches("javascript typescript")
        assert score < 0.2


# =============================================================================
# HistoryManager Tests
# =============================================================================
class TestHistoryManager:
    """Tests for HistoryManager class."""

    def test_extract_pattern_controller(self):
        """Test pattern extraction for Controller files."""
        pattern = HistoryManager._extract_pattern("UserController.php")
        assert pattern == "*Controller.php"

    def test_extract_pattern_service(self):
        """Test pattern extraction for Service files."""
        pattern = HistoryManager._extract_pattern("auth.service.ts")
        assert pattern == "*.service.ts"

    def test_extract_pattern_test(self):
        """Test pattern extraction for test files."""
        pattern = HistoryManager._extract_pattern("user_test.py")
        assert pattern == "*_test.py"

    def test_extract_pattern_generic(self):
        """Test pattern extraction for generic files."""
        pattern = HistoryManager._extract_pattern("index.js")
        assert pattern == "*.js"

    def test_extract_pattern_unknown(self):
        """Test pattern extraction for unknown files."""
        pattern = HistoryManager._extract_pattern("Makefile")
        assert pattern == "Makefile"

    def test_patterns_match_exact(self):
        """Test exact pattern matching."""
        assert HistoryManager._patterns_match("*Controller.php", "*Controller.php")

    def test_patterns_match_extension(self):
        """Test extension-based matching."""
        assert HistoryManager._patterns_match("*.php", "*Controller.php")

    def test_patterns_match_different(self):
        """Test non-matching patterns."""
        assert not HistoryManager._patterns_match("*.js", "*.php")

    def test_messages_similar_same_pattern(self):
        """Test message similarity with same error pattern."""
        assert HistoryManager._messages_similar(
            "unexpected } in line 42",
            "unexpected } found at line 10"
        )

    def test_messages_similar_different(self):
        """Test message similarity with different errors."""
        assert not HistoryManager._messages_similar(
            "unexpected }",
            "undefined variable $foo"
        )


# =============================================================================
# Async Tests
# =============================================================================
class TestHistoryManagerAsync:
    """Async tests for HistoryManager."""

    @pytest.fixture
    def temp_home(self, monkeypatch, tmp_path):
        """Create temp CHAINGUARD_HOME."""
        monkeypatch.setattr("chainguard.history.CHAINGUARD_HOME", tmp_path)
        (tmp_path / "projects").mkdir(exist_ok=True)
        return tmp_path

    @pytest.mark.asyncio
    async def test_log_change(self, temp_home):
        """Test logging a change."""
        await HistoryManager.log_change(
            project_id="test123",
            file="test.php",
            action="edit",
            validation_result="PASS"
        )

        history_path = temp_home / "projects" / "test123" / "history.jsonl"
        assert history_path.exists()

        with open(history_path) as f:
            line = f.readline()
            data = json.loads(line)
            assert data["file"] == "test.php"
            assert data["action"] == "edit"
            assert data["validation"] == "PASS"

    @pytest.mark.asyncio
    async def test_get_history(self, temp_home):
        """Test getting history entries."""
        # Log multiple changes
        for i in range(5):
            await HistoryManager.log_change(
                project_id="test123",
                file=f"file{i}.php",
                action="edit",
                validation_result="PASS"
            )

        entries = await HistoryManager.get_history("test123", limit=3)
        assert len(entries) == 3
        # Most recent first
        assert entries[0].file == "file4.php"

    @pytest.mark.asyncio
    async def test_index_error(self, temp_home):
        """Test indexing an error."""
        await HistoryManager.index_error(
            project_id="test123",
            file="UserController.php",
            error_type="PHP Syntax",
            error_msg="unexpected }",
            scope_desc="Auth feature"
        )

        index_path = temp_home / "projects" / "test123" / "error_index.json"
        assert index_path.exists()

        with open(index_path) as f:
            data = json.load(f)
            assert len(data) == 1
            assert data[0]["error_type"] == "PHP Syntax"
            assert data[0]["file_pattern"] == "*Controller.php"

    @pytest.mark.asyncio
    async def test_find_similar_errors(self, temp_home):
        """Test finding similar errors."""
        # Index an error with resolution
        await HistoryManager.index_error(
            project_id="test123",
            file="AuthController.php",
            error_type="PHP Syntax",
            error_msg="unexpected }",
            scope_desc="Auth feature",
            resolution="Missing semicolon before }"
        )

        # Find similar
        similar = await HistoryManager.find_similar_errors(
            project_id="test123",
            file="UserController.php",
            error_type="PHP Syntax",
            error_msg="unexpected } at line 50"
        )

        assert len(similar) == 1
        assert similar[0].resolution == "Missing semicolon before }"

    @pytest.mark.asyncio
    async def test_recall(self, temp_home):
        """Test recall search."""
        await HistoryManager.index_error(
            project_id="test123",
            file="AuthController.php",
            error_type="PHP Syntax",
            error_msg="unexpected }",
            scope_desc="Auth feature"
        )

        results = await HistoryManager.recall("test123", "php Controller")
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_update_resolution(self, temp_home):
        """Test updating resolution."""
        await HistoryManager.index_error(
            project_id="test123",
            file="UserController.php",
            error_type="PHP Syntax",
            error_msg="unexpected }",
            scope_desc="Test"
        )

        success = await HistoryManager.update_resolution(
            project_id="test123",
            file_pattern="*Controller.php",
            error_type="PHP Syntax",
            resolution="Fixed by adding semicolon"
        )

        assert success

        # Verify update
        index = await HistoryManager._load_error_index("test123")
        assert index[0].resolution == "Fixed by adding semicolon"


# =============================================================================
# Format Auto-Suggest Tests
# =============================================================================
class TestFormatAutoSuggest:
    """Tests for format_auto_suggest function."""

    def test_empty_list(self):
        """Test with no suggestions."""
        result = format_auto_suggest([])
        assert result == ""

    def test_single_suggestion(self):
        """Test with single suggestion."""
        entry = ErrorEntry(
            ts=datetime.now().isoformat(),
            file_pattern="*Controller.php",
            error_type="PHP Syntax",
            error_msg="unexpected }",
            resolution="Missing semicolon",
            scope_desc="Test",
            project_id="test"
        )
        result = format_auto_suggest([entry])
        assert "Similar error fixed before" in result
        assert "*Controller.php" in result
        assert "Missing semicolon" in result

    def test_time_ago_today(self):
        """Test time ago calculation for today."""
        entry = ErrorEntry(
            ts=datetime.now().isoformat(),
            file_pattern="*.php",
            error_type="PHP",
            error_msg="test",
            resolution="fix",
            scope_desc="",
            project_id="test"
        )
        result = format_auto_suggest([entry])
        assert "today" in result

    def test_time_ago_yesterday(self):
        """Test time ago calculation for yesterday."""
        yesterday = datetime.now() - timedelta(days=1)
        entry = ErrorEntry(
            ts=yesterday.isoformat(),
            file_pattern="*.php",
            error_type="PHP",
            error_msg="test",
            resolution="fix",
            scope_desc="",
            project_id="test"
        )
        result = format_auto_suggest([entry])
        assert "1d ago" in result
