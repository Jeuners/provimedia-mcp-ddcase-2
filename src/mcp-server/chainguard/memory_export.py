"""
CHAINGUARD MCP Server - Memory Export/Import Module

Export and import project memory to/from portable formats.

Copyright (c) 2026 Provimedia GmbH
Licensed under the Polyform Noncommercial License 1.0.0
See LICENSE file in the project root for full license information.
"""

import json
import gzip
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, AsyncIterator
from pathlib import Path
from datetime import datetime
import asyncio

from .config import logger, CHAINGUARD_HOME


# =============================================================================
# Constants
# =============================================================================

EXPORT_FORMAT_VERSION = "1.0"
EXPORT_DIR = CHAINGUARD_HOME / "exports"
EXPORT_DIR.mkdir(exist_ok=True)

# Maximum documents per export file (to prevent huge files)
MAX_DOCS_PER_FILE = 10000


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class ExportMetadata:
    """Metadata for an export file."""
    format_version: str = EXPORT_FORMAT_VERSION
    project_id: str = ""
    project_path: str = ""
    export_date: str = ""
    collections: List[str] = field(default_factory=list)
    total_documents: int = 0
    chainguard_version: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "format_version": self.format_version,
            "project_id": self.project_id,
            "project_path": self.project_path,
            "export_date": self.export_date,
            "collections": self.collections,
            "total_documents": self.total_documents,
            "chainguard_version": self.chainguard_version,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExportMetadata":
        return cls(
            format_version=data.get("format_version", "1.0"),
            project_id=data.get("project_id", ""),
            project_path=data.get("project_path", ""),
            export_date=data.get("export_date", ""),
            collections=data.get("collections", []),
            total_documents=data.get("total_documents", 0),
            chainguard_version=data.get("chainguard_version", ""),
        )


@dataclass
class ExportDocument:
    """A single document for export."""
    id: str
    content: str
    collection: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[List[float]] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "content": self.content,
            "collection": self.collection,
            "metadata": self.metadata,
        }
        if self.embedding is not None:
            result["embedding"] = self.embedding
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExportDocument":
        return cls(
            id=data.get("id", ""),
            content=data.get("content", ""),
            collection=data.get("collection", ""),
            metadata=data.get("metadata", {}),
            embedding=data.get("embedding"),
        )


@dataclass
class ExportResult:
    """Result of an export operation."""
    success: bool
    file_path: str = ""
    documents_exported: int = 0
    collections_exported: List[str] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "file_path": self.file_path,
            "documents_exported": self.documents_exported,
            "collections_exported": self.collections_exported,
            "error": self.error,
        }


@dataclass
class ImportResult:
    """Result of an import operation."""
    success: bool
    documents_imported: int = 0
    documents_skipped: int = 0
    collections_imported: List[str] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "documents_imported": self.documents_imported,
            "documents_skipped": self.documents_skipped,
            "collections_imported": self.collections_imported,
            "error": self.error,
        }


# =============================================================================
# Memory Exporter
# =============================================================================

