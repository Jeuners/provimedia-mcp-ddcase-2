<!-- CHAINGUARD-MANDATORY-START v5.3.0 -->

# ================================================
# STOP - LIES DAS ZUERST!
# ================================================
#
# BEVOR DU IRGENDETWAS ANDERES TUST:
#
#     chainguard_set_scope(
#         description="...",
#         working_dir="...",
#         acceptance_criteria=[...]
#     )
#
# ALLE anderen Chainguard-Tools sind BLOCKIERT
# bis du set_scope aufgerufen hast!
#
# v5.3: HARD ENFORCEMENT + Task-Mode System
# BLOCKIERT wenn DB-Schema nicht geprüft wurde!
#
# ================================================

## CHAINGUARD v5.3 - PFLICHT-ANWEISUNGEN (HARD ENFORCEMENT!)

| # | PFLICHT-AKTION | WANN |
|---|----------------|------|
| 1 | `chainguard_set_scope(...)` | **ALLERERSTE AKTION bei jedem Task!** |
| 2 | `chainguard_db_connect() + chainguard_db_schema()` | **VOR jeder DB/Schema-Arbeit! (BLOCKIERT sonst!)** |
| 3 | `chainguard_track(file="...", ctx="...")` | Nach JEDER Dateiänderung |
| 4 | `chainguard_test_endpoint(...)` | **Bei Web-Projekten: VOR finish!** |
| 5 | `chainguard_finish(confirmed=True)` | Am Task-Ende |

> **v5.3 Features:** Task-Mode System, Long-Term Memory, AST-Analyse, Architektur-Erkennung

### Minimaler Workflow

```python
# 1. ZUERST - Scope setzen (PFLICHT!)
chainguard_set_scope(description="Was du baust", working_dir="/pfad")

# 2. BEI DB-ARBEIT - Schema prüfen (BLOCKIERT SONST!)
chainguard_db_connect(host="localhost", user="root", password="...", database="mydb")
chainguard_db_schema()  # Zeigt alle Tabellen + Spalten!

# 3. Arbeiten + Tracken
# ... Edit/Write ...
chainguard_track(file="...", ctx="...")

# 4. Bei Web-Projekten (PHP/JS/TS): HTTP-Tests!
chainguard_set_base_url(base_url="http://localhost:8888/app")
chainguard_test_endpoint(url="/geänderte-route", method="GET")

# 5. Abschliessen
chainguard_finish(confirmed=True)
```

### Context-Canary: `ctx="..."`

Bei JEDEM Chainguard-Aufruf `ctx="..."` mitgeben! Fehlt er -> Kontext verloren -> Auto-Refresh.
<!-- CHAINGUARD-MANDATORY-END -->


























# CHAINGUARD v5.0.0 - Task-Mode System + Hard Enforcement

> **🔴 WICHTIG - Modulare Struktur:**
> Der MCP-Server läuft von `~/.chainguard/` - NICHT aus diesem Projekt!
>
> **Bei Updates:** Siehe **[SYNCINSTALL.md](SYNCINSTALL.md)** für die vollständige Sync-Checkliste!
>
> **Quick-Sync:**
> ```bash
> rm -rf ~/.chainguard/chainguard && cp -r src/mcp-server/chainguard ~/.chainguard/ && \
> cp src/mcp-server/chainguard_mcp.py ~/.chainguard/ && \
> cp src/hooks/chainguard_enforcer.py ~/.chainguard/hooks/ && \
> cp src/templates/CHAINGUARD.md.block ~/.chainguard/templates/
> ```
> Danach Claude Code neu starten!

## Modulare Architektur (v4.12)

```
~/.chainguard/
├── chainguard_mcp.py      ← Wrapper (importiert Package)
└── chainguard/            ← Modulares Package
    ├── __init__.py        (Exports)
    ├── server.py          (MCP Server Setup)
    ├── handlers.py        (Handler-Registry Pattern - testbar!)
    ├── tools.py           (Tool Definitionen)
    ├── models.py          (Dataclasses)
    ├── project_manager.py (Projekt-CRUD)
    ├── validators.py      (Syntax-Checks, async JSON)
    ├── analyzers.py       (Code-Analyse)
    ├── http_session.py    (HTTP/Login mit TTL-Cache)
    ├── test_runner.py     (Test-Ausführung, v4.10)
    ├── history.py         (Error Memory System, v4.11)
    ├── db_inspector.py    (Database Schema Inspector, v4.12)
    ├── cache.py           (LRU + TTL-LRU Cache)
    ├── checklist.py       (Async Checklist-Ausführung)
    ├── config.py          (Konstanten)
    └── utils.py           (Hilfsfunktionen)
```

