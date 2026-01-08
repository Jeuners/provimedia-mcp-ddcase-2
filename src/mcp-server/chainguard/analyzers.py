"""
CHAINGUARD MCP Server - Analyzers Module

Contains: CodeAnalyzer, ImpactAnalyzer

Copyright (c) 2026 Provimedia GmbH
Licensed under the Polyform Noncommercial License 1.0.0
See LICENSE file in the project root for full license information.
"""

import re
from pathlib import Path
from typing import Dict, Any, List

from .config import logger

class CodeAnalyzer:
    """
    Performs lightweight static analysis to prepare Claude for code review.
    """

    PATTERNS = {
        "mcp-server": {
            "indicators": ["from mcp.server import", "@server.list_tools", "stdio_server"],
            "checklist": [
                "Async/Await korrekt verwendet?",
                "Error Handling in Tool-Handlern?",
                "Input Validation für alle Parameter?",
                "Bounded Collections (keine unbegrenzten Listen)?",
                "Resource Cleanup (Connections, Files)?",
            ]
        },
        "async-io": {
            "indicators": ["async def", "await ", "asyncio.", "aiofiles"],
            "checklist": [
                "Alle async Funktionen awaited?",
                "Keine blocking I/O in async Context?",
                "Proper Exception Handling?",
                "Timeouts für externe Calls?",
            ]
        },
        "http-client": {
            "indicators": ["aiohttp", "requests.", "urllib", "http.client"],
            "checklist": [
                "Timeouts gesetzt?",
                "SSL Verification aktiv?",
                "Error Response Handling?",
                "Rate Limiting bedacht?",
            ]
        },
        "caching": {
            "indicators": ["LRUCache", "cache", "_cache", "TTL", "maxsize"],
            "checklist": [
                "Cache Size begrenzt?",
                "TTL/Expiration definiert?",
                "Cache Invalidation korrekt?",
                "Thread-Safety?",
            ]
        },
        "file-io": {
            "indicators": ["open(", "Path(", "os.path", "with open"],
            "checklist": [
                "Path Traversal verhindert?",
                "File Handles geschlossen (with statement)?",
                "Encoding explizit (utf-8)?",
                "Error Handling für I/O?",
            ]
        },
        "subprocess": {
            "indicators": ["subprocess.", "Popen", "create_subprocess", "shell=True"],
            "checklist": [
                "shell=False verwendet?",
                "Input sanitized (keine Injection)?",
                "Timeout gesetzt?",
                "Return Code geprüft?",
            ]
        },
        "laravel-controller": {
            "indicators": ["extends Controller", "function index", "function store", "->validate("],
            "checklist": [
                "Input Validation vorhanden?",
                "Authorization Checks?",
                "CSRF Protection aktiv?",
                "Mass Assignment geschützt?",
            ]
        },
        "react-component": {
            "indicators": ["import React", "useState", "useEffect", "export default function"],
            "checklist": [
                "useEffect Dependencies korrekt?",
                "Cleanup in useEffect?",
                "Keys für Listen?",
                "Error Boundaries?",
            ]
        },
    }

    @classmethod
    async def analyze_file(cls, file_path: str, project_path: str) -> Dict[str, Any]:
        """Analyze a file and return structured metrics + checklist."""
        full_path = Path(project_path) / file_path if not Path(file_path).is_absolute() else Path(file_path)

        if not full_path.exists():
            return {"error": f"File not found: {file_path}"}

        try:
            with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            lines = content.split('\n')
            metrics = cls._calculate_metrics(content, lines)
            detected_patterns = cls._detect_patterns(content)
            checklist = cls._build_checklist(detected_patterns)
            hotspots = cls._find_hotspots(content, lines)
            todos = cls._find_todos(lines)

            return {
                "file": str(full_path.name),
                "path": str(full_path),
                "metrics": metrics,
                "patterns": detected_patterns,
                "checklist": checklist,
                "hotspots": hotspots[:5],
                "todos": todos[:5],
            }

        except Exception as e:
            logger.error(f"CodeAnalyzer error for {file_path}: {e}")
            return {"error": str(e)}

    @classmethod
    def _calculate_metrics(cls, content: str, lines: List[str]) -> Dict[str, Any]:
        """Calculate basic code metrics."""
        loc = len(lines)
        loc_code = len([l for l in lines if l.strip() and not l.strip().startswith('#') and not l.strip().startswith('//')])

        func_count = len(re.findall(r'^\s*(async\s+)?def\s+\w+', content, re.MULTILINE))
        func_count += len(re.findall(r'^\s*(async\s+)?function\s+\w+', content, re.MULTILINE))
        class_count = len(re.findall(r'^\s*class\s+\w+', content, re.MULTILINE))

        complexity_indicators = (
            content.count(' if ') + content.count(' else:') + content.count(' elif ') +
            content.count(' for ') + content.count(' while ') +
            content.count(' try:') + content.count(' except') +
            content.count(' and ') + content.count(' or ')
        )

        complexity_per_100 = (complexity_indicators / max(loc_code, 1)) * 100
        if complexity_per_100 < 2:
            complexity_level = 1
        elif complexity_per_100 < 4:
            complexity_level = 2
        elif complexity_per_100 < 6:
            complexity_level = 3
        elif complexity_per_100 < 10:
            complexity_level = 4
        else:
            complexity_level = 5

        return {
            "loc": loc,
            "loc_code": loc_code,
            "functions": func_count,
            "classes": class_count,
            "complexity": complexity_level,
            "complexity_raw": complexity_indicators,
        }

    @classmethod
    def _detect_patterns(cls, content: str) -> List[str]:
        """Detect code patterns based on content."""
        detected = []
        for pattern_name, pattern_info in cls.PATTERNS.items():
            for indicator in pattern_info["indicators"]:
                if indicator in content:
                    if pattern_name not in detected:
                        detected.append(pattern_name)
                    break
        return detected

    @classmethod
    def _build_checklist(cls, patterns: List[str]) -> List[str]:
        """Build combined checklist from detected patterns."""
        checklist = []
        seen = set()
        for pattern in patterns:
            if pattern in cls.PATTERNS:
                for item in cls.PATTERNS[pattern]["checklist"]:
                    if item not in seen:
                        seen.add(item)
                        checklist.append(item)
        return checklist[:10]

    @classmethod
    def _find_hotspots(cls, content: str, lines: List[str]) -> List[Dict[str, Any]]:
        """Find potentially complex functions."""
        hotspots = []
        func_pattern = re.compile(r'^\s*(async\s+)?(def|function)\s+(\w+)')

        current_func = None
        current_start = 0
        current_complexity = 0

        for i, line in enumerate(lines):
            match = func_pattern.match(line)
            if match:
                if current_func:
                    hotspots.append({
                        "name": current_func,
                        "line": current_start + 1,
                        "complexity": current_complexity,
                    })
                current_func = match.group(3)
                current_start = i
                current_complexity = 0
            elif current_func:
                current_complexity += (
                    line.count(' if ') + line.count(' else:') +
                    line.count(' for ') + line.count(' while ') +
                    line.count(' try:') + line.count(' except')
                )

        if current_func:
            hotspots.append({
                "name": current_func,
                "line": current_start + 1,
                "complexity": current_complexity,
            })

        hotspots.sort(key=lambda x: x["complexity"], reverse=True)
        return [h for h in hotspots if h["complexity"] > 3]

    @classmethod
    def _find_todos(cls, lines: List[str]) -> List[Dict[str, Any]]:
        """Find TODO/FIXME/HACK comments."""
        todos = []
        pattern = re.compile(r'#\s*(TODO|FIXME|HACK|XXX):?\s*(.*)', re.IGNORECASE)

        for i, line in enumerate(lines):
            match = pattern.search(line)
            if match:
                todos.append({
                    "type": match.group(1).upper(),
                    "text": match.group(2).strip()[:50],
                    "line": i + 1,
                })
        return todos

    @classmethod
    def format_output(cls, result: Dict[str, Any]) -> str:
        """Format analysis result for Claude."""
        if "error" in result:
            return f"❌ Analyse fehlgeschlagen: {result['error']}"

        m = result["metrics"]
        complexity_bar = "●" * m["complexity"] + "○" * (5 - m["complexity"])

        lines = []
        lines.append(f"📊 **{result['file']}**")
        lines.append(f"├── {m['loc']} LOC ({m['loc_code']} Code) | {m['functions']} Funktionen | {m['classes']} Klassen")
        lines.append(f"├── Komplexität: {complexity_bar} ({m['complexity']}/5)")

        if result["patterns"]:
            lines.append(f"├── Patterns: {', '.join(result['patterns'])}")

        if result["hotspots"]:
            hotspot_str = ", ".join([f"{h['name']}:{h['line']}" for h in result["hotspots"][:3]])
            lines.append(f"├── Hotspots: {hotspot_str}")

        if result["todos"]:
            lines.append(f"└── TODOs: {len(result['todos'])} gefunden")
        else:
            lines.append(f"└── TODOs: keine")

        if result["checklist"]:
            lines.append(f"\n**Checkliste [{', '.join(result['patterns'][:2])}]:**")
            for item in result["checklist"]:
                lines.append(f"□ {item}")

        return "\n".join(lines)


