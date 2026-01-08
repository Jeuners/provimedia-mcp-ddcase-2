"""
Tests for chainguard.ast_analyzer module.

Tests AST-based code analysis with regex fallback.
"""

import pytest
import tempfile
from pathlib import Path


class TestSymbolType:
    """Tests for SymbolType enum."""

    def test_import(self):
        """Test that SymbolType can be imported."""
        from chainguard.ast_analyzer import SymbolType
        assert SymbolType is not None

    def test_enum_values(self):
        """Test that all expected symbol types exist."""
        from chainguard.ast_analyzer import SymbolType

        assert SymbolType.CLASS.value == "class"
        assert SymbolType.FUNCTION.value == "function"
        assert SymbolType.METHOD.value == "method"
        assert SymbolType.INTERFACE.value == "interface"
        assert SymbolType.IMPORT.value == "import"


class TestRelationType:
    """Tests for RelationType enum."""

    def test_import(self):
        """Test that RelationType can be imported."""
        from chainguard.ast_analyzer import RelationType
        assert RelationType is not None

    def test_enum_values(self):
        """Test that all expected relation types exist."""
        from chainguard.ast_analyzer import RelationType

        assert RelationType.IMPORTS.value == "imports"
        assert RelationType.EXTENDS.value == "extends"
        assert RelationType.IMPLEMENTS.value == "implements"
        assert RelationType.USES.value == "uses"


class TestCodeSymbol:
    """Tests for CodeSymbol dataclass."""

    def test_create_symbol(self):
        """Test creating a CodeSymbol."""
        from chainguard.ast_analyzer import CodeSymbol, SymbolType

        symbol = CodeSymbol(
            name="MyClass",
            type=SymbolType.CLASS,
            file_path="src/models.py",
            line_start=10,
            line_end=50,
            signature="class MyClass(BaseModel):"
        )

        assert symbol.name == "MyClass"
        assert symbol.type == SymbolType.CLASS
        assert symbol.line_start == 10
        assert symbol.line_end == 50

    def test_to_dict(self):
        """Test CodeSymbol.to_dict()."""
        from chainguard.ast_analyzer import CodeSymbol, SymbolType

        symbol = CodeSymbol(
            name="my_function",
            type=SymbolType.FUNCTION,
            file_path="utils.py",
            line_start=5,
            line_end=15,
            parameters=["arg1", "arg2"],
            return_type="str"
        )

        d = symbol.to_dict()
        assert d["name"] == "my_function"
        assert d["type"] == "function"
        assert d["parameters"] == ["arg1", "arg2"]
        assert d["return_type"] == "str"

    def test_to_memory_content(self):
        """Test generating memory content from symbol."""
        from chainguard.ast_analyzer import CodeSymbol, SymbolType

        symbol = CodeSymbol(
            name="UserController",
            type=SymbolType.CLASS,
            file_path="controllers.py",
            line_start=1,
            line_end=100,
            signature="class UserController:",
            docstring="Handles user operations"
        )

        content = symbol.to_memory_content()
        assert "class" in content
        assert "UserController" in content
        assert "Handles user" in content


class TestFileAnalysis:
    """Tests for FileAnalysis dataclass."""

    def test_create_analysis(self):
        """Test creating a FileAnalysis."""
        from chainguard.ast_analyzer import FileAnalysis

        analysis = FileAnalysis(
            file_path="src/main.py",
            language="python",
            imports=["os", "sys"],
        )

        assert analysis.file_path == "src/main.py"
        assert analysis.language == "python"
        assert "os" in analysis.imports

    def test_to_dict(self):
        """Test FileAnalysis.to_dict()."""
        from chainguard.ast_analyzer import FileAnalysis, CodeSymbol, SymbolType

        symbol = CodeSymbol(
            name="test",
            type=SymbolType.FUNCTION,
            file_path="test.py",
            line_start=1,
            line_end=5
        )

        analysis = FileAnalysis(
            file_path="test.py",
            language="python",
            symbols=[symbol],
            imports=["pytest"]
        )

        d = analysis.to_dict()
        assert d["file_path"] == "test.py"
        assert d["language"] == "python"
        assert len(d["symbols"]) == 1
        assert d["imports"] == ["pytest"]