**Vorteile:**
- Einzelne Module lesbar (nicht 31K+ Tokens)
- Handler-Registry Pattern: Testbar, erweiterbar
- Klare Trennung der Verantwortlichkeiten

**Design-Prinzip:** Minimaler Kontextverbrauch, maximaler Nutzen, maximale Performance.

## Unit-Tests (PFLICHT bei neuen Features!)

> **Bei jeder Änderung am MCP-Server müssen die Tests erweitert/angepasst werden!**

```bash
# Tests ausführen
cd src/mcp-server && python3 -m pytest tests/ -v

# Einzelnes Modul testen
python3 -m pytest tests/test_cache.py -v
```

| Test-Datei | Testet | Anzahl |
|------------|--------|--------|
| `test_cache.py` | LRUCache, TTLLRUCache, GitCache | 19 |
| `test_models.py` | ScopeDefinition, ProjectState | 19 |
| `test_test_runner.py` | TestConfig, TestResult, OutputParser | 28 |
| `test_history.py` | HistoryManager, ErrorEntry, Auto-Suggest | 29 |
| `test_db_inspector.py` | DBConfig, DBInspector, SchemaInfo | 26 |
| `test_task_mode.py` | TaskMode, ModeFeatures, Auto-Detection | 32 |

**Checkliste für neue Features:**
1. Neues Modul? → Neue `tests/test_<module>.py` erstellen
2. Neue Klasse/Funktion? → Tests in bestehende Datei hinzufügen
3. Bug-Fix? → Regression-Test hinzufügen
4. **Alle 399 Tests müssen grün sein vor Sync!**

Siehe **[docs/TESTING.md](docs/TESTING.md)** für vollständige Dokumentation.

## v5.0.0 Features (NEU!)

### Task-Mode System - Flexibel für alle Aufgaben!

Das fundamentale Problem: Chainguard war zu Code-zentrisch. Syntax-Validierung, DB-Schema-Checks, HTTP-Tests - alles sinnvoll für Programmierung, aber störend bei:
- **Bücher schreiben** → Keine Syntax-Checks für Markdown!
- **Server verwalten** → Keine DB-Pflicht bei WordPress CLI!
- **Recherche** → Keine HTTP-Tests bei Analyse-Tasks!

**v5.0 löst das durch den Task-Mode:**

```
┌─────────────────────────────────────────────────┐
│  User: "Schreibe Kapitel 3 meines Buches"       │
│       ↓                                          │
│  Claude (LLM) liest Tool-Description            │
│       ↓                                          │
│  LLM erkennt: Buch → CONTENT Modus              │
│       ↓                                          │
│  chainguard_set_scope(mode="content", ...)      │
│       ↓                                          │
│  - Keine Syntax-Blockaden ✓                      │
│  - Word-Count verfügbar ✓                        │
│  - Kapitel-Tracking ✓                            │
└─────────────────────────────────────────────────┘
```

### Task-Modi im Überblick

| Modus | Features ON | Features OFF |
|-------|-------------|--------------|
| **programming** | Syntax-Check, DB-Pflicht, HTTP-Tests, Scope-Enforcement | - |
| **content** | Word-Count, Chapter-Tracking, File-Tracking | Syntax, DB, HTTP, Blockaden |
| **devops** | Command-Logging, Checkpoints, Health-Checks, Config-Validation | Code-Syntax, DB-Pflicht |
| **research** | Source-Tracking, Fact-Indexing | Syntax, DB, HTTP, Blockaden |
| **generic** | File-Tracking | Alles andere |

### Automatische Modus-Erkennung

Der Modus wird **vom LLM entschieden** (nicht deterministisch!):

1. **Tool-Description Injection**: Claude bekommt Modus-Optionen in der Tool-Beschreibung
2. **Semantisches Verstehen**: LLM erkennt "Kapitel schreiben" → content, "Server einrichten" → devops
3. **Fallback Auto-Detection**: Keywords + Dateimuster als Hinweis

