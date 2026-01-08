# CHAINGUARD Long-Term Memory System - Konzept v1.0

> **Datum:** 2026-01-08
> **Status:** Phase 1-4 COMPLETE (v5.4.0), Phase 5 geplant
> **Ziel:** Persistentes Projekt-Wissen ohne externe API-Anbindung

---

## Executive Summary

Das Long-Term Memory (LTM) System erweitert Chainguard um die Fähigkeit, Projekt-Wissen dauerhaft zu speichern und semantisch abzufragen. Es nutzt **lokale Vektor-Datenbanken** und **offline-fähige Embedding-Modelle**, um ohne API-Calls zu funktionieren.

**Kernvorteile:**
- Kein API-Key erforderlich (100% offline)
- Einmalige Indexierung, dauerhaftes Wissen
- Semantische Suche ("Wo werden Benutzer authentifiziert?")
- Automatische Updates bei Projektänderungen
- ~50MB zusätzlicher Speicher pro Projekt
- **Strikte Projekt-Isolation** - kein Datenvermischen zwischen Projekten

---

## 1. Projekt-Isolation (KRITISCH!)

### 1.1 Übersicht

> **WICHTIG:** Jedes Projekt hat sein eigenes, komplett isoliertes Memory.
> Es gibt **keine Vermischung** zwischen Projekten - auch nicht bei gleichzeitigen Sessions.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    PROJEKT-ISOLATION ARCHITEKTUR                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  Rechner mit 3 Projekten:                                               │
│                                                                          │
│  ~/.chainguard/memory/                                                   │
│  ├── a1b2c3d4e5f6g7h8/     ← Projekt A (E-Commerce)                     │
│  │   ├── chroma.sqlite3    ← Eigene Vektor-DB                           │
│  │   ├── collections/      ← Eigene Collections                         │
│  │   └── metadata.json     ← Projekt-Infos                              │
│  │                                                                       │
│  ├── x9y8z7w6v5u4t3s2/     ← Projekt B (Blog)                           │
│  │   ├── chroma.sqlite3    ← Komplett separate DB!                      │
│  │   ├── collections/                                                    │
│  │   └── metadata.json                                                   │
│  │                                                                       │
│  └── m1n2o3p4q5r6s7t8/     ← Projekt C (API)                            │
│      ├── chroma.sqlite3    ← Wieder eigene DB!                          │
│      ├── collections/                                                    │
│      └── metadata.json                                                   │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │  WICHTIG: Jede ChromaDB-Instanz ist ein eigener SQLite-File!    │    │
│  │  → Physische Trennung auf Dateisystem-Ebene                     │    │
│  │  → Kein gemeinsamer State, keine Vermischung möglich            │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Project-ID Berechnung

Die `project_id` wird **identisch** zum bestehenden Chainguard-System berechnet:

```python
import hashlib
import subprocess

def get_project_id(working_dir: str) -> str:
    """
    Berechnet eine eindeutige, stabile Project-ID.

    Priorität:
    1. Git Remote URL (wenn vorhanden) → Gleiche ID auf verschiedenen Rechnern
    2. Git Root Path (wenn Git-Repo)   → Stabil auch bei Unterverzeichnissen
    3. Working Directory Path          → Fallback

    Returns:
        16-Zeichen Hex-Hash (z.B. "a1b2c3d4e5f6g7h8")
    """

    # 1. Versuche Git Remote URL
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=working_dir,
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            source = result.stdout.strip()
            return hashlib.sha256(source.encode()).hexdigest()[:16]
    except:
        pass

    # 2. Versuche Git Root Path
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=working_dir,
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            source = result.stdout.strip()
            return hashlib.sha256(source.encode()).hexdigest()[:16]
    except:
        pass

    # 3. Fallback: Working Directory
    source = str(Path(working_dir).resolve())
    return hashlib.sha256(source.encode()).hexdigest()[:16]
```

**Beispiele:**

| Projekt | Source für Hash | Project-ID |
|---------|-----------------|------------|
| `/Users/dev/ecommerce` (mit git remote) | `git@github.com:user/ecommerce.git` | `a1b2c3d4e5f6g7h8` |
| `/Users/dev/blog` (lokales git) | `/Users/dev/blog` | `x9y8z7w6v5u4t3s2` |
| `/var/www/api` (kein git) | `/var/www/api` | `m1n2o3p4q5r6s7t8` |

### 1.3 Gleichzeitige Sessions (Concurrency)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    GLEICHZEITIGE SESSIONS                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  Terminal 1                    Terminal 2                                │
│  ──────────────────           ──────────────────                        │
│  cd ~/ecommerce               cd ~/blog                                  │
│  claude                       claude                                     │
│       │                            │                                     │
│       ▼                            ▼                                     │
│  project_id: a1b2c3d4         project_id: x9y8z7w6                      │
│       │                            │                                     │
│       ▼                            ▼                                     │
│  ┌─────────────────┐          ┌─────────────────┐                       │
│  │ ChromaDB Client │          │ ChromaDB Client │                       │
│  │ path: .../a1b2  │          │ path: .../x9y8  │                       │
│  └────────┬────────┘          └────────┬────────┘                       │
│           │                            │                                 │
│           ▼                            ▼                                 │
│  ┌─────────────────┐          ┌─────────────────┐                       │
│  │ a1b2.../        │          │ x9y8.../        │                       │
│  │ chroma.sqlite3  │          │ chroma.sqlite3  │                       │
│  └─────────────────┘          └─────────────────┘                       │
│                                                                          │
│  ✓ Komplett getrennte Dateien                                           │
│  ✓ Keine Konflikte möglich                                              │
│  ✓ Keine Locks zwischen Projekten                                       │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.4 Gleiches Projekt, mehrere Sessions

Was passiert bei **zwei Sessions im gleichen Projekt**?

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    ZWEI SESSIONS, EIN PROJEKT                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  Terminal 1                    Terminal 2                                │
│  ──────────────────           ──────────────────                        │
│  cd ~/ecommerce               cd ~/ecommerce                             │
│  claude                       claude                                     │
│       │                            │                                     │
│       ▼                            ▼                                     │
│  project_id: a1b2c3d4         project_id: a1b2c3d4  (GLEICH!)           │
│       │                            │                                     │
│       └──────────┬─────────────────┘                                    │
│                  ▼                                                       │
│         ┌─────────────────┐                                             │
│         │ ChromaDB Client │  ← SQLite handles concurrent access!        │
│         │ path: .../a1b2  │                                             │
│         └────────┬────────┘                                             │
│                  │                                                       │
│                  ▼                                                       │
│         ┌─────────────────┐                                             │
│         │ a1b2.../        │                                             │
│         │ chroma.sqlite3  │                                             │
│         └─────────────────┘                                             │
│                                                                          │
│  SQLite WAL-Mode garantiert:                                            │
│  ✓ Mehrere Reader gleichzeitig                                          │
│  ✓ Ein Writer zur Zeit (automatisches Locking)                          │
│  ✓ Keine Korruption                                                     │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.5 Memory Manager mit Projekt-Isolation

