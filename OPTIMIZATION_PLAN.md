# Chainguard MCP Server v4.8 - Optimierungsplan

> Erstellt: 2026-01-04
> Status: In Bearbeitung

## Übersicht

6 Optimierungen zur Verbesserung von Performance, Code-Qualität und Wartbarkeit.

---

## TODO Liste

### Quick Wins

- [x] **1. _init_lock Bug fixen** (`cache.py`) ✅
  - Problem: `asyncio.Lock()` wird zur Import-Zeit erstellt (kein Event Loop)
  - Lösung: Zeile entfernen, lazy initialization nutzen
  - Aufwand: 1 Zeile löschen
  - Risiko: Niedrig

- [x] **2. JSON-Validierung async** (`validators.py`) ✅
  - Problem: `open()` blockiert den Event Loop
  - Lösung: `aiofiles.open()` verwenden
  - Aufwand: ~10 Zeilen
  - Risiko: Niedrig

- [x] **3. HTTPSessionManager LRU Cache** (`http_session.py`) ✅
  - Problem: `_sessions` Dict wächst unbegrenzt (Memory Leak)
  - Lösung: TTLLRUCache mit maxsize=50, TTL=24h verwenden
  - Aufwand: ~5 Zeilen
  - Risiko: Niedrig

### Mittlere Änderungen

- [x] **4. Handler-Registry Pattern** (`handlers.py`) ✅
  - Problem: 587 Zeilen if-elif-Kette, nicht testbar
  - Lösung: Decorator-basierte Handler-Registry mit @handler.register()
  - Aufwand: Komplettes Refactoring (~680 Zeilen)
  - Risiko: Mittel (viele Änderungen)

- [x] **5. ChecklistRunner async** (`checklist.py`) ✅
  - Problem: `subprocess.run()` blockiert Event Loop
  - Lösung: `asyncio.create_subprocess_exec()` + parallele Ausführung
  - Aufwand: ~30 Zeilen
  - Risiko: Niedrig

### Größere Änderung

- [x] **6. TTL-LRU Cache** (`cache.py`) ✅
  - Problem: Cache-Einträge werden nie invalidiert (außer bei Kapazität)
  - Lösung: Generic TTLLRUCache[T] mit konfigurierbarer TTL
  - Aufwand: ~75 Zeilen neue Klasse
  - Risiko: Niedrig (neue Klasse, bestehende bleibt)

---

## Implementierungsreihenfolge

1. `cache.py` - Bug fix + TTLLRUCache (Basis für andere)
2. `validators.py` - JSON async
3. `http_session.py` - LRU Cache nutzen
4. `checklist.py` - Async subprocess
5. `handlers.py` - Registry Pattern (größte Änderung zuletzt)

---

## Betroffene Dateien

| Datei | Änderungstyp | Zeilen ca. |
|-------|--------------|------------|
| `cache.py` | Fix + Erweiterung | +45 |
| `validators.py` | Refactoring | +8 |
| `http_session.py` | Refactoring | +5 |
| `checklist.py` | Refactoring | +25 |
| `handlers.py` | Großes Refactoring | ~600 (Umstrukturierung) |
| `config.py` | Version bump | +1 |

---

## Rollback-Plan

Falls Probleme auftreten:
1. Alle Änderungen sind in einzelnen Commits
2. Original-Dateien bleiben in `~/.chainguard/` bis manuell kopiert

---

## Nach Implementierung

- [x] Syntax-Check aller Python-Dateien ✅
- [ ] Server-Start testen
- [ ] Nach `~/.chainguard/` kopieren
- [ ] Claude Code neu starten

---

## Abgeschlossen: 2026-01-04

Alle 6 Optimierungen wurden erfolgreich implementiert:

1. **cache.py**: _init_lock Bug gefixt + TTLLRUCache hinzugefügt
2. **validators.py**: JSON-Validierung auf async I/O umgestellt
3. **http_session.py**: TTLLRUCache für Session-Management
4. **handlers.py**: Komplett auf Handler-Registry Pattern refactored
5. **checklist.py**: Async subprocess mit paralleler Ausführung
6. **config.py**: Version auf 4.8.0 erhöht

Deployment:
```bash
cp src/mcp-server/chainguard_mcp.py ~/.chainguard/
cp -r src/mcp-server/chainguard/ ~/.chainguard/
```
