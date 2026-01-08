"""
CHAINGUARD MCP Server - AST Analyzer Module

Code analysis using tree-sitter for precise structure extraction.
This module is optional - requires tree-sitter and language grammars.

Copyright (c) 2026 Provimedia GmbH
Licensed under the Polyform Noncommercial License 1.0.0
See LICENSE file in the project root for full license information.

Supported Languages:
- Python (tree-sitter-python)
- JavaScript/TypeScript (tree-sitter-javascript, tree-sitter-typescript)
- PHP (tree-sitter-php)
- Go (tree-sitter-go)
- Rust (tree-sitter-rust)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Any, Tuple, TYPE_CHECKING
from pathlib import Path
from enum import Enum
import re

from .config import logger

# Import docstring parser (v5.4)
try:
    from .docstring_parser import parse_docstring, ParsedDocstring
    DOCSTRING_PARSER_AVAILABLE = True
except ImportError:
    DOCSTRING_PARSER_AVAILABLE = False
    ParsedDocstring = None  # type: ignore


# =============================================================================
# Constants
# =============================================================================

class SymbolType(str, Enum):
    """Types of code symbols."""
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    INTERFACE = "interface"
    TRAIT = "trait"
    ENUM = "enum"
    CONSTANT = "constant"
    VARIABLE = "variable"
    IMPORT = "import"
    EXPORT = "export"


class RelationType(str, Enum):
    """Types of relationships between symbols/files."""
    IMPORTS = "imports"
    EXTENDS = "extends"
    IMPLEMENTS = "implements"
    USES = "uses"
    CALLS = "calls"
    INSTANTIATES = "instantiates"


# Language file extensions
LANGUAGE_EXTENSIONS: Dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".php": "php",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".java": "java",
}


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class CodeSymbol:
    """Represents a code symbol (class, function, etc.)."""
    name: str
    type: SymbolType
    file_path: str
    line_start: int
    line_end: int
    signature: str = ""
    docstring: str = ""
    parent: Optional[str] = None  # For methods: class name
    parameters: List[str] = field(default_factory=list)
    return_type: Optional[str] = None
    modifiers: List[str] = field(default_factory=list)  # public, private, static, async
    _parsed_docstring: Any = field(default=None, repr=False)  # Cached ParsedDocstring

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type.value,
            "file_path": self.file_path,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "signature": self.signature,
            "docstring": self.docstring,
            "parent": self.parent,
            "parameters": self.parameters,
            "return_type": self.return_type,
            "modifiers": self.modifiers,
        }

    @property
    def parsed_docstring(self) -> Optional[Any]:
        """
        Get parsed docstring with full semantic information.

        Returns:
            ParsedDocstring object or None if parsing not available.
        """
        if self._parsed_docstring is not None:
            return self._parsed_docstring

        if not DOCSTRING_PARSER_AVAILABLE or not self.docstring:
            return None

        self._parsed_docstring = parse_docstring(self.docstring)
        return self._parsed_docstring

    def to_memory_content(self) -> str:
        """
        Generate rich content suitable for memory storage.

        v5.4: Uses parsed docstring for semantic understanding.
        Creates a searchable description that captures the full meaning.
        """
        parts = []

        # Type and name
        type_prefix = self.type.value
        if self.parent:
            parts.append(f"{type_prefix} {self.parent}.{self.name}")
        else:
            parts.append(f"{type_prefix} {self.name}")

        # Try to use parsed docstring for rich content
        parsed = self.parsed_docstring
        if parsed and not parsed.is_empty():
            # Use the parsed docstring's rich content
            rich_content = parsed.to_memory_content()
            if rich_content:
                parts.append(rich_content)
        elif self.docstring:
            # Fallback: use raw docstring (first 300 chars)
            clean_doc = ' '.join(self.docstring.split())[:300]
            if len(self.docstring) > 300:
                clean_doc += "..."
            parts.append(clean_doc)

        # Add signature if not already in docstring
        if self.signature and "signature" not in ' '.join(parts).lower():
            sig = self.signature[:150]
            if len(self.signature) > 150:
                sig += "..."
            parts.append(f"Signature: {sig}")

        # Add return type if known and not in docstring
        if self.return_type and self.return_type not in ' '.join(parts):
            parts.append(f"Returns: {self.return_type}")

        # Add parameters if not in parsed docstring
        if self.parameters and (not parsed or not parsed.params):
            param_str = ", ".join(self.parameters[:5])
            if len(self.parameters) > 5:
                param_str += f", ... (+{len(self.parameters) - 5} more)"
            parts.append(f"Parameters: {param_str}")

        # Add modifiers (async, static, etc.)
        if self.modifiers:
            important_mods = [m for m in self.modifiers if m in ['async', 'static', 'abstract', 'private']]
            if important_mods:
                parts.append(f"Modifiers: {', '.join(important_mods)}")

        # Add file location
        if self.file_path:
            file_name = Path(self.file_path).name if '/' in self.file_path else self.file_path
            parts.append(f"File: {file_name}")

        return ". ".join(parts)

    def get_semantic_category(self) -> str:
        """
        Infer semantic category from name and type.

        Returns category like 'validation', 'data_access', 'handler', etc.
        """
        name_lower = self.name.lower()

        # Name-based inference
        if name_lower.startswith('validate') or name_lower.startswith('check'):
            return "validation"
        elif name_lower.startswith('get_') or name_lower.startswith('fetch_'):
            return "data_retrieval"
        elif name_lower.startswith('set_') or name_lower.startswith('update_'):
            return "data_mutation"
        elif name_lower.startswith('create_') or name_lower.startswith('make_'):
            return "factory"
        elif name_lower.startswith('handle_') or name_lower.endswith('_handler'):
            return "event_handler"
        elif name_lower.startswith('parse_') or name_lower.startswith('extract_'):
            return "parsing"
        elif name_lower.startswith('test_') or name_lower.startswith('_test'):
            return "testing"
        elif name_lower.startswith('_'):
            return "internal"
        elif self.type == SymbolType.CLASS:
            # Class name patterns
            if 'manager' in name_lower:
                return "management"
            elif 'factory' in name_lower:
                return "factory"
            elif 'handler' in name_lower:
                return "event_handler"
            elif 'service' in name_lower:
                return "service"
            elif 'repository' in name_lower or 'repo' in name_lower:
                return "data_access"
            elif 'controller' in name_lower:
                return "controller"
            elif 'model' in name_lower:
                return "model"

        return "general"


@dataclass
class FileRelation:
    """Represents a relationship between files."""
    source_file: str
    target_file: str
    relation_type: RelationType
    symbols: List[str] = field(default_factory=list)  # Imported symbols

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source_file,
            "target": self.target_file,
            "type": self.relation_type.value,
            "symbols": self.symbols,
        }


@dataclass
class FileAnalysis:
    """Complete analysis result for a file."""
    file_path: str
    language: str
    symbols: List[CodeSymbol] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    exports: List[str] = field(default_factory=list)
    relations: List[FileRelation] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "language": self.language,
            "symbols": [s.to_dict() for s in self.symbols],
            "imports": self.imports,
            "exports": self.exports,
            "relations": [r.to_dict() for r in self.relations],
        }


# =============================================================================
# Fallback Regex-based Analyzer (when tree-sitter not available)
# =============================================================================

class RegexAnalyzer:
    """
    Fallback analyzer using regex patterns.
    Less accurate than tree-sitter but works without dependencies.
    """

    # Regex patterns for different languages
    PATTERNS = {
        "python": {
            "class": r'^class\s+(\w+)(?:\(([^)]*)\))?:',
            "function": r'^def\s+(\w+)\s*\(([^)]*)\)(?:\s*->\s*(\S+))?:',
            "method": r'^    def\s+(\w+)\s*\(([^)]*)\)(?:\s*->\s*(\S+))?:',
            "import": r'^(?:from\s+(\S+)\s+)?import\s+(.+)$',
            "docstring": r'^\s*"""([^"]*)"""',
        },
        "javascript": {
            "class": r'^(?:export\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?',
            "function": r'^(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)',
            "arrow": r'^(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\([^)]*\)\s*=>',
            "import": r'^import\s+(?:{([^}]+)}|(\w+))\s+from\s+[\'"]([^\'"]+)[\'"]',
            "export": r'^export\s+(?:default\s+)?(?:class|function|const|let|var)\s+(\w+)',
        },
        "typescript": {
            "class": r'^(?:export\s+)?class\s+(\w+)(?:<[^>]+>)?(?:\s+extends\s+(\w+))?(?:\s+implements\s+(\w+))?',
            "interface": r'^(?:export\s+)?interface\s+(\w+)(?:<[^>]+>)?(?:\s+extends\s+(\w+))?',
            "function": r'^(?:export\s+)?(?:async\s+)?function\s+(\w+)(?:<[^>]+>)?\s*\(([^)]*)\)(?:\s*:\s*(\S+))?',
            "type": r'^(?:export\s+)?type\s+(\w+)(?:<[^>]+>)?\s*=',
            "import": r'^import\s+(?:{([^}]+)}|(\w+)|\*\s+as\s+(\w+))\s+from\s+[\'"]([^\'"]+)[\'"]',
        },
        "php": {
            "class": r'^(?:abstract\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?(?:\s+implements\s+([^{]+))?',
            "interface": r'^interface\s+(\w+)(?:\s+extends\s+(\w+))?',
            "trait": r'^trait\s+(\w+)',
            "function": r'^(?:public|private|protected|static|\s)*function\s+(\w+)\s*\(([^)]*)\)(?:\s*:\s*(\S+))?',
            "use": r'^use\s+([^;]+);',
            "namespace": r'^namespace\s+([^;]+);',
        },
        "go": {
            "struct": r'^type\s+(\w+)\s+struct\s*{',
            "interface": r'^type\s+(\w+)\s+interface\s*{',
            "function": r'^func\s+(\w+)\s*\(([^)]*)\)(?:\s*\(([^)]*)\))?(?:\s*(\w+))?',
            "method": r'^func\s+\((\w+)\s+\*?(\w+)\)\s+(\w+)\s*\(([^)]*)\)',
            "import": r'^import\s+(?:"([^"]+)"|(\w+)\s+"([^"]+)")',
        },
    }

    @classmethod
    def analyze(cls, content: str, language: str, file_path: str) -> FileAnalysis:
        """Analyze file content using regex patterns."""
        patterns = cls.PATTERNS.get(language, {})
        if not patterns:
            return FileAnalysis(file_path=file_path, language=language)

        symbols: List[CodeSymbol] = []
        imports: List[str] = []
        relations: List[FileRelation] = []

        lines = content.split('\n')
        current_class: Optional[str] = None
        current_class_end: int = 0

        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()

            # Track class context
            if line_num > current_class_end:
                current_class = None

            # Check class pattern
            if "class" in patterns:
                match = re.match(patterns["class"], stripped)
                if match:
                    class_name = match.group(1)
                    parent = match.group(2) if len(match.groups()) > 1 else None
                    current_class = class_name
                    # Estimate class end (simple heuristic)
                    current_class_end = cls._find_block_end(lines, line_num - 1, language)

                    # Extract docstring for class
                    class_docstring = cls._extract_docstring(lines, line_num - 1, language)

                    symbols.append(CodeSymbol(
                        name=class_name,
                        type=SymbolType.CLASS,
                        file_path=file_path,
                        line_start=line_num,
                        line_end=current_class_end,
                        signature=stripped,
                        docstring=class_docstring,
                    ))

                    if parent:
                        relations.append(FileRelation(
                            source_file=file_path,
                            target_file="",  # Will be resolved later
                            relation_type=RelationType.EXTENDS,
                            symbols=[parent],
                        ))

            # Check interface pattern (TypeScript, PHP, Go)
            if "interface" in patterns:
                match = re.match(patterns["interface"], stripped)
                if match:
                    iface_docstring = cls._extract_docstring(lines, line_num - 1, language)
                    symbols.append(CodeSymbol(
                        name=match.group(1),
                        type=SymbolType.INTERFACE,
                        file_path=file_path,
                        line_start=line_num,
                        line_end=cls._find_block_end(lines, line_num - 1, language),
                        signature=stripped,
                        docstring=iface_docstring,
                    ))

            # Check function pattern
            if "function" in patterns:
                match = re.match(patterns["function"], stripped)
                if match:
                    func_name = match.group(1)
                    params = match.group(2) if len(match.groups()) > 1 else ""
                    return_type = match.group(3) if len(match.groups()) > 2 else None

                    # Determine if this is a method (inside class)
                    is_method = current_class is not None and language in ["python", "php"]

                    # Extract docstring
                    func_docstring = cls._extract_docstring(lines, line_num - 1, language)

                    symbols.append(CodeSymbol(
                        name=func_name,
                        type=SymbolType.METHOD if is_method else SymbolType.FUNCTION,
                        file_path=file_path,
                        line_start=line_num,
                        line_end=cls._find_block_end(lines, line_num - 1, language),
                        signature=stripped,
                        parent=current_class if is_method else None,
                        parameters=cls._parse_params(params),
                        return_type=return_type,
                        docstring=func_docstring,
                    ))

            # Check method pattern (Python indented methods)
            if "method" in patterns and language == "python":
                match = re.match(patterns["method"], line)  # Don't strip - check indentation
                if match and current_class:
                    func_name = match.group(1)
                    params = match.group(2)
                    return_type = match.group(3) if len(match.groups()) > 2 else None

                    # Extract docstring
                    method_docstring = cls._extract_docstring(lines, line_num - 1, language)

                    symbols.append(CodeSymbol(
                        name=func_name,
                        type=SymbolType.METHOD,
                        file_path=file_path,
                        line_start=line_num,
                        line_end=cls._find_block_end(lines, line_num - 1, language),
                        signature=stripped,
                        parent=current_class,
                        parameters=cls._parse_params(params),
                        return_type=return_type,
                        docstring=method_docstring,
                    ))

            # Check import pattern
            if "import" in patterns:
                match = re.match(patterns["import"], stripped)
                if match:
                    if language == "python":
                        module = match.group(1) or ""
                        imported = match.group(2)
                        imports.append(f"{module}.{imported}" if module else imported)
                    elif language in ["javascript", "typescript"]:
                        named = match.group(1) or ""
                        default = match.group(2) or ""
                        source = match.group(3) if len(match.groups()) > 2 else match.group(4) if len(match.groups()) > 3 else ""
                        imports.append(source)
                        relations.append(FileRelation(
                            source_file=file_path,
                            target_file=source,
                            relation_type=RelationType.IMPORTS,
                            symbols=[s.strip() for s in (named or default).split(",") if s.strip()],
                        ))
                    elif language == "php":
                        imports.append(match.group(1))

        return FileAnalysis(
            file_path=file_path,
            language=language,
            symbols=symbols,
            imports=imports,
            relations=relations,
        )

    @staticmethod
    def _find_block_end(lines: List[str], start_index: int, language: str) -> int:
        """Estimate where a block ends (class/function)."""
        if language == "python":
            # Python: track indentation
            if start_index >= len(lines):
                return start_index + 1

            start_line = lines[start_index]
            base_indent = len(start_line) - len(start_line.lstrip())

            for i in range(start_index + 1, len(lines)):
                line = lines[i]
                if line.strip():  # Non-empty line
                    indent = len(line) - len(line.lstrip())
                    if indent <= base_indent:
                        return i
            return len(lines)

        elif language in ["javascript", "typescript", "php", "go", "java"]:
            # Brace-counting
            brace_count = 0
            started = False

            for i in range(start_index, len(lines)):
                line = lines[i]
                for char in line:
                    if char == '{':
                        brace_count += 1
                        started = True
                    elif char == '}':
                        brace_count -= 1
                        if started and brace_count == 0:
                            return i + 1
            return len(lines)

        return start_index + 10  # Fallback

    @staticmethod
    def _parse_params(params_str: str) -> List[str]:
        """Parse parameter string into list."""
        if not params_str:
            return []
        return [p.strip() for p in params_str.split(",") if p.strip()]

    @staticmethod
    def _extract_docstring(lines: List[str], def_line_index: int, language: str) -> Optional[str]:
        """
        Extract docstring from lines following a function/class definition.

        Args:
            lines: All lines of the file.
            def_line_index: 0-based index of the definition line.
            language: Programming language.

        Returns:
            Extracted docstring or None.
        """
        if def_line_index + 1 >= len(lines):
            return None

        if language == "python":
            # Python: look for """ or ''' on the next non-empty line
            for i in range(def_line_index + 1, min(def_line_index + 3, len(lines))):
                line = lines[i].strip()
                if not line:
                    continue

                # Single-line docstring: """...""" or '''...'''
                for quote in ['"""', "'''"]:
                    if line.startswith(quote):
                        if line.count(quote) >= 2 and line.endswith(quote) and len(line) > 6:
                            # Single line docstring
                            return line[3:-3].strip()
                        else:
                            # Multi-line docstring - collect until closing quote
                            docstring_lines = [line[3:]]  # Remove opening quote
                            for j in range(i + 1, min(i + 50, len(lines))):
                                doc_line = lines[j]
                                if quote in doc_line:
                                    # Found closing quote
                                    end_idx = doc_line.find(quote)
                                    docstring_lines.append(doc_line[:end_idx].strip())
                                    return '\n'.join(docstring_lines).strip()
                                else:
                                    docstring_lines.append(doc_line.strip())
                            return '\n'.join(docstring_lines).strip()
                break  # Only check first non-empty line

        elif language == "php":
            # PHP: look for /** ... */ before or after the definition
            # Check lines before (PHPDoc is usually before function)
            for i in range(max(0, def_line_index - 1), max(0, def_line_index - 10), -1):
                line = lines[i].strip()
                if line.endswith('*/'):
                    # Found end of PHPDoc, collect backwards
                    docstring_lines = []
                    for j in range(i, max(0, i - 30), -1):
                        doc_line = lines[j].strip()
                        # Remove common PHPDoc prefixes
                        clean_line = doc_line.lstrip('*').strip()
                        if clean_line.startswith('/'):
                            clean_line = clean_line[1:].strip()
                        docstring_lines.insert(0, clean_line)
                        if doc_line.startswith('/**'):
                            break
                    # Filter out empty lines and join
                    result = '\n'.join(l for l in docstring_lines if l and not l.startswith('@'))
                    return result.strip() if result.strip() else None
                elif line and not line.startswith('*') and not line.startswith('/'):
                    break  # Non-comment line found

        elif language in ["javascript", "typescript"]:
            # JS/TS: look for /** ... */ or // comments before
            for i in range(max(0, def_line_index - 1), max(0, def_line_index - 10), -1):
                line = lines[i].strip()
                if line.endswith('*/'):
                    # JSDoc block
                    docstring_lines = []
                    for j in range(i, max(0, i - 30), -1):
                        doc_line = lines[j].strip()
                        clean_line = doc_line.lstrip('*').strip()
                        if clean_line.startswith('/'):
                            clean_line = clean_line[1:].strip()
                        docstring_lines.insert(0, clean_line)
                        if doc_line.startswith('/**') or doc_line.startswith('/*'):
                            break
                    result = '\n'.join(l for l in docstring_lines if l and not l.startswith('@'))
                    return result.strip() if result.strip() else None
                elif line.startswith('//'):
                    # Single-line comment - collect consecutive //
                    docstring_lines = []
                    for j in range(i, max(0, i - 10), -1):
                        doc_line = lines[j].strip()
                        if doc_line.startswith('//'):
                            docstring_lines.insert(0, doc_line[2:].strip())
                        else:
                            break
                    return ' '.join(docstring_lines) if docstring_lines else None
                elif line and not line.startswith('*') and not line.startswith('/'):
                    break

        return None