```python
class ProjectMemoryManager:
    """
    Verwaltet Memory-Instanzen mit strikter Projekt-Isolation.

    GARANTIEN:
    - Jedes Projekt hat eigene ChromaDB-Instanz
    - Keine Cross-Projekt Queries möglich
    - Automatisches Cleanup inaktiver Instanzen
    """

    def __init__(self):
        # Cache für aktive Memory-Instanzen (pro project_id)
        self._instances: Dict[str, ProjectMemory] = {}
        self._lock = asyncio.Lock()

    async def get_memory(self, project_id: str) -> "ProjectMemory":
        """
        Holt oder erstellt Memory-Instanz für ein Projekt.

        WICHTIG: Jeder project_id bekommt seine eigene Instanz!
        """
        async with self._lock:
            if project_id not in self._instances:
                # Neue Instanz erstellen
                memory_path = CHAINGUARD_HOME / "memory" / project_id
                memory_path.mkdir(parents=True, exist_ok=True)

                self._instances[project_id] = ProjectMemory(
                    project_id=project_id,
                    path=memory_path
                )

            return self._instances[project_id]

    async def cleanup_inactive(self, max_age_seconds: int = 3600):
        """Entfernt inaktive Memory-Instanzen aus dem RAM."""
        async with self._lock:
            now = time.time()
            to_remove = [
                pid for pid, mem in self._instances.items()
                if (now - mem.last_access) > max_age_seconds
            ]
            for pid in to_remove:
                await self._instances[pid].close()
                del self._instances[pid]


class ProjectMemory:
    """
    Memory für ein einzelnes Projekt.

    Kapselt alle ChromaDB-Operationen für dieses Projekt.
    """

    def __init__(self, project_id: str, path: Path):
        self.project_id = project_id
        self.path = path
        self.last_access = time.time()

        # ChromaDB mit Projekt-spezifischem Pfad
        self._client = chromadb.PersistentClient(
            path=str(path),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=False,  # Schutz vor versehentlichem Löschen
                is_persistent=True
            )
        )

        # Collections für dieses Projekt
        self._collections = {
            "code_structure": self._client.get_or_create_collection("code_structure"),
            "functions": self._client.get_or_create_collection("functions"),
            "database_schema": self._client.get_or_create_collection("database_schema"),
            "architecture": self._client.get_or_create_collection("architecture"),
            "learnings": self._client.get_or_create_collection("learnings"),
            "code_summaries": self._client.get_or_create_collection("code_summaries"),  # v5.4
        }

    async def query(self, query: str, collection: str = "all", limit: int = 5):
        """
        Query IMMER nur in diesem Projekt's Memory!
        """
        self.last_access = time.time()

        if collection == "all":
            # Alle Collections durchsuchen
            results = []
            for coll_name, coll in self._collections.items():
                hits = coll.query(query_texts=[query], n_results=limit)
                results.extend(self._format_results(hits, coll_name))
            return results
        else:
            coll = self._collections.get(collection)
            if not coll:
                return []
            hits = coll.query(query_texts=[query], n_results=limit)
            return self._format_results(hits, collection)

    async def close(self):
        """Schließt die ChromaDB-Verbindung sauber."""
        # ChromaDB PersistentClient braucht kein explizites close,
        # aber wir können Ressourcen freigeben
        self._client = None
        self._collections = {}
```

### 1.6 Sicherheits-Checks

```python
# In jedem Memory-Tool: Projekt-Isolation validieren

async def _validate_project_isolation(
    requested_project_id: str,
    current_working_dir: str
) -> bool:
    """
    Stellt sicher, dass nur auf das eigene Projekt zugegriffen wird.

    VERHINDERT:
    - Zugriff auf fremde project_ids
    - Path-Traversal Angriffe
    - Manipulation der project_id
    """
    # 1. Project-ID neu berechnen aus working_dir
    expected_id = get_project_id(current_working_dir)

    # 2. Muss mit angefragter ID übereinstimmen
    if requested_project_id != expected_id:
        raise SecurityError(
            f"Project-ID mismatch! Expected {expected_id}, got {requested_project_id}"
        )

    # 3. Memory-Pfad validieren (kein Path-Traversal)
    memory_path = CHAINGUARD_HOME / "memory" / requested_project_id
    try:
        # Resolve und prüfen ob innerhalb von memory/
        resolved = memory_path.resolve()
        resolved.relative_to(CHAINGUARD_HOME / "memory")
    except ValueError:
        raise SecurityError(f"Invalid memory path: {memory_path}")

    return True
```

### 1.7 Zusammenfassung Projekt-Isolation

| Aspekt | Garantie |
|--------|----------|
| **Speicher** | Jedes Projekt hat eigenen Ordner unter `~/.chainguard/memory/{project_id}/` |
| **Datenbank** | Separate SQLite-Datei pro Projekt |
| **Collections** | Nur innerhalb des eigenen Projekts sichtbar |
| **Queries** | Können nur eigenes Projekt durchsuchen |
| **Concurrent Access** | SQLite WAL-Mode für gleichzeitige Sessions |
| **Cross-Project** | Physisch unmöglich (separate Dateien) |
| **Sicherheit** | Project-ID wird aus working_dir berechnet, nicht übergeben |

---

## 2. Architektur-Übersicht

```
┌─────────────────────────────────────────────────────────────────────┐
│                    CHAINGUARD MCP SERVER                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────────┐ │
│  │ set_scope   │───▶│ memory_init │───▶│  INITIAL INDEXIERUNG    │ │
│  └─────────────┘    └─────────────┘    │  - Code-Struktur        │ │
│                                         │  - DB-Schema            │ │
│  ┌─────────────┐    ┌─────────────┐    │  - Architektur-Patterns │ │
│  │   track     │───▶│memory_update│───▶│  - Funktionen/Klassen   │ │
│  └─────────────┘    └─────────────┘    └───────────┬─────────────┘ │
│                                                     │               │
│  ┌─────────────┐    ┌─────────────┐                ▼               │
│  │memory_query │───▶│  RETRIEVAL  │◀───────────────┐               │
│  └─────────────┘    └─────────────┘                │               │
│                                                     │               │
├─────────────────────────────────────────────────────┼───────────────┤
│                     MEMORY LAYER                    │               │
│  ┌──────────────────────────────────────────────────┴─────────────┐ │
│  │                                                                 │ │
│  │  ┌─────────────────┐     ┌─────────────────────────────────┐   │ │
│  │  │  EMBEDDING      │     │         CHROMADB                │   │ │
│  │  │  ENGINE         │     │  (Lokale Vektor-Datenbank)      │   │ │
│  │  │                 │     │                                 │   │ │
│  │  │  all-MiniLM-L6  │────▶│  Collections:                   │   │ │
│  │  │  (22MB, offline)│     │  - code_structure               │   │ │
│  │  │                 │     │  - functions                    │   │ │
│  │  │  384 dimensions │     │  - database_schema              │   │ │
│  │  └─────────────────┘     │  - architecture                 │   │ │
│  │                          │  - learnings                    │   │ │
│  │                          └─────────────────────────────────┘   │ │
│  │                                        │                        │ │
│  │                                        ▼                        │ │
│  │                          ~/.chainguard/memory/{project_id}/     │ │
│  │                          └── chroma.sqlite3                     │ │
│  └─────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Technologie-Stack

### 2.1 Vektor-Datenbank: ChromaDB

**Warum ChromaDB?**

| Kriterium | ChromaDB | LanceDB | Vectorlite |
|-----------|----------|---------|------------|
| Installation | `pip install chromadb` | `pip install lancedb` | Komplex (C-Extension) |
| Persistenz | SQLite + hnswlib | Lance Format | SQLite |
| Python-Native | ✓ | ✓ | Teilweise |
| Embedding-Integration | Eingebaut | Extern | Extern |
| Community | Sehr aktiv | Wachsend | Klein |
| Dokumentation | Excellent | Gut | Begrenzt |

**Entscheidung:** ChromaDB bietet die beste Balance aus Einfachheit, Features und Community-Support.

```python
# Beispiel-Nutzung
import chromadb
from chromadb.config import Settings