```python
# LLM entscheidet basierend auf Kontext:
chainguard_set_scope(
    description="WordPress auf Server einrichten",
    mode="devops"  # LLM wählt basierend auf "WordPress", "Server"
)
```

### Neue Mode-spezifische Tools

#### Content Mode
| Tool | Zweck |
|------|-------|
| `chainguard_word_count` | Zeigt Wort-Zählung für aktuellen Scope |
| `chainguard_track_chapter` | Trackt Kapitel-Status (draft/review/done) |

#### DevOps Mode
| Tool | Zweck |
|------|-------|
| `chainguard_log_command` | Protokolliert ausgeführte CLI-Commands |
| `chainguard_checkpoint` | Erstellt Checkpoint vor kritischen Änderungen |
| `chainguard_health_check` | Prüft Endpoints auf Verfügbarkeit |

#### Research Mode
| Tool | Zweck |
|------|-------|
| `chainguard_add_source` | Fügt Quelle mit Relevanz hinzu |
| `chainguard_index_fact` | Indexiert Fakt mit Konfidenz-Level |
| `chainguard_sources` | Zeigt alle gesammelten Quellen |
| `chainguard_facts` | Zeigt alle indexierten Fakten |

### Context Injection per Mode

Jeder Modus injiziert spezifische Anweisungen:

```
────────────────────────────────────────
📝 CONTENT-MODUS - Flexibles Schreiben:

- Keine Syntax-Validierung (Texte, nicht Code)
- Keine Blockaden - freies kreatives Arbeiten
- Word-Count: chainguard_word_count()

Tipp: Nutze acceptance_criteria als Kapitel-Checkliste!
────────────────────────────────────────
```

### Migration von v4.x

**Keine Änderung nötig!** Bestehende Workflows funktionieren weiterhin:
- Default-Mode ist `programming`
- Alle v4.x Tools unverändert
- Backwards-kompatibel

---

## v4.19.0 Features

### HARD ENFORCEMENT via PreToolUse Hook
Das fundamentale Problem von v4.16 und früher war: Claude konnte Warnungen ignorieren und Regeln umgehen.

**v4.19 löst das durch echte BLOCKADEN + Auto-Marker:**

```
┌─────────────────────────────────────────────────┐
│  User Request                                    │
│       ↓                                          │
│  Claude will Edit aufrufen                       │
│       ↓                                          │
│  ┌───────────────────────────────────────────┐  │
│  │ PreToolUse Hook (chainguard_enforcer.py)  │  │
│  │ → Liest enforcement-state.json            │  │
│  │ → Prüft: DB-Schema geladen?               │  │
│  │ → Prüft: Blocking Alerts?                 │  │
│  │ → exit(2) wenn nicht OK → BLOCKIERT!      │  │
│  └───────────────────────────────────────────┘  │
│       ↓ (nur wenn Hook OK)                       │
│  Edit wird ausgeführt                            │
└─────────────────────────────────────────────────┘
```

### Neue Dateien

| Datei | Zweck |
|-------|-------|
| `hooks/chainguard_enforcer.py` | PreToolUse Hook - blockiert Edit/Write |
| `enforcement-state.json` | Minimaler State für Hook (vom MCP geschrieben) |

### Blockade-Regeln

1. **Schema-Dateien ohne DB-Inspektion**: Edit/Write auf `.sql`, `migration`, etc. wird BLOCKIERT bis `chainguard_db_schema()` aufgerufen wurde
2. **Blocking Alerts**: Edit/Write wird BLOCKIERT wenn nicht-bestätigte blocking Alerts existieren

### Hook-Konfiguration

Der Installer konfiguriert automatisch:
```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [{"type": "command", "command": "python3 ~/.chainguard/hooks/chainguard_enforcer.py"}]
      }
    ]
  }
}
```

---

## v4.12.0 Features

### Database Inspector - Keine SQL-Fehler mehr!
- **Live-Schema-Abfrage**: Verifizierte Feldnamen statt Raten
- **MySQL/PostgreSQL/SQLite**: Alle gängigen Datenbanken unterstützt
- **TTL-Cache**: Schema wird 5 Minuten gecacht (konfigurierbar)
- **Token-effizient**: Kompakte Darstellung (~50-100 Tokens)
- **Scope-gebunden**: Credentials nur im Memory, verschwinden mit Scope

