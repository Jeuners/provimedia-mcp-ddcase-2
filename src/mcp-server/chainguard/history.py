"""
CHAINGUARD MCP Server - History Module

Error Memory System:
- Logs all changes per scope (append-only JSONL)
- Maintains an error index for fast lookup
- Provides Auto-Suggest for similar errors
- Supports recall queries across project history

Copyright (c) 2026 Provimedia GmbH
Licensed under the Polyform Noncommercial License 1.0.0
See LICENSE file in the project root for full license information.
"""

import json
import asyncio
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict, field
from typing import Dict, Any, List, Optional

from .config import CHAINGUARD_HOME, logger

# Async file I/O
try:
    import aiofiles
    import aiofiles.os
    HAS_AIOFILES = True
except ImportError:
    HAS_AIOFILES = False


# =============================================================================
# Constants
# =============================================================================
HISTORY_MAX_ENTRIES = 500       # Max entries per history file
ERROR_INDEX_MAX_ENTRIES = 100   # Max errors in index
SIMILARITY_THRESHOLD = 0.6     # For fuzzy matching
AUTO_SUGGEST_MAX_RESULTS = 2   # Max suggestions to show


# =============================================================================
# Data Models
# =============================================================================
@dataclass
class HistoryEntry:
    """Single entry in the scope history log."""
    ts: str                           # ISO timestamp
    file: str                         # File path (relative)
    action: str                       # edit, create, delete
    validation: str                   # PASS, FAIL:message
    scope_id: str = ""                # Reference to scope
    scope_desc: str = ""              # Scope description (for context)
    fix_applied: Optional[str] = None # If error was fixed, describe how

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None and v != ""}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HistoryEntry":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class ErrorEntry:
    """Entry in the error index for fast lookup."""
    ts: str                             # When error occurred
    file_pattern: str                   # File name pattern (e.g., "*Controller.php")
    error_type: str                     # PHP Syntax, JS Syntax, Python Syntax, etc.
    error_msg: str                      # The error message
    scope_desc: str                     # What was being worked on
    project_id: str                     # Project reference
    resolution: Optional[str] = None    # How it was fixed (if known)

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ErrorEntry":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def matches(self, query: str) -> float:
        """Calculate match score for a query (0.0 - 1.0)."""
        # Split query into words and check each
        query_words = query.lower().split()
        if not query_words:
            return 0.0

        total_score = 0.0

        for word in query_words:
            word_score = 0.0

            # Check file pattern
            if word in self.file_pattern.lower():
                word_score = max(word_score, 0.3)

            # Check error type
            if word in self.error_type.lower():
                word_score = max(word_score, 0.3)

            # Check error message
            if word in self.error_msg.lower():
                word_score = max(word_score, 0.3)

            # Check scope
            if word in self.scope_desc.lower():
                word_score = max(word_score, 0.1)

            total_score += word_score

        # Normalize by number of query words
        return min(total_score / len(query_words), 1.0) if query_words else 0.0


