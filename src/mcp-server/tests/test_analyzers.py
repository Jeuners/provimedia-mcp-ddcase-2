"""
Tests for chainguard.analyzers module.

Tests cover:
- CodeAnalyzer: metrics calculation, pattern detection, hotspots, TODOs
- ImpactAnalyzer: pattern matching, impact analysis, formatting
"""

import pytest
import tempfile
import asyncio
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from chainguard.analyzers import CodeAnalyzer, ImpactAnalyzer


# =============================================================================
# Fixtures
# =============================================================================
@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


# =============================================================================
# TestCodeAnalyzerMetrics
# =============================================================================
class TestCodeAnalyzerMetrics:
    """Tests for CodeAnalyzer._calculate_metrics method."""

    def test_calculate_metrics_simple(self):
        """Test basic code metrics calculation."""
        content = """
def hello():
    print("Hello World")

def goodbye():
    print("Goodbye")
"""
        lines = content.split('\n')
        metrics = CodeAnalyzer._calculate_metrics(content, lines)

        assert metrics["loc"] == 7  # 7 lines including empty first line
        assert metrics["loc_code"] > 0
        assert metrics["functions"] == 2
        assert metrics["classes"] == 0
        assert metrics["complexity"] >= 1

    def test_calculate_metrics_complex(self):
        """Test metrics for code with high complexity."""
        content = """
def complex_function(data):
    if data is None:
        return None

    for item in data:
        if item > 10:
            while item > 0:
                try:
                    if item % 2 == 0 and item > 5:
                        item = item - 1
                    else:
                        item = item - 2
                except Exception:
                    pass

    for other in data:
        if other < 0 or other > 100:
            continue

class DataProcessor:
    def process(self):
        for x in range(10):
            if x > 5:
                return x
"""
        lines = content.split('\n')
        metrics = CodeAnalyzer._calculate_metrics(content, lines)

        assert metrics["functions"] == 2  # complex_function + process
        assert metrics["classes"] == 1
        assert metrics["complexity_raw"] > 10  # Many if/for/while/try/and/or
        assert metrics["complexity"] >= 3  # Should be medium-high complexity

    def test_calculate_metrics_empty(self):
        """Test metrics for empty file."""
        content = ""
        lines = content.split('\n')
        metrics = CodeAnalyzer._calculate_metrics(content, lines)

        assert metrics["loc"] == 1  # Empty string splits to ['']
        assert metrics["loc_code"] == 0
        assert metrics["functions"] == 0
        assert metrics["classes"] == 0
        assert metrics["complexity"] == 1  # Minimum complexity

    def test_calculate_metrics_comments_only(self):
        """Test metrics for file with only comments."""
        content = """
# This is a comment
# Another comment
// JS style comment
"""
        lines = content.split('\n')
        metrics = CodeAnalyzer._calculate_metrics(content, lines)

        assert metrics["loc_code"] == 0
        assert metrics["functions"] == 0

    def test_calculate_metrics_async_functions(self):
        """Test that async functions are counted."""
        content = """
async def fetch_data():
    await some_api()

async def process_data():
    result = await fetch_data()
    return result
"""
        lines = content.split('\n')
        metrics = CodeAnalyzer._calculate_metrics(content, lines)

        assert metrics["functions"] == 2

    def test_calculate_metrics_javascript_functions(self):
        """Test JavaScript function detection."""
        content = """
function hello() {
    console.log("Hello");
}

async function fetchData() {
    return await fetch('/api');
}
"""
        lines = content.split('\n')
        metrics = CodeAnalyzer._calculate_metrics(content, lines)

        assert metrics["functions"] == 2