### DB-Inspector Workflow

```python
# 1. Datenbankverbindung herstellen
chainguard_db_connect(
    host="localhost",
    user="root",
    password="root",
    database="knowledge",
    db_type="mysql"
)
# → ✓ Connected to knowledge (mysql 8.0.32)

# 2. Schema abrufen
chainguard_db_schema()
# → 📊 Database: knowledge (mysql 8.0.32)
#
#   users (4 cols, ~5 rows)
#   ├─ id: INT PK AUTO
#   ├─ username: VARCHAR(255) UNIQUE
#   ├─ email: VARCHAR(255)
#   └─ created_at: DATETIME
#
#   articles (6 cols, ~50 rows)
#   ├─ id: INT PK AUTO
#   ├─ title: VARCHAR(255)
#   ├─ content: TEXT
#   ├─ author_id: INT FK→users.id
#   └─ created_at: DATETIME

# 3. Jetzt korrekter SQL-Query:
$stmt = $pdo->prepare("SELECT id, username FROM users");
#                              ^^^^^^^^
#                              Exakter Feldname - kein Raten!

# 4. Einzelne Tabelle mit Sample-Daten
chainguard_db_table(table="users", sample=True)
# → Zeigt 5 Beispielzeilen
```

### Neue Tools (v4.12)

| Tool | Zweck |
|------|-------|
| `chainguard_db_connect` | Datenbankverbindung herstellen |
| `chainguard_db_schema` | Schema aller Tabellen abrufen (gecacht) |
| `chainguard_db_table` | Details einer Tabelle + Sample-Daten |
| `chainguard_db_disconnect` | Verbindung trennen, Cache löschen |

## v4.11.0 Features

### Error Memory System - Lerne aus Fehlern
- **Automatisches History-Log**: Jede Änderung wird dokumentiert (JSONL, append-only)
- **Error-Index**: Fehler werden indexiert für schnelles Nachschlagen
- **Auto-Suggest**: Bei bekannten Fehlern wird automatisch die Lösung vorgeschlagen
- **Token-effizient**: Kostet nur bei Fehlern etwas (0 Token bei Erfolg)

### Auto-Suggest Workflow

```python
# 1. Fehler tritt auf
chainguard_track(file="UserController.php", ctx="🔗")
→ "✗ PHP Syntax: unexpected }

   💡 Similar error fixed before:
      - *Controller.php (2d ago)
        → Missing semicolon before }"

# 2. Nach dem Fix - Resolution dokumentieren
chainguard_learn(resolution="Missing semicolon before closing brace")
→ "✓ Resolution dokumentiert"

# 3. Später: Fehler-History durchsuchen
chainguard_recall(query="php syntax Controller")
→ "🔍 2 Ergebnisse:
   1. *Controller.php - unexpected } → Missing semicolon"
```

### Neue Tools (v4.11)

| Tool | Zweck |
|------|-------|
| `chainguard_recall` | Durchsucht Error-History nach ähnlichen Problemen |
| `chainguard_history` | Zeigt Change-Log für aktuellen Scope |
| `chainguard_learn` | Dokumentiert einen Fix für zukünftige Auto-Suggests |

## v4.10.0 Features

### Test Runner - Technologie-agnostisch
- **Beliebiges Framework**: PHPUnit, Jest, pytest, mocha, vitest, etc.
- **Benutzer-definierter Command**: Flexibel konfigurierbar
- **Auto-Detection**: Erkennt Framework anhand des Outputs
- **Fehler-Tracking**: Speichert Ergebnisse, erstellt Alerts bei Failures

### Test Runner Workflow

```python
# 1. Einmalig konfigurieren (pro Projekt)
chainguard_test_config(
    command="./vendor/bin/phpunit",
    args="tests/ --colors=never"
)

# 2. Tests ausführen
chainguard_run_tests()
→ "✓ phpunit: 23/23 tests passed
   Duration: 4.2s"

# 3. Bei Fehler
chainguard_run_tests()
→ "✗ phpunit: 22/23 tests (1 failed)
   Duration: 3.8s

   Errors:
   • FAILED: LoginTest::testInvalidPassword
   • Expected 401, got 200"

# 4. Status prüfen
chainguard_test_status()
→ "Test Status: ✗ 22/23 (2m ago)"
```

