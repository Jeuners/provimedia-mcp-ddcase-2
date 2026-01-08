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
# ================================================

# CHAINGUARD v4.19.1 - Hard Enforcement via PreToolUse Hook

> **v4.9 NEU:** Alle Tools außer set_scope sind **HART BLOCKIERT** wenn kein Scope existiert!

> **Installationspfad:**
> Der MCP-Server läuft von `~/.chainguard/` - NICHT aus diesem Projekt!
>
> **Nach Code-Änderungen immer kopieren:**
> ```bash
> rm -rf ~/.chainguard/chainguard && cp -r src/mcp-server/chainguard ~/.chainguard/
> cp src/mcp-server/chainguard_mcp.py ~/.chainguard/
> ```
> Danach Claude Code neu starten!

**Design-Prinzip:** Minimaler Kontextverbrauch, maximaler Nutzen, maximale Performance.

## v4.11.0 Features

### Error Memory System - Lerne aus Fehlern
- **Automatisches History-Log**: Jede Änderung wird dokumentiert (JSONL, append-only)
- **Error-Index**: Fehler werden indexiert für schnelles Nachschlagen
- **Auto-Suggest**: Bei bekannten Fehlern wird automatisch die Lösung vorgeschlagen
- **Token-effizient**: Kostet nur bei Fehlern etwas (0 Token bei Erfolg)

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

### Test Runner Tools

| Tool | Zweck |
|------|-------|
| `chainguard_test_config` | Test-Command konfigurieren |
| `chainguard_run_tests` | Tests ausführen mit Auto-Detection |
| `chainguard_test_status` | Letztes Test-Ergebnis anzeigen |

## v4.8.0 Features

### Handler-Registry Pattern
- **Decorator-basierte Handler**: `@handler.register("tool_name")`
- **Testbar**: Jeder Handler ist eine separate async Funktion
- **Erweiterbar**: Neue Tools einfach hinzufügen

### TTL-LRU Cache
- **Memory-bounded + Zeit-limitiert**: Items verfallen nach TTL
- **Generic**: `TTLLRUCache[T]` für beliebige Typen
- **Cleanup**: Automatische Bereinigung abgelaufener Einträge

### Async Checklist-Ausführung
- **Parallele Ausführung**: `run_all_async()` führt Checks parallel aus
- **Non-blocking**: `asyncio.create_subprocess_exec()`

## v4.6.0 Features

### Context-Check mit Canary-Parameter
- **Problem**: Claude Code verliert manchmal den CLAUDE.md Kontext bei langen Sessions
- **Lösung**: `ctx="🔗"` Parameter als "Canary" - wenn er fehlt, ist der Kontext verloren
- **Auto-Refresh**: MCP gibt automatisch die wichtigsten Regeln zurück wenn ctx fehlt

## v4.5.0 Features

### Syntax-Validierung
- **Python**: `python3 -m py_compile`
- **TypeScript/TSX**: `npx tsc --noEmit`
- **PHP**: `php -l`
- **JavaScript**: `node --check`
- **JSON**: Struktur-Validierung

### Batch-Tracking
```python
chainguard_track_batch(files=["a.py", "b.ts", "c.php"])
```

## Workflow

### 1. Task starten
```python
chainguard_set_scope(
  description="Feature X implementieren",
  modules=["src/feature/*.ts"],
  acceptance_criteria=["Tests grün", "Docs aktualisiert"]
)
```

### 2. Arbeiten + Tracken
```python
chainguard_track(file="Controller.php", ctx="🔗")
```

### 3. Abschließen
```python
chainguard_check_criteria(criterion="...", fulfilled=true)
chainguard_finish(confirmed=True)
```

## Tools (v4.11)

### Core
| Tool | Zweck |
|------|-------|
| `chainguard_set_scope` | Definiert Task-Grenzen und Kriterien |
| `chainguard_track` | Trackt Änderungen + AUTO-VALIDIERT |
| `chainguard_track_batch` | Mehrere Dateien auf einmal tracken |
| `chainguard_status` | Ultra-kompakte Statuszeile |
| `chainguard_set_phase` | Phase setzen |
| `chainguard_finish` | Vollständiger Abschluss mit Prüfung |

### Test Runner (v4.10)
| Tool | Zweck |
|------|-------|
| `chainguard_test_config` | Test-Command konfigurieren |
| `chainguard_run_tests` | Tests ausführen |
| `chainguard_test_status` | Letztes Ergebnis |

### Error Memory (v4.11)
| Tool | Zweck |
|------|-------|
| `chainguard_recall` | Error-History durchsuchen |
| `chainguard_history` | Change-Log anzeigen |
| `chainguard_learn` | Fix dokumentieren |

### Analysis (v4.7)
| Tool | Zweck |
|------|-------|
| `chainguard_analyze` | Pre-Flight Check |

### Validation
| Tool | Zweck |
|------|-------|
| `chainguard_check_criteria` | Akzeptanzkriterien |
| `chainguard_run_checklist` | Automatische Checks |
| `chainguard_validate` | PASS/FAIL speichern |

### HTTP Testing (v4.2)
| Tool | Zweck |
|------|-------|
| `chainguard_set_base_url` | Base URL setzen |
| `chainguard_test_endpoint` | Endpoint testen |
| `chainguard_login` | Session speichern |
| `chainguard_clear_session` | Session löschen |

### Utility
| Tool | Zweck |
|------|-------|
| `chainguard_context` | Voller Kontext |
| `chainguard_alert` | Problem markieren |
| `chainguard_clear_alerts` | Alerts bestätigen |
| `chainguard_projects` | Alle Projekte |
| `chainguard_config` | Konfiguration |

## Best Practices

1. **ctx="🔗" immer mitgeben** - bei jedem Chainguard-Aufruf
2. **Tracking nach jeder Änderung** - für Syntax-Validierung
3. **Status nur bei Bedarf** - nicht nach jeder Änderung
4. **chainguard_finish am Ende** - prüft alles automatisch

## Performance

| Szenario | v3.0 | v4.11 |
|----------|------|-------|
| 10 Dateiänderungen | ~3.000 tok | ~150 tok |
| Disk-Writes bei 10 Tracks | 20 | 2 |
| Git Subprocess-Calls | 2/track | 0 (cached) |
| Checklist (10 Items) | 10s | ~1s (parallel) |