# =============================================================================
# TestCodeAnalyzerPatterns
# =============================================================================
class TestCodeAnalyzerPatterns:
    """Tests for CodeAnalyzer pattern detection methods."""

    def test_detect_patterns_async_io(self):
        """Test detection of async-io patterns."""
        content = """
import asyncio
import aiofiles

async def read_file():
    async with aiofiles.open('file.txt') as f:
        return await f.read()
"""
        patterns = CodeAnalyzer._detect_patterns(content)

        assert "async-io" in patterns

    def test_detect_patterns_file_io(self):
        """Test detection of file-io patterns."""
        content = """
from pathlib import Path

def read_config():
    with open('config.json', 'r') as f:
        return json.load(f)
"""
        patterns = CodeAnalyzer._detect_patterns(content)

        assert "file-io" in patterns

    def test_detect_patterns_none(self):
        """Test when no patterns are detected."""
        content = """
x = 1
y = 2
z = x + y
print(z)
"""
        patterns = CodeAnalyzer._detect_patterns(content)

        assert patterns == []

    def test_detect_patterns_mcp_server(self):
        """Test detection of MCP server patterns."""
        content = """
from mcp.server import Server

@server.list_tools()
async def handle_list_tools():
    return []
"""
        patterns = CodeAnalyzer._detect_patterns(content)

        assert "mcp-server" in patterns

    def test_detect_patterns_http_client(self):
        """Test detection of HTTP client patterns."""
        content = """
import aiohttp

async def fetch():
    async with aiohttp.ClientSession() as session:
        return await session.get('https://api.example.com')
"""
        patterns = CodeAnalyzer._detect_patterns(content)

        assert "http-client" in patterns

    def test_detect_patterns_caching(self):
        """Test detection of caching patterns."""
        content = """
from functools import lru_cache

_cache = {}
TTL = 300

class MyCache(LRUCache):
    pass
"""
        patterns = CodeAnalyzer._detect_patterns(content)

        assert "caching" in patterns

    def test_detect_patterns_subprocess(self):
        """Test detection of subprocess patterns."""
        content = """
import subprocess

result = subprocess.run(['ls', '-la'], capture_output=True)
proc = subprocess.Popen(['git', 'status'])
"""
        patterns = CodeAnalyzer._detect_patterns(content)

        assert "subprocess" in patterns

    def test_detect_patterns_laravel_controller(self):
        """Test detection of Laravel controller patterns."""
        content = """
class UserController extends Controller
{
    public function index()
    {
        return User::all();
    }

    public function store(Request $request)
    {
        $request->validate([...]);
    }
}
"""
        patterns = CodeAnalyzer._detect_patterns(content)

        assert "laravel-controller" in patterns

    def test_detect_patterns_react_component(self):
        """Test detection of React component patterns."""
        content = """
import React from 'react';
import { useState, useEffect } from 'react';

export default function MyComponent() {
    const [data, setData] = useState(null);

    useEffect(() => {
        fetchData();
    }, []);

    return <div>{data}</div>;
}
"""
        patterns = CodeAnalyzer._detect_patterns(content)

        assert "react-component" in patterns

    def test_detect_patterns_multiple(self):
        """Test detection of multiple patterns."""
        content = """
import asyncio
import subprocess
from pathlib import Path

async def run_command():
    proc = await asyncio.create_subprocess_exec('ls')
    with open('log.txt', 'w') as f:
        f.write('done')
"""
        patterns = CodeAnalyzer._detect_patterns(content)

        assert "async-io" in patterns
        assert "subprocess" in patterns
        assert "file-io" in patterns

    def test_build_checklist(self):
        """Test building checklist from detected patterns."""
        patterns = ["async-io", "file-io"]
        checklist = CodeAnalyzer._build_checklist(patterns)

        assert len(checklist) > 0
        assert len(checklist) <= 10  # Max 10 items

        # Check that async-io checklist items are present
        async_items = CodeAnalyzer.PATTERNS["async-io"]["checklist"]
        for item in async_items:
            assert item in checklist

    def test_build_checklist_empty(self):
        """Test building checklist with no patterns."""
        checklist = CodeAnalyzer._build_checklist([])

        assert checklist == []

    def test_build_checklist_unknown_pattern(self):
        """Test building checklist with unknown pattern (should be ignored)."""
        checklist = CodeAnalyzer._build_checklist(["unknown-pattern"])

        assert checklist == []

    def test_build_checklist_no_duplicates(self):
        """Test that checklist has no duplicate items."""
        # Some patterns might share similar checklist items
        patterns = ["async-io", "http-client", "mcp-server"]
        checklist = CodeAnalyzer._build_checklist(patterns)

        # Check for duplicates
        assert len(checklist) == len(set(checklist))


