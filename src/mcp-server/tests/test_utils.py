"""
Tests for chainguard.utils module.

Tests path sanitization and security functions.
"""

import pytest
from pathlib import Path
from chainguard.utils import sanitize_path, is_path_safe


class TestSanitizePath:
    """Tests for sanitize_path function."""

    def test_absolute_path(self, temp_dir):
        """Test handling of absolute paths."""
        project_path = str(temp_dir)
        file_path = str(temp_dir / "src" / "file.py")

        # Create the directory structure
        (temp_dir / "src").mkdir(parents=True, exist_ok=True)
        (temp_dir / "src" / "file.py").touch()

        result = sanitize_path(file_path, project_path)
        assert result is not None
        assert result == str(Path(file_path).resolve())

    def test_relative_path(self, temp_dir):
        """Test handling of relative paths."""
        project_path = str(temp_dir)

        # Create file
        (temp_dir / "file.py").touch()

        # Use relative path from current working directory perspective
        result = sanitize_path("file.py", project_path)
        assert result is not None
        # Result should be an absolute resolved path
        assert Path(result).is_absolute()

    def test_path_within_project(self, temp_dir):
        """Test that paths within project return resolved path."""
        project_path = str(temp_dir)
        (temp_dir / "src").mkdir(parents=True, exist_ok=True)
        (temp_dir / "src" / "main.py").touch()

        file_path = str(temp_dir / "src" / "main.py")
        result = sanitize_path(file_path, project_path)

        assert result is not None
        assert result == str(Path(file_path).resolve())
        # Verify the resolved path is under project
        assert str(temp_dir.resolve()) in result

    def test_path_outside_project(self, temp_dir):
        """Test that paths outside project still return resolved path."""
        project_path = str(temp_dir / "project")
        (temp_dir / "project").mkdir(parents=True, exist_ok=True)

        # Create a file outside the project
        outside_file = temp_dir / "outside.py"
        outside_file.touch()

        result = sanitize_path(str(outside_file), project_path)

        # According to the implementation, it returns the resolved path
        # even for files outside the project
        assert result is not None
        assert result == str(outside_file.resolve())

    def test_invalid_path(self):
        """Test that invalid paths return None."""
        # Use a path that will cause an OSError or ValueError
        # NUL character in path is invalid on most systems
        result = sanitize_path("\x00invalid", "/some/project")
        assert result is None

    def test_path_with_traversal_resolved(self, temp_dir):
        """Test that path traversal is resolved correctly."""
        project_path = str(temp_dir)
        (temp_dir / "src").mkdir(parents=True, exist_ok=True)
        (temp_dir / "file.py").touch()

        # Path with traversal that stays within project
        file_path = str(temp_dir / "src" / ".." / "file.py")
        result = sanitize_path(file_path, project_path)

        assert result is not None
        # Should resolve to the canonical path
        expected = str((temp_dir / "file.py").resolve())
        assert result == expected

    def test_empty_path(self, temp_dir):
        """Test handling of empty path."""
        project_path = str(temp_dir)
        result = sanitize_path("", project_path)
        # Empty path resolves to current directory
        assert result is not None

    def test_nested_directory_path(self, temp_dir):
        """Test deeply nested directory paths."""
        project_path = str(temp_dir)
        nested_path = temp_dir / "a" / "b" / "c" / "d" / "file.py"
        nested_path.parent.mkdir(parents=True, exist_ok=True)
        nested_path.touch()

        result = sanitize_path(str(nested_path), project_path)
        assert result is not None
        assert result == str(nested_path.resolve())


class TestIsPathSafe:
    """Tests for is_path_safe function."""

    def test_empty_path(self, temp_dir):
        """Test that empty path returns True."""
        project_path = str(temp_dir)
        assert is_path_safe("", project_path) is True

    def test_simple_path(self, temp_dir):
        """Test that simple safe paths return True."""
        project_path = str(temp_dir)
        (temp_dir / "file.py").touch()

        assert is_path_safe(str(temp_dir / "file.py"), project_path) is True

    def test_path_traversal_within_project(self, temp_dir):
        """Test path traversal that stays within project returns True."""
        project_path = str(temp_dir)
        (temp_dir / "src").mkdir(parents=True, exist_ok=True)
        (temp_dir / "file.py").touch()

        # Traversal that resolves back into project
        file_path = str(temp_dir / "src" / ".." / "file.py")
        assert is_path_safe(file_path, project_path) is True

    def test_path_traversal_outside_project(self, temp_dir):
        """Test path traversal that goes outside project returns False."""
        project_path = str(temp_dir / "project")
        (temp_dir / "project").mkdir(parents=True, exist_ok=True)

        # Create a file outside
        (temp_dir / "outside.py").touch()

        # Traversal that goes outside project
        file_path = str(temp_dir / "project" / ".." / "outside.py")
        assert is_path_safe(file_path, project_path) is False

    def test_no_traversal(self, temp_dir):
        """Test that paths without .. return True."""
        project_path = str(temp_dir)
        (temp_dir / "src" / "subdir").mkdir(parents=True, exist_ok=True)

        file_path = str(temp_dir / "src" / "subdir" / "file.py")
        assert is_path_safe(file_path, project_path) is True

    def test_invalid_characters(self, temp_dir):
        """Test handling of edge cases with invalid characters."""
        project_path = str(temp_dir)

        # NUL character should cause exception and return False
        result = is_path_safe("\x00invalid/path", project_path)
        assert result is False

    def test_relative_path_without_traversal(self, temp_dir):
        """Test relative path without traversal."""
        project_path = str(temp_dir)

        # Simple relative path without ..
        assert is_path_safe("file.py", project_path) is True
        assert is_path_safe("src/file.py", project_path) is True

    def test_dot_in_filename(self, temp_dir):
        """Test that dots in filename (not ..) are safe."""
        project_path = str(temp_dir)

        # Dots in filename should be fine
        assert is_path_safe("file.test.py", project_path) is True
        assert is_path_safe(".hidden", project_path) is True

    def test_multiple_traversals_within_project(self, temp_dir):
        """Test multiple .. that still resolve within project."""
        project_path = str(temp_dir)
        (temp_dir / "a" / "b" / "c").mkdir(parents=True, exist_ok=True)
        (temp_dir / "file.py").touch()

        # Multiple traversals but still in project
        file_path = str(temp_dir / "a" / "b" / ".." / ".." / "file.py")
        assert is_path_safe(file_path, project_path) is True

    def test_multiple_traversals_outside_project(self, temp_dir):
        """Test multiple .. that go outside project."""
        project_path = str(temp_dir / "project" / "subdir")
        (temp_dir / "project" / "subdir").mkdir(parents=True, exist_ok=True)
        (temp_dir / "outside.py").touch()

        # Multiple traversals going outside
        file_path = str(temp_dir / "project" / "subdir" / ".." / ".." / "outside.py")
        assert is_path_safe(file_path, project_path) is False

    def test_absolute_path_no_traversal(self, temp_dir):
        """Test absolute path without traversal is safe."""
        project_path = str(temp_dir)
        (temp_dir / "src").mkdir(parents=True, exist_ok=True)

        file_path = str(temp_dir / "src" / "file.py")
        assert is_path_safe(file_path, project_path) is True

    def test_none_handling(self, temp_dir):
        """Test behavior with None-like values."""
        project_path = str(temp_dir)

        # Empty string is explicitly handled
        assert is_path_safe("", project_path) is True