client = chromadb.PersistentClient(
    path="~/.chainguard/memory/{project_id}",
    settings=Settings(anonymized_telemetry=False)
)

collection = client.get_or_create_collection(
    name="code_structure",
    metadata={"hnsw:space": "cosine"}
)
```

### 2.2 Embedding-Modell: all-MiniLM-L6-v2

**Warum dieses Modell?**

| Eigenschaft | Wert |
|-------------|------|
| Größe | 22MB (Download einmalig) |
| Dimensionen | 384 |
| Max. Tokens | 256 |
| Geschwindigkeit | ~1000 Embeddings/Sekunde (CPU) |
| Qualität | State-of-the-art für Größe |
| Offline | ✓ Komplett lokal |

```python
from sentence_transformers import SentenceTransformer

# Einmalig laden (cached in ~/.cache/huggingface/)
model = SentenceTransformer('all-MiniLM-L6-v2')

# Embeddings erzeugen
embeddings = model.encode([
    "UserController handles authentication",
    "Database migration for users table"
], normalize_embeddings=True)
```

**Alternative für schwache Hardware:** `all-MiniLM-L12-v2` (etwas langsamer, aber besser)

---

## 3. Datenmodell

### 3.1 Collections (Vektor-Sammlungen)

```
project_memory/
├── code_structure      # Dateien, Module, Verzeichnisse
├── functions           # Funktionen, Methoden, Klassen
├── database_schema     # Tabellen, Spalten, Beziehungen
├── architecture        # Patterns, Frameworks, Konventionen
├── learnings           # Erkenntnisse aus der Arbeit
├── code_summaries      # Deep Logic Summaries (v5.4) - menschenlesbare Code-Beschreibungen
└── errors_fixes        # Fehler und deren Lösungen
```

### 3.2 Document-Schema

```python
@dataclass
class MemoryDocument:
    id: str                    # Eindeutige ID (hash)
    content: str               # Text für Embedding
    metadata: Dict[str, Any]   # Strukturierte Daten

    # Metadaten-Beispiele:
    # - type: "function" | "class" | "table" | "pattern"
    # - file_path: "src/controllers/UserController.php"
    # - language: "php" | "python" | "typescript"
    # - created_at: ISO timestamp
    # - updated_at: ISO timestamp
    # - confidence: 0.0 - 1.0
```

### 3.3 Beispiel-Dokumente

```python
# Code-Struktur
{
    "id": "file_abc123",
    "content": "UserController.php: Handles user authentication, login, logout, password reset. Located in app/Http/Controllers/",
    "metadata": {
        "type": "file",
        "path": "app/Http/Controllers/UserController.php",
        "language": "php",
        "framework": "laravel",
        "functions": ["login", "logout", "resetPassword"],
        "lines": 250
    }
}

# Funktion
{
    "id": "func_def456",
    "content": "login() method in UserController validates credentials against users table, creates session, returns JWT token. Uses bcrypt for password hashing.",
    "content": "...",
    "metadata": {
        "type": "function",
        "name": "login",
        "file": "UserController.php",
        "params": ["email", "password"],
        "returns": "JsonResponse",
        "calls": ["User::findByEmail", "Hash::check", "JWTAuth::attempt"]
    }
}

# Datenbank-Schema
{
    "id": "table_users",
    "content": "users table stores user accounts with id (PK), email (unique), password (hashed), name, created_at, updated_at. Has many articles, belongs to roles.",
    "metadata": {
        "type": "table",
        "name": "users",
        "columns": ["id", "email", "password", "name", "created_at"],
        "primary_key": "id",
        "relations": {"articles": "has_many", "roles": "belongs_to_many"}
    }
}
```

---

## 4. Workflows

### 4.1 Initiale Indexierung (memory_init)

```
┌─────────────────────────────────────────────────────────────────┐
│                    INITIALE INDEXIERUNG                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. PROJEKT-SCAN                                                 │
│     ├── Verzeichnisstruktur analysieren                         │
│     ├── Dateitypen identifizieren (PHP, JS, Python, etc.)       │
│     └── Framework erkennen (Laravel, React, Django, etc.)       │
│                                                                  │
│  2. CODE-ANALYSE                                                 │
│     ├── Für jede Datei:                                         │
│     │   ├── AST parsen (tree-sitter oder language-specific)     │
│     │   ├── Klassen/Funktionen extrahieren                      │
│     │   ├── Imports/Dependencies identifizieren                 │
│     │   └── Docstrings/Kommentare sammeln                       │
│     └── Beziehungen zwischen Dateien erkennen                   │
│                                                                  │
│  3. DATENBANK-SCHEMA (wenn verfügbar)                           │
│     ├── chainguard_db_schema() Ergebnis nutzen                  │
│     ├── Migrations-Dateien analysieren                          │
│     └── ORM-Models parsen (Eloquent, SQLAlchemy, etc.)          │
│                                                                  │
│  4. ARCHITEKTUR-ERKENNUNG                                       │
│     ├── MVC/MVVM/etc. Pattern erkennen                          │
│     ├── API-Endpunkte identifizieren                            │
│     ├── Auth-Mechanismen finden                                 │
│     └── Konfiguration analysieren                               │
│                                                                  │
│  5. EMBEDDING & SPEICHERUNG                                      │
│     ├── Dokumente in Chunks aufteilen (max 256 Tokens)          │
│     ├── Embeddings mit all-MiniLM-L6 erzeugen                   │
│     └── In ChromaDB Collections speichern                       │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Geschätzte Zeit:** 1-5 Minuten je nach Projektgröße

### 4.2 Inkrementelles Update (bei track/finish)

```python
async def incremental_update(file_path: str, action: str):
    """
    Wird bei chainguard_track() oder chainguard_finish() aufgerufen.

    Nur geänderte Dateien werden neu indexiert.
    """
    if action == "delete":
        # Dokumente für diese Datei entfernen
        memory.delete(where={"file_path": file_path})
    else:
        # Datei neu analysieren und Embeddings aktualisieren
        documents = analyze_file(file_path)
        memory.upsert(documents)
```

### 4.3 Semantische Abfrage (memory_query)

```python
async def memory_query(query: str, limit: int = 5) -> List[Dict]:
    """
    Semantische Suche im Projekt-Memory.

    Beispiele:
    - "Wo werden Benutzer authentifiziert?"
    - "Welche Tabellen haben eine Beziehung zu users?"
    - "Wie funktioniert das Caching?"
    """
    # Query in Embedding umwandeln
    query_embedding = model.encode(query, normalize_embeddings=True)

    # In allen relevanten Collections suchen
    results = []
    for collection in ["code_structure", "functions", "database_schema"]:
        hits = memory.query(
            collection=collection,
            query_embeddings=[query_embedding],
            n_results=limit,
            include=["documents", "metadatas", "distances"]
        )
        results.extend(hits)

    # Nach Relevanz sortieren und zurückgeben
    return sorted(results, key=lambda x: x["distance"])[:limit]
```

---

## 5. Neue MCP Tools

### 5.1 chainguard_memory_init

