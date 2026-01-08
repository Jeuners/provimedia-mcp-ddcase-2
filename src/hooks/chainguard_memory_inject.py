#!/usr/bin/env python3
"""
CHAINGUARD Memory Injection Hook

UserPromptSubmit Hook - injects Memory context BEFORE the LLM call.
Injects relevant project context from Long-Term Memory.

Copyright (c) 2026 Provimedia GmbH
Licensed under the Polyform Noncommercial License 1.0.0
See LICENSE file in the project root for full license information.
"""

import sys
import json
import hashlib
import time
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple

# CHAINGUARD Home
CHAINGUARD_HOME = Path.home() / ".chainguard"
MEMORY_HOME = CHAINGUARD_HOME / "memory"

# Performance settings
HOOK_TIMEOUT = 3.0  # Max seconds for hook execution
CACHE_TTL = 300     # Cache results for 5 minutes
MAX_RESULTS = 5     # Max memory results to inject
MIN_RELEVANCE = 0.5 # Minimum relevance score

# Simple file-based cache
CACHE_FILE = CHAINGUARD_HOME / "memory_inject_cache.json"


def get_project_id(working_dir: str) -> str:
    """
    Berechnet die Project ID (identisch mit MCP Server).
    """
    import subprocess

    # 1. Try git remote
    try:
        result = subprocess.run(
            ["git", "-C", working_dir, "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=2
        )
        if result.returncode == 0 and result.stdout.strip():
            return hashlib.sha256(result.stdout.strip().encode()).hexdigest()[:16]
    except Exception:
        pass

    # 2. Try git root
    try:
        result = subprocess.run(
            ["git", "-C", working_dir, "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=2
        )
        if result.returncode == 0 and result.stdout.strip():
            return hashlib.sha256(result.stdout.strip().encode()).hexdigest()[:16]
    except Exception:
        pass

    # 3. Fallback: path hash
    resolved = str(Path(working_dir).resolve())
    return hashlib.sha256(resolved.encode()).hexdigest()[:16]


def memory_exists(project_id: str) -> bool:
    """Prüft ob Memory für dieses Projekt existiert."""
    memory_path = MEMORY_HOME / project_id
    return memory_path.exists() and (memory_path / "chroma.sqlite3").exists()


def load_cache() -> Dict[str, Any]:
    """Lädt den Cache."""
    if not CACHE_FILE.exists():
        return {}
    try:
        with open(CACHE_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def save_cache(cache: Dict[str, Any]):
    """Speichert den Cache."""
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE_FILE, 'w') as f:
            json.dump(cache, f)
    except Exception:
        pass


def get_cached_context(cache_key: str) -> Optional[str]:
    """Holt gecachten Kontext wenn noch gültig."""
    cache = load_cache()
    entry = cache.get(cache_key)
    if entry:
        cached_at = entry.get("timestamp", 0)
        if time.time() - cached_at < CACHE_TTL:
            return entry.get("context")
    return None


def set_cached_context(cache_key: str, context: str):
    """Speichert Kontext im Cache."""
    cache = load_cache()
    # Limit cache size
    if len(cache) > 100:
        # Remove oldest entries
        sorted_entries = sorted(cache.items(), key=lambda x: x[1].get("timestamp", 0))
        cache = dict(sorted_entries[-50:])

    cache[cache_key] = {
        "context": context,
        "timestamp": time.time()
    }
    save_cache(cache)


def extract_keywords(text: str) -> List[str]:
    """Extrahiert Keywords aus dem Prompt (lightweight Version)."""
    import re

    # Normalize
    text = text.lower()
    text = re.sub(r'[^a-zäöüß0-9\s]', ' ', text)

    # Stop words (minimal set for speed)
    stop_words = {
        'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'of', 'and', 'or',
        'is', 'are', 'was', 'were', 'be', 'been', 'this', 'that', 'it',
        'with', 'from', 'by', 'den', 'die', 'das', 'der', 'ein', 'eine',
        'und', 'oder', 'für', 'mit', 'ich', 'du', 'bitte', 'kannst', 'can',
        'you', 'please', 'help', 'me', 'want', 'need', 'would', 'like'
    }

    words = text.split()
    keywords = [w for w in words if w not in stop_words and len(w) > 2]

    return list(set(keywords))[:10]  # Max 10 keywords


def query_memory_sync(project_id: str, query_text: str) -> List[Dict[str, Any]]:
    """
    Synchrone Memory-Abfrage (für Hook-Kontext).

    Returns: List of {content, metadata, distance}
    """
    try:
        import chromadb
        from chromadb.config import Settings

        memory_path = MEMORY_HOME / project_id

        client = chromadb.PersistentClient(
            path=str(memory_path),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=False,
                is_persistent=True
            )
        )

        # Query all collections
        collections = ["code_structure", "functions", "learnings", "architecture"]
        results = []

        for coll_name in collections:
            try:
                coll = client.get_collection(coll_name)
                if coll.count() == 0:
                    continue

                hits = coll.query(
                    query_texts=[query_text],
                    n_results=3,
                    include=["documents", "metadatas", "distances"]
                )

                if hits and hits.get("ids") and hits["ids"][0]:
                    for i, doc_id in enumerate(hits["ids"][0]):
                        results.append({
                            "id": doc_id,
                            "content": hits["documents"][0][i] if hits.get("documents") else "",
                            "metadata": hits["metadatas"][0][i] if hits.get("metadatas") else {},
                            "distance": hits["distances"][0][i] if hits.get("distances") else 1.0,
                            "collection": coll_name
                        })
            except Exception:
                continue

        # Sort by distance (lower is better)
        results.sort(key=lambda x: x["distance"])
        return results[:MAX_RESULTS]

    except ImportError:
        return []
    except Exception:
        return []


def format_context(results: List[Dict[str, Any]], prompt_preview: str) -> str:
    """Formatiert die Memory-Ergebnisse als Kontext."""
    if not results:
        return ""

    # Filter by relevance (distance < threshold means relevant)
    # ChromaDB cosine distance: 0 = identical, 2 = opposite
    relevant = [r for r in results if r["distance"] < 1.0]

    if not relevant:
        return ""

    lines = [
        "",
        "📚 **CHAINGUARD Memory Context** (auto-injected):",
        ""
    ]

    # Group by collection
    by_collection: Dict[str, List] = {}
    for r in relevant:
        coll = r.get("collection", "other")
        if coll not in by_collection:
            by_collection[coll] = []
        by_collection[coll].append(r)

    icons = {
        "code_structure": "📁",
        "functions": "⚡",
        "learnings": "💡",
        "architecture": "🏗️",
        "database_schema": "📊"
    }

    for coll, items in by_collection.items():
        icon = icons.get(coll, "📄")
        lines.append(f"{icon} **{coll.replace('_', ' ').title()}:**")

        for item in items[:2]:
            path = item["metadata"].get("path", item["metadata"].get("name", ""))
            if path:
                lines.append(f"  • {path}")

            # Add brief summary
            content = item["content"]
            if len(content) > 100:
                content = content[:100] + "..."
            if content and not path:
                lines.append(f"  • {content}")

        lines.append("")

    return "\n".join(lines)


def main():
    """Hauptfunktion - Memory Injection Hook."""
    start_time = time.time()

    # Hook-Input von stdin lesen
    hook_input = {}
    if not sys.stdin.isatty():
        try:
            raw_input = sys.stdin.read()
            if raw_input.strip():
                hook_input = json.loads(raw_input)
        except json.JSONDecodeError:
            pass

    # Extrahiere relevante Daten
    prompt = hook_input.get("prompt", "")
    cwd = hook_input.get("cwd", str(Path.cwd()))

    # Kurze Prompts ignorieren (z.B. "yes", "ok", etc.)
    if len(prompt) < 20:
        sys.exit(0)

    # Projekt ID berechnen
    try:
        project_id = get_project_id(cwd)
    except Exception:
        sys.exit(0)

    # Memory existiert?
    if not memory_exists(project_id):
        sys.exit(0)

    # Cache prüfen
    cache_key = f"{project_id}:{prompt[:50]}"
    cached = get_cached_context(cache_key)
    if cached:
        print(cached)
        sys.exit(0)

    # Keywords extrahieren
    keywords = extract_keywords(prompt)
    if not keywords:
        sys.exit(0)

    query_text = " ".join(keywords)

    # Timeout check
    elapsed = time.time() - start_time
    if elapsed > HOOK_TIMEOUT:
        sys.exit(0)

    # Memory abfragen
    try:
        results = query_memory_sync(project_id, query_text)
    except Exception:
        sys.exit(0)

    # Timeout check
    elapsed = time.time() - start_time
    if elapsed > HOOK_TIMEOUT:
        sys.exit(0)

    # Kontext formatieren
    context = format_context(results, prompt[:50])

    if context:
        # Cache speichern
        set_cached_context(cache_key, context)

        # Kontext ausgeben (wird zu Claude's Kontext hinzugefügt)
        print(context)

    sys.exit(0)


if __name__ == "__main__":
    main()
