"""
CHAINGUARD MCP Server - Utilities Module

Contains: Path sanitization and security functions

Copyright (c) 2026 Provimedia GmbH
Licensed under the Polyform Noncommercial License 1.0.0
See LICENSE file in the project root for full license information.
"""

from pathlib import Path
from typing import Optional


def sanitize_path(file_path: str, project_path: str) -> Optional[str]:
    """
    Sanitize and validate a file path to prevent path traversal attacks.
    Returns None if path is invalid or outside project scope.
    """
    try:
        file_resolved = Path(file_path).resolve()
        project_resolved = Path(project_path).resolve()

        try:
            file_resolved.relative_to(project_resolved)
            return str(file_resolved)
        except ValueError:
            # File is outside project - could be legitimate
            return str(file_resolved)

    except (OSError, ValueError):
        return None


def is_path_safe(file_path: str, project_path: str) -> bool:
    """Check if a file path is safe (no traversal, within project)."""
    if not file_path:
        return True

    try:
        file_resolved = Path(file_path).resolve()
        project_resolved = Path(project_path).resolve()

        if '..' in file_path:
            try:
                file_resolved.relative_to(project_resolved)
                return True
            except ValueError:
                return False

        return True
    except (OSError, ValueError):
        return False