```python
Tool(
    name="chainguard_memory_init",
    description="""
    Initiale Projekt-Indexierung für Long-Term Memory.

    Analysiert:
    - Code-Struktur (Dateien, Module, Verzeichnisse)
    - Funktionen und Klassen
    - Datenbank-Schema (wenn DB verbunden)
    - Architektur-Patterns

    Dauer: 1-5 Minuten je nach Projektgröße.
    Einmalig pro Projekt ausführen.
    """,
    inputSchema={
        "type": "object",
        "properties": {
            "working_dir": {"type": "string"},
            "include_patterns": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Glob patterns to include (default: **/*.{php,py,js,ts})"
            },
            "exclude_patterns": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Glob patterns to exclude (default: node_modules, vendor, .git)"
            },
            "force": {
                "type": "boolean",
                "description": "Force re-indexierung auch wenn Memory existiert"
            }
        }
    }
)
```

**Response-Beispiel:**
```
✓ Memory initialisiert für: myproject

📊 Indexiert:
   - 127 Dateien
   - 342 Funktionen/Methoden
   - 23 Klassen
   - 15 Datenbank-Tabellen
   - 8 API-Endpunkte

💾 Speicher: 12.4 MB
⏱️  Dauer: 2m 34s

Das Memory ist jetzt aktiv. Nutze chainguard_memory_query() für semantische Suchen.
```

### 5.2 chainguard_memory_query

```python
Tool(
    name="chainguard_memory_query",
    description="""
    Semantische Suche im Projekt-Memory.

    Beispiel-Queries:
    - "Wo werden Benutzer authentifiziert?"
    - "Welche Funktionen nutzen die users Tabelle?"
    - "Wie funktioniert das Error-Handling?"

    Gibt relevante Code-Stellen, Funktionen und Schema-Infos zurück.
    """,
    inputSchema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Natürlichsprachliche Frage"
            },
            "limit": {
                "type": "integer",
                "default": 5,
                "description": "Max. Anzahl Ergebnisse"
            },
            "filter_type": {
                "type": "string",
                "enum": ["all", "code", "functions", "database", "architecture"],
                "description": "Nur bestimmte Typen durchsuchen"
            }
        },
        "required": ["query"]
    }
)
```

**Response-Beispiel:**
```
🔍 Query: "Wo werden Benutzer authentifiziert?"

📍 Relevante Stellen (Top 5):

1. [0.92] app/Http/Controllers/AuthController.php:45
   └─ login() - Validates credentials, creates JWT token

2. [0.87] app/Http/Middleware/Authenticate.php:12
   └─ handle() - Checks JWT token on protected routes

3. [0.82] app/Models/User.php:78
   └─ validatePassword() - Bcrypt password verification

4. [0.76] database/migrations/2024_01_users.php
   └─ users table with email, password columns

5. [0.71] config/auth.php
   └─ JWT guard configuration, token TTL settings
```

### 5.3 chainguard_memory_update

```python
Tool(
    name="chainguard_memory_update",
    description="""
    Manuelles Update des Projekt-Memory.

    Optionen:
    - Bestimmte Dateien neu indexieren
    - Erkenntnisse/Learnings hinzufügen
    - Veraltete Einträge entfernen
    """,
    inputSchema={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["reindex_file", "add_learning", "cleanup"],
            },
            "file_path": {"type": "string"},
            "learning": {
                "type": "string",
                "description": "Erkenntnis zum Speichern"
            }
        }
    }
)
```

### 5.4 chainguard_memory_status

```python
Tool(
    name="chainguard_memory_status",
    description="Zeigt Status und Statistiken des Projekt-Memory.",
    inputSchema={
        "type": "object",
        "properties": {
            "working_dir": {"type": "string"}
        }
    }
)
```

**Response-Beispiel:**
```
📊 Memory Status: myproject

Initialisiert: 2026-01-05 14:32
Letztes Update: 2026-01-08 09:15

Collections:
├─ code_structure:   127 Dokumente
├─ functions:        342 Dokumente
├─ database_schema:   15 Dokumente
├─ architecture:      23 Dokumente
├─ learnings:         8 Dokumente
└─ code_summaries:   51 Dokumente

Speicher: 12.4 MB
Embedding-Model: all-MiniLM-L6-v2
```

### 5.5 chainguard_memory_summarize (NEU v5.4)

```python
Tool(
    name="chainguard_memory_summarize",
    description="""
    Generate deep logic summaries for code files.

    Unlike basic indexing which only captures structure (function names, class names),
    this tool extracts and stores detailed descriptions of what the code actually DOES.
    It analyzes docstrings, comments, function names, and code patterns to create
    human-readable summaries of the logic and purpose.

    Use this when you need the Memory to understand code behavior, not just structure.
    """,
    inputSchema={
        "type": "object",
        "properties": {
            "working_dir": {"type": "string"},
            "file": {
                "type": "string",
                "description": "Optional specific file to summarize"
            },
            "force": {
                "type": "boolean",
                "default": False,
                "description": "Re-summarize even if summary exists"
            }
        }
    }
)
```

**Response-Beispiel:**
```
📝 Code-Summaries erstellt

✓ 51 Dateien analysiert
✓ 51 neue Summaries erstellt
  0 bereits vorhanden (übersprungen)

Beispiel-Summary:
├─ chainguard/handlers.py
│  PURPOSE: Handles all MCP tool requests via registry pattern
│  CLASSES:
│    - HandlerRegistry: Manages tool handlers with decorator-based registration
│  FUNCTIONS:
│    - handle_set_scope: Sets task boundaries and acceptance criteria
│    - handle_track: Records file changes with syntax validation
│    ...
```

---

## 6. Smart Context Injection (Killer-Feature!)

### 6.1 Übersicht

Das **Smart Context Injection** Feature ist das Herzstück des Memory Systems. Bei jedem `chainguard_set_scope()` Aufruf wird automatisch relevanter Kontext aus dem Memory geladen und Claude zur Verfügung gestellt.

**Das Problem ohne Memory:**
```
User: "Fix den Login-Bug"
Claude: "Okay, ich muss erst herausfinden wo der Login-Code ist..."
        → Sucht mit Glob/Grep
        → Liest mehrere Dateien
        → Verbraucht Zeit und Tokens
```

**Mit Smart Context Injection:**
```
User: "Fix den Login-Bug"
Claude: "Ich sehe dass Login in AuthController.php:45 ist,
         JWT-Auth verwendet wird, und die users-Tabelle
         email+password hat. Lass mich den Bug analysieren..."
        → Sofort produktiv
        → Weniger Token-Verbrauch
        → Bessere Ergebnisse
```

### 6.2 Architektur

