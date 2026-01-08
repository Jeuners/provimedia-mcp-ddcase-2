# Chainguard MCP Server - Test-System

Diese Dokumentation beschreibt das Unit-Test-System für den Chainguard MCP Server.

## Übersicht

| Metrik | Wert |
|--------|------|
| Test-Framework | pytest |
| Anzahl Tests | 605+ |
| Test-Dateien | 15 |
| Gesamt-Coverage | ~70% |
| Abdeckung | Alle Module inkl. Phase 4 Features |

## Struktur

```
src/mcp-server/
├── pytest.ini              # pytest Konfiguration
├── tests/
│   ├── __init__.py
│   ├── conftest.py         # Shared Fixtures
│   │
│   │   # Core Tests
│   ├── test_cache.py       # Cache-Tests (19 Tests)
│   ├── test_models.py      # Model-Tests (19 Tests)
│   ├── test_handlers.py    # Handler-Tests (50 Tests)
│   ├── test_validators.py  # Validator-Tests (48 Tests)
│   ├── test_utils.py       # Utils-Tests (20 Tests)
│   ├── test_checklist.py   # Checklist-Tests (43 Tests)
│   ├── test_analyzers.py   # Analyzer-Tests (46 Tests)
│   │
│   │   # Feature Tests
│   ├── test_test_runner.py # TestRunner-Tests (28 Tests)
│   ├── test_history.py     # History-Tests (29 Tests)
│   ├── test_db_inspector.py # DB-Inspector-Tests (26 Tests)
│   ├── test_task_mode.py   # Task-Mode-Tests (32 Tests)
│   │
│   │   # Memory System Tests (v5.1+)
│   ├── test_memory.py      # Memory-Tests (71 Tests)
│   ├── test_embeddings.py  # Embedding-Tests (32 Tests)
│   │
│   │   # Phase 3 Tests (v5.3+)
│   ├── test_ast_analyzer.py    # AST-Analyse (32 Tests)
│   ├── test_architecture.py    # Architektur-Erkennung (29 Tests)
│   ├── test_memory_export.py   # Export/Import (29 Tests)
│   │
│   │   # Phase 4 Tests (v5.4+)
│   └── test_code_summarizer.py # Deep Logic Summaries (45 Tests)
│
└── chainguard/
    └── ...                  # Module unter Test
```

## Tests ausführen

### Alle Tests
```bash
cd src/mcp-server
python3 -m pytest tests/ -v
```

### Einzelne Test-Datei
```bash
python3 -m pytest tests/test_cache.py -v
```

### Mit Coverage
```bash
python3 -m pytest tests/ --cov=chainguard --cov-report=html
```

## Test-Konfiguration (pytest.ini)

```ini
[pytest]
testpaths = tests
python_files = test_*.py
asyncio_mode = auto
addopts = -v --tb=short
```

## Fixtures (conftest.py)

### `temp_dir`
Erstellt ein temporäres Verzeichnis, das nach dem Test automatisch gelöscht wird.

```python
def test_something(temp_dir):
    file = temp_dir / "test.txt"
    file.write_text("content")
```

### `sample_project_path`
Erstellt eine Beispiel-Projektstruktur mit `src/` und `tests/` Verzeichnissen.

```python
def test_project(sample_project_path):
    assert (sample_project_path / "src").exists()
```

## Test-Module

### test_cache.py (19 Tests)

Testet die Cache-Implementierungen:

| Klasse | Tests | Beschreibung |
|--------|-------|--------------|
| `TestLRUCache` | 5 | LRU-Eviction, Set/Get, Order |
| `TestTTLLRUCache` | 9 | TTL-Expiration, Cleanup, Iteration |
| `TestGitCache` | 5 | Git-spezifischer Cache mit TTL |

**Wichtige Tests:**
- `test_maxsize_eviction` - Prüft dass älteste Einträge bei Überlauf entfernt werden
- `test_ttl_expiration` - Prüft dass Einträge nach TTL verfallen
- `test_access_updates_order` - Prüft dass Zugriff die LRU-Reihenfolge aktualisiert

### test_models.py (19 Tests)

Testet die Datenmodelle:

| Klasse | Tests | Beschreibung |
|--------|-------|--------------|
| `TestScopeDefinition` | 2 | Scope-Dataclass |
| `TestProjectState` | 17 | Projekt-State mit allen Methoden |

**Wichtige Tests:**
- `test_roundtrip_serialization` - JSON Serialisierung und Deserialisierung
- `test_check_file_in_scope_with_patterns` - Glob-Pattern-Matching
- `test_get_completion_status_*` - Kriterien-Prüfung

