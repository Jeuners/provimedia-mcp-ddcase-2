# Chainguard v5.4.0 - Nutzungsanleitung

## Schnellstart

Nach der Installation stehen dir folgende MCP-Tools in Claude Code zur Verfügung:

### 1. Task starten (PFLICHT)

```
chainguard_set_scope(
    description="User-Login System implementieren",
    modules=["src/auth/*", "tests/auth/*"],
    acceptance_criteria=["Login funktioniert", "Session wird gespeichert", "Tests grün"]
)
chainguard_set_phase(phase="implementation")
```

### 2. Änderungen tracken (automatische Syntax-Prüfung)

```
chainguard_track(file="src/AuthController.php", ctx="🔗")
```

**WICHTIG (v4.6+):** Immer `ctx="🔗"` mitgeben! Das Tool:
- Trackt die Dateiänderung
- Prüft automatisch PHP/JS/JSON/Python/TypeScript Syntax
- Warnt bei Out-of-Scope Dateien
- Meldet Fehler sofort
- Refresht Kontext falls verloren

### 3. Status prüfen

```
chainguard_status(ctx="🔗")
```

Zeigt ultra-kompakte Statuszeile:
`projektname|impl|F5/V3 [V!8] Login System impl...`

### 4. Task abschließen (2-Schritt-Prozess)

```
chainguard_finish                    # Schritt 1: Zeigt Impact-Check
chainguard_finish(confirmed=true)    # Schritt 2: Schließt ab
```

## v5.4 - Modulare Architektur & Long-Term Memory

Das Chainguard Package besteht aus **20 Modulen**:

### Core Module
| Modul | Zweck |
|-------|-------|
| `config.py` | Konstanten, Enums, Konfiguration |
| `models.py` | Datenmodelle (ScopeDefinition, ProjectState) |
| `project_manager.py` | Projekt-State-Management |
| `handlers.py` | Handler-Registry mit Tool-Handlern |
| `tools.py` | MCP Tool-Definitionen |
| `server.py` | MCP Server Setup |

### Validation & Analysis
| Modul | Zweck |
|-------|-------|
| `validators.py` | Syntax-Validierung (PHP, JS, JSON, Python, TS) |
| `analyzers.py` | Code-Analyse und Impact-Analyse |
| `checklist.py` | Async Checklist-Ausführung |

### Testing & HTTP
| Modul | Zweck |
|-------|-------|
| `test_runner.py` | Test-Ausführung (PHPUnit, Jest, pytest) |
| `http_session.py` | HTTP Session-Management |

### Memory System (v5.1+)
| Modul | Zweck |
|-------|-------|
| `memory.py` | Long-Term Memory mit ChromaDB |
| `embeddings.py` | Embedding Engine (sentence-transformers) |

### Phase 3 Features (v5.3+)
| Modul | Zweck |
|-------|-------|
| `ast_analyzer.py` | AST-basierte Code-Analyse (tree-sitter Fallback: Regex) |
| `architecture.py` | Architektur-Pattern-Erkennung (MVC, Clean, etc.) |
| `memory_export.py` | Memory Export/Import (JSON, JSONL) |

### Phase 4 Features (v5.4+)
| Modul | Zweck |
|-------|-------|
| `code_summarizer.py` | Deep Logic Extraction - menschenlesbare Code-Summaries |

### Utilities
| Modul | Zweck |
|-------|-------|
| `cache.py` | LRU Cache, TTL-LRU Cache, Git Cache |
| `history.py` | Error Memory System |
| `db_inspector.py` | Database Schema Inspection |
| `utils.py` | Path-Sanitization, Hilfsfunktionen |

**v5.4 Highlights:**
- **Deep Logic Summaries**: Code-Logik wird in menschenlesbaren Summaries gespeichert
- **Neue Collection**: `code_summaries` für semantische Suche nach Code-Funktionalität
- **Neues Tool**: `chainguard_memory_summarize` für On-Demand-Summarization

**v5.3 Highlights:**
- **AST-Analyse**: Tree-sitter für präzises Code-Parsing mit Regex-Fallback
- **Architektur-Erkennung**: MVC, MVVM, Clean Architecture, Hexagonal, Layered, API-first
- **Framework-Detection**: Laravel, Django, React, Vue, Angular, FastAPI, und mehr
- **Memory Export/Import**: JSON und JSONL Formate mit optionaler Komprimierung

### Installationspfad