```
┌─────────────────────────────────────────────────────────────────────┐
│                    SMART CONTEXT INJECTION FLOW                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  INPUT: chainguard_set_scope(description="Login-Bug fixen")  │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                              ↓                                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  STEP 1: KEYWORD EXTRACTION                                   │   │
│  │                                                               │   │
│  │  "Login-Bug fixen"                                            │   │
│  │       ↓                                                       │   │
│  │  Keywords: ["login", "bug", "authentication", "auth"]         │   │
│  │  Expanded: ["login", "auth", "session", "jwt", "password"]    │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                              ↓                                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  STEP 2: MULTI-COLLECTION QUERY                               │   │
│  │                                                               │   │
│  │  Query-Embedding: encode("Login Bug Authentication")          │   │
│  │       ↓                                                       │   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐             │   │
│  │  │ functions   │ │ code_struct │ │ db_schema   │             │   │
│  │  │ collection  │ │ collection  │ │ collection  │             │   │
│  │  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘             │   │
│  │         │               │               │                     │   │
│  │         ▼               ▼               ▼                     │   │
│  │  [login()     ] [AuthController] [users table  ]             │   │
│  │  [authenticate] [Middleware    ] [sessions     ]             │   │
│  │  [logout()    ] [User.php      ] [tokens       ]             │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                              ↓                                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  STEP 3: RELEVANCE SCORING & RANKING                          │   │
│  │                                                               │   │
│  │  Score = (semantic_similarity * 0.6) +                        │   │
│  │          (keyword_match * 0.25) +                             │   │
│  │          (recency_bonus * 0.15)                               │   │
│  │                                                               │   │
│  │  Ranked Results:                                              │   │
│  │  1. [0.94] login() in AuthController.php                      │   │
│  │  2. [0.89] Authenticate.php middleware                        │   │
│  │  3. [0.85] users table (email, password)                      │   │
│  │  4. [0.78] JWT config in auth.php                             │   │
│  │  5. [0.72] User model validatePassword()                      │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                              ↓                                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  STEP 4: CONTEXT FORMATTING & INJECTION                       │   │
│  │                                                               │   │
│  │  📚 **Relevanter Kontext aus Memory:**                        │   │
│  │                                                               │   │
│  │  🔐 **Authentication:**                                       │   │
│  │  • AuthController.php:45-120                                  │   │
│  │    └─ login(), logout(), validateCredentials()                │   │
│  │  • Authenticate.php (Middleware)                              │   │
│  │    └─ JWT Token Validation, Guard: api                        │   │
│  │                                                               │   │
│  │  📊 **Datenbank:**                                            │   │
│  │  • users: id, email (unique), password (bcrypt)               │   │
│  │                                                               │   │
│  │  ⚙️ **Konfiguration:**                                        │   │
│  │  • config/auth.php → JWT Guard, TTL: 60min                    │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                              ↓                                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  OUTPUT: set_scope Response mit injiziertem Kontext           │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### 6.3 Keyword Extraction

```python
class KeywordExtractor:
    """Extrahiert und erweitert Keywords aus der Scope-Description."""

    # Synonyme und verwandte Begriffe
    KEYWORD_EXPANSIONS = {
        "login": ["auth", "authentication", "signin", "session", "jwt", "token"],
        "user": ["account", "profile", "member", "customer"],
        "database": ["db", "sql", "table", "schema", "migration"],
        "api": ["endpoint", "route", "controller", "rest", "request"],
        "bug": ["fix", "error", "issue", "problem", "debug"],
        "feature": ["implement", "add", "create", "new"],
        "test": ["spec", "unit", "integration", "phpunit", "jest"],
        "payment": ["stripe", "checkout", "billing", "invoice", "cart"],
        "email": ["mail", "notification", "smtp", "newsletter"],
        "upload": ["file", "image", "storage", "s3", "media"],
    }

    # Stoppwörter die ignoriert werden
    STOP_WORDS = {"the", "a", "an", "in", "on", "at", "to", "for", "of", "and", "or",
                  "is", "are", "was", "were", "be", "been", "being", "have", "has",
                  "do", "does", "did", "will", "would", "could", "should", "may",
                  "might", "must", "shall", "can", "need", "dare", "ought", "used",
                  "den", "die", "das", "der", "ein", "eine", "und", "oder", "für"}

    @classmethod
    def extract(cls, text: str) -> List[str]:
        """
        Extrahiert Keywords aus Text.

        Args:
            text: "Login-Bug fixen und Session-Handling verbessern"

        Returns:
            ["login", "bug", "session", "handling"]
        """
        # Normalisieren
        text = text.lower()

        # Sonderzeichen durch Leerzeichen ersetzen
        text = re.sub(r'[^a-zäöü0-9\s]', ' ', text)

        # Tokenisieren
        words = text.split()

        # Stoppwörter entfernen, kurze Wörter ignorieren
        keywords = [
            w for w in words
            if w not in cls.STOP_WORDS and len(w) > 2
        ]

        return list(set(keywords))

    @classmethod
    def expand(cls, keywords: List[str]) -> List[str]:
        """
        Erweitert Keywords um verwandte Begriffe.

        Args:
            keywords: ["login", "bug"]

        Returns:
            ["login", "bug", "auth", "authentication", "signin",
             "session", "jwt", "token", "fix", "error", "issue"]
        """
        expanded = set(keywords)

        for keyword in keywords:
            if keyword in cls.KEYWORD_EXPANSIONS:
                expanded.update(cls.KEYWORD_EXPANSIONS[keyword])

        return list(expanded)

    @classmethod
    def extract_and_expand(cls, text: str) -> Tuple[List[str], List[str]]:
        """
        Kombiniert Extraktion und Expansion.

        Returns:
            (original_keywords, expanded_keywords)
        """
        original = cls.extract(text)
        expanded = cls.expand(original)
        return original, expanded
```

### 6.4 Relevance Scoring

```python
@dataclass
class ScoredResult:
    """Ein Suchergebnis mit Relevanz-Score."""
    document: MemoryDocument
    semantic_score: float      # 0.0 - 1.0 (Cosine Similarity)
    keyword_score: float       # 0.0 - 1.0 (Keyword Match Ratio)
    recency_score: float       # 0.0 - 1.0 (Wie kürzlich geändert)
    final_score: float         # Gewichtete Kombination

class RelevanceScorer:
    """Berechnet Relevanz-Scores für Memory-Ergebnisse."""

    # Gewichtung der Score-Komponenten
    WEIGHTS = {
        "semantic": 0.60,    # Semantische Ähnlichkeit (Hauptfaktor)
        "keyword": 0.25,     # Keyword-Übereinstimmung
        "recency": 0.15,     # Aktualität
    }

    # Bonus für bestimmte Dokumenttypen je nach Task
    TYPE_BONUSES = {
        "bug": {"function": 0.1, "error": 0.15},
        "feature": {"architecture": 0.1, "pattern": 0.1},
        "database": {"table": 0.2, "migration": 0.15},
        "test": {"test": 0.2, "spec": 0.15},
    }

    @classmethod
    def score(
        cls,
        document: MemoryDocument,
        semantic_distance: float,
        keywords: List[str],
        task_type: str = "general"
    ) -> ScoredResult:
        """
        Berechnet den finalen Relevanz-Score.

        Args:
            document: Das Memory-Dokument
            semantic_distance: ChromaDB Distance (0 = identisch, 2 = maximal verschieden)
            keywords: Extrahierte Keywords aus der Scope-Description
            task_type: Art des Tasks (bug, feature, database, etc.)
        """
        # 1. Semantic Score (Distance zu Similarity umwandeln)
        # ChromaDB Cosine Distance: 0 = gleich, 2 = entgegengesetzt
        semantic_score = 1.0 - (semantic_distance / 2.0)

        # 2. Keyword Score
        doc_text = f"{document.content} {document.metadata.get('name', '')}".lower()
        matched = sum(1 for kw in keywords if kw in doc_text)
        keyword_score = matched / max(len(keywords), 1)

        # 3. Recency Score (basierend auf updated_at)
        updated_at = document.metadata.get("updated_at", "")
        recency_score = cls._calculate_recency(updated_at)

        # 4. Type Bonus
        doc_type = document.metadata.get("type", "")
        type_bonus = cls.TYPE_BONUSES.get(task_type, {}).get(doc_type, 0)

        # 5. Final Score berechnen
        final_score = (
            cls.WEIGHTS["semantic"] * semantic_score +
            cls.WEIGHTS["keyword"] * keyword_score +
            cls.WEIGHTS["recency"] * recency_score +
            type_bonus
        )

        # Auf 0-1 normalisieren
        final_score = min(1.0, max(0.0, final_score))

        return ScoredResult(
            document=document,
            semantic_score=semantic_score,
            keyword_score=keyword_score,
            recency_score=recency_score,
            final_score=final_score
        )

    @staticmethod
    def _calculate_recency(updated_at: str) -> float:
        """
        Berechnet Recency-Score basierend auf Timestamp.

        Letzte 24h: 1.0
        Letzte Woche: 0.8
        Letzter Monat: 0.5
        Älter: 0.2
        """
        if not updated_at:
            return 0.5  # Default für unbekannt

        try:
            updated = datetime.fromisoformat(updated_at)
            age = datetime.now() - updated

            if age.days < 1:
                return 1.0
            elif age.days < 7:
                return 0.8
            elif age.days < 30:
                return 0.5
            else:
                return 0.2
        except:
            return 0.5