class TestLanguageExtensions:
    """Tests for LANGUAGE_EXTENSIONS mapping."""

    def test_extensions_defined(self):
        """Test that language extensions are defined."""
        from chainguard.ast_analyzer import LANGUAGE_EXTENSIONS

        assert ".py" in LANGUAGE_EXTENSIONS
        assert ".js" in LANGUAGE_EXTENSIONS
        assert ".ts" in LANGUAGE_EXTENSIONS
        assert ".php" in LANGUAGE_EXTENSIONS
        assert ".go" in LANGUAGE_EXTENSIONS

    def test_extension_values(self):
        """Test that extensions map to correct languages."""
        from chainguard.ast_analyzer import LANGUAGE_EXTENSIONS

        assert LANGUAGE_EXTENSIONS[".py"] == "python"
        assert LANGUAGE_EXTENSIONS[".js"] == "javascript"
        assert LANGUAGE_EXTENSIONS[".ts"] == "typescript"
        assert LANGUAGE_EXTENSIONS[".php"] == "php"


class TestRegexAnalyzer:
    """Tests for RegexAnalyzer (fallback analyzer)."""

    def test_import(self):
        """Test that RegexAnalyzer can be imported."""
        from chainguard.ast_analyzer import RegexAnalyzer
        assert RegexAnalyzer is not None

    def test_analyze_python_class(self):
        """Test analyzing Python class."""
        from chainguard.ast_analyzer import RegexAnalyzer

        code = '''
class MyClass(BaseClass):
    """A sample class."""

    def __init__(self, name):
        self.name = name

    def greet(self):
        return f"Hello, {self.name}"
'''

        analysis = RegexAnalyzer.analyze(code, "python", "test.py")

        assert analysis.language == "python"
        assert len(analysis.symbols) >= 1

        # Find the class
        classes = [s for s in analysis.symbols if s.type.value == "class"]
        assert len(classes) == 1
        assert classes[0].name == "MyClass"

    def test_analyze_python_function(self):
        """Test analyzing Python function."""
        from chainguard.ast_analyzer import RegexAnalyzer

        code = '''
def calculate_sum(a, b, c=0):
    """Calculate sum of numbers."""
    return a + b + c

def another_function():
    pass
'''

        analysis = RegexAnalyzer.analyze(code, "python", "test.py")

        functions = [s for s in analysis.symbols if s.type.value == "function"]
        assert len(functions) >= 2

        calc_func = [f for f in functions if f.name == "calculate_sum"]
        assert len(calc_func) == 1
        assert "a" in calc_func[0].parameters

    def test_analyze_python_imports(self):
        """Test analyzing Python imports."""
        from chainguard.ast_analyzer import RegexAnalyzer

        code = '''
import os
import sys
from pathlib import Path
from typing import Dict, List
'''

        analysis = RegexAnalyzer.analyze(code, "python", "test.py")

        assert len(analysis.imports) >= 2
        assert any("os" in imp for imp in analysis.imports)
        assert any("pathlib" in imp or "Path" in imp for imp in analysis.imports)

    def test_analyze_javascript_class(self):
        """Test analyzing JavaScript class."""
        from chainguard.ast_analyzer import RegexAnalyzer

        code = '''
class UserService extends BaseService {
    constructor(db) {
        super();
        this.db = db;
    }

    async getUser(id) {
        return await this.db.find(id);
    }
}
'''

        analysis = RegexAnalyzer.analyze(code, "javascript", "test.js")

        classes = [s for s in analysis.symbols if s.type.value == "class"]
        assert len(classes) == 1
        assert classes[0].name == "UserService"

    def test_analyze_javascript_function(self):
        """Test analyzing JavaScript function."""
        from chainguard.ast_analyzer import RegexAnalyzer

        code = '''
function processData(data, options) {
    return data.map(item => item * 2);
}

async function fetchUser(id) {
    return await api.get(`/users/${id}`);
}

const helper = (x) => x + 1;
'''

        analysis = RegexAnalyzer.analyze(code, "javascript", "test.js")

        functions = [s for s in analysis.symbols if s.type.value in ["function", "arrow_function"]]
        assert len(functions) >= 2

    def test_analyze_php_class(self):
        """Test analyzing PHP class."""
        from chainguard.ast_analyzer import RegexAnalyzer

        code = '''
<?php

class UserController extends Controller
{
    public function index()
    {
        return view('users.index');
    }

    private function validateUser($user)
    {
        return $user->isValid();
    }
}
'''

        analysis = RegexAnalyzer.analyze(code, "php", "UserController.php")

        classes = [s for s in analysis.symbols if s.type.value == "class"]
        assert len(classes) == 1
        assert classes[0].name == "UserController"

        methods = [s for s in analysis.symbols if s.type.value == "method"]
        assert len(methods) >= 2

    def test_analyze_typescript_interface(self):
        """Test analyzing TypeScript interface."""
        from chainguard.ast_analyzer import RegexAnalyzer

        code = '''
export interface UserDTO {
    id: number;
    name: string;
    email: string;
}

export class UserService implements UserDTO {
    constructor(public id: number, public name: string, public email: string) {}
}
'''

        analysis = RegexAnalyzer.analyze(code, "typescript", "user.ts")

        interfaces = [s for s in analysis.symbols if s.type.value == "interface"]
        assert len(interfaces) >= 1
        assert interfaces[0].name == "UserDTO"