# =============================================================================
# Tree-sitter Analyzer (when available)
# =============================================================================

class TreeSitterAnalyzer:
    """
    Analyzer using tree-sitter for precise AST parsing.
    Requires: pip install tree-sitter tree-sitter-python tree-sitter-javascript ...
    """

    _parser = None
    _languages: Dict[str, Any] = {}

    @classmethod
    def is_available(cls) -> bool:
        """Check if tree-sitter is available."""
        try:
            import tree_sitter
            return True
        except ImportError:
            return False

    @classmethod
    def _ensure_parser(cls, language: str) -> bool:
        """Ensure parser is loaded for language."""
        if not cls.is_available():
            return False

        if language in cls._languages:
            return True

        try:
            import tree_sitter

            # Map language to package name
            package_map = {
                "python": "tree_sitter_python",
                "javascript": "tree_sitter_javascript",
                "typescript": "tree_sitter_typescript",
                "php": "tree_sitter_php",
                "go": "tree_sitter_go",
                "rust": "tree_sitter_rust",
            }

            package_name = package_map.get(language)
            if not package_name:
                return False

            # Dynamic import
            lang_module = __import__(package_name)
            if hasattr(lang_module, 'language'):
                cls._languages[language] = tree_sitter.Language(lang_module.language())
                return True

        except (ImportError, AttributeError) as e:
            logger.debug(f"tree-sitter language {language} not available: {e}")

        return False

    @classmethod
    def analyze(cls, content: str, language: str, file_path: str) -> FileAnalysis:
        """Analyze file content using tree-sitter."""
        if not cls._ensure_parser(language):
            # Fallback to regex
            return RegexAnalyzer.analyze(content, language, file_path)

        try:
            import tree_sitter

            parser = tree_sitter.Parser()
            parser.language = cls._languages[language]
            tree = parser.parse(bytes(content, "utf8"))

            symbols: List[CodeSymbol] = []
            imports: List[str] = []
            relations: List[FileRelation] = []

            # Walk tree and extract symbols
            cls._walk_tree(
                tree.root_node,
                content,
                file_path,
                language,
                symbols,
                imports,
                relations,
            )

            return FileAnalysis(
                file_path=file_path,
                language=language,
                symbols=symbols,
                imports=imports,
                relations=relations,
            )

        except Exception as e:
            logger.error(f"tree-sitter analysis failed: {e}")
            return RegexAnalyzer.analyze(content, language, file_path)

    @classmethod
    def _walk_tree(
        cls,
        node,
        content: str,
        file_path: str,
        language: str,
        symbols: List[CodeSymbol],
        imports: List[str],
        relations: List[FileRelation],
        parent_class: Optional[str] = None,
    ):
        """Recursively walk AST and extract symbols."""
        # Python-specific node types
        if language == "python":
            if node.type == "class_definition":
                name_node = node.child_by_field_name("name")
                if name_node:
                    class_name = content[name_node.start_byte:name_node.end_byte]
                    symbols.append(CodeSymbol(
                        name=class_name,
                        type=SymbolType.CLASS,
                        file_path=file_path,
                        line_start=node.start_point[0] + 1,
                        line_end=node.end_point[0] + 1,
                        signature=cls._get_node_text(node, content)[:100],
                    ))
                    # Process children with class context
                    for child in node.children:
                        cls._walk_tree(child, content, file_path, language, symbols, imports, relations, class_name)
                    return

            elif node.type == "function_definition":
                name_node = node.child_by_field_name("name")
                if name_node:
                    func_name = content[name_node.start_byte:name_node.end_byte]
                    params = cls._extract_params_python(node, content)
                    symbols.append(CodeSymbol(
                        name=func_name,
                        type=SymbolType.METHOD if parent_class else SymbolType.FUNCTION,
                        file_path=file_path,
                        line_start=node.start_point[0] + 1,
                        line_end=node.end_point[0] + 1,
                        signature=cls._get_node_text(node, content)[:100],
                        parent=parent_class,
                        parameters=params,
                    ))

            elif node.type == "import_statement" or node.type == "import_from_statement":
                import_text = content[node.start_byte:node.end_byte]
                imports.append(import_text)

        # JavaScript/TypeScript node types
        elif language in ["javascript", "typescript"]:
            if node.type == "class_declaration":
                name_node = node.child_by_field_name("name")
                if name_node:
                    class_name = content[name_node.start_byte:name_node.end_byte]
                    symbols.append(CodeSymbol(
                        name=class_name,
                        type=SymbolType.CLASS,
                        file_path=file_path,
                        line_start=node.start_point[0] + 1,
                        line_end=node.end_point[0] + 1,
                        signature=cls._get_node_text(node, content)[:100],
                    ))
                    for child in node.children:
                        cls._walk_tree(child, content, file_path, language, symbols, imports, relations, class_name)
                    return

            elif node.type in ["function_declaration", "arrow_function", "method_definition"]:
                name_node = node.child_by_field_name("name")
                if name_node:
                    func_name = content[name_node.start_byte:name_node.end_byte]
                    symbols.append(CodeSymbol(
                        name=func_name,
                        type=SymbolType.METHOD if parent_class or node.type == "method_definition" else SymbolType.FUNCTION,
                        file_path=file_path,
                        line_start=node.start_point[0] + 1,
                        line_end=node.end_point[0] + 1,
                        signature=cls._get_node_text(node, content)[:100],
                        parent=parent_class,
                    ))

            elif node.type == "import_statement":
                import_text = content[node.start_byte:node.end_byte]
                imports.append(import_text)

        # Recurse to children
        for child in node.children:
            cls._walk_tree(child, content, file_path, language, symbols, imports, relations, parent_class)

    @staticmethod
    def _get_node_text(node, content: str) -> str:
        """Get text of a node, limited to first line."""
        text = content[node.start_byte:node.end_byte]
        first_line = text.split('\n')[0]
        return first_line.strip()

    @staticmethod
    def _extract_params_python(node, content: str) -> List[str]:
        """Extract parameter names from Python function."""
        params = []
        params_node = node.child_by_field_name("parameters")
        if params_node:
            for child in params_node.children:
                if child.type == "identifier":
                    params.append(content[child.start_byte:child.end_byte])
                elif child.type in ["typed_parameter", "default_parameter"]:
                    name_node = child.child_by_field_name("name")
                    if name_node:
                        params.append(content[name_node.start_byte:name_node.end_byte])
        return params


