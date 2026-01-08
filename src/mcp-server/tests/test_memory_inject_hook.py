"""
Tests for chainguard_memory_inject.py hook.

Tests the UserPromptSubmit hook that injects memory context before LLM processing.
"""

import pytest
import json
import tempfile
import os
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add hooks directory to path for imports
# tests/ -> mcp-server/ -> src/ -> src/hooks/
HOOKS_DIR = Path(__file__).parent.parent.parent / "hooks"
sys.path.insert(0, str(HOOKS_DIR))


class TestGetProjectId:
    """Tests for get_project_id function."""

    def test_returns_16_char_hash(self):
        """Test that project_id is always 16 characters."""
        # Import from hook module
        sys.path.insert(0, str(HOOKS_DIR))
        from chainguard_memory_inject import get_project_id

        project_id = get_project_id("/some/test/path")
        assert len(project_id) == 16
        assert all(c in '0123456789abcdef' for c in project_id)

    def test_same_path_same_id(self):
        """Test that same path returns same project_id."""
        from chainguard_memory_inject import get_project_id

        id1 = get_project_id("/path/to/project")
        id2 = get_project_id("/path/to/project")
        assert id1 == id2

    def test_different_path_different_id(self):
        """Test that different paths return different project_ids."""
        from chainguard_memory_inject import get_project_id

        id1 = get_project_id("/path/to/project1")
        id2 = get_project_id("/path/to/project2")
        assert id1 != id2


class TestExtractKeywords:
    """Tests for extract_keywords function."""

    def test_basic_extraction(self):
        """Test basic keyword extraction."""
        from chainguard_memory_inject import extract_keywords

        keywords = extract_keywords("implement login feature")
        assert "implement" in keywords
        assert "login" in keywords
        assert "feature" in keywords

    def test_removes_stop_words(self):
        """Test that stop words are removed."""
        from chainguard_memory_inject import extract_keywords

        keywords = extract_keywords("the login is a feature")
        assert "the" not in keywords
        assert "is" not in keywords
        assert "a" not in keywords
        assert "login" in keywords

    def test_removes_short_words(self):
        """Test that short words (<=2 chars) are removed."""
        from chainguard_memory_inject import extract_keywords

        keywords = extract_keywords("do it now ok")
        assert "do" not in keywords
        assert "it" not in keywords
        assert "ok" not in keywords

    def test_handles_german(self):
        """Test German keyword extraction."""
        from chainguard_memory_inject import extract_keywords

        keywords = extract_keywords("implementiere Benutzer-Authentifizierung")
        assert "implementiere" in keywords
        assert "benutzer" in keywords or "authentifizierung" in keywords

    def test_max_keywords_limit(self):
        """Test that max 10 keywords are returned."""
        from chainguard_memory_inject import extract_keywords

        long_text = " ".join([f"keyword{i}" for i in range(20)])
        keywords = extract_keywords(long_text)
        assert len(keywords) <= 10


class TestMemoryExists:
    """Tests for memory_exists function."""

    def test_returns_false_for_nonexistent(self):
        """Test returns False when memory doesn't exist."""
        from chainguard_memory_inject import memory_exists

        result = memory_exists("nonexistent12345")
        assert result is False

    def test_returns_false_without_chroma_sqlite(self):
        """Test returns False when chroma.sqlite3 doesn't exist."""
        from chainguard_memory_inject import memory_exists, MEMORY_HOME

        # Create directory without chroma.sqlite3
        test_dir = MEMORY_HOME / "test_project_1234"
        test_dir.mkdir(parents=True, exist_ok=True)

        try:
            result = memory_exists("test_project_1234")
            assert result is False
        finally:
            # Cleanup
            test_dir.rmdir()


class TestCaching:
    """Tests for cache functions."""

    def test_cache_roundtrip(self):
        """Test cache save and load."""
        from chainguard_memory_inject import (
            get_cached_context,
            set_cached_context,
            load_cache,
            CACHE_FILE
        )

        # Save to cache
        test_key = "test_project:test query"
        test_context = "Test context content"
        set_cached_context(test_key, test_context)

        # Load from cache
        cached = get_cached_context(test_key)
        assert cached == test_context

        # Cleanup
        if CACHE_FILE.exists():
            CACHE_FILE.unlink()

    def test_cache_expiration(self):
        """Test that cached context expires after TTL."""
        import time
        from chainguard_memory_inject import (
            get_cached_context,
            CACHE_FILE,
            CACHE_TTL
        )

        # Create expired cache entry
        cache_data = {
            "expired_key": {
                "context": "old content",
                "timestamp": time.time() - CACHE_TTL - 100  # Expired
            }
        }

        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE_FILE, 'w') as f:
            json.dump(cache_data, f)

        # Should return None for expired entry
        cached = get_cached_context("expired_key")
        assert cached is None

        # Cleanup
        if CACHE_FILE.exists():
            CACHE_FILE.unlink()