class TestASTAnalyzer:
    """Tests for main ASTAnalyzer class."""

    def test_import(self):
        """Test that ASTAnalyzer can be imported."""
        from chainguard.ast_analyzer import ASTAnalyzer
        assert ASTAnalyzer is not None

    def test_create_analyzer(self):
        """Test creating an ASTAnalyzer."""
        from chainguard.ast_analyzer import ASTAnalyzer

        analyzer = ASTAnalyzer()
        assert analyzer is not None

    def test_global_analyzer_exists(self):
        """Test that global ast_analyzer instance exists."""
        from chainguard.ast_analyzer import ast_analyzer

        assert ast_analyzer is not None

    def test_analyze_file_with_content(self):
        """Test analyzing file with provided content."""
        from chainguard.ast_analyzer import ASTAnalyzer

        analyzer = ASTAnalyzer()
        code = '''
def hello():
    print("Hello, World!")
'''

        analysis = analyzer.analyze_file("test.py", content=code)

        assert analysis.language == "python"
        assert len(analysis.symbols) >= 1

    def test_analyze_unsupported_extension(self):
        """Test analyzing file with unsupported extension."""
        from chainguard.ast_analyzer import ASTAnalyzer

        analyzer = ASTAnalyzer()
        analysis = analyzer.analyze_file("test.xyz", content="some content")

        assert analysis.language == "unknown"
        assert len(analysis.symbols) == 0

    def test_analyze_real_file(self):
        """Test analyzing a real file."""
        from chainguard.ast_analyzer import ASTAnalyzer

        analyzer = ASTAnalyzer()

        with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode='w') as f:
            f.write('''
class TestClass:
    def method_one(self):
        pass

    def method_two(self, arg):
        return arg
''')
            f.flush()

            analysis = analyzer.analyze_file(f.name)

            assert analysis.language == "python"
            assert len(analysis.symbols) >= 1

            # Cleanup
            Path(f.name).unlink()


class TestTreeSitterAnalyzer:
    """Tests for TreeSitterAnalyzer (when available)."""

    def test_import(self):
        """Test that TreeSitterAnalyzer can be imported."""
        from chainguard.ast_analyzer import TreeSitterAnalyzer
        assert TreeSitterAnalyzer is not None

    def test_is_available(self):
        """Test is_available() method."""
        from chainguard.ast_analyzer import TreeSitterAnalyzer

        # Should return bool without error
        result = TreeSitterAnalyzer.is_available()
        assert isinstance(result, bool)


class TestFileRelation:
    """Tests for FileRelation dataclass."""

    def test_create_relation(self):
        """Test creating a FileRelation."""
        from chainguard.ast_analyzer import FileRelation, RelationType

        relation = FileRelation(
            source_file="src/app.py",
            target_file="src/utils.py",
            relation_type=RelationType.IMPORTS,
            symbols=["helper", "format_date"]
        )

        assert relation.source_file == "src/app.py"
        assert relation.target_file == "src/utils.py"
        assert relation.relation_type == RelationType.IMPORTS
        assert "helper" in relation.symbols

    def test_to_dict(self):
        """Test FileRelation.to_dict()."""
        from chainguard.ast_analyzer import FileRelation, RelationType

        relation = FileRelation(
            source_file="a.py",
            target_file="b.py",
            relation_type=RelationType.EXTENDS,
            symbols=["BaseClass"]
        )

        d = relation.to_dict()
        assert d["source"] == "a.py"
        assert d["target"] == "b.py"
        assert d["type"] == "extends"