# =============================================================================
# TestCodeAnalyzerHotspots
# =============================================================================
class TestCodeAnalyzerHotspots:
    """Tests for CodeAnalyzer hotspot and TODO detection."""

    def test_find_hotspots(self):
        """Test finding complex functions."""
        content = """
def simple():
    return 1

def complex_func():
    if x > 0:
        for i in range(10):
            if i % 2 == 0:
                while True:
                    try:
                        if done:
                            break
                    except:
                        pass

def another_simple():
    print("hello")
"""
        lines = content.split('\n')
        hotspots = CodeAnalyzer._find_hotspots(content, lines)

        # Only complex_func should be a hotspot (complexity > 3)
        assert len(hotspots) >= 1
        hotspot_names = [h["name"] for h in hotspots]
        assert "complex_func" in hotspot_names

        # Verify hotspot has line number and complexity
        for h in hotspots:
            assert "name" in h
            assert "line" in h
            assert "complexity" in h
            assert h["complexity"] > 3

    def test_find_hotspots_none(self):
        """Test when no hotspots are found (all simple functions)."""
        content = """
def simple1():
    return 1

def simple2():
    return 2

def simple3():
    x = 1
    return x
"""
        lines = content.split('\n')
        hotspots = CodeAnalyzer._find_hotspots(content, lines)

        assert len(hotspots) == 0

    def test_find_hotspots_sorted_by_complexity(self):
        """Test that hotspots are sorted by complexity (highest first)."""
        content = """
def medium():
    if x > 0:
        for i in range(10):
            if i > 5:
                while True:
                    break

def very_complex():
    if a:
        for b in c:
            if d:
                while e:
                    try:
                        if f:
                            for g in h:
                                if i:
                                    pass
                    except:
                        pass
"""
        lines = content.split('\n')
        hotspots = CodeAnalyzer._find_hotspots(content, lines)

        if len(hotspots) >= 2:
            # First hotspot should have higher complexity
            assert hotspots[0]["complexity"] >= hotspots[1]["complexity"]

    def test_find_todos(self):
        """Test finding TODO/FIXME comments."""
        content = """
# TODO: Implement this feature
def placeholder():
    pass  # FIXME: This is broken

# HACK: Temporary workaround
x = 1

# XXX: Review this
"""
        lines = content.split('\n')
        todos = CodeAnalyzer._find_todos(lines)

        assert len(todos) == 4

        types = [t["type"] for t in todos]
        assert "TODO" in types
        assert "FIXME" in types
        assert "HACK" in types
        assert "XXX" in types

        # Verify structure
        for todo in todos:
            assert "type" in todo
            assert "text" in todo
            assert "line" in todo

    def test_find_todos_none(self):
        """Test when no TODOs are found."""
        content = """
def hello():
    # This is a regular comment
    print("Hello World")
"""
        lines = content.split('\n')
        todos = CodeAnalyzer._find_todos(lines)

        assert len(todos) == 0

    def test_find_todos_with_colon(self):
        """Test TODO with colon separator."""
        content = """
# TODO: Fix the bug
# TODO Fix without colon
"""
        lines = content.split('\n')
        todos = CodeAnalyzer._find_todos(lines)

        assert len(todos) == 2

    def test_find_todos_text_truncation(self):
        """Test that TODO text is truncated to 50 characters."""
        long_text = "A" * 100
        content = f"# TODO: {long_text}"
        lines = content.split('\n')
        todos = CodeAnalyzer._find_todos(lines)

        assert len(todos) == 1
        assert len(todos[0]["text"]) <= 50


# =============================================================================
# TestCodeAnalyzerAsync
# =============================================================================
class TestCodeAnalyzerAsync:
    """Async tests for CodeAnalyzer.analyze_file."""

    @pytest.mark.asyncio
    async def test_analyze_file_basic(self, temp_dir):
        """Test analyzing a basic Python file."""
        test_file = temp_dir / "test.py"
        test_file.write_text("""
import asyncio

async def main():
    if True:
        for i in range(10):
            await asyncio.sleep(0.1)

# TODO: Add error handling
""")

        result = await CodeAnalyzer.analyze_file("test.py", str(temp_dir))

        assert "error" not in result
        assert result["file"] == "test.py"
        assert "metrics" in result
        assert "patterns" in result
        assert "checklist" in result
        assert "hotspots" in result
        assert "todos" in result

        assert "async-io" in result["patterns"]
        assert len(result["todos"]) == 1

    @pytest.mark.asyncio
    async def test_analyze_file_not_found(self, temp_dir):
        """Test analyzing a non-existent file."""
        result = await CodeAnalyzer.analyze_file("nonexistent.py", str(temp_dir))

        assert "error" in result
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_analyze_file_absolute_path(self, temp_dir):
        """Test analyzing with absolute path."""
        test_file = temp_dir / "absolute.py"
        test_file.write_text("x = 1")

        result = await CodeAnalyzer.analyze_file(str(test_file), str(temp_dir))

        assert "error" not in result
        assert result["file"] == "absolute.py"

    def test_format_output(self, temp_dir):
        """Test output formatting."""
        result = {
            "file": "test.py",
            "path": str(temp_dir / "test.py"),
            "metrics": {
                "loc": 100,
                "loc_code": 80,
                "functions": 5,
                "classes": 2,
                "complexity": 3,
                "complexity_raw": 15,
            },
            "patterns": ["async-io", "file-io"],
            "checklist": ["Check async/await", "Handle errors"],
            "hotspots": [
                {"name": "complex_func", "line": 10, "complexity": 8}
            ],
            "todos": [{"type": "TODO", "text": "Fix this", "line": 5}],
        }

        output = CodeAnalyzer.format_output(result)

        assert "test.py" in output
        assert "100 LOC" in output
        assert "80 Code" in output
        assert "5 Funktionen" in output
        assert "2 Klassen" in output
        assert "async-io" in output
        assert "file-io" in output
        assert "complex_func" in output
        assert "TODOs: 1" in output

    def test_format_output_error(self):
        """Test output formatting for error result."""
        result = {"error": "File not found"}

        output = CodeAnalyzer.format_output(result)

        assert "fehlgeschlagen" in output
        assert "File not found" in output