class ImpactAnalyzer:
    """
    Analyzes changed files and suggests potential impacts.
    """

    PATTERNS = [
        # Documentation
        ("CLAUDE.md", "Template auch aktualisieren?", "docs", "exact"),
        ("README.md", "Andere Dokumentation konsistent?", "docs", "exact"),
        ("CHANGELOG.md", "Version konsistent?", "docs", "exact"),

        # MCP Server
        ("chainguard_mcp.py", "Nach ~/.chainguard/ kopieren!", "mcp", "exact"),

        # Installer
        ("install.sh", "Versionsnummer konsistent?", "installer", "exact"),
        ("setup.py", "pyproject.toml auch aktualisieren?", "installer", "exact"),
        ("package.json", "package-lock.json regenerieren?", "installer", "exact"),

        # Config
        ("docker-compose.yml", "Dockerfile konsistent?", "config", "exact"),

        # PHP/Laravel
        ("Controller.php", "Tests vorhanden?", "code", "suffix"),
        ("Model.php", "Migrations aktuell?", "code", "suffix"),
        ("/migrations/", "Model-Änderungen konsistent?", "code", "contains"),

        # Tests
        ("Test.php", "Implementierung auch geändert?", "test", "suffix"),
        ("_test.py", "Implementierung auch geändert?", "test", "suffix"),
        (".test.ts", "Implementierung auch geändert?", "test", "suffix"),
        ("/tests/", "Getesteter Code auch geändert?", "test", "contains"),

        # Frontend
        (".tsx", "CSS/Styles konsistent?", "frontend", "suffix"),
        (".vue", "TypeScript-Typen aktuell?", "frontend", "suffix"),

        # API
        ("/routes/", "API-Dokumentation aktualisieren?", "api", "contains"),
        ("/api/", "Client-Code aktualisieren?", "api", "contains"),

        # Types
        (".d.ts", "Implementierung nutzt neue Typen?", "types", "suffix"),
    ]

    @classmethod
    def _matches_pattern(cls, file: str, pattern: str, match_type: str) -> bool:
        """Check if file matches pattern based on match type."""
        file_lower = file.lower()
        pattern_lower = pattern.lower()

        if match_type == "exact":
            return file_lower.endswith(f"/{pattern_lower}") or file_lower == pattern_lower
        elif match_type == "suffix":
            return file_lower.endswith(pattern_lower)
        elif match_type == "prefix":
            filename = file_lower.split("/")[-1] if "/" in file_lower else file_lower
            return filename.startswith(pattern_lower)
        elif match_type == "contains":
            return pattern_lower in file_lower
        return False

    @classmethod
    def analyze(cls, changed_files: List[str]) -> List[Dict[str, str]]:
        """Analyze changed files and return impact hints."""
        hints = []
        seen_hints = set()

        for file in changed_files:
            for pattern, hint, category, match_type in cls.PATTERNS:
                if cls._matches_pattern(file, pattern, match_type):
                    hint_key = f"{category}:{hint}"
                    if hint_key not in seen_hints:
                        seen_hints.add(hint_key)
                        hints.append({
                            "file": file,
                            "hint": hint,
                            "category": category
                        })

        return hints

    @classmethod
    def format_impact_check(cls, changed_files: List[str], scope_desc: str) -> str:
        """Format the impact check message."""
        lines = []
        lines.append("📋 **IMPACT-CHECK**")
        lines.append("")

        if changed_files:
            files_preview = ", ".join(changed_files[:8])
            if len(changed_files) > 8:
                files_preview += f" (+{len(changed_files) - 8} weitere)"
            lines.append(f"**Geänderte Dateien:** {files_preview}")
            lines.append("")

        hints = cls.analyze(changed_files)
        if hints:
            lines.append("**Erkannte Abhängigkeiten:**")
            for h in hints[:5]:
                lines.append(f"• {h['file']} → {h['hint']}")
            lines.append("")

        lines.append("**Bitte prüfen:**")
        lines.append("→ Haben diese Änderungen Auswirkungen auf andere Bereiche?")
        lines.append("")
        lines.append("Falls nein: `chainguard_finish(confirmed=true)`")
        lines.append("Falls ja: Erst die weiteren Änderungen durchführen, dann finish.")

        return "\n".join(lines)