class MemoryExporter:
    """
    Export project memory to portable formats.
    """

    def __init__(self):
        from .config import VERSION
        self.version = VERSION

    async def export_json(
        self,
        memory,  # ProjectMemory instance
        output_path: Optional[str] = None,
        collections: Optional[List[str]] = None,
        include_embeddings: bool = False,
        compress: bool = False,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> ExportResult:
        """
        Export memory to JSON format.

        Args:
            memory: ProjectMemory instance to export
            output_path: Optional output file path (defaults to exports dir)
            collections: Optional list of collections to export (defaults to all)
            include_embeddings: Whether to include vector embeddings
            compress: Whether to gzip the output
            progress_callback: Optional callback(current, total) for progress

        Returns:
            ExportResult with status and file path
        """
        try:
            # Determine collections to export
            if collections is None:
                from .memory import COLLECTIONS
                collections = COLLECTIONS

            # Generate output path
            if output_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"memory_export_{memory.project_id[:8]}_{timestamp}.json"
                if compress:
                    filename += ".gz"
                output_path = str(EXPORT_DIR / filename)

            # Collect all documents
            documents: List[ExportDocument] = []
            total_docs = 0

            for collection in collections:
                try:
                    # Get all documents from collection
                    docs = await memory.get_all(collection)
                    for doc, embedding in docs:
                        export_doc = ExportDocument(
                            id=doc.id,
                            content=doc.content,
                            collection=collection,
                            metadata=doc.metadata,
                            embedding=embedding if include_embeddings else None,
                        )
                        documents.append(export_doc)
                        total_docs += 1

                        if progress_callback:
                            progress_callback(total_docs, -1)

                        if total_docs >= MAX_DOCS_PER_FILE:
                            logger.warning(f"Export limit reached: {MAX_DOCS_PER_FILE}")
                            break

                except Exception as e:
                    logger.warning(f"Failed to export collection {collection}: {e}")

                if total_docs >= MAX_DOCS_PER_FILE:
                    break

            # Build export data
            metadata = ExportMetadata(
                project_id=memory.project_id,
                project_path=str(memory.project_path) if hasattr(memory, 'project_path') else "",
                export_date=datetime.now().isoformat(),
                collections=collections,
                total_documents=len(documents),
                chainguard_version=self.version,
            )

            export_data = {
                "metadata": metadata.to_dict(),
                "documents": [d.to_dict() for d in documents],
            }

            # Write to file
            json_str = json.dumps(export_data, indent=2, ensure_ascii=False)

            if compress:
                with gzip.open(output_path, 'wt', encoding='utf-8') as f:
                    f.write(json_str)
            else:
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(json_str)

            return ExportResult(
                success=True,
                file_path=output_path,
                documents_exported=len(documents),
                collections_exported=collections,
            )

        except Exception as e:
            logger.error(f"Export failed: {e}")
            return ExportResult(
                success=False,
                error=str(e),
            )

    async def export_jsonl(
        self,
        memory,  # ProjectMemory instance
        output_path: Optional[str] = None,
        collections: Optional[List[str]] = None,
        include_embeddings: bool = False,
        compress: bool = False,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> ExportResult:
        """
        Export memory to JSONL (line-delimited JSON) format.
        Better for large datasets and streaming imports.

        Args:
            memory: ProjectMemory instance to export
            output_path: Optional output file path
            collections: Optional list of collections to export
            include_embeddings: Whether to include vector embeddings
            compress: Whether to gzip the output
            progress_callback: Optional callback(current, total) for progress

        Returns:
            ExportResult with status and file path
        """
        try:
            # Determine collections to export
            if collections is None:
                from .memory import COLLECTIONS
                collections = COLLECTIONS

            # Generate output path
            if output_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"memory_export_{memory.project_id[:8]}_{timestamp}.jsonl"
                if compress:
                    filename += ".gz"
                output_path = str(EXPORT_DIR / filename)

            # Build metadata
            metadata = ExportMetadata(
                project_id=memory.project_id,
                project_path=str(memory.project_path) if hasattr(memory, 'project_path') else "",
                export_date=datetime.now().isoformat(),
                collections=collections,
                total_documents=0,  # Will be updated
                chainguard_version=self.version,
            )

            total_docs = 0
            exported_collections: List[str] = []

            # Open file and write
            if compress:
                f = gzip.open(output_path, 'wt', encoding='utf-8')
            else:
                f = open(output_path, 'w', encoding='utf-8')

            try:
                # Write metadata as first line
                f.write(json.dumps({"_metadata": metadata.to_dict()}) + "\n")

                for collection in collections:
                    try:
                        docs = await memory.get_all(collection)
                        collection_docs = 0

                        for doc, embedding in docs:
                            export_doc = ExportDocument(
                                id=doc.id,
                                content=doc.content,
                                collection=collection,
                                metadata=doc.metadata,
                                embedding=embedding if include_embeddings else None,
                            )
                            f.write(json.dumps(export_doc.to_dict(), ensure_ascii=False) + "\n")

                            total_docs += 1
                            collection_docs += 1

                            if progress_callback:
                                progress_callback(total_docs, -1)

                            if total_docs >= MAX_DOCS_PER_FILE:
                                break

                        if collection_docs > 0:
                            exported_collections.append(collection)

                    except Exception as e:
                        logger.warning(f"Failed to export collection {collection}: {e}")

                    if total_docs >= MAX_DOCS_PER_FILE:
                        break

            finally:
                f.close()

            return ExportResult(
                success=True,
                file_path=output_path,
                documents_exported=total_docs,
                collections_exported=exported_collections,
            )

        except Exception as e:
            logger.error(f"JSONL export failed: {e}")
            return ExportResult(
                success=False,
                error=str(e),
            )


# =============================================================================
# Memory Importer
# =============================================================================

class MemoryImporter:
    """
    Import project memory from exported files.
    """

    async def import_json(
        self,
        memory,  # ProjectMemory instance
        input_path: str,
        merge: bool = True,
        skip_existing: bool = True,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> ImportResult:
        """
        Import memory from JSON format.

        Args:
            memory: ProjectMemory instance to import into
            input_path: Path to import file
            merge: If True, merge with existing data. If False, clear first.
            skip_existing: If True, skip documents that already exist
            progress_callback: Optional callback(current, total) for progress

        Returns:
            ImportResult with status and counts
        """
        try:
            # Read file
            path = Path(input_path)
            if path.suffix == '.gz':
                with gzip.open(path, 'rt', encoding='utf-8') as f:
                    data = json.load(f)
            else:
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

            # Validate format
            if "metadata" not in data or "documents" not in data:
                return ImportResult(
                    success=False,
                    error="Invalid export format: missing metadata or documents",
                )

            metadata = ExportMetadata.from_dict(data["metadata"])
            documents = [ExportDocument.from_dict(d) for d in data["documents"]]
            total = len(documents)

            # Clear existing if not merging
            if not merge:
                for collection in metadata.collections:
                    try:
                        await memory.clear_collection(collection)
                    except Exception:
                        pass

            # Import documents
            imported = 0
            skipped = 0
            imported_collections: set = set()

            for i, doc in enumerate(documents):
                try:
                    # Check if exists
                    if skip_existing:
                        existing = await memory.get(doc.id, doc.collection)
                        if existing:
                            skipped += 1
                            continue

                    # Import with or without embedding
                    if doc.embedding is not None:
                        await memory.add_with_embedding(
                            doc_id=doc.id,
                            content=doc.content,
                            collection=doc.collection,
                            metadata=doc.metadata,
                            embedding=doc.embedding,
                        )
                    else:
                        await memory.add(
                            content=doc.content,
                            collection=doc.collection,
                            metadata=doc.metadata,
                            doc_id=doc.id,
                        )

                    imported += 1
                    imported_collections.add(doc.collection)

                    if progress_callback:
                        progress_callback(i + 1, total)

                except Exception as e:
                    logger.warning(f"Failed to import document {doc.id}: {e}")
                    skipped += 1

            return ImportResult(
                success=True,
                documents_imported=imported,
                documents_skipped=skipped,
                collections_imported=list(imported_collections),
            )

        except Exception as e:
            logger.error(f"Import failed: {e}")
            return ImportResult(
                success=False,
                error=str(e),
            )

    async def import_jsonl(
        self,
        memory,  # ProjectMemory instance
        input_path: str,
        merge: bool = True,
        skip_existing: bool = True,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> ImportResult:
        """
        Import memory from JSONL format.

        Args:
            memory: ProjectMemory instance to import into
            input_path: Path to import file
            merge: If True, merge with existing data. If False, clear first.
            skip_existing: If True, skip documents that already exist
            progress_callback: Optional callback(current, total) for progress

        Returns:
            ImportResult with status and counts
        """
        try:
            path = Path(input_path)
            if path.suffix == '.gz':
                f = gzip.open(path, 'rt', encoding='utf-8')
            else:
                f = open(path, 'r', encoding='utf-8')

            try:
                imported = 0
                skipped = 0
                imported_collections: set = set()
                metadata: Optional[ExportMetadata] = None

                for line_num, line in enumerate(f):
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        data = json.loads(line)

                        # First line is metadata
                        if "_metadata" in data:
                            metadata = ExportMetadata.from_dict(data["_metadata"])

                            # Clear existing if not merging
                            if not merge and metadata:
                                for collection in metadata.collections:
                                    try:
                                        await memory.clear_collection(collection)
                                    except Exception:
                                        pass
                            continue

                        # Parse document
                        doc = ExportDocument.from_dict(data)

                        # Check if exists
                        if skip_existing:
                            existing = await memory.get(doc.id, doc.collection)
                            if existing:
                                skipped += 1
                                continue

                        # Import
                        if doc.embedding is not None:
                            await memory.add_with_embedding(
                                doc_id=doc.id,
                                content=doc.content,
                                collection=doc.collection,
                                metadata=doc.metadata,
                                embedding=doc.embedding,
                            )
                        else:
                            await memory.add(
                                content=doc.content,
                                collection=doc.collection,
                                metadata=doc.metadata,
                                doc_id=doc.id,
                            )

                        imported += 1
                        imported_collections.add(doc.collection)

                        if progress_callback:
                            progress_callback(imported + skipped, -1)

                    except json.JSONDecodeError as e:
                        logger.warning(f"Invalid JSON on line {line_num}: {e}")
                        skipped += 1

            finally:
                f.close()

            return ImportResult(
                success=True,
                documents_imported=imported,
                documents_skipped=skipped,
                collections_imported=list(imported_collections),
            )

        except Exception as e:
            logger.error(f"JSONL import failed: {e}")
            return ImportResult(
                success=False,
                error=str(e),
            )


# =============================================================================
# Utility Functions
# =============================================================================

def list_exports(project_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    List available export files.

    Args:
        project_id: Optional filter by project ID

    Returns:
        List of export file info dicts
    """
    exports: List[Dict[str, Any]] = []

    for path in EXPORT_DIR.glob("memory_export_*"):
        try:
            stat = path.stat()
            info = {
                "filename": path.name,
                "path": str(path),
                "size_bytes": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            }

            # Try to extract project_id from filename
            parts = path.stem.split("_")
            if len(parts) >= 3:
                info["project_id_prefix"] = parts[2]

                if project_id and not project_id.startswith(parts[2]):
                    continue

            exports.append(info)

        except Exception as e:
            logger.debug(f"Failed to read export info for {path}: {e}")

    return sorted(exports, key=lambda x: x.get("modified", ""), reverse=True)


# =============================================================================
# Global Instances
# =============================================================================

memory_exporter = MemoryExporter()
memory_importer = MemoryImporter()