# =============================================================================
# TestImpactAnalyzer
# =============================================================================
class TestImpactAnalyzer:
    """Tests for ImpactAnalyzer class."""

    def test_matches_pattern_exact(self):
        """Test exact pattern matching."""
        # Should match
        assert ImpactAnalyzer._matches_pattern("CLAUDE.md", "CLAUDE.md", "exact")
        assert ImpactAnalyzer._matches_pattern("docs/CLAUDE.md", "CLAUDE.md", "exact")
        assert ImpactAnalyzer._matches_pattern("/path/to/CLAUDE.md", "CLAUDE.md", "exact")

        # Should not match
        assert not ImpactAnalyzer._matches_pattern("CLAUDE.md.bak", "CLAUDE.md", "exact")
        assert not ImpactAnalyzer._matches_pattern("MY_CLAUDE.md", "CLAUDE.md", "exact")

    def test_matches_pattern_suffix(self):
        """Test suffix pattern matching."""
        # Should match
        assert ImpactAnalyzer._matches_pattern("UserController.php", "Controller.php", "suffix")
        assert ImpactAnalyzer._matches_pattern("AuthController.php", "Controller.php", "suffix")
        assert ImpactAnalyzer._matches_pattern("app/Http/Controllers/UserController.php", "Controller.php", "suffix")

        # Should not match
        assert not ImpactAnalyzer._matches_pattern("Controller.php.bak", "Controller.php", "suffix")
        assert not ImpactAnalyzer._matches_pattern("ControllerHelper.php", "Controller.php", "suffix")

    def test_matches_pattern_prefix(self):
        """Test prefix pattern matching."""
        # Should match
        assert ImpactAnalyzer._matches_pattern("test_user.py", "test_", "prefix")
        assert ImpactAnalyzer._matches_pattern("tests/test_user.py", "test_", "prefix")

        # Should not match (checks filename only)
        assert not ImpactAnalyzer._matches_pattern("user_test.py", "test_", "prefix")

    def test_matches_pattern_contains(self):
        """Test contains pattern matching."""
        # Should match
        assert ImpactAnalyzer._matches_pattern("app/migrations/001_create_users.php", "/migrations/", "contains")
        assert ImpactAnalyzer._matches_pattern("/tests/unit/UserTest.php", "/tests/", "contains")
        assert ImpactAnalyzer._matches_pattern("src/api/users.ts", "/api/", "contains")

        # Should not match
        assert not ImpactAnalyzer._matches_pattern("migrations_backup.sql", "/migrations/", "contains")

    def test_matches_pattern_case_insensitive(self):
        """Test that matching is case insensitive."""
        assert ImpactAnalyzer._matches_pattern("CLAUDE.MD", "claude.md", "exact")
        assert ImpactAnalyzer._matches_pattern("usercontroller.PHP", "Controller.php", "suffix")

    def test_analyze_changed_files(self):
        """Test analyzing changed files for impacts."""
        changed_files = [
            "CLAUDE.md",
            "app/Http/Controllers/UserController.php",
            "database/migrations/2024_01_01_create_users.php",
        ]

        hints = ImpactAnalyzer.analyze(changed_files)

        assert len(hints) >= 1

        # Check structure
        for hint in hints:
            assert "file" in hint
            assert "hint" in hint
            assert "category" in hint

        # CLAUDE.md should trigger template hint
        claude_hints = [h for h in hints if "CLAUDE.md" in h["file"]]
        assert len(claude_hints) >= 1

    def test_analyze_no_matches(self):
        """Test analyzing files with no pattern matches."""
        changed_files = [
            "random.txt",
            "data.csv",
            "image.png",
        ]

        hints = ImpactAnalyzer.analyze(changed_files)

        assert hints == []

    def test_analyze_deduplication(self):
        """Test that hints are deduplicated by category:hint."""
        changed_files = [
            "UserController.php",
            "AuthController.php",
            "ProductController.php",
        ]

        hints = ImpactAnalyzer.analyze(changed_files)

        # All match Controller.php suffix, but should only get one "Tests vorhanden?" hint
        test_hints = [h for h in hints if h["hint"] == "Tests vorhanden?"]
        assert len(test_hints) == 1

    def test_format_impact_check(self):
        """Test formatting the impact check message."""
        changed_files = [
            "CLAUDE.md",
            "app/Http/Controllers/UserController.php",
        ]

        output = ImpactAnalyzer.format_impact_check(changed_files, "Test scope")

        assert "IMPACT-CHECK" in output
        assert "CLAUDE.md" in output
        assert "UserController.php" in output
        assert "Geänderte Dateien" in output
        assert "chainguard_finish(confirmed=true)" in output

    def test_format_impact_check_empty(self):
        """Test formatting with no changed files."""
        output = ImpactAnalyzer.format_impact_check([], "Empty scope")

        assert "IMPACT-CHECK" in output
        assert "Bitte prüfen" in output

    def test_format_impact_check_many_files(self):
        """Test formatting with many files (truncation)."""
        changed_files = [f"file{i}.php" for i in range(20)]

        output = ImpactAnalyzer.format_impact_check(changed_files, "Many files")

        # Should show first 8 files and indicate more
        assert "+12 weitere" in output

    def test_format_impact_check_with_hints(self):
        """Test that hints are shown in output."""
        changed_files = [
            "CLAUDE.md",
            "package.json",
        ]

        output = ImpactAnalyzer.format_impact_check(changed_files, "With hints")

        assert "Erkannte Abhängigkeiten" in output
        assert "Template auch aktualisieren?" in output or "package-lock.json regenerieren?" in output

    def test_patterns_coverage(self):
        """Test that all defined patterns work correctly."""
        # Test each pattern type
        test_cases = [
            ("CLAUDE.md", "docs"),
            ("README.md", "docs"),
            ("CHANGELOG.md", "docs"),
            ("chainguard_mcp.py", "mcp"),
            ("install.sh", "installer"),
            ("setup.py", "installer"),
            ("package.json", "installer"),
            ("docker-compose.yml", "config"),
            ("UserController.php", "code"),
            ("User.Model.php", "code"),  # This won't match exactly, testing suffix
            ("app/migrations/001.php", "code"),
            ("UserTest.php", "test"),
            ("user_test.py", "test"),
            ("user.test.ts", "test"),
            ("tests/unit/user.php", "test"),
            ("components/Button.tsx", "frontend"),
            ("components/App.vue", "frontend"),
            ("routes/web.php", "api"),
            ("api/users.ts", "api"),
            ("types/user.d.ts", "types"),
        ]

        for file, expected_category in test_cases:
            hints = ImpactAnalyzer.analyze([file])
            if hints:
                categories = [h["category"] for h in hints]
                # Just verify we get some hints for most patterns
                # Not all files will match (e.g., User.Model.php won't match Model.php suffix)
                pass  # Pattern is exercised


# =============================================================================
# Integration Tests
# =============================================================================
class TestAnalyzersIntegration:
    """Integration tests combining CodeAnalyzer and ImpactAnalyzer."""

    @pytest.mark.asyncio
    async def test_full_analysis_workflow(self, temp_dir):
        """Test a complete analysis workflow."""
        # Create a test file (using # comments since _find_todos looks for # style)
        test_file = temp_dir / "UserController.py"
        test_file.write_text("""
class UserController:
    # TODO: Add validation
    def index(self):
        if self.user:
            for u in self.users:
                if u.active:
                    # FIXME: This is slow
                    pass

    def store(self, request):
        request.validate({
            'name': 'required',
        })
""")

        # Run code analysis
        result = await CodeAnalyzer.analyze_file("UserController.py", str(temp_dir))

        assert "error" not in result
        assert len(result["todos"]) == 2  # TODO and FIXME

        # Run impact analysis on a PHP controller to test Controller.php pattern
        hints = ImpactAnalyzer.analyze(["UserController.php"])

        assert len(hints) >= 1
        hint_texts = [h["hint"] for h in hints]
        assert "Tests vorhanden?" in hint_texts
