"""
CHAINGUARD v5.0 - Task Mode System Tests

Tests for the multi-mode architecture: programming, content, devops, research, generic
"""

import pytest
import asyncio
from datetime import datetime
from pathlib import Path

# Import from the chainguard package
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from chainguard.config import (
    TaskMode, ModeFeatures, TASK_MODE_CONFIG, TASK_MODE_CONTEXT,
    detect_task_mode, get_mode_features, get_mode_context, should_validate_syntax,
    MODE_DETECTION_KEYWORDS
)
from chainguard.models import ProjectState, ScopeDefinition


# =============================================================================
# TaskMode Enum Tests
# =============================================================================

class TestTaskModeEnum:
    """Tests for TaskMode enum."""

    def test_all_modes_exist(self):
        """Verify all expected modes exist."""
        assert TaskMode.PROGRAMMING == "programming"
        assert TaskMode.CONTENT == "content"
        assert TaskMode.DEVOPS == "devops"
        assert TaskMode.RESEARCH == "research"
        assert TaskMode.GENERIC == "generic"

    def test_from_string_valid(self):
        """Test conversion from valid strings."""
        assert TaskMode.from_string("programming") == TaskMode.PROGRAMMING
        assert TaskMode.from_string("CONTENT") == TaskMode.CONTENT
        assert TaskMode.from_string("DevOps") == TaskMode.DEVOPS

    def test_from_string_invalid(self):
        """Test conversion from invalid string defaults to PROGRAMMING."""
        assert TaskMode.from_string("invalid") == TaskMode.PROGRAMMING
        assert TaskMode.from_string("") == TaskMode.PROGRAMMING

    def test_str_conversion(self):
        """Test string conversion."""
        assert str(TaskMode.PROGRAMMING) == "programming"
        assert str(TaskMode.CONTENT) == "content"


# =============================================================================
# ModeFeatures Tests
# =============================================================================

class TestModeFeatures:
    """Tests for ModeFeatures dataclass."""

    def test_programming_mode_features(self):
        """Programming mode should have all validations enabled."""
        features = TASK_MODE_CONFIG[TaskMode.PROGRAMMING]
        assert features.syntax_validation is True
        assert features.db_inspection is True
        assert features.http_testing is True
        assert features.scope_enforcement is True

    def test_content_mode_features(self):
        """Content mode should have no validations, but word_count enabled."""
        features = TASK_MODE_CONFIG[TaskMode.CONTENT]
        assert features.syntax_validation is False
        assert features.db_inspection is False
        assert features.http_testing is False
        assert features.scope_enforcement is False
        assert features.word_count is True
        assert features.chapter_tracking is True

    def test_devops_mode_features(self):
        """DevOps mode should validate only config files."""
        features = TASK_MODE_CONFIG[TaskMode.DEVOPS]
        assert isinstance(features.syntax_validation, set)
        assert ".yaml" in features.syntax_validation
        assert ".json" in features.syntax_validation
        assert ".conf" in features.syntax_validation
        assert features.command_logging is True
        assert features.rollback_tracking is True

    def test_research_mode_features(self):
        """Research mode should have source and fact tracking."""
        features = TASK_MODE_CONFIG[TaskMode.RESEARCH]
        assert features.syntax_validation is False
        assert features.source_tracking is True
        assert features.fact_indexing is True

    def test_generic_mode_features(self):
        """Generic mode should have minimal features."""
        features = TASK_MODE_CONFIG[TaskMode.GENERIC]
        assert features.syntax_validation is False
        assert features.db_inspection is False
        assert features.http_testing is False
        assert features.scope_enforcement is False


# =============================================================================
# Auto-Detection Tests
# =============================================================================

