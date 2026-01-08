"""
Pytest fixtures for Chainguard MCP Server tests.
"""

import pytest
import tempfile
import shutil
from pathlib import Path


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    tmp = tempfile.mkdtemp()
    yield Path(tmp)
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def sample_project_path(temp_dir):
    """Create a sample project structure."""
    project = temp_dir / "sample_project"
    project.mkdir()
    (project / "src").mkdir()
    (project / "tests").mkdir()
    (project / "src" / "main.py").write_text("# Main file")
    return project
