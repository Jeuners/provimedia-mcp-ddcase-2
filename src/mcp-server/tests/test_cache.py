"""
Tests for chainguard.cache module.

Tests LRUCache, TTLLRUCache, and GitCache functionality.
"""

import time
import pytest
from chainguard.cache import LRUCache, TTLLRUCache, GitCache


class TestLRUCache:
    """Tests for LRUCache."""

    def test_basic_set_get(self):
        """Test basic set and get operations."""
        cache = LRUCache(maxsize=10)
        cache["key1"] = "value1"
        assert cache["key1"] == "value1"

    def test_maxsize_eviction(self):
        """Test that oldest items are evicted when maxsize is reached."""
        cache = LRUCache(maxsize=3)
        cache["a"] = 1
        cache["b"] = 2
        cache["c"] = 3
        cache["d"] = 4  # Should evict "a"

        assert "a" not in cache
        assert cache["b"] == 2
        assert cache["c"] == 3
        assert cache["d"] == 4

    def test_access_updates_order(self):
        """Test that accessing an item moves it to the end (most recent)."""
        cache = LRUCache(maxsize=3)
        cache["a"] = 1
        cache["b"] = 2
        cache["c"] = 3

        # Access "a" to make it most recent
        _ = cache["a"]

        # Add new item, should evict "b" (now oldest)
        cache["d"] = 4

        assert "a" in cache  # Still here (was accessed)
        assert "b" not in cache  # Evicted
        assert "c" in cache
        assert "d" in cache

    def test_update_existing_key(self):
        """Test updating an existing key."""
        cache = LRUCache(maxsize=3)
        cache["a"] = 1
        cache["a"] = 2
        assert cache["a"] == 2
        assert len(cache) == 1

    def test_empty_cache(self):
        """Test behavior with empty cache."""
        cache = LRUCache(maxsize=5)
        assert len(cache) == 0
        with pytest.raises(KeyError):
            _ = cache["nonexistent"]


class TestTTLLRUCache:
    """Tests for TTLLRUCache with time-based expiration."""

    def test_basic_set_get(self):
        """Test basic set and get operations."""
        cache = TTLLRUCache[str](maxsize=10, ttl_seconds=60)
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_get_default(self):
        """Test get with default value for missing key."""
        cache = TTLLRUCache[str](maxsize=10, ttl_seconds=60)
        assert cache.get("missing") is None
        assert cache.get("missing", "default") == "default"

    def test_contains(self):
        """Test __contains__ (in operator)."""
        cache = TTLLRUCache[str](maxsize=10, ttl_seconds=60)
        cache.set("exists", "value")
        assert "exists" in cache
        assert "missing" not in cache

    def test_ttl_expiration(self):
        """Test that items expire after TTL."""
        cache = TTLLRUCache[str](maxsize=10, ttl_seconds=0.1)  # 100ms TTL
        cache.set("key", "value")

        assert cache.get("key") == "value"

        # Wait for expiration
        time.sleep(0.15)

        assert cache.get("key") is None
        assert "key" not in cache

    def test_maxsize_eviction(self):
        """Test eviction when maxsize is reached."""
        cache = TTLLRUCache[int](maxsize=3, ttl_seconds=60)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.set("d", 4)  # Should evict oldest

        assert len(cache) == 3
        assert cache.get("a") is None  # Evicted

    def test_invalidate(self):
        """Test manual invalidation."""
        cache = TTLLRUCache[str](maxsize=10, ttl_seconds=60)
        cache.set("key", "value")
        cache.invalidate("key")
        assert cache.get("key") is None

    def test_clear(self):
        """Test clearing all items."""
        cache = TTLLRUCache[str](maxsize=10, ttl_seconds=60)
        cache.set("a", "1")
        cache.set("b", "2")
        cache.clear()
        assert len(cache) == 0

    def test_cleanup_expired(self):
        """Test cleanup of expired items."""
        cache = TTLLRUCache[str](maxsize=10, ttl_seconds=0.1)
        cache.set("a", "1")
        cache.set("b", "2")

        time.sleep(0.15)

        removed = cache.cleanup_expired()
        assert removed == 2
        assert len(cache) == 0

    def test_items_iterator(self):
        """Test iteration over non-expired items."""
        cache = TTLLRUCache[int](maxsize=10, ttl_seconds=60)
        cache.set("a", 1)
        cache.set("b", 2)

        items = list(cache.items())
        assert len(items) == 2
        assert ("a", 1) in items
        assert ("b", 2) in items


class TestGitCache:
    """Tests for GitCache."""

    def test_basic_set_get(self):
        """Test basic set and get."""
        cache = GitCache(ttl_seconds=60)
        cache.set("/path/to/repo", "abc123")
        assert cache.get("/path/to/repo") == "abc123"

    def test_missing_key(self):
        """Test get for missing key returns None."""
        cache = GitCache(ttl_seconds=60)
        assert cache.get("/nonexistent") is None

    def test_ttl_expiration(self):
        """Test TTL expiration."""
        cache = GitCache(ttl_seconds=0.1)
        cache.set("/path", "value")

        assert cache.get("/path") == "value"

        time.sleep(0.15)

        assert cache.get("/path") is None

    def test_invalidate(self):
        """Test manual invalidation."""
        cache = GitCache(ttl_seconds=60)
        cache.set("/path", "value")
        cache.invalidate("/path")
        assert cache.get("/path") is None

    def test_invalidate_nonexistent(self):
        """Test invalidating nonexistent key doesn't raise."""
        cache = GitCache(ttl_seconds=60)
        cache.invalidate("/nonexistent")  # Should not raise