```

### 6.5 Context Formatter

```python
class ContextFormatter:
    """Formatiert Memory-Ergebnisse für die Kontext-Injektion."""

    # Maximale Anzahl Ergebnisse pro Kategorie
    MAX_RESULTS_PER_CATEGORY = 3

    # Kategorie-Icons
    CATEGORY_ICONS = {
        "authentication": "🔐",
        "database": "📊",
        "api": "🌐",
        "config": "⚙️",
        "test": "🧪",
        "model": "📦",
        "view": "🖼️",
        "controller": "🎮",
        "service": "⚡",
        "util": "🔧",
        "recent": "🕐",
    }

    @classmethod
    def format(
        cls,
        results: List[ScoredResult],
        scope_description: str,
        max_tokens: int = 500
    ) -> str:
        """
        Formatiert Ergebnisse für die Kontext-Injektion.

        Args:
            results: Sortierte Liste von ScoredResults
            scope_description: Die Original-Beschreibung
            max_tokens: Maximale Token-Anzahl für den Kontext

        Returns:
            Formatierter Kontext-String
        """
        if not results:
            return ""

        # Nach Kategorien gruppieren
        categories = cls._categorize_results(results)

        # Output zusammenbauen
        lines = ["", "📚 **Relevanter Kontext aus Memory:**", ""]

        for category, items in categories.items():
            if not items:
                continue

            icon = cls.CATEGORY_ICONS.get(category, "📄")
            lines.append(f"{icon} **{category.title()}:**")

            for result in items[:cls.MAX_RESULTS_PER_CATEGORY]:
                doc = result.document
                score = result.final_score

                # Hauptzeile
                path = doc.metadata.get("path", doc.metadata.get("name", "unknown"))
                lines.append(f"• {path}")

                # Detail-Zeile
                summary = cls._get_summary(doc)
                if summary:
                    lines.append(f"  └─ {summary}")

            lines.append("")  # Leerzeile zwischen Kategorien

        # Letzte Änderungen hinzufügen (wenn relevant)
        recent = cls._get_recent_changes(results)
        if recent:
            lines.append("💡 **Letzte relevante Änderungen:**")
            for change in recent[:2]:
                lines.append(f"• {change}")
            lines.append("")

        return "\n".join(lines)

    @classmethod
    def _categorize_results(
        cls,
        results: List[ScoredResult]
    ) -> Dict[str, List[ScoredResult]]:
        """Gruppiert Ergebnisse nach Kategorien."""
        categories = defaultdict(list)

        for result in results:
            doc_type = result.document.metadata.get("type", "other")
            path = result.document.metadata.get("path", "").lower()

            # Kategorie bestimmen
            if "auth" in path or doc_type == "auth":
                categories["authentication"].append(result)
            elif doc_type == "table" or "migration" in path:
                categories["database"].append(result)
            elif "controller" in path or doc_type == "controller":
                categories["controller"].append(result)
            elif "model" in path or doc_type == "model":
                categories["model"].append(result)
            elif "config" in path or doc_type == "config":
                categories["config"].append(result)
            elif "test" in path or doc_type == "test":
                categories["test"].append(result)
            elif "api" in path or "route" in path:
                categories["api"].append(result)
            else:
                categories["other"].append(result)

        # "other" entfernen wenn leer oder zu voll
        if len(categories.get("other", [])) > 5:
            del categories["other"]

        return dict(categories)

    @classmethod
    def _get_summary(cls, doc: MemoryDocument) -> str:
        """Erstellt eine kurze Zusammenfassung des Dokuments."""
        metadata = doc.metadata

        if metadata.get("type") == "function":
            params = metadata.get("params", [])
            returns = metadata.get("returns", "void")
            return f"{metadata.get('name', '?')}({', '.join(params)}) → {returns}"

        elif metadata.get("type") == "table":
            columns = metadata.get("columns", [])[:4]
            return f"Columns: {', '.join(columns)}{'...' if len(metadata.get('columns', [])) > 4 else ''}"

        elif metadata.get("type") == "file":
            functions = metadata.get("functions", [])[:3]
            if functions:
                return f"Functions: {', '.join(functions)}"

        # Fallback: Ersten Satz des Contents
        content = doc.content
        if ". " in content:
            return content.split(". ")[0] + "."
        return content[:80] + "..." if len(content) > 80 else content

    @classmethod
    def _get_recent_changes(cls, results: List[ScoredResult]) -> List[str]:
        """Findet kürzlich geänderte relevante Dateien."""
        recent = []

        for result in results:
            updated = result.document.metadata.get("updated_at", "")
            if result.recency_score >= 0.8 and updated:
                try:
                    dt = datetime.fromisoformat(updated)
                    age = datetime.now() - dt
                    if age.days < 7:
                        path = result.document.metadata.get("path", "?")
                        ago = f"{age.days}d ago" if age.days > 0 else "today"
                        recent.append(f"{ago}: {path}")
                except:
                    pass

        return recent
```

### 6.6 Integration in set_scope Handler

```python
@handler.register("chainguard_set_scope")
async def handle_set_scope(args: Dict[str, Any]) -> List[TextContent]:
    """
    Handler für chainguard_set_scope mit Smart Context Injection.
    """
    description = args.get("description", "")
    working_dir = args.get("working_dir")

    # ... bestehende Scope-Logik ...

    # ========== SMART CONTEXT INJECTION ==========

    if memory_exists(project_id):
        # 1. Keywords extrahieren
        original_keywords, expanded_keywords = KeywordExtractor.extract_and_expand(description)

        # 2. Task-Typ erkennen
        task_type = detect_task_type(description)  # "bug", "feature", "database", etc.

        # 3. Multi-Collection Query
        query_text = " ".join(original_keywords + [description])

        raw_results = await memory.multi_query(
            query=query_text,
            collections=["functions", "code_structure", "database_schema", "architecture"],
            n_results=10
        )

        # 4. Relevanz-Scoring
        scored_results = [
            RelevanceScorer.score(
                document=doc,
                semantic_distance=distance,
                keywords=expanded_keywords,
                task_type=task_type
            )
            for doc, distance in raw_results
        ]

        # 5. Sortieren nach Score
        scored_results.sort(key=lambda x: x.final_score, reverse=True)

        # 6. Nur relevante Ergebnisse (Score > 0.5)
        relevant_results = [r for r in scored_results if r.final_score > 0.5]

        # 7. Formatieren und injizieren
        if relevant_results:
            context = ContextFormatter.format(
                results=relevant_results[:8],
                scope_description=description
            )
            response += context
        else:
            response += "\n📚 Memory: Keine stark relevanten Einträge gefunden."

    else:
        # Memory nicht initialisiert - Hinweis zeigen
        response += """

💡 **Long-Term Memory verfügbar!**
   Führe `chainguard_memory_init()` aus für:
   - Automatischen Kontext bei jedem Task
   - Semantische Code-Suche
   - Persistentes Projekt-Wissen
"""

    return _text(response)