```
~/.chainguard/
├── chainguard/           # v4.7 Modulares Package
│   ├── __init__.py
│   ├── config.py
│   ├── models.py
│   └── ...
├── chainguard_mcp.py     # Wrapper (ruft chainguard.server auf)
├── hooks/
└── projects/
```

## chainguard_analyze

Analyse einer Datei vor dem Review:

```
chainguard_analyze(target="src/mcp-server/chainguard_mcp.py")
```

**Output:**
```
📊 **chainguard_mcp.py**
├── 2976 LOC (2500 Code) | 45 Funktionen | 12 Klassen
├── Komplexität: ●●●○○ (3/5)
├── Patterns: mcp-server, async-io, caching, file-io
├── Hotspots: call_tool:2262, get_async:1173
└── TODOs: 2 gefunden

**Checkliste [mcp-server, async-io]:**
□ Async/Await korrekt verwendet?
□ Error Handling in Tool-Handlern?
□ Timeouts für externe Calls?
```

## v4.6 - Context-Check Feature

Der `ctx="🔗"` Parameter dient als "Canary":

```python
# Mit Kontext - kurze Response
chainguard_status(ctx="🔗")
→ "proj|impl|5F ✓"

# Ohne Kontext (vergessen) - Auto-Refresh!
chainguard_status()
→ "proj|impl|5F ✓

⚠️ CHAINGUARD CONTEXT REFRESH
Wichtige Regeln: ctx='🔗' bei jedem Aufruf..."
```

**Immer mitgeben bei:** `chainguard_track`, `chainguard_status`

## v4.5 - Batch-Tracking & Erweiterte Validierung

### Mehrere Dateien auf einmal tracken

```
chainguard_track_batch(
    files=["src/a.py", "src/b.py", "src/c.py"],
    action="edit"
)
```

### Unterstützte Syntax-Validierung

| Sprache | Prüfung |
|---------|---------|
| PHP | `php -l` |
| JavaScript | `node --check` |
| JSON | Python json.load() |
| Python | `python3 -m py_compile` |
| TypeScript/TSX | `npx tsc --noEmit` |

## Alle verfügbaren Tools

### Core Tools

| Tool | Beschreibung |
|------|--------------|
| `chainguard_set_scope` | Task-Scope definieren mit Kriterien |
| `chainguard_track` | Dateiänderung tracken + Syntax-Check |
| `chainguard_track_batch` | Mehrere Dateien auf einmal tracken |
| `chainguard_status` | Ultra-kompakte Statuszeile |
| `chainguard_set_phase` | Phase setzen |
| `chainguard_finish` | 2-Schritt-Abschluss mit Impact-Check |
| `chainguard_analyze` | **NEU v4.7:** Code-Analyse Pre-Flight |

### Validierung

| Tool | Beschreibung |
|------|--------------|
| `chainguard_validate` | PASS/FAIL speichern |
| `chainguard_check_criteria` | Kriterien als erfüllt markieren |
| `chainguard_run_checklist` | Automatische Checks ausführen |

### HTTP Testing

| Tool | Beschreibung |
|------|--------------|
| `chainguard_set_base_url` | Base URL setzen |
| `chainguard_test_endpoint` | HTTP Endpoint testen |
| `chainguard_login` | Einloggen und Session speichern |
| `chainguard_clear_session` | Session löschen |

### Utility

| Tool | Beschreibung |
|------|--------------|
| `chainguard_context` | Voller Kontext (sparsam nutzen!) |
| `chainguard_alert` | Problem markieren |
| `chainguard_clear_alerts` | Alerts bestätigen |
| `chainguard_projects` | Alle Projekte listen |
| `chainguard_config` | Konfiguration |

### Long-Term Memory (v5.1+)

| Tool | Beschreibung |
|------|--------------|
| `chainguard_memory_init` | Projekt-Memory initialisieren |
| `chainguard_memory_query` | Semantische Suche im Memory |
| `chainguard_memory_status` | Memory-Status und Statistiken |
| `chainguard_memory_update` | Memory manuell aktualisieren |
| `chainguard_memory_summarize` | **NEU v5.4:** Deep Logic Summaries generieren |

### AST & Architecture Analysis (v5.3+)

| Tool | Beschreibung |
|------|--------------|
| `chainguard_analyze_code` | AST-basierte Code-Analyse (Funktionen, Klassen, Imports) |
| `chainguard_detect_architecture` | Architektur-Pattern und Framework erkennen |