### test_test_runner.py (28 Tests)

Testet den Test-Runner (v4.10):

| Klasse | Tests | Beschreibung |
|--------|-------|--------------|
| `TestTestConfig` | 6 | Konfiguration |
| `TestTestResult` | 3 | Ergebnis-Dataclass |
| `TestOutputParser` | 15 | Framework-Detection & Parsing |
| `TestTestRunnerFormat` | 4 | Output-Formatierung |

**Framework-Detection-Tests:**
- PHPUnit: `test_detect_phpunit`, `test_parse_phpunit_success/failure`
- Jest: `test_detect_jest`, `test_parse_jest_success/failure`
- pytest: `test_detect_pytest`, `test_parse_pytest_success/failure`
- mocha: `test_detect_mocha`, `test_parse_mocha_success/failure`

### test_handlers.py (50 Tests)

Testet die Tool-Handler (v4.11):

| Klasse | Tests | Beschreibung |
|--------|-------|--------------|
| `TestHandlerRegistry` | 6 | Registry-Pattern, Dispatch, Scope-Blocking |
| `TestHelperFunctions` | 4 | `_text()`, `_check_context()` |
| `TestHandleSetScope` | 3 | Scope-Setting, Kriterien, Warnings |
| `TestHandleTrack` | 4 | File-Tracking, Syntax-Validation, OOS |
| `TestHandleTrackBatch` | 3 | Batch-Tracking mehrerer Dateien |
| `TestHandleStatus` | 2 | Status-Ausgabe mit/ohne Context |
| `TestHandleContext` | 2 | Full Context Output |
| `TestHandleSetPhase` | 2 | Phase-Wechsel, Done-Warnings |
| `TestHandleCheckCriteria` | 3 | Kriterien anzeigen/markieren |
| `TestHandleValidate` | 2 | PASS/FAIL Validation |
| `TestHandleRunChecklist` | 2 | Checklist-Ausführung |
| `TestHandleAlert` | 1 | Alert hinzufügen |
| `TestHandleClearAlerts` | 1 | Alerts bestätigen |
| `TestHandleProjects` | 2 | Projekt-Liste |
| `TestHandleConfig` | 1 | Config anzeigen |
| `TestHandleFinish` | 2 | Task-Abschluss, Force-Mode |
| `TestHandleTestConfig` | 2 | Test-Command konfigurieren |
| `TestHandleRunTests` | 2 | Tests ausführen |
| `TestHandleTestStatus` | 1 | Test-Status anzeigen |
| `TestHandleRecall` | 2 | Error-History durchsuchen |
| `TestHandleHistory` | 1 | Change-History anzeigen |
| `TestHandleLearn` | 2 | Resolutions dokumentieren |

**Wichtige Tests:**
- `test_dispatch_blocks_without_scope` - Prüft Scope-Blockade (v4.9)
- `test_track_file_syntax_error` - Prüft Auto-Validierung
- `test_check_context_*` - Prüft Context-Canary-Feature (v4.6)

### test_validators.py (48 Tests)

Testet die Syntax-Validierung:

| Klasse | Tests | Beschreibung |
|--------|-------|--------------|
| `TestSyntaxValidator` | 19 | validate_file für PHP, JS, JSON, Python, TS |
| `TestExtractErrors` | 18 | Error-Extraktion für verschiedene Sprachen |
| `TestRunCommand` | 6 | Command-Ausführung, Timeout, Fehlerbehandlung |
| `TestValidationIntegration` | 6 | End-to-end Validation-Tests |

**Wichtige Tests:**
- `test_validate_blade_php_skipped` - Blade-Templates werden übersprungen
- `test_run_command_timeout` - Timeout-Handling bei langsamen Commands
- `test_validate_ts_no_error_marker` - Edge-Case bei TypeScript-Validierung

### test_utils.py (20 Tests)

Testet Hilfsfunktionen:

| Klasse | Tests | Beschreibung |
|--------|-------|--------------|
| `TestSanitizePath` | 8 | Path-Sanitization und -Auflösung |
| `TestIsPathSafe` | 12 | Path-Traversal-Erkennung |

**Wichtige Tests:**
- `test_path_traversal_outside_project` - Verhindert Directory Traversal
- `test_invalid_characters` - Erkennt ungültige Zeichen in Pfaden

### test_checklist.py (43 Tests)

Testet die Checklist-Ausführung:

| Klasse | Tests | Beschreibung |
|--------|-------|--------------|
| `TestChecklistConstants` | 4 | Whitelist-Konstanten |
| `TestChecklistRunnerAsync` | 26 | Async-Ausführung, Command-Whitelist |
| `TestChecklistRunnerSync` | 5 | Sync-Wrapper-Tests |
| `TestChecklistRunnerTimeout` | 1 | Timeout-Handling |
| `TestChecklistRunnerEdgeCases` | 7 | Edge-Cases und Fehlerbehandlung |

**Wichtige Tests:**
- `test_run_check_disallowed_command_*` - Command-Whitelist-Sicherheit
- `test_run_all_async_parallel_execution` - Parallele Ausführung
- `test_run_check_timeout` - Timeout bei langsamen Commands

### test_analyzers.py (46 Tests)

Testet die Code-Analyse:

| Klasse | Tests | Beschreibung |
|--------|-------|--------------|
| `TestCodeAnalyzerMetrics` | 6 | LOC, Funktionen, Komplexität |
| `TestCodeAnalyzerPatterns` | 13 | Pattern-Erkennung (async-io, mcp-server, etc.) |
| `TestCodeAnalyzerHotspots` | 7 | Hotspot- und TODO-Erkennung |
| `TestCodeAnalyzerAsync` | 5 | Async analyze_file, format_output |
| `TestImpactAnalyzer` | 14 | Impact-Pattern-Matching |
| `TestAnalyzersIntegration` | 1 | End-to-end Workflow |

**Wichtige Tests:**
- `test_detect_patterns_*` - Erkennt Code-Patterns (React, Laravel, etc.)
- `test_analyze_changed_files` - Impact-Analyse für geänderte Dateien
- `test_build_checklist_no_duplicates` - Deduplizierte Checklist-Items

---

## Phase 3 Tests (v5.3+)

### test_ast_analyzer.py (32 Tests)

Testet die AST-basierte Code-Analyse:

| Klasse | Tests | Beschreibung |
|--------|-------|--------------|
| `TestSymbolType` | 2 | SymbolType Enum |
| `TestRelationType` | 2 | RelationType Enum |
| `TestCodeSymbol` | 3 | CodeSymbol Dataclass |
| `TestFileAnalysis` | 2 | FileAnalysis Dataclass |
| `TestLanguageExtensions` | 2 | Sprach-Extensions-Mapping |
| `TestRegexAnalyzer` | 7 | Regex-Fallback für Python, JS, PHP, TS |
| `TestASTAnalyzer` | 6 | Main Analyzer-Klasse |
| `TestTreeSitterAnalyzer` | 2 | Tree-sitter (wenn verfügbar) |
| `TestFileRelation` | 2 | Beziehungen zwischen Dateien |

**Wichtige Tests:**
- `test_analyze_python_class/function` - Python AST-Parsing
- `test_analyze_javascript_class/function` - JavaScript AST-Parsing
- `test_analyze_php_class` - PHP AST-Parsing
- `test_analyze_typescript_interface` - TypeScript AST-Parsing

### test_architecture.py (29 Tests)

Testet die Architektur-Erkennung:

| Klasse | Tests | Beschreibung |
|--------|-------|--------------|
| `TestArchitecturePattern` | 2 | Pattern Enum (MVC, MVVM, Clean, etc.) |
| `TestFrameworkType` | 4 | Framework Enum (Laravel, Django, React, etc.) |
| `TestArchitectureAnalysis` | 3 | Analyse-Ergebnis Dataclass |
| `TestDirectoryPatterns` | 2 | Directory-Muster für Pattern-Erkennung |
| `TestFrameworkPatterns` | 2 | Framework-Erkennungs-Muster |
| `TestArchitectureDetector` | 12 | Hauptdetector-Klasse |
| `TestProjectStructure` | 2 | Projektstruktur-Dataclass |

**Wichtige Tests:**
- `test_analyze_mvc_structure` - Erkennt MVC-Pattern
- `test_detect_laravel_framework` - Erkennt Laravel
- `test_detect_react_framework` - Erkennt React
- `test_detect_design_patterns` - Erkennt Repository, Service, Factory, etc.

### test_memory_export.py (29 Tests)

Testet Memory Export/Import:

| Klasse | Tests | Beschreibung |
|--------|-------|--------------|
| `TestExportMetadata` | 4 | Export-Metadaten Dataclass |
| `TestExportDocument` | 6 | Export-Dokument Dataclass |
| `TestExportResult` | 4 | Export-Ergebnis |
| `TestImportResult` | 3 | Import-Ergebnis |
| `TestExportDir` | 2 | Export-Verzeichnis-Konstante |
| `TestMemoryExporter` | 3 | Exporter-Klasse |
| `TestMemoryImporter` | 3 | Importer-Klasse |
| `TestListExports` | 3 | Export-Liste-Funktion |
| `TestJsonExportFormat` | 1 | JSON-Format-Validierung |
| `TestJsonlExportFormat` | 1 | JSONL-Format-Validierung |

**Wichtige Tests:**
- `test_to_dict/from_dict` - Serialisierung/Deserialisierung
- `test_document_with_embedding` - Export mit Embeddings
- `test_create_valid_export_structure` - Valides Export-Format

---

## Phase 4 Tests (v5.4+)

### test_code_summarizer.py (45 Tests)

Testet die Deep Logic Extraction:

| Klasse | Tests | Beschreibung |
|--------|-------|--------------|
| `TestFunctionInfo` | 11 | FunctionInfo Dataclass, Purpose-Inferenz |
| `TestClassInfo` | 9 | ClassInfo Dataclass, Pattern-Erkennung |
| `TestFileSummary` | 5 | FileSummary Dataclass, Text-Generierung |
| `TestCodeSummarizer` | 10 | Hauptsummarizer, Sprachenerkennung |
| `TestGlobalInstance` | 2 | Singleton-Pattern |
| `TestEdgeCases` | 8 | Edge-Cases und Fehlerbehandlung |

**Wichtige Tests:**
- `test_docstring_overrides_name` - Docstrings haben Vorrang vor Name-Inferenz
- `test_*_function_purpose` - Erkennt get_, set_, is_, create_, delete_, validate_ Präfixe
- `test_*_class_purpose` - Erkennt Controller, Service, Repository, Factory, Validator Suffixe
- `test_summarize_python/php/javascript_file` - Multi-Language-Support
- `test_malformed_code` - Robustheit bei fehlerhaftem Code

---

## Neue Tests hinzufügen

### 1. Neue Test-Datei erstellen

```python
# tests/test_new_module.py
"""
Tests for chainguard.new_module.
"""

import pytest
from chainguard.new_module import NewClass


class TestNewClass:
    """Tests for NewClass."""

    def test_basic_functionality(self):
        """Test basic usage."""
        obj = NewClass()
        assert obj.method() == expected

    def test_edge_case(self):
        """Test edge case handling."""
        obj = NewClass()
        with pytest.raises(ValueError):
            obj.method(invalid_input)
```

### 2. Async Tests

```python
import pytest

class TestAsyncFeature:
    @pytest.mark.asyncio
    async def test_async_method(self):
        result = await some_async_function()
        assert result == expected
```

### 3. Fixtures nutzen

```python
def test_with_temp_dir(temp_dir):
    """Test that uses temp directory fixture."""
    test_file = temp_dir / "test.json"
    test_file.write_text('{"key": "value"}')

    result = load_config(test_file)
    assert result["key"] == "value"
```

## Test-Konventionen

1. **Namensgebung**
   - Test-Dateien: `test_<module>.py`
   - Test-Klassen: `Test<ClassName>`
   - Test-Methoden: `test_<what_is_tested>`

2. **Docstrings**
   - Jede Test-Methode hat einen kurzen Docstring
   - Erklärt WAS getestet wird, nicht WIE

3. **Assertions**
   - Eine logische Assertion pro Test
   - Aussagekräftige Fehlermeldungen

4. **Isolation**
   - Tests sind unabhängig voneinander
   - Kein Shared State zwischen Tests
   - Fixtures für Setup/Teardown

## Bekannte Warnungen

```
PytestCollectionWarning: cannot collect test class 'TestConfig'
PytestCollectionWarning: cannot collect test class 'TestResult'
```

Diese Warnungen sind harmlos - pytest versucht die Dataclasses `TestConfig` und `TestResult` aus `test_runner.py` als Test-Klassen zu sammeln, ignoriert sie aber wegen des `__init__` Konstruktors.

## CI/CD Integration

Für GitHub Actions:

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: |
          pip install pytest pytest-asyncio aiofiles
      - name: Run tests
        run: |
          cd src/mcp-server
          python -m pytest tests/ -v
```

## Abhängigkeiten

```
pytest>=8.0.0
pytest-asyncio>=0.25.0
aiofiles  # Für async File I/O Tests
```

**Hinweis:** Das `mcp` Package ist für Tests NICHT erforderlich. Der Server-Import in `__init__.py` ist optional und wird übersprungen wenn `mcp` nicht installiert ist.