### Unterstützte Frameworks

| Framework | Detection Pattern |
|-----------|------------------|
| PHPUnit | `OK (X tests)`, `FAILURES!` |
| Jest | `Tests: X passed, Y total` |
| pytest | `X passed`, `X failed` |
| mocha | `X passing`, `X failing` |
| vitest | `X passed`, `X failed` |
| Generisch | Exit-Code 0 = PASS |

## v4.8.0 Features

### Handler-Registry Pattern
- **Decorator-basierte Handler**: `@handler.register("tool_name")`
- **Testbar**: Jeder Handler ist eine separate Funktion
- **Erweiterbar**: Neue Tools einfach hinzufügen

### TTL-LRU Cache
- **Memory-bounded + Zeit-limitiert**: Items verfallen nach TTL
- **Generic**: `TTLLRUCache[T]` für beliebige Typen
- **Cleanup**: Automatische Bereinigung abgelaufener Einträge

### Async Checklist-Ausführung
- **Parallele Ausführung**: `run_all_async()` führt Checks parallel aus
- **Non-blocking**: `asyncio.create_subprocess_exec()`
- **Schneller**: N Checks gleichzeitig statt sequentiell

### Memory-safe HTTP Sessions
- **TTLLRUCache**: Max 50 Sessions, 24h TTL
- **Kein Memory Leak**: Alte Sessions werden automatisch entfernt

### Async JSON-Validierung
- **aiofiles**: JSON-Dateien werden async gelesen
- **Non-blocking**: Event Loop wird nicht blockiert

## v4.6.0 Features (NEU!)

### Context-Check mit Canary-Parameter
- **Problem**: Claude Code verliert manchmal den CLAUDE.md Kontext bei langen Sessions
- **Lösung**: `ctx="🔗"` Parameter als "Canary" - wenn er fehlt, ist der Kontext verloren
- **Auto-Refresh**: MCP gibt automatisch die wichtigsten Regeln zurück wenn ctx fehlt
- **Selbstheilend**: Claude lernt die Regeln neu und gibt ctx wieder mit

**So funktioniert's:**
```python
# Mit Kontext - kurze Response
chainguard_status(ctx="🔗")
→ "proj|impl|5F ✓"

# Ohne Kontext (Canary fehlt) - Auto-Refresh!
chainguard_status()
→ "proj|impl|5F ✓

⚠️ CHAINGUARD CONTEXT REFRESH
Wichtige Regeln: ctx='🔗' bei jedem Aufruf..."
```

## v4.5.0 Features

### Python & TypeScript Syntax-Validierung
- **Python**: `chainguard_track` validiert jetzt `.py` Dateien mit `python3 -m py_compile`
- **TypeScript/TSX**: `.ts` und `.tsx` Dateien werden mit `npx tsc --noEmit` geprüft
- Fehler werden sofort gemeldet - nicht erst im Browser/Runtime

### Batch-Tracking für mehrere Dateien
```python
chainguard_track_batch(files=["a.py", "b.ts", "c.php"])
# → Effizienter als 3x chainguard_track
# → Validiert alle Dateien, zeigt Zusammenfassung
```

### Präzisere Impact-Patterns
- **Keine False-Positives mehr**: "test" matched nicht mehr "latest.php"
- **Match-Types**: exact, suffix, prefix, contains
- **Mehr Patterns**: TypeScript types, Docker, package.json, etc.

### Konstanten statt Magic Numbers
- Alle Limits jetzt als Konstanten definiert (MAX_CHANGED_FILES, etc.)
- Bessere Wartbarkeit und Konfigurierbarkeit

### Phase-Enum
- Type-safe Phases: `Phase.PLANNING`, `Phase.IMPLEMENTATION`, etc.
- Backward-compatible (String-Serialisierung)

## v4.4.0 Features

### Scope-Optimierung für lange Descriptions
- **Empfohlenes Limit**: Description max 500 Zeichen
- **Warnung**: Bei langer Description automatischer Strukturierungs-Hinweis
- **Token-Sparend**: `chainguard_context` zeigt nur 200 Zeichen Preview
- **Keine LLM-API nötig**: Alles reine Python-String-Logik