class TestAutoDetection:
    """Tests for task mode auto-detection."""

    def test_detect_content_mode_keywords(self):
        """Content keywords should trigger content mode."""
        assert detect_task_mode("Schreibe Kapitel 3 meines Buches") == TaskMode.CONTENT
        assert detect_task_mode("Write documentation for API") == TaskMode.CONTENT
        assert detect_task_mode("Blog article about AI") == TaskMode.CONTENT
        assert detect_task_mode("Roman story chapter") == TaskMode.CONTENT

    def test_detect_devops_mode_keywords(self):
        """DevOps keywords should trigger devops mode."""
        assert detect_task_mode("Setup nginx server") == TaskMode.DEVOPS
        assert detect_task_mode("Deploy with Docker") == TaskMode.DEVOPS
        assert detect_task_mode("WordPress installation") == TaskMode.DEVOPS
        assert detect_task_mode("Configure kubernetes cluster") == TaskMode.DEVOPS

    def test_detect_research_mode_keywords(self):
        """Research keywords should trigger research mode."""
        assert detect_task_mode("Recherche zu KI-Tools") == TaskMode.RESEARCH
        assert detect_task_mode("Analyse der Konkurrenz") == TaskMode.RESEARCH
        assert detect_task_mode("Market research for product") == TaskMode.RESEARCH

    def test_detect_programming_default(self):
        """Unknown descriptions should default to programming."""
        assert detect_task_mode("Implementiere Login Feature") == TaskMode.PROGRAMMING
        assert detect_task_mode("Fix bug in user controller") == TaskMode.PROGRAMMING
        assert detect_task_mode("Random task description") == TaskMode.PROGRAMMING


# =============================================================================
# Syntax Validation Tests
# =============================================================================

class TestShouldValidateSyntax:
    """Tests for syntax validation decision logic."""

    def test_programming_validates_all(self):
        """Programming mode validates all code files."""
        assert should_validate_syntax(TaskMode.PROGRAMMING, "test.php") is True
        assert should_validate_syntax(TaskMode.PROGRAMMING, "test.js") is True
        assert should_validate_syntax(TaskMode.PROGRAMMING, "test.py") is True
        assert should_validate_syntax(TaskMode.PROGRAMMING, "test.md") is True

    def test_content_validates_none(self):
        """Content mode validates no files."""
        assert should_validate_syntax(TaskMode.CONTENT, "test.php") is False
        assert should_validate_syntax(TaskMode.CONTENT, "test.md") is False
        assert should_validate_syntax(TaskMode.CONTENT, "chapter.txt") is False

    def test_devops_validates_config_only(self):
        """DevOps mode only validates config files."""
        assert should_validate_syntax(TaskMode.DEVOPS, "config.yaml") is True
        assert should_validate_syntax(TaskMode.DEVOPS, "settings.json") is True
        assert should_validate_syntax(TaskMode.DEVOPS, "nginx.conf") is True
        assert should_validate_syntax(TaskMode.DEVOPS, "script.php") is False
        assert should_validate_syntax(TaskMode.DEVOPS, "app.py") is False

    def test_generic_validates_none(self):
        """Generic mode validates no files."""
        assert should_validate_syntax(TaskMode.GENERIC, "anything.php") is False
        assert should_validate_syntax(TaskMode.GENERIC, "config.yaml") is False


# =============================================================================
# Context Injection Tests
# =============================================================================

class TestContextInjection:
    """Tests for mode-specific context injection."""

    def test_programming_context(self):
        """Programming context should mention tracking and validation."""
        context = get_mode_context(TaskMode.PROGRAMMING)
        assert "chainguard_track" in context
        assert "Syntax-Validierung" in context or "Syntax" in context

    def test_content_context(self):
        """Content context should mention writing and word count."""
        context = get_mode_context(TaskMode.CONTENT)
        assert "Keine Syntax" in context or "keine Blockaden" in context.lower()
        assert "word" in context.lower() or "Word" in context

    def test_devops_context(self):
        """DevOps context should mention commands and checkpoints."""
        context = get_mode_context(TaskMode.DEVOPS)
        assert "Command" in context or "command" in context

    def test_research_context(self):
        """Research context should mention sources and facts."""
        context = get_mode_context(TaskMode.RESEARCH)
        assert "source" in context.lower() or "Quellen" in context
        assert "fact" in context.lower() or "Fakt" in context


# =============================================================================
# ProjectState Task Mode Tests
# =============================================================================