def detect_task_type(description: str) -> str:
    """Erkennt den Task-Typ aus der Beschreibung."""
    description = description.lower()

    if any(w in description for w in ["bug", "fix", "fehler", "error", "issue"]):
        return "bug"
    elif any(w in description for w in ["feature", "implement", "add", "neu", "create"]):
        return "feature"
    elif any(w in description for w in ["database", "db", "migration", "table", "schema"]):
        return "database"
    elif any(w in description for w in ["test", "spec", "unit", "integration"]):
        return "test"
    elif any(w in description for w in ["refactor", "cleanup", "optimize"]):
        return "refactor"
    else:
        return "general"
```

### 6.7 Beispiel-Output

```
✓ Scope: Login-Bug fixen
💻 Mode: programming
Modules: all | Criteria: 0 | Checks: 0

📚 **Relevanter Kontext aus Memory:**

🔐 **Authentication:**
• app/Http/Controllers/AuthController.php
  └─ login(email, password) → JsonResponse
• app/Http/Middleware/Authenticate.php
  └─ JWT Token Validation, Guard: api
• app/Models/User.php
  └─ validatePassword(), findByEmail()

📊 **Database:**
• users
  └─ Columns: id, email, password, remember_token...
• sessions
  └─ Columns: id, user_id, ip_address, last_activity

⚙️ **Config:**
• config/auth.php
  └─ Guards: web, api (JWT). Token TTL: 60min.

💡 **Letzte relevante Änderungen:**
• 2d ago: app/Http/Controllers/AuthController.php
• 5d ago: database/migrations/2024_01_add_2fa.php

────────────────────────────────────────
📋 **PROGRAMMING-MODUS - Pflicht-Aktionen:**
...
```

### 6.8 Performance-Optimierungen

```python
class SmartContextCache:
    """
    Cache für häufige Context-Abfragen.

    Vermeidet redundante Queries wenn:
    - Gleicher/ähnlicher Scope innerhalb 5 Minuten
    - Keine Dateiänderungen seit letzter Query
    """

    def __init__(self, ttl_seconds: int = 300):
        self._cache: TTLLRUCache[str, List[ScoredResult]] = TTLLRUCache(
            maxsize=10,
            ttl_seconds=ttl_seconds
        )
        self._last_file_change: Dict[str, str] = {}

    def get_cache_key(self, project_id: str, description: str) -> str:
        """Generiert Cache-Key basierend auf Keywords."""
        keywords = sorted(KeywordExtractor.extract(description))
        return f"{project_id}:{':'.join(keywords[:5])}"

    def get(self, project_id: str, description: str) -> Optional[List[ScoredResult]]:
        """Holt gecachte Ergebnisse wenn verfügbar und gültig."""
        key = self.get_cache_key(project_id, description)

        # Prüfen ob Dateien geändert wurden
        last_change = self._last_file_change.get(project_id, "")
        current_change = get_last_file_change(project_id)

        if last_change != current_change:
            # Dateien wurden geändert - Cache invalidieren
            self._cache.invalidate(key)
            self._last_file_change[project_id] = current_change
            return None

        return self._cache.get(key)

    def set(self, project_id: str, description: str, results: List[ScoredResult]):
        """Speichert Ergebnisse im Cache."""
        key = self.get_cache_key(project_id, description)
        self._cache.set(key, results)
        self._last_file_change[project_id] = get_last_file_change(project_id)
```

---

## 7. Integration in bestehende Workflows

### 7.1 Automatische Initialisierung bei set_scope

```python
@handler.register("chainguard_set_scope")
async def handle_set_scope(args):
    # ... bestehende Logik ...
    # ... Smart Context Injection (siehe Kapitel 6) ...

    # Memory-Check für Initialisierungs-Hinweis
    if not memory_exists(project_id):
        # Hinweis auf Memory-Initialisierung
        response += """

💡 **Long-Term Memory verfügbar!**
   Führe `chainguard_memory_init()` aus für:
   - Semantische Code-Suche
   - Persistentes Projekt-Wissen
   - Schnellere Kontext-Erfassung
        """
    else:
        # Memory-Status kurz zeigen (nach Context Injection)
        response += f"\n📊 Memory: {memory.doc_count} Dokumente indexiert"
```

### 6.2 Inkrementelles Update bei track

```python
@handler.register("chainguard_track")
async def handle_track(args):
    # ... bestehende Logik ...

    # NEU: Memory-Update (async, non-blocking)
    if memory_exists(project_id) and file_path:
        asyncio.create_task(
            memory.incremental_update(file_path, action)
        )
```

### 6.3 Konsolidierung bei finish

```python
@handler.register("chainguard_finish")
async def handle_finish(args):
    # ... bestehende Logik ...

    # NEU: Memory-Konsolidierung
    if memory_exists(project_id):
        # Alle geänderten Dateien im Batch neu indexieren
        await memory.batch_update(state.changed_files)

        # Optional: Learnings aus der Session speichern
        if state.scope and state.scope.description:
            await memory.add_learning(
                f"Task completed: {state.scope.description}",
                metadata={"files_changed": state.files_changed}
            )
```

---

## 7. Installer-Erweiterung

### 7.1 Neue Dependencies

```bash
# In install.sh: install_python_deps()

local required_packages=(
    # ... bestehende ...
    "chromadb>=0.4.0"           # Vektor-Datenbank
    "sentence-transformers>=2.2.0"  # Embedding-Modell
)

# Optional für bessere Performance
local optional_packages=(
    # ... bestehende ...
    "onnxruntime>=1.15.0"       # Schnellere Inferenz (optional)
)
```

### 7.2 Model-Download

```bash
# Neuer Step in install.sh

download_embedding_model() {
    step "Lade Embedding-Modell herunter"

    info "Downloading all-MiniLM-L6-v2 (~22MB)..."

    # Python-Script zum Vorladen
    $PYTHON_CMD << 'EOF'
from sentence_transformers import SentenceTransformer
import os

# Model wird in ~/.cache/huggingface/ gespeichert
model = SentenceTransformer('all-MiniLM-L6-v2')
print(f"Model loaded: {model.get_sentence_embedding_dimension()} dimensions")

# Test-Embedding
test = model.encode(["Hello world"])
print(f"Test embedding shape: {test.shape}")
EOF

    if [[ $? -eq 0 ]]; then
        success "Embedding-Modell geladen und gecacht"
    else
        warn "Modell-Download fehlgeschlagen (wird bei erster Nutzung nachgeladen)"
    fi
}
```

### 7.3 Memory-Verzeichnis

```bash
# In install_files()

mkdir -p "$CHAINGUARD_HOME"/{hooks,projects,config,logs,backup,templates,memory}
#                                                                        ^^^^^^ NEU
```

### 7.4 Neue Dateien

```bash
# Zu kopierende Dateien erweitern