# =============================================================================
# History Manager
# =============================================================================
class HistoryManager:
    """
    Manages project history and error index.

    Storage:
    - ~/.chainguard/projects/{id}/history.jsonl  (append-only log)
    - ~/.chainguard/projects/{id}/error_index.json (error lookup)
    """

    @staticmethod
    def _get_history_path(project_id: str) -> Path:
        return CHAINGUARD_HOME / "projects" / project_id / "history.jsonl"

    @staticmethod
    def _get_error_index_path(project_id: str) -> Path:
        return CHAINGUARD_HOME / "projects" / project_id / "error_index.json"

    @staticmethod
    async def _ensure_dir(path: Path):
        """Ensure parent directory exists."""
        parent = path.parent
        if HAS_AIOFILES:
            try:
                await aiofiles.os.makedirs(str(parent), exist_ok=True)
            except (OSError, FileExistsError):
                pass
        else:
            parent.mkdir(parents=True, exist_ok=True)

    # =========================================================================
    # History Log (append-only)
    # =========================================================================
    @classmethod
    async def log_change(
        cls,
        project_id: str,
        file: str,
        action: str,
        validation_result: str,
        scope_id: str = "",
        scope_desc: str = ""
    ):
        """
        Append a change to the history log.

        This is called after every chainguard_track to maintain a complete
        audit trail of all changes within each scope.
        """
        entry = HistoryEntry(
            ts=datetime.now().isoformat(),
            file=file,
            action=action,
            validation=validation_result,
            scope_id=scope_id,
            scope_desc=scope_desc
        )

        path = cls._get_history_path(project_id)
        await cls._ensure_dir(path)

        try:
            line = json.dumps(entry.to_dict(), ensure_ascii=False) + "\n"

            if HAS_AIOFILES:
                async with aiofiles.open(path, 'a', encoding='utf-8') as f:
                    await f.write(line)
            else:
                with open(path, 'a', encoding='utf-8') as f:
                    f.write(line)

        except Exception as e:
            logger.error(f"Failed to log change: {e}")

    @classmethod
    async def get_history(
        cls,
        project_id: str,
        limit: int = 50,
        scope_id: Optional[str] = None
    ) -> List[HistoryEntry]:
        """
        Read history entries (most recent first).

        Args:
            project_id: Project identifier
            limit: Max entries to return
            scope_id: Filter by specific scope (optional)
        """
        path = cls._get_history_path(project_id)

        if not path.exists():
            return []

        entries = []
        try:
            if HAS_AIOFILES:
                async with aiofiles.open(path, 'r', encoding='utf-8') as f:
                    lines = await f.readlines()
            else:
                with open(path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()

            # Parse in reverse (most recent first)
            for line in reversed(lines[-HISTORY_MAX_ENTRIES:]):
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    entry = HistoryEntry.from_dict(data)

                    # Filter by scope if specified
                    if scope_id and entry.scope_id != scope_id:
                        continue

                    entries.append(entry)
                    if len(entries) >= limit:
                        break
                except json.JSONDecodeError:
                    continue

        except Exception as e:
            logger.error(f"Failed to read history: {e}")

        return entries

    # =========================================================================
    # Error Index
    # =========================================================================
    @classmethod
    async def index_error(
        cls,
        project_id: str,
        file: str,
        error_type: str,
        error_msg: str,
        scope_desc: str,
        resolution: Optional[str] = None
    ):
        """
        Add an error to the index for future lookup.

        This is called when chainguard_track detects a syntax error.
        """
        # Extract file pattern (e.g., "UserController.php" -> "*Controller.php")
        file_name = Path(file).name
        pattern = cls._extract_pattern(file_name)

        entry = ErrorEntry(
            ts=datetime.now().isoformat(),
            file_pattern=pattern,
            error_type=error_type,
            error_msg=error_msg[:200],  # Truncate long messages
            resolution=resolution,
            scope_desc=scope_desc[:100],
            project_id=project_id
        )

        # Load existing index
        index = await cls._load_error_index(project_id)

        # Add new entry (avoid duplicates based on pattern + error type)
        existing = next(
            (e for e in index if e.file_pattern == pattern and e.error_type == error_type),
            None
        )

        if existing:
            # Update existing entry with newer info
            index.remove(existing)

        index.insert(0, entry)

        # Trim to max size
        index = index[:ERROR_INDEX_MAX_ENTRIES]

        # Save
        await cls._save_error_index(project_id, index)

    @classmethod
    async def update_resolution(
        cls,
        project_id: str,
        file_pattern: str,
        error_type: str,
        resolution: str
    ):
        """
        Update the resolution for an error entry.

        Called when a previously failing file now passes validation.
        """
        index = await cls._load_error_index(project_id)

        for entry in index:
            if entry.file_pattern == file_pattern and entry.error_type == error_type:
                entry.resolution = resolution
                await cls._save_error_index(project_id, index)
                return True

        return False

    @classmethod
    async def find_similar_errors(
        cls,
        project_id: str,
        file: str,
        error_type: str,
        error_msg: str
    ) -> List[ErrorEntry]:
        """
        Find similar errors from the index.

        This powers the Auto-Suggest feature - when an error occurs,
        we check if we've seen something similar before.

        Returns: List of matching ErrorEntry with resolutions
        """
        index = await cls._load_error_index(project_id)

        if not index:
            return []

        file_pattern = cls._extract_pattern(Path(file).name)
        matches = []

        for entry in index:
            if not entry.resolution:
                continue  # Skip entries without known resolution

            score = 0.0

            # Same error type is important
            if entry.error_type == error_type:
                score += 0.4

            # Similar file pattern
            if cls._patterns_match(entry.file_pattern, file_pattern):
                score += 0.3

            # Similar error message
            if cls._messages_similar(entry.error_msg, error_msg):
                score += 0.3

            if score >= SIMILARITY_THRESHOLD:
                matches.append((score, entry))

        # Sort by score descending
        matches.sort(key=lambda x: x[0], reverse=True)

        return [entry for _, entry in matches[:AUTO_SUGGEST_MAX_RESULTS]]

    @classmethod
    async def recall(
        cls,
        project_id: str,
        query: str,
        limit: int = 5
    ) -> List[ErrorEntry]:
        """
        Search the error index for matching entries.

        This is the main recall API - searches across file patterns,
        error types, and error messages.
        """
        index = await cls._load_error_index(project_id)

        if not index:
            return []

        matches = []
        for entry in index:
            score = entry.matches(query)
            if score > 0.2:  # Minimum threshold
                matches.append((score, entry))

        # Sort by score descending
        matches.sort(key=lambda x: x[0], reverse=True)

        return [entry for _, entry in matches[:limit]]

    # =========================================================================
    # Scope Summary (for MD export)
    # =========================================================================
    @classmethod
    async def generate_scope_summary(
        cls,
        project_id: str,
        scope_id: str,
        scope_desc: str
    ) -> str:
        """
        Generate a markdown summary for a completed scope.

        This is called at chainguard_finish to create a compact
        documentation of what was done.
        """
        entries = await cls.get_history(project_id, limit=100, scope_id=scope_id)

        if not entries:
            return f"# {scope_desc}\n\nNo changes recorded."

        # Collect stats
        files_changed = set()
        errors_encountered = []

        for entry in entries:
            files_changed.add(entry.file)
            if entry.validation.startswith("FAIL"):
                errors_encountered.append({
                    "file": entry.file,
                    "error": entry.validation
                })

        # Build markdown
        lines = [
            f"# {scope_desc}",
            "",
            f"**Date:** {entries[-1].ts[:10]} - {entries[0].ts[:10]}",
            f"**Files Changed:** {len(files_changed)}",
            f"**Errors Encountered:** {len(errors_encountered)}",
            "",
            "## Changed Files",
            ""
        ]

        for f in sorted(files_changed):
            lines.append(f"- `{f}`")

        if errors_encountered:
            lines.extend([
                "",
                "## Errors & Fixes",
                ""
            ])
            for err in errors_encountered[:10]:
                lines.append(f"- **{err['file']}**: {err['error']}")

        return "\n".join(lines)

    # =========================================================================
    # Internal Helpers
    # =========================================================================
    @classmethod
    async def _load_error_index(cls, project_id: str) -> List[ErrorEntry]:
        """Load the error index from disk."""
        path = cls._get_error_index_path(project_id)

        if not path.exists():
            return []

        try:
            if HAS_AIOFILES:
                async with aiofiles.open(path, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    data = json.loads(content)
            else:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

            return [ErrorEntry.from_dict(e) for e in data]

        except (json.JSONDecodeError, OSError) as e:
            logger.error(f"Failed to load error index: {e}")
            return []

    @classmethod
    async def _save_error_index(cls, project_id: str, index: List[ErrorEntry]):
        """Save the error index to disk."""
        path = cls._get_error_index_path(project_id)
        await cls._ensure_dir(path)

        try:
            content = json.dumps([e.to_dict() for e in index], indent=2, ensure_ascii=False)

            if HAS_AIOFILES:
                async with aiofiles.open(path, 'w', encoding='utf-8') as f:
                    await f.write(content)
            else:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(content)

        except Exception as e:
            logger.error(f"Failed to save error index: {e}")

    @staticmethod
    def _extract_pattern(file_name: str) -> str:
        """
        Extract a pattern from a file name for matching.

        Examples:
            UserController.php -> *Controller.php
            auth.service.ts -> *.service.ts
            index.js -> index.js (no pattern)
        """
        # Common suffixes to pattern
        suffixes = [
            "Controller.php", "Service.php", "Model.php", "Repository.php",
            ".service.ts", ".component.ts", ".module.ts", ".controller.ts",
            ".test.ts", ".spec.ts", ".test.js", ".spec.js",
            "_test.py", "_spec.py"
        ]

        for suffix in suffixes:
            if file_name.endswith(suffix):
                return f"*{suffix}"

        # Return just extension pattern for common files
        ext = Path(file_name).suffix
        if ext in [".php", ".js", ".ts", ".py", ".json"]:
            return f"*{ext}"

        return file_name

    @staticmethod
    def _patterns_match(pattern1: str, pattern2: str) -> bool:
        """Check if two patterns are similar."""
        # Exact match
        if pattern1 == pattern2:
            return True

        # Both are wildcards with same extension
        if pattern1.startswith("*") and pattern2.startswith("*"):
            ext1 = pattern1.split(".")[-1] if "." in pattern1 else ""
            ext2 = pattern2.split(".")[-1] if "." in pattern2 else ""
            return ext1 == ext2

        return False

    @staticmethod
    def _messages_similar(msg1: str, msg2: str) -> bool:
        """Check if two error messages are similar."""
        # Normalize
        msg1 = msg1.lower()
        msg2 = msg2.lower()

        # Common error patterns
        patterns = [
            "unexpected", "syntax error", "parse error", "missing",
            "undefined", "expected", "invalid", "cannot find"
        ]

        for pattern in patterns:
            if pattern in msg1 and pattern in msg2:
                return True

        # Check word overlap
        words1 = set(msg1.split())
        words2 = set(msg2.split())
        overlap = len(words1 & words2) / max(len(words1 | words2), 1)

        return overlap > 0.3


# =============================================================================
# Auto-Suggest Formatter
# =============================================================================
def format_auto_suggest(similar_errors: List[ErrorEntry]) -> str:
    """Format similar errors as Auto-Suggest hints."""
    if not similar_errors:
        return ""

    lines = ["", "💡 Similar error fixed before:"]

    for entry in similar_errors:
        # Time ago
        try:
            ts = datetime.fromisoformat(entry.ts)
            days_ago = (datetime.now() - ts).days
            if days_ago == 0:
                time_str = "today"
            elif days_ago == 1:
                time_str = "1d ago"
            else:
                time_str = f"{days_ago}d ago"
        except ValueError:
            time_str = ""

        lines.append(f"   - {entry.file_pattern} ({time_str})")
        if entry.resolution:
            lines.append(f"     → {entry.resolution}")

    return "\n".join(lines)
