"""
CHAINGUARD MCP Server - Cache Module

Contains: LRUCache, TTLLRUCache, AsyncFileLock, GitCache

Copyright (c) 2026 Provimedia GmbH
Licensed under the Polyform Noncommercial License 1.0.0
See LICENSE file in the project root for full license information.
"""

import asyncio
import time
from pathlib import Path
from typing import Optional, Dict, Set, TypeVar, Generic
from collections import OrderedDict

from .config import MAX_PROJECTS_IN_CACHE, GIT_CACHE_TTL_SECONDS

T = TypeVar('T')


# =============================================================================
# LRU Cache with Size Limit
# =============================================================================
class LRUCache(OrderedDict):
    """Memory-bounded LRU cache to prevent unbounded growth."""

    def __init__(self, maxsize: int = MAX_PROJECTS_IN_CACHE):
        super().__init__()
        self.maxsize = maxsize

    def __getitem__(self, key):
        value = super().__getitem__(key)
        self.move_to_end(key)
        return value

    def __setitem__(self, key, value):
        if key in self:
            self.move_to_end(key)
        super().__setitem__(key, value)
        while len(self) > self.maxsize:
            oldest = next(iter(self))
            del self[oldest]


# =============================================================================
# TTL-LRU Cache (Size + Time bounded)
# =============================================================================
class TTLLRUCache(Generic[T]):
    """
    LRU Cache with TTL (Time-To-Live) support.

    - Items expire after ttl_seconds
    - Cache is bounded by maxsize
    - Expired items are cleaned on access
    """

    def __init__(self, maxsize: int = 20, ttl_seconds: int = 3600):
        self._cache: OrderedDict[str, T] = OrderedDict()
        self._timestamps: Dict[str, float] = {}
        self.maxsize = maxsize
        self.ttl = ttl_seconds

    def __contains__(self, key: str) -> bool:
        if key not in self._cache:
            return False
        if self._is_expired(key):
            self._remove(key)
            return False
        return True

    def __len__(self) -> int:
        return len(self._cache)

    def _is_expired(self, key: str) -> bool:
        if key not in self._timestamps:
            return True
        return time.time() - self._timestamps[key] > self.ttl

    def _remove(self, key: str):
        self._cache.pop(key, None)
        self._timestamps.pop(key, None)

    def get(self, key: str, default: Optional[T] = None) -> Optional[T]:
        if key not in self._cache:
            return default
        if self._is_expired(key):
            self._remove(key)
            return default
        self._cache.move_to_end(key)
        return self._cache[key]

    def set(self, key: str, value: T):
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = value
        self._timestamps[key] = time.time()

        # Enforce size limit
        while len(self._cache) > self.maxsize:
            oldest = next(iter(self._cache))
            self._remove(oldest)

    def invalidate(self, key: str):
        self._remove(key)

    def clear(self):
        self._cache.clear()
        self._timestamps.clear()

    def cleanup_expired(self) -> int:
        """Remove all expired items. Returns count of removed items."""
        expired = [k for k in self._cache if self._is_expired(k)]
        for k in expired:
            self._remove(k)
        return len(expired)

    def items(self):
        """Iterate over non-expired items."""
        for key in list(self._cache.keys()):
            if not self._is_expired(key):
                yield key, self._cache[key]


# =============================================================================
# Async File Locking (non-blocking, thread-safe)
# =============================================================================
class AsyncFileLock:
    """
    Non-blocking async file lock using asyncio.Lock per path.

    Fixed v4.19.1: Lazy initialization of _global_lock to avoid creating Lock
    before event loop exists (Python 3.10+ deprecation, 3.12+ error).
    """

    _locks: Dict[str, asyncio.Lock] = {}
    _global_lock: Optional[asyncio.Lock] = None  # Lazy init

    @classmethod
    def _get_or_create_global_lock(cls) -> asyncio.Lock:
        """Get or create the global lock (lazy initialization)."""
        if cls._global_lock is None:
            cls._global_lock = asyncio.Lock()
        return cls._global_lock

    @classmethod
    async def acquire(cls, path: Path) -> asyncio.Lock:
        """Get or create a lock for the given path."""
        path_str = str(path)
        global_lock = cls._get_or_create_global_lock()

        async with global_lock:
            if path_str not in cls._locks:
                cls._locks[path_str] = asyncio.Lock()
            return cls._locks[path_str]

    @classmethod
    async def cleanup_unused(cls, keep_paths: Set[str]):
        """Remove locks for paths no longer in use."""
        global_lock = cls._get_or_create_global_lock()
        async with global_lock:
            to_remove = [p for p in cls._locks if p not in keep_paths]
            for p in to_remove:
                del cls._locks[p]


# =============================================================================
# Git Call Cache (with TTL)
# =============================================================================
class GitCache:
    """Cache Git subprocess results with TTL to avoid repeated calls."""

    def __init__(self, ttl_seconds: int = GIT_CACHE_TTL_SECONDS):
        self._cache: Dict[str, tuple] = {}
        self.ttl = ttl_seconds

    def get(self, path: str) -> Optional[str]:
        if path in self._cache:
            result, ts = self._cache[path]
            if time.time() - ts < self.ttl:
                return result
            del self._cache[path]
        return None

    def set(self, path: str, result: str):
        self._cache[path] = (result, time.time())

    def invalidate(self, path: str):
        self._cache.pop(path, None)


# Global git cache instance
git_cache = GitCache()