### Memory Export/Import (v5.3+)

| Tool | Beschreibung |
|------|--------------|
| `chainguard_memory_export` | Memory exportieren (JSON/JSONL) |
| `chainguard_memory_import` | Memory importieren |
| `chainguard_list_exports` | Verfügbare Exports auflisten |

## Typischer Workflow

```
1. Task beginnen
   → chainguard_set_scope(description="...", acceptance_criteria=[...])
   → chainguard_set_phase(phase="implementation")

2. Arbeiten
   → Code schreiben
   → chainguard_track(file="...", ctx="🔗") nach jeder Änderung

3. Kriterien erfüllen
   → chainguard_check_criteria(criterion="...", fulfilled=true)

4. Task abschließen (2-Schritt!)
   → chainguard_finish                 # Impact-Check
   → chainguard_finish(confirmed=true) # Abschließen
```

## Pattern-Erkennung im Impact-Check

Der Impact-Check erkennt automatisch:

| Datei | Hinweis |
|-------|---------|
| CLAUDE.md | Template auch aktualisieren? |
| chainguard_mcp.py | Nach ~/.chainguard/ kopieren! |
| install.sh | Versionsnummer konsistent? |
| Controller.php | Tests vorhanden? |
| *.test.ts | Implementierung auch geändert? |
| /migrations/ | Model-Änderungen konsistent? |

## Konfiguration

Globale Config: `~/.chainguard/config.json`

```json
{
  "validation_reminder_threshold": 8,
  "max_log_entries": 50,
  "cleanup_inactive_days": 30
}
```

## Performance

- **Async I/O** - Non-blocking Dateioperationen
- **Write Debouncing** - 90% weniger Disk-Writes
- **LRU Cache** - Max 20 Projekte im Speicher
- **Git Caching** - 5min TTL für Git-Calls

## Migration von v4.x auf v4.8

Keine manuelle Migration nötig! Der Installer:
1. Erkennt das modulare Package automatisch
2. Erstellt einen Wrapper `chainguard_mcp.py`
3. Erhält alle bestehenden Projekt-States

Falls du manuell aktualisieren willst:
```bash
# Aus dem Chainguard Projekt-Verzeichnis:
cp src/mcp-server/chainguard_mcp.py ~/.chainguard/
cp -r src/mcp-server/chainguard ~/.chainguard/
```

## v5.4.0 Changelog (Phase 4)

- **Deep Logic Extraction**: `code_summarizer.py` extrahiert menschenlesbare Code-Logik
- **Code-Purpose-Inferenz**: Erkennt Zweck aus Docstrings, Kommentaren und Naming-Conventions
- **Neue Collection**: `code_summaries` für semantische Suche nach Code-Funktionalität
- **Neues Tool**: `chainguard_memory_summarize` für On-Demand-Summarization
- **Memory-Init Integration**: Summaries werden automatisch bei `memory_init` erstellt

## v5.3.0 Changelog (Phase 3)

- **AST-Analyse**: `ast_analyzer.py` mit tree-sitter und Regex-Fallback
- **Architektur-Erkennung**: `architecture.py` erkennt MVC, Clean, Hexagonal, etc.
- **Framework-Detection**: Laravel, Django, React, Vue, Angular, und mehr
- **Memory Export/Import**: `memory_export.py` für JSON/JSONL Formate
- **Neue Tools**: `chainguard_analyze_code`, `chainguard_detect_architecture`, `chainguard_memory_export`, `chainguard_memory_import`, `chainguard_list_exports`

## v5.2.0 Changelog (Phase 2)

- **Memory Integration**: Automatisches Update bei `track`, Konsolidierung bei `finish`
- **Smart Context Injection**: Relevanter Kontext bei `set_scope`
- **Memory Status**: `chainguard_memory_status` Tool

## v5.1.0 Changelog (Phase 1)

- **Long-Term Memory**: ChromaDB + sentence-transformers Integration
- **Projekt-Memory**: Semantische Suche im Projekt-Wissen
- **Memory Tools**: `chainguard_memory_init`, `chainguard_memory_query`, `chainguard_memory_update`

## v5.0.0 Changelog

- **Task-Mode System**: programming, content, devops, research, generic Modi
- **Mode-spezifische Tools**: Word-Count, Chapter-Tracking, Command-Logging, etc.
- **Context Injection**: Automatische Modus-Hinweise
