"""
Tests for chainguard.memory module.

Tests project isolation, ID generation, memory management, and scoring.
Note: Full memory tests require chromadb which may not be installed.
"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestGetProjectId:
    """Tests for get_project_id function."""

    def test_import(self):
        """Test that get_project_id can be imported."""
        from chainguard.memory import get_project_id
        assert get_project_id is not None

    def test_returns_16_char_hash(self):
        """Test that project_id is always 16 characters."""
        from chainguard.memory import get_project_id

        project_id = get_project_id("/some/path")
        assert len(project_id) == 16
        assert all(c in '0123456789abcdef' for c in project_id)

    def test_same_path_same_id(self):
        """Test that same path returns same project_id."""
        from chainguard.memory import get_project_id

        id1 = get_project_id("/path/to/project")
        id2 = get_project_id("/path/to/project")
        assert id1 == id2

    def test_different_path_different_id(self):
        """Test that different paths return different project_ids."""
        from chainguard.memory import get_project_id

        id1 = get_project_id("/path/to/project1")
        id2 = get_project_id("/path/to/project2")
        assert id1 != id2

    def test_with_temp_directory(self):
        """Test with actual temporary directory."""
        from chainguard.memory import get_project_id

        with tempfile.TemporaryDirectory() as tmpdir:
            project_id = get_project_id(tmpdir)
            assert len(project_id) == 16


class TestValidateProjectIsolation:
    """Tests for validate_project_isolation function."""

    def test_import(self):
        """Test that validate_project_isolation can be imported."""
        from chainguard.memory import validate_project_isolation
        assert validate_project_isolation is not None

    def test_valid_project(self):
        """Test validation with matching project ID."""
        from chainguard.memory import validate_project_isolation, get_project_id

        with tempfile.TemporaryDirectory() as tmpdir:
            expected_id = get_project_id(tmpdir)
            result = validate_project_isolation(expected_id, tmpdir)
            assert result is True

    def test_invalid_project_id(self):
        """Test validation with mismatched project ID."""
        from chainguard.memory import validate_project_isolation, SecurityError

        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(SecurityError):
                validate_project_isolation("wrongprojectid01", tmpdir)


class TestMemoryDocument:
    """Tests for MemoryDocument dataclass."""

    def test_create_document(self):
        """Test creating a MemoryDocument."""
        from chainguard.memory import MemoryDocument

        doc = MemoryDocument(
            id="doc123",
            content="Test content",
            metadata={"type": "file", "path": "/test.py"}
        )

        assert doc.id == "doc123"
        assert doc.content == "Test content"
        assert doc.metadata["type"] == "file"
        assert doc.metadata["path"] == "/test.py"

    def test_to_dict(self):
        """Test MemoryDocument.to_dict()."""
        from chainguard.memory import MemoryDocument

        doc = MemoryDocument(
            id="doc123",
            content="Test content",
            metadata={"type": "file"}
        )

        d = doc.to_dict()
        assert d["id"] == "doc123"
        assert d["content"] == "Test content"
        assert d["metadata"]["type"] == "file"

    def test_default_metadata(self):
        """Test MemoryDocument with default metadata."""
        from chainguard.memory import MemoryDocument

        doc = MemoryDocument(id="doc", content="content")
        assert doc.metadata == {}


class TestScoredResult:
    """Tests for ScoredResult dataclass."""

    def test_create_scored_result(self):
        """Test creating a ScoredResult."""
        from chainguard.memory import ScoredResult, MemoryDocument

        doc = MemoryDocument(id="doc1", content="test")
        result = ScoredResult(
            document=doc,
            semantic_score=0.8,
            keyword_score=0.6,
            recency_score=0.9,
            final_score=0.75,
            collection="code_structure"
        )

        assert result.document == doc
        assert result.semantic_score == 0.8
        assert result.keyword_score == 0.6
        assert result.recency_score == 0.9
        assert result.final_score == 0.75
        assert result.collection == "code_structure"


class TestMemoryStats:
    """Tests for MemoryStats dataclass."""

    def test_create_stats(self):
        """Test creating MemoryStats."""
        from chainguard.memory import MemoryStats

        stats = MemoryStats(
            project_id="abc123def456gh",
            initialized_at="2025-01-08T10:00:00",
            last_update="2025-01-08T12:00:00",
            collections={"code_structure": 100, "functions": 50},
            total_documents=150,
            storage_size_mb=2.5
        )

        assert stats.project_id == "abc123def456gh"
        assert stats.total_documents == 150
        assert stats.storage_size_mb == 2.5
        assert stats.collections["code_structure"] == 100


class TestRelevanceScorer:
    """Tests for RelevanceScorer class."""

    def test_import(self):
        """Test that RelevanceScorer can be imported."""
        from chainguard.memory import RelevanceScorer
        assert RelevanceScorer is not None

    def test_score_high_semantic(self):
        """Test scoring with high semantic similarity."""
        from chainguard.memory import RelevanceScorer, MemoryDocument

        doc = MemoryDocument(
            id="doc1",
            content="Authentication login system",
            metadata={"type": "file", "updated_at": "2025-01-08T10:00:00"}
        )

        result = RelevanceScorer.score(
            document=doc,
            semantic_distance=0.2,  # Close match (0=identical, 2=opposite)
            keywords=["login", "authentication"],
            task_type="bug",
            collection="code_structure"
        )

        assert result.semantic_score == 0.9  # (1.0 - 0.2/2.0)
        assert result.keyword_score > 0.5  # Keywords match
        assert result.final_score > 0.5

    def test_score_low_semantic(self):
        """Test scoring with low semantic similarity."""
        from chainguard.memory import RelevanceScorer, MemoryDocument

        doc = MemoryDocument(
            id="doc2",
            content="Unrelated content here",
            metadata={"type": "file", "updated_at": "2024-06-01T10:00:00"}
        )

        result = RelevanceScorer.score(
            document=doc,
            semantic_distance=1.8,  # Far match
            keywords=["login"],
            task_type="general",
            collection="code_structure"
        )

        assert 0.09 <= result.semantic_score <= 0.11  # (1.0 - 1.8/2.0) with float tolerance
        assert result.keyword_score == 0.0  # No keyword match
        # Final score depends on recency; with old date it should be low
        assert result.final_score < 0.5  # Allow for recency contribution

    def test_score_with_type_bonus(self):
        """Test scoring with task-type bonus."""
        from chainguard.memory import RelevanceScorer, MemoryDocument

        doc = MemoryDocument(
            id="doc3",
            content="Database table users",
            metadata={"type": "table", "updated_at": "2025-01-08T10:00:00"}
        )

        result = RelevanceScorer.score(
            document=doc,
            semantic_distance=0.5,
            keywords=["users"],
            task_type="database",  # Matches type=table
            collection="database_schema"
        )

        # Should have type bonus for database task + table type
        assert result.final_score > 0.4


class TestContextFormatter:
    """Tests for ContextFormatter class."""

    def test_import(self):
        """Test that ContextFormatter can be imported."""
        from chainguard.memory import ContextFormatter
        assert ContextFormatter is not None

    def test_format_empty_results(self):
        """Test formatting with empty results."""
        from chainguard.memory import ContextFormatter

        result = ContextFormatter.format([], "Test scope")
        assert result == ""

    def test_format_with_results(self):
        """Test formatting with actual results."""
        from chainguard.memory import ContextFormatter, ScoredResult, MemoryDocument

        doc = MemoryDocument(
            id="doc1",
            content="Authentication handler",
            metadata={"path": "src/auth/handler.py", "type": "file"}
        )
        result = ScoredResult(
            document=doc,
            semantic_score=0.8,
            keyword_score=0.6,
            recency_score=0.7,
            final_score=0.75,
            collection="code_structure"
        )

        formatted = ContextFormatter.format([result], "Login feature")
        assert "Memory" in formatted
        assert "src/auth/handler.py" in formatted


class TestShouldIndexFile:
    """Tests for should_index_file function."""

    def test_import(self):
        """Test that should_index_file can be imported."""
        from chainguard.memory import should_index_file
        assert should_index_file is not None

    def test_normal_file(self):
        """Test that normal files should be indexed."""
        from chainguard.memory import should_index_file

        assert should_index_file("src/app/controller.py") is True
        assert should_index_file("lib/utils.js") is True
        assert should_index_file("public/styles.css") is True

    def test_sensitive_files(self):
        """Test that sensitive files should not be indexed."""
        from chainguard.memory import should_index_file

        assert should_index_file(".env") is False
        assert should_index_file("config/.env.local") is False
        assert should_index_file("credentials.json") is False
        assert should_index_file("secrets/api_key.txt") is False
        assert should_index_file("private_key.pem") is False
        assert should_index_file("id_rsa") is False
        assert should_index_file("password.txt") is False


class TestProjectMemoryManager:
    """Tests for ProjectMemoryManager class."""

    def test_import(self):
        """Test that ProjectMemoryManager can be imported."""
        from chainguard.memory import ProjectMemoryManager
        assert ProjectMemoryManager is not None

    def test_create_manager(self):
        """Test creating a ProjectMemoryManager."""
        from chainguard.memory import ProjectMemoryManager

        manager = ProjectMemoryManager()
        assert manager is not None

    def test_global_manager_exists(self):
        """Test that global memory_manager instance exists."""
        from chainguard.memory import memory_manager

        assert memory_manager is not None

    @pytest.mark.asyncio
    async def test_memory_exists_false(self):
        """Test memory_exists returns False for new project."""
        from chainguard.memory import ProjectMemoryManager
        import uuid

        manager = ProjectMemoryManager()
        # Use a truly unique random ID to avoid false positives
        random_id = f"test_{uuid.uuid4().hex[:16]}"
        exists = await manager.memory_exists(random_id)
        assert exists is False

    @pytest.mark.asyncio
    async def test_list_projects_empty(self):
        """Test list_projects with no projects."""
        from chainguard.memory import ProjectMemoryManager

        manager = ProjectMemoryManager()
        projects = await manager.list_projects()
        assert isinstance(projects, list)


class TestSmartContextInjector:
    """Tests for SmartContextInjector class."""

    def test_import(self):
        """Test that SmartContextInjector can be imported."""
        from chainguard.memory import SmartContextInjector
        assert SmartContextInjector is not None

    def test_global_injector_exists(self):
        """Test that global context_injector instance exists."""
        from chainguard.memory import context_injector

        assert context_injector is not None


class TestMemoryHome:
    """Tests for MEMORY_HOME constant."""

    def test_memory_home_exists(self):
        """Test that MEMORY_HOME is set."""
        from chainguard.memory import MEMORY_HOME

        assert MEMORY_HOME is not None
        assert isinstance(MEMORY_HOME, Path)

    def test_memory_home_in_chainguard(self):
        """Test that MEMORY_HOME is under CHAINGUARD_HOME."""
        from chainguard.memory import MEMORY_HOME
        from chainguard.config import CHAINGUARD_HOME

        # MEMORY_HOME should be CHAINGUARD_HOME / "memory"
        assert MEMORY_HOME.parent == CHAINGUARD_HOME
        assert MEMORY_HOME.name == "memory"


class TestCollections:
    """Tests for COLLECTIONS constant."""

    def test_collections_defined(self):
        """Test that COLLECTIONS list is defined."""
        from chainguard.memory import COLLECTIONS

        assert isinstance(COLLECTIONS, list)
        assert "code_structure" in COLLECTIONS
        assert "functions" in COLLECTIONS
        assert "database_schema" in COLLECTIONS
        assert "architecture" in COLLECTIONS
        assert "learnings" in COLLECTIONS


class TestScoringWeights:
    """Tests for SCORING_WEIGHTS constant."""

    def test_weights_defined(self):
        """Test that SCORING_WEIGHTS are defined."""
        from chainguard.memory import SCORING_WEIGHTS

        assert isinstance(SCORING_WEIGHTS, dict)
        assert "semantic" in SCORING_WEIGHTS
        assert "keyword" in SCORING_WEIGHTS
        assert "recency" in SCORING_WEIGHTS

    def test_weights_sum_to_one(self):
        """Test that weights sum to approximately 1.0."""
        from chainguard.memory import SCORING_WEIGHTS

        total = sum(SCORING_WEIGHTS.values())
        assert 0.99 <= total <= 1.01  # Allow small floating point variance


# =============================================================================
# Phase 2 Tests: Auto-Update & Session Consolidation (v5.2)
# =============================================================================

class TestAutoUpdateMemory:
    """Tests for auto-update memory feature (v5.2)."""

    def test_should_index_file_code_files(self):
        """Test that code files should be indexed."""
        from chainguard.memory import should_index_file

        assert should_index_file("src/controller.py") is True
        assert should_index_file("lib/utils.ts") is True
        assert should_index_file("app/Model.php") is True

    def test_should_not_index_node_modules(self):
        """Test that node_modules files should not be indexed."""
        from chainguard.memory import should_index_file

        assert should_index_file("node_modules/express/index.js") is False
        assert should_index_file("node_modules/@types/node/index.d.ts") is False

    def test_should_not_index_vendor(self):
        """Test that vendor files should not be indexed."""
        from chainguard.memory import should_index_file

        assert should_index_file("vendor/laravel/framework/src/Model.php") is False
        assert should_index_file("vendor/autoload.php") is False

    def test_should_not_index_build_dirs(self):
        """Test that build directories should not be indexed."""
        from chainguard.memory import should_index_file

        assert should_index_file("dist/bundle.js") is False
        assert should_index_file("build/output.js") is False
        assert should_index_file(".next/static/chunks/main.js") is False

    def test_should_not_index_cache(self):
        """Test that cache files should not be indexed."""
        from chainguard.memory import should_index_file

        assert should_index_file("__pycache__/module.cpython-39.pyc") is False
        assert should_index_file(".cache/some_file") is False


class TestSessionConsolidation:
    """Tests for session consolidation feature (v5.2)."""

    def test_memory_document_for_learning(self):
        """Test creating a MemoryDocument for session learning."""
        from chainguard.memory import MemoryDocument

        doc = MemoryDocument(
            id="learning:session123",
            content="Session: Implement login feature. Phase: implementation. Files changed: auth.py, login.ts",
            metadata={
                "type": "session",
                "scope": "Implement login feature",
                "phase": "implementation",
                "files_count": 2
            }
        )

        assert doc.id == "learning:session123"
        assert "login feature" in doc.content
        assert doc.metadata["type"] == "session"
        assert doc.metadata["files_count"] == 2

    def test_learning_document_to_dict(self):
        """Test converting learning document to dict."""
        from chainguard.memory import MemoryDocument

        doc = MemoryDocument(
            id="learning:abc",
            content="Session summary",
            metadata={"type": "session", "scope": "Test scope"}
        )

        d = doc.to_dict()
        assert d["id"] == "learning:abc"
        assert d["content"] == "Session summary"
        assert d["metadata"]["type"] == "session"


class TestProactiveHints:
    """Tests for proactive hints feature (v5.2)."""

    def test_relevance_scorer_for_learnings(self):
        """Test scoring learning documents."""
        from chainguard.memory import RelevanceScorer, MemoryDocument

        doc = MemoryDocument(
            id="learning:1",
            content="Session: Login feature implementation",
            metadata={
                "type": "session",
                "scope": "Implement login",
                "updated_at": "2025-01-08T10:00:00"
            }
        )

        result = RelevanceScorer.score(
            document=doc,
            semantic_distance=0.3,  # Similar task
            keywords=["login", "authentication"],
            task_type="feature",
            collection="learnings"
        )

        # Should have high score for similar login task
        assert result.semantic_score > 0.7
        assert result.final_score > 0.4

    def test_context_formatter_with_learnings(self):
        """Test formatting learnings in context."""
        from chainguard.memory import ContextFormatter, ScoredResult, MemoryDocument

        doc = MemoryDocument(
            id="learning:1",
            content="Session: User authentication. Phase: done. Files: auth.py",
            metadata={"type": "session", "scope": "User authentication"}
        )

        result = ScoredResult(
            document=doc,
            semantic_score=0.8,
            keyword_score=0.6,
            recency_score=0.9,
            final_score=0.75,
            collection="learnings"
        )

        formatted = ContextFormatter.format([result], "Login feature")

        # Should mention learnings or memory
        assert "Memory" in formatted or "learning" in formatted.lower()

    def test_keyword_extraction_for_scope(self):
        """Test keyword extraction from scope description."""
        from chainguard.embeddings import KeywordExtractor

        # Test German scope description
        scope = "Implementiere Benutzer-Authentifizierung"
        keywords = KeywordExtractor.extract(scope)

        assert "implementiere" in keywords or "benutzer" in keywords
        assert "authentifizierung" in keywords

    def test_keyword_expansion_for_hints(self):
        """Test keyword expansion for better hint matching."""
        from chainguard.embeddings import KeywordExtractor

        keywords = ["login", "user"]
        expanded = KeywordExtractor.expand(keywords)

        # Should include original keywords
        assert "login" in expanded
        assert "user" in expanded

        # Should include related terms
        assert len(expanded) > len(keywords)


class TestMemoryAutoUpdate:
    """Tests for memory auto-update integration."""

    def test_get_project_id_consistency(self):
        """Test that project ID is consistent for same path."""
        from chainguard.memory import get_project_id

        id1 = get_project_id("/path/to/project")
        id2 = get_project_id("/path/to/project")

        assert id1 == id2
        assert len(id1) == 16

    def test_should_index_file_comprehensive(self):
        """Test comprehensive file indexing rules."""
        from chainguard.memory import should_index_file

        # Should index
        assert should_index_file("src/main.py") is True
        assert should_index_file("app/Controller.php") is True
        assert should_index_file("components/Button.tsx") is True
        assert should_index_file("lib/utils.go") is True

        # Should NOT index
        assert should_index_file(".env") is False
        assert should_index_file(".env.local") is False
        assert should_index_file("secrets.json") is False
        assert should_index_file(".git/config") is False
        assert should_index_file("package-lock.json") is False
        assert should_index_file("yarn.lock") is False


# Integration tests (require chromadb)
@pytest.mark.skipif(
    True,  # Change to False to run integration tests locally
    reason="Requires chromadb package"
)
class TestProjectMemoryIntegration:
    """Integration tests that require chromadb."""

    @pytest.mark.asyncio
    async def test_create_and_query_memory(self):
        """Test creating memory and querying it."""
        from chainguard.memory import ProjectMemoryManager, get_project_id
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            project_id = get_project_id(tmpdir)
            manager = ProjectMemoryManager()

            memory = await manager.get_memory(project_id, tmpdir)

            # Add a document
            doc_id = await memory.add(
                content="Login authentication handler",
                collection="code_structure",
                metadata={"path": "auth/login.py"}
            )
            assert doc_id is not None

            # Query
            results = await memory.query("authentication", n_results=1)
            assert len(results) > 0

            # Cleanup
            await memory.close()


# =============================================================================
# Phase 3 Tests: Missing Methods for Export/Import (v5.3)
# =============================================================================

class TestProjectMemoryMethods:
    """Tests for ProjectMemory methods added for export/import support."""

    def test_get_all_method_exists(self):
        """Test that get_all method exists on ProjectMemory."""
        from chainguard.memory import ProjectMemory
        import inspect

        assert hasattr(ProjectMemory, 'get_all')
        sig = inspect.signature(ProjectMemory.get_all)
        params = list(sig.parameters.keys())
        assert 'collection' in params

    def test_get_method_exists(self):
        """Test that get method exists on ProjectMemory."""
        from chainguard.memory import ProjectMemory
        import inspect

        assert hasattr(ProjectMemory, 'get')
        sig = inspect.signature(ProjectMemory.get)
        params = list(sig.parameters.keys())
        assert 'doc_id' in params
        assert 'collection' in params

    def test_clear_collection_method_exists(self):
        """Test that clear_collection method exists on ProjectMemory."""
        from chainguard.memory import ProjectMemory
        import inspect

        assert hasattr(ProjectMemory, 'clear_collection')
        sig = inspect.signature(ProjectMemory.clear_collection)
        params = list(sig.parameters.keys())
        assert 'collection' in params

    def test_add_with_embedding_method_exists(self):
        """Test that add_with_embedding method exists on ProjectMemory."""
        from chainguard.memory import ProjectMemory
        import inspect

        assert hasattr(ProjectMemory, 'add_with_embedding')
        sig = inspect.signature(ProjectMemory.add_with_embedding)
        params = list(sig.parameters.keys())
        assert 'doc_id' in params
        assert 'content' in params
        assert 'collection' in params
        assert 'embedding' in params

    def test_all_export_import_methods_present(self):
        """Verify all methods required for export/import are present."""
        from chainguard.memory import ProjectMemory

        required_methods = ['get_all', 'get', 'clear_collection', 'add_with_embedding']
        for method_name in required_methods:
            assert hasattr(ProjectMemory, method_name), f"Missing method: {method_name}"


class TestArchitectureMemoryIntegration:
    """Tests for v5.4 Architecture-Memory Integration."""

    def test_collections_include_architecture(self):
        """Test that architecture collection is defined."""
        from chainguard.memory import COLLECTIONS

        assert "architecture" in COLLECTIONS

    def test_architecture_analysis_has_required_attributes(self):
        """Test that ArchitectureAnalysis has all required attributes for memory storage."""
        from chainguard.architecture import ArchitectureAnalysis, ArchitecturePattern

        analysis = ArchitectureAnalysis(
            pattern=ArchitecturePattern.MVC,
            confidence=0.85,
            detected_layers=["models", "views", "controllers"],
            detected_patterns=["Repository", "Service"]
        )

        # These are needed for memory storage
        assert hasattr(analysis, 'pattern')
        assert hasattr(analysis, 'confidence')
        assert hasattr(analysis, 'framework')
        assert hasattr(analysis, 'detected_layers')
        assert hasattr(analysis, 'detected_patterns')

        # Test that to_dict works (used in metadata)
        d = analysis.to_dict()
        assert "pattern" in d
        assert "confidence" in d
        assert "detected_layers" in d

    def test_memory_document_for_architecture(self):
        """Test creating MemoryDocument for architecture."""
        from chainguard.memory import MemoryDocument

        doc = MemoryDocument(
            id="arch:main",
            content="Project architecture: mvc. Framework: laravel. Detected layers: models, views, controllers.",
            metadata={
                "type": "architecture",
                "name": "project_architecture",
                "pattern": "mvc",
                "framework": "laravel",
                "confidence": 0.85,
                "layers": "models,views,controllers",
                "design_patterns": "Repository,Service",
            }
        )

        assert doc.id == "arch:main"
        assert "mvc" in doc.content
        assert doc.metadata["type"] == "architecture"
        assert doc.metadata["confidence"] == 0.85

    def test_architecture_detector_analyze_returns_correct_format(self):
        """Test that architecture_detector.analyze returns usable format."""
        from chainguard.architecture import architecture_detector, ArchitecturePattern
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            analysis = architecture_detector.analyze(tmpdir)

            # Must have these attributes for memory integration
            assert isinstance(analysis.pattern, ArchitecturePattern)
            assert isinstance(analysis.confidence, float)
            assert 0 <= analysis.confidence <= 1
            assert isinstance(analysis.detected_layers, list)
            assert isinstance(analysis.detected_patterns, list)

    def test_architecture_content_format_for_semantic_search(self):
        """Test that architecture content is formatted for semantic search."""
        from chainguard.architecture import ArchitectureAnalysis, ArchitecturePattern, FrameworkType

        analysis = ArchitectureAnalysis(
            pattern=ArchitecturePattern.MVC,
            confidence=0.9,
            framework=FrameworkType.LARAVEL,
            detected_layers=["Models", "Controllers", "Views"],
            detected_patterns=["Repository", "Service", "Factory"]
        )

        # This is the format used in handlers.py for memory storage
        arch_content = (
            f"Project architecture: {analysis.pattern.value}. "
            f"Framework: {analysis.framework.value if analysis.framework else 'unknown'}. "
            f"Detected layers: {', '.join(analysis.detected_layers[:5])}. "
            f"Design patterns: {', '.join(analysis.detected_patterns[:5])}."
        )

        # Content should be searchable
        assert "mvc" in arch_content.lower()
        assert "laravel" in arch_content.lower()
        assert "models" in arch_content.lower()
        assert "repository" in arch_content.lower()