# =============================================================================
# Main Analyzer Class
# =============================================================================

class ASTAnalyzer:
    """
    Main AST analyzer that uses tree-sitter when available, falls back to regex.
    """

    def __init__(self):
        self.use_tree_sitter = TreeSitterAnalyzer.is_available()
        if self.use_tree_sitter:
            logger.info("AST Analyzer: Using tree-sitter")
        else:
            logger.info("AST Analyzer: Using regex fallback")

    def analyze_file(self, file_path: str, content: Optional[str] = None) -> FileAnalysis:
        """
        Analyze a single file and extract symbols and relations.

        Args:
            file_path: Path to the file
            content: Optional file content (if not provided, file is read)

        Returns:
            FileAnalysis with symbols, imports, and relations
        """
        path = Path(file_path)
        language = LANGUAGE_EXTENSIONS.get(path.suffix.lower())

        if not language:
            return FileAnalysis(file_path=file_path, language="unknown")

        if content is None:
            try:
                content = path.read_text(encoding='utf-8', errors='ignore')
            except Exception as e:
                logger.error(f"Failed to read file {file_path}: {e}")
                return FileAnalysis(file_path=file_path, language=language)

        if self.use_tree_sitter:
            return TreeSitterAnalyzer.analyze(content, language, file_path)
        else:
            return RegexAnalyzer.analyze(content, language, file_path)

    def analyze_directory(
        self,
        directory: str,
        extensions: Optional[Set[str]] = None,
    ) -> Dict[str, FileAnalysis]:
        """
        Analyze all files in a directory.

        Args:
            directory: Path to directory
            extensions: Optional set of extensions to include

        Returns:
            Dict mapping file paths to FileAnalysis
        """
        results: Dict[str, FileAnalysis] = {}
        dir_path = Path(directory)

        if extensions is None:
            extensions = set(LANGUAGE_EXTENSIONS.keys())

        for ext in extensions:
            for file_path in dir_path.rglob(f"*{ext}"):
                # Skip common non-source directories
                path_str = str(file_path)
                if any(skip in path_str for skip in [
                    "node_modules", "vendor", ".git", "dist", "build",
                    "__pycache__", ".venv", "venv"
                ]):
                    continue

                analysis = self.analyze_file(str(file_path))
                if analysis.symbols:
                    results[str(file_path)] = analysis

        return results

    def build_relationship_graph(
        self,
        analyses: Dict[str, FileAnalysis],
    ) -> Dict[str, List[FileRelation]]:
        """
        Build a relationship graph from multiple file analyses.

        Args:
            analyses: Dict of file path to FileAnalysis

        Returns:
            Dict mapping file paths to their relations
        """
        graph: Dict[str, List[FileRelation]] = {}

        for file_path, analysis in analyses.items():
            graph[file_path] = analysis.relations

        # Resolve relative imports to actual files
        # TODO: Implement import resolution

        return graph

    def get_symbol_index(
        self,
        analyses: Dict[str, FileAnalysis],
    ) -> Dict[str, List[CodeSymbol]]:
        """
        Build an index of all symbols by name.

        Args:
            analyses: Dict of file path to FileAnalysis

        Returns:
            Dict mapping symbol names to their definitions
        """
        index: Dict[str, List[CodeSymbol]] = {}

        for analysis in analyses.values():
            for symbol in analysis.symbols:
                if symbol.name not in index:
                    index[symbol.name] = []
                index[symbol.name].append(symbol)

        return index


# =============================================================================
# Global Instance
# =============================================================================

ast_analyzer = ASTAnalyzer()