local files_to_copy=(
    # ... bestehende ...
    "mcp-server/chainguard/memory.py:chainguard/memory.py"
    "mcp-server/chainguard/embeddings.py:chainguard/embeddings.py"
    "mcp-server/chainguard/code_analyzer.py:chainguard/code_analyzer.py"
)
```

---

## 8. Speicher- und Performance-Anforderungen

### 8.1 Speicherbedarf

| Komponente | Größe |
|------------|-------|
| Embedding-Modell (all-MiniLM-L6-v2) | ~22 MB (einmalig) |
| ChromaDB SQLite pro Projekt | 5-50 MB (je nach Größe) |
| hnswlib Index pro Collection | ~10% der Embedding-Größe |

**Beispiel-Rechnung:**
- 500 Dateien × 3 Chunks/Datei = 1500 Dokumente
- 1500 × 384 dimensions × 4 bytes = ~2.3 MB Embeddings
- + Metadaten + Index ≈ **5-10 MB pro Projekt**

### 8.2 Performance

| Operation | Dauer (Beispiel) |
|-----------|------------------|
| Initiale Indexierung (500 Dateien) | 2-5 Minuten |
| Inkrementelles Update (1 Datei) | 100-500 ms |
| Semantische Query | 10-50 ms |
| Model laden (erster Start) | 1-3 Sekunden |

### 8.3 System-Anforderungen

| Ressource | Minimum | Empfohlen |
|-----------|---------|-----------|
| RAM | 512 MB frei | 1 GB frei |
| CPU | Any (x86/ARM) | Multi-Core |
| Disk | 100 MB | 500 MB |
| Python | 3.9+ | 3.11+ |

---

## 9. Sicherheit & Datenschutz

### 9.1 Lokale Verarbeitung

- **Kein Datenabfluss:** Alle Embeddings werden lokal erzeugt
- **Kein API-Key:** sentence-transformers läuft offline
- **Keine Telemetrie:** ChromaDB Telemetrie ist deaktiviert

```python
client = chromadb.PersistentClient(
    settings=Settings(anonymized_telemetry=False)  # Wichtig!
)
```

### 9.2 Sensible Daten

```python
# Patterns für sensible Daten (werden nicht indexiert)
SENSITIVE_PATTERNS = [
    r"password\s*=",
    r"api_key\s*=",
    r"secret\s*=",
    r"\.env",
    r"credentials",
]

def should_index_file(path: str) -> bool:
    """Prüft ob Datei indexiert werden soll."""
    return not any(
        re.search(pattern, path, re.I)
        for pattern in SENSITIVE_PATTERNS
    )
```

---

## 10. Implementierungs-Roadmap

### Phase 1: Core Memory (v5.1) ✅ COMPLETE
- [x] `memory.py` Modul mit ChromaDB-Integration
- [x] `embeddings.py` mit sentence-transformers
- [x] `chainguard_memory_init` Tool
- [x] `chainguard_memory_query` Tool
- [x] Installer-Erweiterung

### Phase 2: Integration (v5.2) ✅ COMPLETE
- [x] Automatisches Update bei `track`
- [x] Konsolidierung bei `finish`
- [x] `chainguard_memory_status` Tool
- [x] Hinweise bei `set_scope`
- [x] Smart Context Injection

### Phase 3: Erweiterte Features (v5.3) ✅ COMPLETE
- [x] Code-AST-Analyse mit tree-sitter (+ Regex-Fallback)
- [x] Beziehungs-Graph zwischen Dateien (FileRelation)
- [x] Automatische Architektur-Erkennung (MVC, Clean, Hexagonal, etc.)
- [x] Framework-Detection (Laravel, Django, React, Vue, Angular, etc.)
- [x] Export/Import von Memory (JSON, JSONL Formate)

**Phase 3 Module:**
- `ast_analyzer.py` - AST-Parsing mit tree-sitter, Regex-Fallback
- `architecture.py` - Architektur-Pattern und Framework-Erkennung
- `memory_export.py` - Export/Import mit Embeddings

**Phase 3 Tools:**
- `chainguard_analyze_code` - AST-Analyse von Dateien/Verzeichnissen
- `chainguard_detect_architecture` - Architektur und Framework erkennen
- `chainguard_memory_export` - Memory in JSON/JSONL exportieren
- `chainguard_memory_import` - Memory aus Export importieren
- `chainguard_list_exports` - Verfügbare Exports auflisten

### Phase 4: Deep Logic Summaries (v5.4) ✅ COMPLETE
- [x] Architecture Collection wird bei `memory_init` automatisch befüllt
- [x] `chainguard_detect_architecture` speichert in Memory
- [x] Layers und Design Patterns als separate Dokumente für bessere Suche
- [x] Tests für Architecture-Memory-Integration (5 neue Tests)
- [x] **NEU:** `code_summarizer.py` - Extrahiert menschenlesbare Code-Logik
- [x] **NEU:** `code_summaries` Collection für Deep Logic Summaries
- [x] **NEU:** `chainguard_memory_summarize` Tool für On-Demand-Summarization
- [x] **NEU:** Purpose-Inferenz aus Docstrings, Kommentaren und Naming-Conventions
- [x] **NEU:** 45 Tests für Code Summarizer

**Änderungen in v5.4:**
- `handlers.py`: `handle_memory_init` speichert jetzt Architecture automatisch
- `handlers.py`: `handle_detect_architecture` schreibt in Memory Collection
- `handlers.py`: `handle_memory_summarize` für Deep Logic Extraction
- `code_summarizer.py`: Neues Modul für menschenlesbare Code-Summaries
- `memory.py`: Neue Collection `code_summaries`
- `test_memory.py`: Neue TestArchitectureMemoryIntegration Klasse
- `test_code_summarizer.py`: 45 Tests für Code Summarizer

### Phase 5: Optimierung (v6.0) - GEPLANT
- [ ] Lazy Loading von Embeddings
- [ ] Batch-Processing für große Projekte
- [ ] Memory-Compression
- [ ] Multi-Projekt Memory-Sharing

---

## 11. Alternativen (evaluiert)

### 11.1 LanceDB statt ChromaDB

**Pro:**
- Schneller bei großen Datensätzen
- Bessere Kompression

**Contra:**
- Weniger Python-Integration
- Kleinere Community
- Komplexere Queries

**Entscheidung:** ChromaDB für v1 wegen Einfachheit

### 11.2 Vectorlite (SQLite Extension)

**Pro:**
- Nutzt bestehende SQLite-Infrastruktur
- Sehr leichtgewichtig

**Contra:**
- C-Extension kompliziert zu installieren
- Weniger Features

**Entscheidung:** Nicht für v1, evtl. später als Option

### 11.3 Ollama Embeddings

**Pro:**
- Bessere Qualität (nomic-embed-text)
- GPU-Beschleunigung

**Contra:**
- Ollama muss laufen
- Größerer Overhead

**Entscheidung:** Als optionale Alternative in v2

---

## 12. Zusammenfassung

Das Long-Term Memory System für Chainguard ermöglicht:

1. **Einmalige Indexierung** des gesamten Projekts
2. **Semantische Suche** ("Wo ist X?", "Wie funktioniert Y?")
3. **Automatische Updates** bei Dateiänderungen
4. **100% offline** - keine API, keine Cloud
5. **Minimaler Overhead** - ~50MB pro Projekt

**Technologie-Stack:**
- **ChromaDB** für Vektor-Speicherung
- **all-MiniLM-L6-v2** für Embeddings
- **SQLite** als Backend (via ChromaDB)

**Nächster Schritt:** Implementation von Phase 1 (Core Memory)

---

## Quellen

- [ChromaDB - Open-source Vector Database](https://github.com/chroma-core/chroma)
- [all-MiniLM-L6-v2 - Lokales Embedding Model](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2)
- [Vectorlite - SQLite Vector Extension](https://github.com/1yefuwang1/vectorlite)
- [Sentence Transformers Documentation](https://www.sbert.net/)
- [ChromaDB Python Documentation](https://docs.trychroma.com/)