class TestFormatContext:
    """Tests for format_context function."""

    def test_empty_results(self):
        """Test formatting with empty results."""
        from chainguard_memory_inject import format_context

        result = format_context([], "test prompt")
        assert result == ""

    def test_filters_irrelevant(self):
        """Test that irrelevant results (distance >= 1.0) are filtered."""
        from chainguard_memory_inject import format_context

        results = [
            {"distance": 1.5, "content": "irrelevant", "metadata": {}, "collection": "test"}
        ]
        result = format_context(results, "test prompt")
        assert result == ""

    def test_includes_relevant(self):
        """Test that relevant results (distance < 1.0) are included."""
        from chainguard_memory_inject import format_context

        results = [
            {
                "distance": 0.3,
                "content": "Authentication handler",
                "metadata": {"path": "src/auth.py"},
                "collection": "code_structure"
            }
        ]
        result = format_context(results, "login feature")

        assert "Memory Context" in result
        assert "src/auth.py" in result

    def test_groups_by_collection(self):
        """Test that results are grouped by collection."""
        from chainguard_memory_inject import format_context

        results = [
            {
                "distance": 0.3,
                "content": "File 1",
                "metadata": {"path": "file1.py"},
                "collection": "code_structure"
            },
            {
                "distance": 0.4,
                "content": "Function 1",
                "metadata": {"name": "auth_handler"},
                "collection": "functions"
            }
        ]
        result = format_context(results, "test")

        assert "Code Structure" in result
        assert "Functions" in result


class TestHookInput:
    """Tests for hook input handling."""

    def test_short_prompt_ignored(self):
        """Test that short prompts are ignored."""
        # Prompts < 20 chars should be skipped
        # This would be tested via main() function
        from chainguard_memory_inject import main

        # Mock stdin with short prompt
        short_input = json.dumps({"prompt": "yes", "cwd": "/tmp"})

        with patch('sys.stdin') as mock_stdin:
            mock_stdin.isatty.return_value = False
            mock_stdin.read.return_value = short_input

            # Should exit 0 without output
            with pytest.raises(SystemExit) as exc_info:
                main()

            assert exc_info.value.code == 0


class TestQueryMemorySync:
    """Tests for query_memory_sync function."""

    def test_returns_empty_without_chromadb(self):
        """Test returns empty list when chromadb not available."""
        from chainguard_memory_inject import query_memory_sync

        # Query non-existent project
        results = query_memory_sync("nonexistent123", "test query")
        assert results == []

    @pytest.mark.skipif(
        True,  # Change to False to test with actual chromadb
        reason="Requires chromadb installation"
    )
    def test_queries_all_collections(self):
        """Test that all collections are queried."""
        from chainguard_memory_inject import query_memory_sync

        # This test requires actual ChromaDB setup
        pass


class TestPerformance:
    """Performance-related tests."""

    def test_keyword_extraction_fast(self):
        """Test that keyword extraction is fast."""
        import time
        from chainguard_memory_inject import extract_keywords

        long_text = " ".join(["word" + str(i) for i in range(1000)])

        start = time.time()
        for _ in range(100):
            extract_keywords(long_text)
        elapsed = time.time() - start

        # Should complete 100 extractions in < 1 second
        assert elapsed < 1.0

    def test_cache_operations_fast(self):
        """Test that cache operations are fast."""
        import time
        from chainguard_memory_inject import (
            set_cached_context,
            get_cached_context,
            CACHE_FILE
        )

        start = time.time()
        for i in range(100):
            set_cached_context(f"key_{i}", f"context_{i}")
            get_cached_context(f"key_{i}")
        elapsed = time.time() - start

        # Should complete 200 operations in < 1 second
        assert elapsed < 1.0

        # Cleanup
        if CACHE_FILE.exists():
            CACHE_FILE.unlink()


class TestConstants:
    """Tests for configuration constants."""

    def test_hook_timeout_reasonable(self):
        """Test that HOOK_TIMEOUT is reasonable."""
        from chainguard_memory_inject import HOOK_TIMEOUT

        # Should be between 1 and 10 seconds
        assert 1 <= HOOK_TIMEOUT <= 10

    def test_cache_ttl_reasonable(self):
        """Test that CACHE_TTL is reasonable."""
        from chainguard_memory_inject import CACHE_TTL

        # Should be between 1 minute and 1 hour
        assert 60 <= CACHE_TTL <= 3600

    def test_max_results_reasonable(self):
        """Test that MAX_RESULTS is reasonable."""
        from chainguard_memory_inject import MAX_RESULTS

        # Should be between 1 and 20
        assert 1 <= MAX_RESULTS <= 20