class TestProjectStateTaskMode:
    """Tests for task mode integration in ProjectState."""

    def test_default_mode_is_programming(self):
        """Default task mode should be programming."""
        state = ProjectState(
            project_id="test",
            project_name="test",
            project_path="/tmp/test"
        )
        assert state.task_mode == "programming"
        assert state.get_task_mode() == TaskMode.PROGRAMMING

    def test_get_features(self):
        """get_features should return correct ModeFeatures."""
        state = ProjectState(
            project_id="test",
            project_name="test",
            project_path="/tmp/test",
            task_mode="content"
        )
        features = state.get_features()
        assert features.word_count is True
        assert features.syntax_validation is False

    def test_content_mode_methods(self):
        """Test content mode specific methods."""
        state = ProjectState(
            project_id="test",
            project_name="test",
            project_path="/tmp/test",
            task_mode="content"
        )

        # Word count
        state.update_word_count(1500)
        assert state.word_count_total == 1500

        # Chapter status
        state.set_chapter_status("Chapter 1", "draft")
        state.set_chapter_status("Chapter 2", "done")
        assert state.chapter_status["Chapter 1"] == "draft"
        assert state.chapter_status["Chapter 2"] == "done"

    def test_devops_mode_methods(self):
        """Test devops mode specific methods."""
        state = ProjectState(
            project_id="test",
            project_name="test",
            project_path="/tmp/test",
            task_mode="devops"
        )

        # Command logging
        state.add_command("wp plugin install woocommerce", "success", "Installed!")
        assert len(state.command_history) == 1
        assert state.command_history[0]["cmd"] == "wp plugin install woocommerce"

        # Checkpoints
        state.add_checkpoint("before-update", ["/etc/nginx/nginx.conf"])
        assert len(state.checkpoints) == 1
        assert state.checkpoints[0]["name"] == "before-update"

    def test_research_mode_methods(self):
        """Test research mode specific methods."""
        state = ProjectState(
            project_id="test",
            project_name="test",
            project_path="/tmp/test",
            task_mode="research"
        )

        # Sources
        state.add_source("https://example.com", "Example Paper", "high")
        assert len(state.sources) == 1
        assert state.sources[0]["relevance"] == "high"

        # Facts
        state.add_fact("AI is transformative", "example.com", "verified")
        assert len(state.facts) == 1
        assert state.facts[0]["confidence"] == "verified"

    def test_mode_status_line(self):
        """Test mode-specific status line generation."""
        # Content mode
        state = ProjectState(
            project_id="test",
            project_name="test",
            project_path="/tmp/test",
            task_mode="content"
        )
        state.word_count_total = 5000
        state.chapter_status = {"Ch1": "done", "Ch2": "draft"}
        status = state.get_mode_status_line()
        assert "5000 words" in status

        # DevOps mode
        state.task_mode = "devops"
        state.command_history = [{"cmd": "test"}]
        state.checkpoints = [{"name": "test"}]
        status = state.get_mode_status_line()
        assert "1 cmds" in status
        assert "1 checkpoints" in status

        # Research mode
        state.task_mode = "research"
        state.sources = [{"url": "test"}]
        state.facts = [{"fact": "test"}]
        status = state.get_mode_status_line()
        assert "1 sources" in status
        assert "1 facts" in status


# =============================================================================
# State Migration Tests
# =============================================================================

class TestStateMigration:
    """Tests for backwards compatibility with old state files."""

    def test_migration_adds_task_mode(self):
        """Old state without task_mode should get default."""
        old_data = {
            "project_id": "test",
            "project_name": "test",
            "project_path": "/tmp/test",
            "phase": "implementation"
            # No task_mode field
        }
        state = ProjectState.from_dict(old_data)
        assert state.task_mode == "programming"

    def test_migration_adds_mode_fields(self):
        """Old state should get all new mode-specific fields."""
        old_data = {
            "project_id": "test",
            "project_name": "test",
            "project_path": "/tmp/test"
            # No content/devops/research fields
        }
        state = ProjectState.from_dict(old_data)
        assert state.word_count_total == 0
        assert state.chapter_status == {}
        assert state.command_history == []
        assert state.checkpoints == []
        assert state.sources == []
        assert state.facts == []


# =============================================================================
# HTTP Test Requirement Tests
# =============================================================================

class TestHTTPTestRequirement:
    """Tests for mode-aware HTTP test requirements."""

    def test_programming_requires_http_tests(self):
        """Programming mode should require HTTP tests for web files."""
        state = ProjectState(
            project_id="test",
            project_name="test",
            project_path="/tmp/test",
            task_mode="programming"
        )
        state.files_changed = 1
        state.changed_files = ["UserController.php"]
        # This would return True if web files are detected
        # (actual detection depends on the _check_http_test_needed method)

    def test_content_no_http_tests(self):
        """Content mode should not require HTTP tests."""
        state = ProjectState(
            project_id="test",
            project_name="test",
            project_path="/tmp/test",
            task_mode="content"
        )
        assert state.is_http_test_required() is False

    def test_generic_no_http_tests(self):
        """Generic mode should not require HTTP tests."""
        state = ProjectState(
            project_id="test",
            project_name="test",
            project_path="/tmp/test",
            task_mode="generic"
        )
        assert state.is_http_test_required() is False


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