**Best Practice für komplexe Projekte:**
```python
# NICHT SO:
description="500+ Wörter detaillierte Beschreibung..."

# BESSER SO:
chainguard_set_scope(
    description="E-Commerce mit 7 Phasen",  # Kurz!
    acceptance_criteria=[
        "Phase 1: Auth mit 2FA",
        "Phase 2: Produktkatalog",
        "Phase 3: Warenkorb",
        # ... Details als checkbare Kriterien
    ]
)
```

## v4.3.1 Features

### 2-Schritt-Finish mit Impact-Check
- **`chainguard_finish`** - Zeigt erst Impact-Check mit geänderten Dateien
- **Pattern-Erkennung** - Erkennt automatisch vergessene Updates:
  - CLAUDE.md → Template auch aktualisieren?
  - chainguard/*.py → Nach ~/.chainguard/chainguard/ kopieren?
  - Controller.php → Tests vorhanden?
- **`chainguard_finish(confirmed=true)`** - Bestätigt und schließt ab
- Mit `force=true` überschreibbar

### Warnungen bei validate/set_phase
- `chainguard_validate(status="PASS")` warnt wenn Kriterien offen
- `chainguard_set_phase(phase="done")` warnt wenn nicht alles erfüllt

## v4.2.0 Features

### Automatische Syntax-Validierung
- `chainguard_track` validiert jetzt **automatisch PHP/JS/JSON**
- Fehler werden **sofort** erkannt - nicht erst im Browser
- `php -l` für PHP, `node --check` für JS

### HTTP Endpoint-Testing mit Sessions
- `chainguard_set_base_url` - Base URL setzen
- `chainguard_test_endpoint` - Endpoints testen mit Session-Support
- `chainguard_login` - Einloggen und Session speichern
- Erkennt automatisch Auth-Anforderungen (401, 403, Login-Redirect)

## v4.1.2 Fixes

- **Full Async Read** - list_all_projects_async() komplett non-blocking
- **Async Resource** - read_resource() nutzt jetzt async

## v4.1.1 Fixes

- **Thread-safe Lock Init** - Race Condition bei AsyncFileLock behoben
- **Full Async I/O** - path.exists(), mkdir() jetzt auch async
- **Memory Limit** - out_of_scope_files auf 20 begrenzt

## v4.1 Performance-Upgrades

- **True Async I/O** - Non-blocking file operations mit aiofiles
- **Write Debouncing** - 500ms Batching, ~90% weniger Disk-Writes
- **LRU Cache** - Memory-bounded (max 20 Projekte)
- **Git Call Caching** - 5min TTL, vermeidet redundante Subprocess-Calls
- **Path Sanitization** - Security-Hardening gegen Path-Traversal

## Workflow

### 1. Task starten (mit Mode!)
```python
# Programming (Standard - Code, Bugs, Features)
chainguard_set_scope(
  description="Feature X implementieren",
  mode="programming",                      # Optional: Default
  modules=["src/feature/*.ts"],
  acceptance_criteria=["Tests grün", "Docs aktualisiert"]
)

# Content (Bücher, Artikel, Dokumentation)
chainguard_set_scope(
  description="Kapitel 3 schreiben",
  mode="content",
  acceptance_criteria=["Kapitel 3 fertig", "5000 Wörter"]
)

# DevOps (Server, WordPress, CLI)
chainguard_set_scope(
  description="WordPress einrichten",
  mode="devops",
  acceptance_criteria=["Site live", "SSL aktiv"]
)

chainguard_set_phase(phase="implementation")
```

### 2. Arbeiten (Tracking mit Auto-Validierung)
```
# Nach Edits - validiert automatisch PHP/JS/JSON!
# WICHTIG: ctx="🔗" immer mitgeben!
chainguard_track(file="app/Http/Controllers/UserController.php", ctx="🔗")
```

**NEU in v4.2:** `chainguard_track` führt jetzt **automatisch Syntax-Checks** durch:
- **PHP**: `php -l` - findet Parse Errors sofort
- **JavaScript**: `node --check` - findet Syntax Errors
- **JSON**: Validiert JSON-Struktur

```
# Beispiel: PHP Fehler wird sofort erkannt
chainguard_track(file="Controller.php", ctx="🔗")
→ ✗ PHP Syntax: Parse error: syntax error, unexpected '}'
```

Silent wenn alles OK. Fehler werden **sofort** gemeldet - nicht erst im Browser!

### 3. Status prüfen (nur bei Bedarf)
```
chainguard_status(ctx="🔗")   # Eine Zeile: "project|impl|F5/V3 Feature X..."
```

### 4. Abschließen (NEU in v4.3)
```
chainguard_check_criteria(criterion="...", fulfilled=true)  # Kriterien markieren
chainguard_finish                            # Prüft alles automatisch!
```

**`chainguard_finish` prüft:**
- Alle Akzeptanzkriterien erfüllt?
- Checklist bestanden?
- Keine offenen Alerts?
- Keine Syntax-Fehler?

**Blockiert** wenn nicht 100% erfüllt! Mit `force=true` überschreibbar.

## Tools (v5.0)

### Core (täglich nutzen)
| Tool | Zweck |
|------|-------|
| `chainguard_set_scope` | Definiert Task-Grenzen, **mode** und Kriterien |
| `chainguard_track` | Trackt Änderungen + **AUTO-VALIDIERT** (mode-abhängig) |
| `chainguard_track_batch` | Mehrere Dateien auf einmal tracken |
| `chainguard_status` | Ultra-kompakte Statuszeile |
| `chainguard_set_phase` | Phase setzen: planning/implementation/testing/review/done |
| `chainguard_finish` | Vollständiger Abschluss mit Prüfung |

### Content Mode (NEU v5.0)
| Tool | Zweck |
|------|-------|
| `chainguard_word_count` | Zeigt Wort-Zählung für aktuellen Scope |
| `chainguard_track_chapter` | Trackt Kapitel-Status (draft/review/done) |

### DevOps Mode (NEU v5.0)
| Tool | Zweck |
|------|-------|
| `chainguard_log_command` | Protokolliert ausgeführte CLI-Commands |
| `chainguard_checkpoint` | Erstellt Checkpoint vor kritischen Änderungen |
| `chainguard_health_check` | Prüft Endpoints auf Verfügbarkeit |

### Research Mode (NEU v5.0)
| Tool | Zweck |
|------|-------|
| `chainguard_add_source` | Fügt Quelle mit Relevanz hinzu |
| `chainguard_index_fact` | Indexiert Fakt mit Konfidenz-Level |
| `chainguard_sources` | Zeigt alle gesammelten Quellen |
| `chainguard_facts` | Zeigt alle indexierten Fakten |

### Test Runner (v4.10)
| Tool | Zweck |
|------|-------|
| `chainguard_test_config` | Test-Command konfigurieren (PHPUnit, Jest, pytest, etc.) |
| `chainguard_run_tests` | Tests ausführen mit Auto-Detection |
| `chainguard_test_status` | Letztes Test-Ergebnis anzeigen |

### Error Memory (v4.11)
| Tool | Zweck |
|------|-------|
| `chainguard_recall` | Durchsucht Error-History nach ähnlichen Problemen |
| `chainguard_history` | Zeigt Change-Log für aktuellen Scope |
| `chainguard_learn` | Dokumentiert einen Fix für zukünftige Auto-Suggests |

### Database Inspector (v4.12)
| Tool | Zweck |
|------|-------|
| `chainguard_db_connect` | Datenbankverbindung herstellen (MySQL/PostgreSQL/SQLite) |
| `chainguard_db_schema` | Schema aller Tabellen abrufen (5 min Cache) |
| `chainguard_db_table` | Details einer Tabelle + optionale Sample-Daten |
| `chainguard_db_disconnect` | Verbindung trennen und Cache löschen |

### Analysis (v4.7)
| Tool | Zweck |
|------|-------|
| `chainguard_analyze` | Pre-Flight Check: Metriken, Patterns, Hotspots, Checkliste |

### Validation
| Tool | Zweck |
|------|-------|
| `chainguard_check_criteria` | Zeigt/setzt Akzeptanzkriterien |
| `chainguard_run_checklist` | Führt automatische Checks aus |
| `chainguard_validate` | Speichert PASS/FAIL (warnt bei offenen Punkten) |

### HTTP Testing (v4.2)
| Tool | Zweck |
|------|-------|
| `chainguard_set_base_url` | Base URL setzen (z.B. `http://localhost:8888/app`) |
| `chainguard_test_endpoint` | Endpoint testen mit Session-Support |
| `chainguard_login` | Einloggen, Session für spätere Requests speichern |
| `chainguard_clear_session` | Session/Cookies löschen |

### Utility
| Tool | Zweck |
|------|-------|
| `chainguard_context` | Voller Kontext (sparsam nutzen!) |
| `chainguard_alert` | Problem markieren |
| `chainguard_clear_alerts` | Alerts bestätigen |
| `chainguard_projects` | Alle Projekte listen |
| `chainguard_config` | Konfiguration |

## HTTP Testing Workflow (NEU v4.2)

### Setup
```
chainguard_set_base_url(base_url="http://localhost:8888/myapp")
```

### Endpoint testen (ohne Auth)
```
chainguard_test_endpoint(url="/api/public/status")
→ ✓ GET 200
```

### Protected Endpoint → Auth erkannt
```
chainguard_test_endpoint(url="/api/users")
→ 🔐 Auth required (302): Redirect to login
→ Use chainguard_login to authenticate
```

### Einloggen
```
chainguard_login(
  login_url="/login",
  username="admin@example.com",
  password="secret123"
)
→ ✓ Logged in as admin@example.com
   Session stored for future requests
```

### Protected Endpoint → jetzt funktioniert's
```
chainguard_test_endpoint(url="/api/users")
→ ✓ GET 200
   [{"id":1,"name":"Admin"}, ...]
```

## Entfernte Features (v4.0)

Diese Features wurden entfernt - sie duplizierten andere Tools oder verbrauchten zu viel Kontext:

| Entfernt | Grund | Alternative |
|----------|-------|-------------|
| `chainguard_track_dependency` | LSP macht das besser | IDE/LSP nutzen |
| `chainguard_impact_analysis` | LSP macht das besser | IDE/LSP nutzen |
| `chainguard_save_learning` | Dupliziert laas_remember | `laas_remember` MCP |
| `chainguard_trends` | Selten nützlich | In `chainguard_context` integriert |
| `chainguard_brief` | Ersetzt durch `chainguard_status` | `chainguard_status` |

## Checklist-Beispiele

```json
{
  "checklist": [
    {"item": "Controller", "check": "test -f app/Http/Controllers/AuthController.php"},
    {"item": "Route", "check": "grep -q 'auth' routes/web.php"},
    {"item": "Test", "check": "test -f tests/Feature/AuthTest.php"}
  ]
}
```

**Erlaubte Commands:** `test`, `grep`, `ls`, `cat`, `head`, `wc`, `find`, `stat`, `php`, `node`, `python`, `npm`, `composer`

## Best Practices

1. **Tracking ist optional** - nur nutzen wenn Scope-Kontrolle wichtig ist
2. **Status nur bei Bedarf** - nicht nach jeder Änderung abfragen
3. **Context sparsam** - `chainguard_context` nur wenn Details wirklich nötig
4. **Validation am Ende** - nicht nach jeder kleinen Änderung

## Performance-Vergleich

| Szenario | v3.0 | v4.0 | v5.0 |
|----------|------|------|------|
| 10 Dateiänderungen tracken | ~3.000 tok | ~150 tok | ~150 tok |
| Lange Description (500+ Wörter) | ~1000 tok | ~1000 tok | **~100 tok** |
| chainguard_mcp.py lesen | 31K tok | 31K tok | **~2K tok** (modular) |
| Content-Mode (keine Syntax) | N/A | N/A | **0 tok** (skip) |
| DevOps-Mode (nur Config) | N/A | N/A | **~50 tok** |
| Disk-Writes bei 10 Tracks | 20 | 20 | **2** |
| Git Subprocess-Calls | 2/track | 2/track | **0** (cached) |
| Checklist (10 Items) | 10s (seq) | 10s (seq) | **~1s** (parallel) |
| HTTP Session Memory | unbegrenzt | unbegrenzt | **50 max** (TTL) |

**v5.0: Task-Mode System + Handler-Registry Pattern + Async Checklist + TTL-Cache.**

## Installation

```bash
pip install mcp aiofiles aiohttp  # aiohttp optional für HTTP-Testing
```
