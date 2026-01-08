"""
Tests for chainguard.memory_export module.

Tests memory export and import functionality.
"""

import pytest
import tempfile
import json
from pathlib import Path


class TestExportMetadata:
    """Tests for ExportMetadata dataclass."""

    def test_import(self):
        """Test that ExportMetadata can be imported."""
        from chainguard.memory_export import ExportMetadata
        assert ExportMetadata is not None

    def test_create_metadata(self):
        """Test creating ExportMetadata."""
        from chainguard.memory_export import ExportMetadata

        metadata = ExportMetadata(
            project_id="abc123def456gh",
            project_path="/path/to/project",
            export_date="2025-01-08T10:00:00",
            collections=["code_structure", "functions"],
            total_documents=100,
            chainguard_version="5.3.0"
        )

        assert metadata.project_id == "abc123def456gh"
        assert metadata.total_documents == 100
        assert "code_structure" in metadata.collections

    def test_to_dict(self):
        """Test ExportMetadata.to_dict()."""
        from chainguard.memory_export import ExportMetadata

        metadata = ExportMetadata(
            project_id="test123",
            export_date="2025-01-08",
            collections=["test"],
            total_documents=10,
        )

        d = metadata.to_dict()
        assert d["project_id"] == "test123"
        assert d["total_documents"] == 10
        assert d["format_version"] == "1.0"

    def test_from_dict(self):
        """Test ExportMetadata.from_dict()."""
        from chainguard.memory_export import ExportMetadata

        data = {
            "project_id": "abc123",
            "project_path": "/test",
            "export_date": "2025-01-08",
            "collections": ["a", "b"],
            "total_documents": 50,
            "format_version": "1.0"
        }

        metadata = ExportMetadata.from_dict(data)
        assert metadata.project_id == "abc123"
        assert metadata.total_documents == 50


class TestExportDocument:
    """Tests for ExportDocument dataclass."""

    def test_import(self):
        """Test that ExportDocument can be imported."""
        from chainguard.memory_export import ExportDocument
        assert ExportDocument is not None

    def test_create_document(self):
        """Test creating an ExportDocument."""
        from chainguard.memory_export import ExportDocument

        doc = ExportDocument(
            id="doc123",
            content="Test content here",
            collection="code_structure",
            metadata={"path": "src/main.py", "type": "file"},
        )

        assert doc.id == "doc123"
        assert doc.content == "Test content here"
        assert doc.collection == "code_structure"
        assert doc.metadata["type"] == "file"

    def test_document_with_embedding(self):
        """Test ExportDocument with embedding."""
        from chainguard.memory_export import ExportDocument

        doc = ExportDocument(
            id="doc456",
            content="Test",
            collection="functions",
            embedding=[0.1, 0.2, 0.3, 0.4]
        )

        assert doc.embedding is not None
        assert len(doc.embedding) == 4

    def test_to_dict(self):
        """Test ExportDocument.to_dict()."""
        from chainguard.memory_export import ExportDocument

        doc = ExportDocument(
            id="test",
            content="content",
            collection="test_collection",
            metadata={"key": "value"}
        )

        d = doc.to_dict()
        assert d["id"] == "test"
        assert d["content"] == "content"
        assert d["collection"] == "test_collection"
        assert "embedding" not in d  # No embedding

    def test_to_dict_with_embedding(self):
        """Test ExportDocument.to_dict() with embedding."""
        from chainguard.memory_export import ExportDocument

        doc = ExportDocument(
            id="test",
            content="content",
            collection="test",
            embedding=[0.5, 0.5]
        )

        d = doc.to_dict()
        assert "embedding" in d
        assert d["embedding"] == [0.5, 0.5]

    def test_from_dict(self):
        """Test ExportDocument.from_dict()."""
        from chainguard.memory_export import ExportDocument

        data = {
            "id": "doc1",
            "content": "Hello",
            "collection": "col1",
            "metadata": {"x": 1}
        }

        doc = ExportDocument.from_dict(data)
        assert doc.id == "doc1"
        assert doc.content == "Hello"
        assert doc.metadata["x"] == 1


class TestExportResult:
    """Tests for ExportResult dataclass."""

    def test_import(self):
        """Test that ExportResult can be imported."""
        from chainguard.memory_export import ExportResult
        assert ExportResult is not None

    def test_success_result(self):
        """Test creating a successful ExportResult."""
        from chainguard.memory_export import ExportResult

        result = ExportResult(
            success=True,
            file_path="/exports/test.json",
            documents_exported=50,
            collections_exported=["code_structure", "functions"]
        )

        assert result.success is True
        assert result.documents_exported == 50
        assert result.error is None

    def test_failure_result(self):
        """Test creating a failed ExportResult."""
        from chainguard.memory_export import ExportResult

        result = ExportResult(
            success=False,
            error="Permission denied"
        )

        assert result.success is False
        assert "Permission" in result.error

    def test_to_dict(self):
        """Test ExportResult.to_dict()."""
        from chainguard.memory_export import ExportResult

        result = ExportResult(
            success=True,
            file_path="/test.json",
            documents_exported=10,
            collections_exported=["test"]
        )

        d = result.to_dict()
        assert d["success"] is True
        assert d["documents_exported"] == 10


