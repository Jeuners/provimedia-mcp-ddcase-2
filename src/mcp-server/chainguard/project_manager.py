"""
CHAINGUARD MCP Server - Project Manager Module

Contains: ProjectManager with async I/O and debouncing

Copyright (c) 2026 Provimedia GmbH
Licensed under the Polyform Noncommercial License 1.0.0
See LICENSE file in the project root for full license information.
"""

import os
import json
import asyncio
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List, Set

from .config import (
    CHAINGUARD_HOME, DEBOUNCE_DELAY_SECONDS,
    MAX_PROJECTS_IN_CACHE, logger
)
from .cache import LRUCache, AsyncFileLock, git_cache
from .models import ProjectState

# Async file I/O
try:
    import aiofiles
    import aiofiles.os
    HAS_AIOFILES = True
except ImportError:
    HAS_AIOFILES = False


class ProjectManager:
    """
    Manages project state with HIGH-END optimizations:
    - LRU cache with size limit
    - Async I/O (non-blocking)
    - Write debouncing (batched saves)
    - Git call caching
    """

    def __init__(self):
        self.cache: LRUCache = LRUCache(maxsize=MAX_PROJECTS_IN_CACHE)
        self._default_project_id: Optional[str] = None
        self._dirty: Set[str] = set()
        self._save_task: Optional[asyncio.Task] = None
        self._debounce_delay: float = DEBOUNCE_DELAY_SECONDS

    async def _get_project_id_async(self, path: str) -> str:
        """Get project ID using async subprocess with caching."""
        path = str(Path(path).resolve())

        cached = git_cache.get(path)
        if cached:
            return cached

        # Try git remote (async)
        try:
            proc = await asyncio.create_subprocess_exec(
                'git', '-C', path, 'remote', 'get-url', 'origin',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5.0)
            if proc.returncode == 0 and stdout:
                result = hashlib.sha256(stdout.strip()).hexdigest()[:16]
                git_cache.set(path, result)
                return result
        except (asyncio.TimeoutError, OSError):
            pass

        # Try git root (async)
        try:
            proc = await asyncio.create_subprocess_exec(
                'git', '-C', path, 'rev-parse', '--show-toplevel',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5.0)
            if proc.returncode == 0 and stdout:
                result = hashlib.sha256(stdout.strip()).hexdigest()[:16]
                git_cache.set(path, result)
                return result
        except (asyncio.TimeoutError, OSError):
            pass

        # Fallback: hash path
        result = hashlib.sha256(path.encode()).hexdigest()[:16]
        git_cache.set(path, result)
        return result

    def _get_project_id_sync(self, path: str) -> str:
        """Sync fallback for non-async contexts."""
        import subprocess
        path = str(Path(path).resolve())

        cached = git_cache.get(path)
        if cached:
            return cached

        try:
            result = subprocess.run(
                ["git", "-C", path, "remote", "get-url", "origin"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                pid = hashlib.sha256(result.stdout.strip().encode()).hexdigest()[:16]
                git_cache.set(path, pid)
                return pid
        except Exception:
            pass

        try:
            result = subprocess.run(
                ["git", "-C", path, "rev-parse", "--show-toplevel"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                pid = hashlib.sha256(result.stdout.strip().encode()).hexdigest()[:16]
                git_cache.set(path, pid)
                return pid
        except Exception:
            pass

        pid = hashlib.sha256(path.encode()).hexdigest()[:16]
        git_cache.set(path, pid)
        return pid

    def _get_state_path(self, project_id: str) -> Path:
        return CHAINGUARD_HOME / "projects" / project_id / "state.json"

    async def resolve_working_dir_async(self, working_dir: Optional[str] = None) -> str:
        if working_dir and working_dir.strip():
            resolved = str(Path(working_dir).resolve())
            self._default_project_id = await self._get_project_id_async(resolved)
            return resolved

        env_path = os.environ.get("CHAINGUARD_PROJECT_PATH")
        if env_path:
            return str(Path(env_path).resolve())

        if self._default_project_id and self._default_project_id in self.cache:
            return self.cache[self._default_project_id].project_path

        return os.getcwd()

    async def _path_exists_async(self, path: Path) -> bool:
        """Async path.exists() - non-blocking."""
        if HAS_AIOFILES:
            try:
                await aiofiles.os.stat(str(path))
                return True
            except (OSError, FileNotFoundError):
                return False
        return path.exists()

    async def _makedirs_async(self, path: Path):
        """Async makedirs - non-blocking."""
        if HAS_AIOFILES:
            try:
                await aiofiles.os.makedirs(str(path), exist_ok=True)
            except (OSError, FileExistsError):
                pass
        else:
            path.mkdir(parents=True, exist_ok=True)

    async def get_async(self, working_dir: Optional[str] = None) -> ProjectState:
        """Async get with non-blocking I/O."""
        resolved_path = await self.resolve_working_dir_async(working_dir)
        project_id = await self._get_project_id_async(resolved_path)

        # Check cache first (LRU)
        if project_id in self.cache:
            self._default_project_id = project_id
            return self.cache[project_id]

        # Load from disk (async)
        state_path = self._get_state_path(project_id)

        if await self._path_exists_async(state_path):
            lock = await AsyncFileLock.acquire(state_path)
            async with lock:
                try:
                    if HAS_AIOFILES:
                        async with aiofiles.open(state_path, 'r') as f:
                            content = await f.read()
                            data = json.loads(content)
                    else:
                        with open(state_path) as f:
                            data = json.load(f)

                    state = ProjectState.from_dict(data)
                    self.cache[project_id] = state
                    self._default_project_id = project_id
                    return state
                except Exception as e:
                    logger.error(f"Load error: {e}")

        # Create new
        state = ProjectState(
            project_id=project_id,
            project_name=Path(resolved_path).name,
            project_path=resolved_path,
            session_start=datetime.now().isoformat()
        )
        await self.save_async(state)
        self._default_project_id = project_id
        return state

    async def save_async(self, state: ProjectState, immediate: bool = False):
        """
        Save state with debouncing.
        - Updates cache immediately
        - Batches disk writes with delay
        - Set immediate=True for critical saves
        """
        self.cache[state.project_id] = state

        if immediate:
            await self._write_state(state)
        else:
            self._dirty.add(state.project_id)
            if self._save_task is None or self._save_task.done():
                self._save_task = asyncio.create_task(self._debounced_save())

    async def _debounced_save(self):
        """Debounced save - waits then saves all dirty states."""
        await asyncio.sleep(self._debounce_delay)

        dirty_copy = self._dirty.copy()
        self._dirty.clear()

        for project_id in dirty_copy:
            if project_id in self.cache:
                await self._write_state(self.cache[project_id])

    async def _write_state(self, state: ProjectState):
        """Actually write state to disk."""
        state_path = self._get_state_path(state.project_id)
        await self._makedirs_async(state_path.parent)

        lock = await AsyncFileLock.acquire(state_path)
        async with lock:
            content = state.to_json()
            if HAS_AIOFILES:
                async with aiofiles.open(state_path, 'w') as f:
                    await f.write(content)
            else:
                with open(state_path, 'w') as f:
                    f.write(content)

        # v4.17: Write enforcement-state for Hook
        await self._write_enforcement_state(state)

    async def _write_enforcement_state(self, state: ProjectState):
        """
        Write simplified enforcement state for PreToolUse Hook.

        This is a minimal JSON that the chainguard_enforcer.py hook reads
        to enforce CHAINGUARD rules BEFORE Edit/Write tools are executed.
        """
        enforcement_path = self._get_state_path(state.project_id).parent / "enforcement-state.json"

        # Extract blocking alerts
        blocking_alerts = []
        for alert in state.alerts:
            if alert.get("blocking") and not alert.get("ack"):
                blocking_alerts.append(alert.get("msg", "Unknown alert"))

        # Minimal enforcement state
        # v4.18: db_schema_checked_at instead of boolean
        enforcement_data = {
            "project_id": state.project_id,
            "has_scope": state.scope is not None,
            "db_schema_checked_at": getattr(state, "db_schema_checked_at", ""),
            "http_tests_performed": getattr(state, "http_tests_performed", 0),
            "blocking_alerts": blocking_alerts,
            "phase": state.phase,
            "updated_at": datetime.now().isoformat()
        }

        try:
            content = json.dumps(enforcement_data, indent=2)
            if HAS_AIOFILES:
                async with aiofiles.open(enforcement_path, 'w') as f:
                    await f.write(content)
            else:
                with open(enforcement_path, 'w') as f:
                    f.write(content)
        except Exception as e:
            logger.error(f"Failed to write enforcement state: {e}")

    async def flush(self):
        """
        Force flush all pending saves.

        Fixed v4.8.1: Proper error handling - failed writes stay dirty for retry,
        successful writes are removed individually. Raises RuntimeError if any fail.
        """
        # 1. Cancel pending debounced save (we'll handle writes ourselves)
        if self._save_task:
            self._save_task.cancel()
            try:
                await self._save_task
            except asyncio.CancelledError:
                pass  # Expected - we're taking over

        # 2. Flush with error tracking
        errors = []
        dirty_copy = list(self._dirty)  # Safe copy for iteration

        for project_id in dirty_copy:
            if project_id in self.cache:
                try:
                    await self._write_state(self.cache[project_id])
                    self._dirty.discard(project_id)  # Only remove on success!
                except Exception as e:
                    errors.append((project_id, str(e)))
                    logger.error(f"Flush failed for {project_id}: {e}")

        # 3. Report failures (dirty states remain for retry)
        if errors:
            failed_ids = [pid for pid, _ in errors]
            raise RuntimeError(f"Flush incomplete: {len(errors)} projects failed: {failed_ids}")

    async def list_all_projects_async(self) -> List[Dict[str, Any]]:
        """List projects with fully async I/O."""
        projects = []
        projects_dir = CHAINGUARD_HOME / "projects"

        if not await self._path_exists_async(projects_dir):
            return projects

        try:
            project_dirs = list(projects_dir.iterdir())
        except OSError:
            return projects

        for project_dir in project_dirs:
            if not project_dir.is_dir():
                continue

            state_file = project_dir / "state.json"
            if not await self._path_exists_async(state_file):
                continue

            try:
                if HAS_AIOFILES:
                    async with aiofiles.open(state_file, 'r') as f:
                        content = await f.read()
                        data = json.loads(content)
                else:
                    with open(state_file) as f:
                        data = json.load(f)

                projects.append({
                    "id": data.get("project_id"),
                    "name": data.get("project_name"),
                    "phase": data.get("phase"),
                    "last": data.get("last_activity", "")[:10]
                })
            except (json.JSONDecodeError, OSError):
                pass

        return projects

    # Sync wrappers for backward compatibility
    def get(self, working_dir: Optional[str] = None) -> ProjectState:
        """Sync wrapper - uses sync file I/O when event loop is running."""
        # Check if there's a running event loop
        try:
            asyncio.get_running_loop()
            has_running_loop = True
        except RuntimeError:
            has_running_loop = False

        if not has_running_loop:
            # No running loop - safe to use asyncio.run
            return asyncio.run(self.get_async(working_dir))

        # Running loop - use sync file I/O fallback
        resolved_path = working_dir or os.getcwd()
        if working_dir:
            resolved_path = str(Path(working_dir).resolve())
        project_id = self._get_project_id_sync(resolved_path)

        if project_id in self.cache:
            return self.cache[project_id]

        state_path = self._get_state_path(project_id)
        if state_path.exists():
            try:
                with open(state_path) as f:
                    data = json.load(f)
                    state = ProjectState.from_dict(data)
                    self.cache[project_id] = state
                    return state
            except Exception:
                pass

        state = ProjectState(
            project_id=project_id,
            project_name=Path(resolved_path).name,
            project_path=resolved_path,
            session_start=datetime.now().isoformat()
        )
        self.cache[project_id] = state
        return state

    def save(self, state: ProjectState):
        """Sync wrapper for save."""
        self.cache[state.project_id] = state
        self._dirty.add(state.project_id)

    def list_all_projects(self) -> List[Dict[str, Any]]:
        """Sync wrapper for listing projects."""
        projects = []
        projects_dir = CHAINGUARD_HOME / "projects"
        if not projects_dir.exists():
            return projects

        for project_dir in projects_dir.iterdir():
            if project_dir.is_dir():
                state_file = project_dir / "state.json"
                if state_file.exists():
                    try:
                        with open(state_file) as f:
                            data = json.load(f)
                            projects.append({
                                "id": data.get("project_id"),
                                "name": data.get("project_name"),
                                "phase": data.get("phase"),
                                "last": data.get("last_activity", "")[:10]
                            })
                    except (json.JSONDecodeError, OSError):
                        pass
        return projects


# Global instance
project_manager = ProjectManager()
