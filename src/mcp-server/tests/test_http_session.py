"""
Tests for chainguard.http_session module.

v4.15: Tests Auto-Re-Login functionality.
"""

import pytest
from chainguard.http_session import HTTPSessionManager


class TestHTTPSessionManager:
    """Tests for HTTPSessionManager class."""

    def test_get_session_creates_new(self):
        """Test that get_session creates a new session if none exists."""
        manager = HTTPSessionManager()
        session = manager.get_session("test_project")

        assert session is not None
        assert session["cookies"] == {}
        assert session["logged_in"] is False
        assert session["credentials"] == {}  # v4.15: credentials field exists

    def test_get_session_returns_existing(self):
        """Test that get_session returns existing session."""
        manager = HTTPSessionManager()
        session1 = manager.get_session("test_project")
        session1["logged_in"] = True
        manager.save_session("test_project", session1)

        session2 = manager.get_session("test_project")
        assert session2["logged_in"] is True

    def test_is_logged_in_false(self):
        """Test is_logged_in returns False for new session."""
        manager = HTTPSessionManager()
        assert manager.is_logged_in("new_project") is False

    def test_is_logged_in_true(self):
        """Test is_logged_in returns True after marking logged in."""
        manager = HTTPSessionManager()
        session = manager.get_session("test_project")
        session["logged_in"] = True
        manager.save_session("test_project", session)

        assert manager.is_logged_in("test_project") is True

    def test_clear_session(self):
        """Test clear_session removes session."""
        manager = HTTPSessionManager()
        session = manager.get_session("test_project")
        session["logged_in"] = True
        manager.save_session("test_project", session)

        manager.clear_session("test_project")
        assert manager.is_logged_in("test_project") is False

    def test_session_has_credentials_field(self):
        """v4.15: Test that session has credentials field for auto-re-login."""
        manager = HTTPSessionManager()
        session = manager.get_session("test_project")

        assert "credentials" in session
        assert isinstance(session["credentials"], dict)


class TestAutoReLogin:
    """Tests for v4.15 Auto-Re-Login functionality."""

    @pytest.mark.asyncio
    async def test_ensure_session_reuses_valid(self):
        """Test ensure_session returns reused=True if already logged in."""
        manager = HTTPSessionManager()
        session = manager.get_session("test_project")
        session["logged_in"] = True
        manager.save_session("test_project", session)

        result = await manager.ensure_session("test_project")

        assert result["success"] is True
        assert result["reused"] is True

    @pytest.mark.asyncio
    async def test_ensure_session_no_credentials(self):
        """Test ensure_session fails gracefully without credentials."""
        manager = HTTPSessionManager()
        # Create session without credentials
        manager.get_session("test_project")

        result = await manager.ensure_session("test_project")

        assert result["success"] is False
        assert "No credentials" in result["error"]

    @pytest.mark.asyncio
    async def test_ensure_session_no_login_url(self):
        """Test ensure_session fails without login_url in credentials."""
        manager = HTTPSessionManager()
        session = manager.get_session("test_project")
        session["credentials"] = {
            "username": "test",
            "password": "test123"
            # No login_url
        }
        manager.save_session("test_project", session)

        result = await manager.ensure_session("test_project")

        assert result["success"] is False
        assert "login_url" in result["error"]

    def test_credentials_stored_after_login_success(self):
        """v4.15: Verify credentials structure is correct for storage."""
        manager = HTTPSessionManager()
        session = manager.get_session("test_project")

        # Simulate what login() does after success
        session["credentials"] = {
            "username": "admin",
            "password": "secret123",
            "login_url": "/login",
            "username_field": "email",
            "password_field": "password"
        }
        session["logged_in"] = True
        manager.save_session("test_project", session)

        # Verify stored
        retrieved = manager.get_session("test_project")
        assert retrieved["credentials"]["username"] == "admin"
        assert retrieved["credentials"]["password"] == "secret123"
        assert retrieved["logged_in"] is True


class TestSessionIsolation:
    """Tests for session isolation between projects."""

    def test_sessions_isolated_between_projects(self):
        """Test that sessions are isolated by project_id."""
        manager = HTTPSessionManager()

        session1 = manager.get_session("project_a")
        session1["logged_in"] = True
        session1["credentials"] = {"username": "user_a"}
        manager.save_session("project_a", session1)

        session2 = manager.get_session("project_b")

        # project_b should have fresh session
        assert session2["logged_in"] is False
        assert session2["credentials"] == {}

        # project_a should still be logged in
        assert manager.is_logged_in("project_a") is True
        assert manager.is_logged_in("project_b") is False

    def test_clear_session_only_affects_target(self):
        """Test that clear_session only clears the target project."""
        manager = HTTPSessionManager()

        # Setup two sessions
        for project in ["project_a", "project_b"]:
            session = manager.get_session(project)
            session["logged_in"] = True
            manager.save_session(project, session)

        # Clear only project_a
        manager.clear_session("project_a")

        assert manager.is_logged_in("project_a") is False
        assert manager.is_logged_in("project_b") is True