class TestImportResult:
    """Tests for ImportResult dataclass."""

    def test_import(self):
        """Test that ImportResult can be imported."""
        from chainguard.memory_export import ImportResult
        assert ImportResult is not None

    def test_success_result(self):
        """Test creating a successful ImportResult."""
        from chainguard.memory_export import ImportResult

        result = ImportResult(
            success=True,
            documents_imported=100,
            documents_skipped=5,
            collections_imported=["code_structure"]
        )

        assert result.success is True
        assert result.documents_imported == 100
        assert result.documents_skipped == 5

    def test_to_dict(self):
        """Test ImportResult.to_dict()."""
        from chainguard.memory_export import ImportResult

        result = ImportResult(
            success=True,
            documents_imported=50,
            documents_skipped=2,
            collections_imported=["a", "b"]
        )

        d = result.to_dict()
        assert d["documents_imported"] == 50
        assert d["documents_skipped"] == 2


class TestExportDir:
    """Tests for EXPORT_DIR constant."""

    def test_export_dir_exists(self):
        """Test that EXPORT_DIR is defined."""
        from chainguard.memory_export import EXPORT_DIR

        assert EXPORT_DIR is not None
        assert isinstance(EXPORT_DIR, Path)

    def test_export_dir_in_chainguard(self):
        """Test that EXPORT_DIR is under CHAINGUARD_HOME."""
        from chainguard.memory_export import EXPORT_DIR
        from chainguard.config import CHAINGUARD_HOME

        assert EXPORT_DIR.parent == CHAINGUARD_HOME
        assert EXPORT_DIR.name == "exports"


class TestMemoryExporter:
    """Tests for MemoryExporter class."""

    def test_import(self):
        """Test that MemoryExporter can be imported."""
        from chainguard.memory_export import MemoryExporter
        assert MemoryExporter is not None

    def test_create_exporter(self):
        """Test creating a MemoryExporter."""
        from chainguard.memory_export import MemoryExporter

        exporter = MemoryExporter()
        assert exporter is not None
        assert hasattr(exporter, "version")

    def test_global_exporter_exists(self):
        """Test that global memory_exporter instance exists."""
        from chainguard.memory_export import memory_exporter

        assert memory_exporter is not None


class TestMemoryImporter:
    """Tests for MemoryImporter class."""

    def test_import(self):
        """Test that MemoryImporter can be imported."""
        from chainguard.memory_export import MemoryImporter
        assert MemoryImporter is not None

    def test_create_importer(self):
        """Test creating a MemoryImporter."""
        from chainguard.memory_export import MemoryImporter

        importer = MemoryImporter()
        assert importer is not None

    def test_global_importer_exists(self):
        """Test that global memory_importer instance exists."""
        from chainguard.memory_export import memory_importer

        assert memory_importer is not None


class TestListExports:
    """Tests for list_exports function."""

    def test_import(self):
        """Test that list_exports can be imported."""
        from chainguard.memory_export import list_exports
        assert list_exports is not None

    def test_list_returns_list(self):
        """Test that list_exports returns a list."""
        from chainguard.memory_export import list_exports

        result = list_exports()
        assert isinstance(result, list)

    def test_list_with_project_filter(self):
        """Test list_exports with project filter."""
        from chainguard.memory_export import list_exports

        # Should not raise even with filter
        result = list_exports("abc12345")
        assert isinstance(result, list)


class TestExportFormatVersion:
    """Tests for EXPORT_FORMAT_VERSION constant."""

    def test_format_version_exists(self):
        """Test that EXPORT_FORMAT_VERSION is defined."""
        from chainguard.memory_export import EXPORT_FORMAT_VERSION

        assert EXPORT_FORMAT_VERSION is not None
        assert EXPORT_FORMAT_VERSION == "1.0"


class TestMaxDocsPerFile:
    """Tests for MAX_DOCS_PER_FILE constant."""

    def test_constant_exists(self):
        """Test that MAX_DOCS_PER_FILE is defined."""
        from chainguard.memory_export import MAX_DOCS_PER_FILE

        assert MAX_DOCS_PER_FILE is not None
        assert MAX_DOCS_PER_FILE == 10000


class TestJsonExportFormat:
    """Tests for JSON export format structure."""

    def test_create_valid_export_structure(self):
        """Test creating a valid export structure."""
        from chainguard.memory_export import ExportMetadata, ExportDocument

        metadata = ExportMetadata(
            project_id="test123",
            export_date="2025-01-08",
            collections=["test"],
            total_documents=1
        )

        doc = ExportDocument(
            id="doc1",
            content="Test content",
            collection="test",
            metadata={}
        )

        export_data = {
            "metadata": metadata.to_dict(),
            "documents": [doc.to_dict()]
        }

        # Should be valid JSON
        json_str = json.dumps(export_data)
        parsed = json.loads(json_str)

        assert "metadata" in parsed
        assert "documents" in parsed
        assert len(parsed["documents"]) == 1


class TestJsonlExportFormat:
    """Tests for JSONL export format structure."""

    def test_create_valid_jsonl_lines(self):
        """Test creating valid JSONL lines."""
        from chainguard.memory_export import ExportMetadata, ExportDocument

        metadata = ExportMetadata(
            project_id="test",
            export_date="2025-01-08",
            collections=["col1"],
            total_documents=2
        )

        doc1 = ExportDocument(id="1", content="a", collection="col1")
        doc2 = ExportDocument(id="2", content="b", collection="col1")

        lines = []
        lines.append(json.dumps({"_metadata": metadata.to_dict()}))
        lines.append(json.dumps(doc1.to_dict()))
        lines.append(json.dumps(doc2.to_dict()))

        # Each line should be valid JSON
        for line in lines:
            parsed = json.loads(line)
            assert isinstance(parsed, dict)
