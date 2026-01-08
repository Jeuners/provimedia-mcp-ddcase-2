"""
CHAINGUARD MCP Server - Code Summarizer Module

Extracts deep logic summaries from source code files.
Creates human-readable descriptions of code purpose, not just structure.

Copyright (c) 2026 Provimedia GmbH
Licensed under the Polyform Noncommercial License 1.0.0
See LICENSE file in the project root for full license information.

Usage:
    from chainguard.code_summarizer import CodeSummarizer

    summarizer = CodeSummarizer()
    summary = summarizer.summarize_file(file_path, content)
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional, Tuple


@dataclass
class FunctionInfo:
    """Information about a function/method."""
    name: str
    docstring: str = ""
    params: List[str] = field(default_factory=list)
    returns: str = ""
    line_number: int = 0
    is_method: bool = False
    class_name: str = ""
    inline_comments: List[str] = field(default_factory=list)

    def get_purpose(self) -> str:
        """Generate purpose description from available info."""
        if self.docstring:
            # First sentence of docstring
            first_sentence = self.docstring.split('.')[0].strip()
            if first_sentence:
                return first_sentence

        # Infer from name
        return self._infer_from_name()

    def _infer_from_name(self) -> str:
        """Infer purpose from function name."""
        name = self.name

        # Common prefixes
        if name.startswith('get_') or name.startswith('get'):
            return f"Retrieves {self._humanize(name[3:] if name.startswith('get_') else name[3:])}"
        elif name.startswith('set_') or name.startswith('set'):
            return f"Sets {self._humanize(name[3:] if name.startswith('set_') else name[3:])}"
        elif name.startswith('is_') or name.startswith('has_') or name.startswith('can_'):
            return f"Checks if {self._humanize(name[3:])}"
        elif name.startswith('create_') or name.startswith('make_'):
            return f"Creates {self._humanize(name[6:] if name.startswith('create_') else name[5:])}"
        elif name.startswith('delete_') or name.startswith('remove_'):
            return f"Removes {self._humanize(name[7:] if name.startswith('delete_') else name[7:])}"
        elif name.startswith('update_'):
            return f"Updates {self._humanize(name[7:])}"
        elif name.startswith('validate_') or name.startswith('check_'):
            return f"Validates {self._humanize(name[9:] if name.startswith('validate_') else name[6:])}"
        elif name.startswith('handle_') or name.startswith('on_'):
            return f"Handles {self._humanize(name[7:] if name.startswith('handle_') else name[3:])}"
        elif name.startswith('process_'):
            return f"Processes {self._humanize(name[8:])}"
        elif name.startswith('load_') or name.startswith('fetch_'):
            return f"Loads {self._humanize(name[5:] if name.startswith('load_') else name[6:])}"
        elif name.startswith('save_') or name.startswith('store_'):
            return f"Saves {self._humanize(name[5:] if name.startswith('save_') else name[6:])}"
        elif name.startswith('init_') or name.startswith('initialize_'):
            return f"Initializes {self._humanize(name[5:] if name.startswith('init_') else name[11:])}"
        elif name.startswith('parse_'):
            return f"Parses {self._humanize(name[6:])}"
        elif name.startswith('render_') or name.startswith('display_'):
            return f"Renders {self._humanize(name[7:] if name.startswith('render_') else name[8:])}"
        elif name.startswith('find_') or name.startswith('search_'):
            return f"Finds {self._humanize(name[5:] if name.startswith('find_') else name[7:])}"
        elif name.startswith('convert_') or name.startswith('transform_'):
            return f"Converts {self._humanize(name[8:] if name.startswith('convert_') else name[10:])}"
        elif name.startswith('calculate_') or name.startswith('compute_'):
            return f"Calculates {self._humanize(name[10:] if name.startswith('calculate_') else name[8:])}"
        elif name.startswith('send_'):
            return f"Sends {self._humanize(name[5:])}"
        elif name.startswith('receive_'):
            return f"Receives {self._humanize(name[8:])}"
        elif name.startswith('format_'):
            return f"Formats {self._humanize(name[7:])}"
        elif name.startswith('build_'):
            return f"Builds {self._humanize(name[6:])}"
        elif name.startswith('register_'):
            return f"Registers {self._humanize(name[9:])}"
        elif name.startswith('unregister_'):
            return f"Unregisters {self._humanize(name[11:])}"
        elif name.startswith('enable_') or name.startswith('activate_'):
            return f"Enables {self._humanize(name[7:] if name.startswith('enable_') else name[9:])}"
        elif name.startswith('disable_') or name.startswith('deactivate_'):
            return f"Disables {self._humanize(name[8:] if name.startswith('disable_') else name[11:])}"
        elif name == '__init__' or name == 'constructor':
            return "Initializes the instance"
        elif name == '__str__' or name == 'toString':
            return "Converts to string representation"
        elif name == '__repr__':
            return "Returns debug representation"
        elif name.startswith('__') and name.endswith('__'):
            return f"Magic method for {self._humanize(name[2:-2])}"
        elif name.startswith('test_'):
            return f"Tests {self._humanize(name[5:])}"

        # Default: just humanize the name
        return self._humanize(name)

    def _humanize(self, name: str) -> str:
        """Convert snake_case/camelCase to human readable."""
        if not name:
            return "operation"

        # Handle camelCase
        name = re.sub(r'([a-z])([A-Z])', r'\1 \2', name)
        # Handle snake_case
        name = name.replace('_', ' ')
        return name.lower().strip() or "operation"


@dataclass
class ClassInfo:
    """Information about a class."""
    name: str
    docstring: str = ""
    methods: List[FunctionInfo] = field(default_factory=list)
    base_classes: List[str] = field(default_factory=list)
    line_number: int = 0
    class_comments: List[str] = field(default_factory=list)

    def get_purpose(self) -> str:
        """Generate purpose description from available info."""
        if self.docstring:
            first_sentence = self.docstring.split('.')[0].strip()
            if first_sentence:
                return first_sentence

        # Infer from name and base classes
        return self._infer_from_name()

    def _infer_from_name(self) -> str:
        """Infer purpose from class name."""
        name = self.name

        # Common suffixes
        if name.endswith('Controller'):
            return f"Handles {self._humanize(name[:-10])} requests"
        elif name.endswith('Service'):
            return f"Provides {self._humanize(name[:-7])} business logic"
        elif name.endswith('Repository'):
            return f"Data access for {self._humanize(name[:-10])}"
        elif name.endswith('Manager'):
            return f"Manages {self._humanize(name[:-7])}"
        elif name.endswith('Handler'):
            return f"Handles {self._humanize(name[:-7])} events"
        elif name.endswith('Factory'):
            return f"Creates {self._humanize(name[:-7])} instances"
        elif name.endswith('Builder'):
            return f"Builds {self._humanize(name[:-7])} objects"
        elif name.endswith('Validator'):
            return f"Validates {self._humanize(name[:-9])} data"
        elif name.endswith('Parser'):
            return f"Parses {self._humanize(name[:-6])} data"
        elif name.endswith('Formatter'):
            return f"Formats {self._humanize(name[:-9])} output"
        elif name.endswith('Provider'):
            return f"Provides {self._humanize(name[:-8])} data"
        elif name.endswith('Adapter'):
            return f"Adapts {self._humanize(name[:-7])} interface"
        elif name.endswith('Wrapper'):
            return f"Wraps {self._humanize(name[:-7])} functionality"
        elif name.endswith('Helper'):
            return f"Helper utilities for {self._humanize(name[:-6])}"
        elif name.endswith('Utils') or name.endswith('Util'):
            base = name[:-5] if name.endswith('Utils') else name[:-4]
            return f"Utility functions for {self._humanize(base)}"
        elif name.endswith('Config') or name.endswith('Configuration'):
            base = name[:-6] if name.endswith('Config') else name[:-13]
            return f"Configuration for {self._humanize(base) if base else 'application'}"
        elif name.endswith('Exception') or name.endswith('Error'):
            base = name[:-9] if name.endswith('Exception') else name[:-5]
            return f"Exception for {self._humanize(base)} errors"
        elif name.endswith('Model'):
            return f"Data model for {self._humanize(name[:-5])}"
        elif name.endswith('Entity'):
            return f"Entity representing {self._humanize(name[:-6])}"
        elif name.endswith('DTO'):
            return f"Data transfer object for {self._humanize(name[:-3])}"
        elif name.endswith('Command'):
            return f"Command for {self._humanize(name[:-7])}"
        elif name.endswith('Query'):
            return f"Query for {self._humanize(name[:-5])}"
        elif name.endswith('Event'):
            return f"Event for {self._humanize(name[:-5])}"
        elif name.endswith('Listener'):
            return f"Listens for {self._humanize(name[:-8])} events"
        elif name.endswith('Middleware'):
            return f"Middleware for {self._humanize(name[:-10])}"
        elif name.endswith('Filter'):
            return f"Filters {self._humanize(name[:-6])} data"
        elif name.endswith('Cache'):
            return f"Caches {self._humanize(name[:-5])} data"
        elif name.endswith('Client'):
            return f"Client for {self._humanize(name[:-6])} API"
        elif name.endswith('Test') or name.startswith('Test'):
            base = name[:-4] if name.endswith('Test') else name[4:]
            return f"Tests for {self._humanize(base)}"
        elif name.endswith('Spec'):
            return f"Specification for {self._humanize(name[:-4])}"

        # Check base classes
        if self.base_classes:
            base = self.base_classes[0]
            if 'Interface' in base or base.startswith('I') and len(base) > 1 and base[1].isupper():
                return f"Implementation of {base}"
            if 'Abstract' in base:
                return f"Concrete implementation of {base}"

        # Default
        return f"Handles {self._humanize(name)} functionality"

    def _humanize(self, name: str) -> str:
        """Convert CamelCase to human readable."""
        if not name:
            return "core"
        name = re.sub(r'([a-z])([A-Z])', r'\1 \2', name)
        return name.lower().strip() or "core"


@dataclass
class FileSummary:
    """Complete summary of a file."""
    path: str
    language: str
    purpose: str  # Main purpose/description
    module_docstring: str = ""
    classes: List[ClassInfo] = field(default_factory=list)
    functions: List[FunctionInfo] = field(default_factory=list)
    important_comments: List[str] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    constants: List[str] = field(default_factory=list)

    def to_text(self, max_length: int = 2000) -> str:
        """Convert to searchable text summary."""
        parts = []

        # Main purpose
        if self.purpose:
            parts.append(f"PURPOSE: {self.purpose}")

        # Module docstring (first 200 chars)
        if self.module_docstring:
            doc = self.module_docstring[:200]
            parts.append(f"DESCRIPTION: {doc}")

        # Classes with their purposes
        if self.classes:
            class_parts = []
            for cls in self.classes[:5]:  # Max 5 classes
                purpose = cls.get_purpose()
                class_parts.append(f"  - {cls.name}: {purpose}")
                # Add key methods
                for method in cls.methods[:3]:
                    method_purpose = method.get_purpose()
                    class_parts.append(f"    * {method.name}: {method_purpose}")
            if class_parts:
                parts.append("CLASSES:\n" + "\n".join(class_parts))

        # Standalone functions
        if self.functions:
            func_parts = []
            for func in self.functions[:8]:  # Max 8 functions
                purpose = func.get_purpose()
                func_parts.append(f"  - {func.name}: {purpose}")
            if func_parts:
                parts.append("FUNCTIONS:\n" + "\n".join(func_parts))

        # Important comments (insights)
        if self.important_comments:
            comments = [c[:100] for c in self.important_comments[:3]]
            parts.append("NOTES: " + " | ".join(comments))

        result = "\n\n".join(parts)
        return result[:max_length]


class CodeSummarizer:
    """
    Extracts deep logic summaries from source code.

    Language support:
    - Python (.py)
    - PHP (.php)
    - JavaScript/TypeScript (.js, .ts, .tsx, .jsx)
    """

    # Patterns for different languages
    PYTHON_DOCSTRING = re.compile(r'"""(.*?)"""|\'\'\'(.*?)\'\'\'', re.DOTALL)
    PYTHON_COMMENT = re.compile(r'#\s*(.+)$', re.MULTILINE)
    PYTHON_FUNCTION = re.compile(
        r'^(?P<indent>\s*)(?P<async>async\s+)?def\s+(?P<name>\w+)\s*\((?P<params>[^)]*)\)'
        r'(?:\s*->\s*(?P<returns>[^:]+))?\s*:',
        re.MULTILINE
    )
    PYTHON_CLASS = re.compile(
        r'^(?P<indent>\s*)class\s+(?P<name>\w+)(?:\((?P<bases>[^)]*)\))?\s*:',
        re.MULTILINE
    )

    PHP_DOCBLOCK = re.compile(r'/\*\*(.*?)\*/', re.DOTALL)
    PHP_COMMENT = re.compile(r'//\s*(.+)$|/\*\s*(.+?)\s*\*/', re.MULTILINE)
    PHP_FUNCTION = re.compile(
        r'(?:public|private|protected|static|\s)*function\s+(?P<name>\w+)\s*\((?P<params>[^)]*)\)',
        re.MULTILINE
    )
    PHP_CLASS = re.compile(
        r'(?:abstract\s+|final\s+)?class\s+(?P<name>\w+)'
        r'(?:\s+extends\s+(?P<extends>\w+))?'
        r'(?:\s+implements\s+(?P<implements>[^{]+))?',
        re.MULTILINE
    )

    JS_JSDOC = re.compile(r'/\*\*(.*?)\*/', re.DOTALL)
    JS_COMMENT = re.compile(r'//\s*(.+)$', re.MULTILINE)
    JS_FUNCTION = re.compile(
        r'(?:export\s+)?(?:async\s+)?function\s+(?P<name>\w+)\s*\((?P<params>[^)]*)\)|'
        r'(?:const|let|var)\s+(?P<name2>\w+)\s*=\s*(?:async\s+)?\([^)]*\)\s*=>|'
        r'(?:const|let|var)\s+(?P<name3>\w+)\s*=\s*(?:async\s+)?function',
        re.MULTILINE
    )
    JS_CLASS = re.compile(
        r'(?:export\s+)?class\s+(?P<name>\w+)'
        r'(?:\s+extends\s+(?P<extends>\w+))?',
        re.MULTILINE
    )

    # Important comment keywords (indicate significant logic)
    IMPORTANT_KEYWORDS = [
        'TODO', 'FIXME', 'HACK', 'NOTE', 'IMPORTANT', 'WARNING',
        'BUG', 'XXX', 'REVIEW', 'OPTIMIZE', 'SECURITY', 'DEPRECATED'
    ]

    def summarize_file(self, file_path: Path, content: str) -> FileSummary:
        """
        Create a deep summary of a source file.

        Args:
            file_path: Path to the file
            content: File content

        Returns:
            FileSummary with extracted information
        """
        ext = file_path.suffix.lower()
        language = self._detect_language(ext)

        if language == "python":
            return self._summarize_python(file_path, content)
        elif language == "php":
            return self._summarize_php(file_path, content)
        elif language in ["javascript", "typescript"]:
            return self._summarize_js(file_path, content)
        else:
            return self._summarize_generic(file_path, content)

    def _detect_language(self, ext: str) -> str:
        """Detect language from file extension."""
        mapping = {
            '.py': 'python',
            '.php': 'php',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.tsx': 'typescript',
            '.jsx': 'javascript',
            '.mjs': 'javascript',
        }
        return mapping.get(ext, 'unknown')

    def _summarize_python(self, file_path: Path, content: str) -> FileSummary:
        """Summarize Python file."""
        summary = FileSummary(
            path=str(file_path),
            language="python",
            purpose=""
        )

        # Extract module docstring (first triple-quoted string)
        module_doc_match = self.PYTHON_DOCSTRING.search(content[:2000])
        if module_doc_match:
            doc = module_doc_match.group(1) or module_doc_match.group(2)
            if doc:
                summary.module_docstring = self._clean_docstring(doc)
                # First sentence as purpose
                summary.purpose = summary.module_docstring.split('.')[0].strip()

        # If no docstring, infer from filename
        if not summary.purpose:
            summary.purpose = self._infer_file_purpose(file_path)

        # Extract classes
        lines = content.splitlines()
        current_class = None

        for class_match in self.PYTHON_CLASS.finditer(content):
            class_name = class_match.group('name')
            class_indent = len(class_match.group('indent') or '')
            bases = class_match.group('bases')
            base_classes = [b.strip() for b in bases.split(',')] if bases else []
            line_num = content[:class_match.start()].count('\n') + 1

            # Find class docstring
            class_docstring = ""
            class_end = class_match.end()
            remaining = content[class_end:class_end + 500]
            doc_match = self.PYTHON_DOCSTRING.search(remaining[:200])
            if doc_match and remaining[:doc_match.start()].strip() == '':
                class_docstring = self._clean_docstring(
                    doc_match.group(1) or doc_match.group(2) or ""
                )

            current_class = ClassInfo(
                name=class_name,
                docstring=class_docstring,
                base_classes=base_classes,
                line_number=line_num
            )
            summary.classes.append(current_class)

        # Extract functions/methods
        for func_match in self.PYTHON_FUNCTION.finditer(content):
            func_name = func_match.group('name')
            func_indent = len(func_match.group('indent') or '')
            params_str = func_match.group('params')
            returns = func_match.group('returns') or ""
            line_num = content[:func_match.start()].count('\n') + 1

            # Parse parameters
            params = [p.strip().split(':')[0].split('=')[0].strip()
                     for p in params_str.split(',') if p.strip()]
            params = [p for p in params if p and p != 'self' and p != 'cls']

            # Find function docstring
            func_docstring = ""
            func_end = func_match.end()
            remaining = content[func_end:func_end + 500]
            doc_match = self.PYTHON_DOCSTRING.search(remaining[:200])
            if doc_match and remaining[:doc_match.start()].strip() == '':
                func_docstring = self._clean_docstring(
                    doc_match.group(1) or doc_match.group(2) or ""
                )

            func_info = FunctionInfo(
                name=func_name,
                docstring=func_docstring,
                params=params,
                returns=returns.strip(),
                line_number=line_num,
                is_method=func_indent > 0
            )

            # Assign to class or standalone
            if func_indent > 0 and summary.classes:
                # Find the class this method belongs to
                for cls in reversed(summary.classes):
                    if cls.line_number < line_num:
                        func_info.class_name = cls.name
                        cls.methods.append(func_info)
                        break
            else:
                summary.functions.append(func_info)

        # Extract important comments
        for comment_match in self.PYTHON_COMMENT.finditer(content):
            comment = comment_match.group(1)
            if comment and any(kw in comment.upper() for kw in self.IMPORTANT_KEYWORDS):
                summary.important_comments.append(comment.strip())

        return summary

    def _summarize_php(self, file_path: Path, content: str) -> FileSummary:
        """Summarize PHP file."""
        summary = FileSummary(
            path=str(file_path),
            language="php",
            purpose=""
        )

        # Extract file-level docblock
        file_doc_match = self.PHP_DOCBLOCK.search(content[:2000])
        if file_doc_match:
            doc = self._clean_php_docblock(file_doc_match.group(1))
            summary.module_docstring = doc
            summary.purpose = doc.split('.')[0].strip()

        if not summary.purpose:
            summary.purpose = self._infer_file_purpose(file_path)

        # Extract classes
        for class_match in self.PHP_CLASS.finditer(content):
            class_name = class_match.group('name')
            extends = class_match.group('extends') or ""
            implements = class_match.group('implements') or ""
            line_num = content[:class_match.start()].count('\n') + 1

            base_classes = [extends] if extends else []
            if implements:
                base_classes.extend([i.strip() for i in implements.split(',')])

            # Find preceding docblock
            class_docstring = ""
            preceding = content[max(0, class_match.start() - 500):class_match.start()]
            doc_matches = list(self.PHP_DOCBLOCK.finditer(preceding))
            if doc_matches:
                class_docstring = self._clean_php_docblock(doc_matches[-1].group(1))

            class_info = ClassInfo(
                name=class_name,
                docstring=class_docstring,
                base_classes=base_classes,
                line_number=line_num
            )
            summary.classes.append(class_info)

        # Extract functions
        for func_match in self.PHP_FUNCTION.finditer(content):
            func_name = func_match.group('name')
            params_str = func_match.group('params')
            line_num = content[:func_match.start()].count('\n') + 1

            # Parse parameters
            params = []
            if params_str:
                for p in params_str.split(','):
                    p = p.strip()
                    if p:
                        # Remove type hints and default values
                        param_name = re.sub(r'^[?\w\\]+\s*', '', p)
                        param_name = re.sub(r'\s*=.*$', '', param_name)
                        param_name = param_name.lstrip('$&')
                        if param_name:
                            params.append(param_name)

            # Find preceding docblock
            func_docstring = ""
            preceding = content[max(0, func_match.start() - 500):func_match.start()]
            doc_matches = list(self.PHP_DOCBLOCK.finditer(preceding))
            if doc_matches:
                func_docstring = self._clean_php_docblock(doc_matches[-1].group(1))

            func_info = FunctionInfo(
                name=func_name,
                docstring=func_docstring,
                params=params,
                line_number=line_num
            )

            # Assign to class if within one
            if summary.classes:
                for cls in reversed(summary.classes):
                    if cls.line_number < line_num:
                        func_info.is_method = True
                        func_info.class_name = cls.name
                        cls.methods.append(func_info)
                        break
                else:
                    summary.functions.append(func_info)
            else:
                summary.functions.append(func_info)

        # Extract important comments
        for comment_match in self.PHP_COMMENT.finditer(content):
            comment = comment_match.group(1) or comment_match.group(2) or ""
            if comment and any(kw in comment.upper() for kw in self.IMPORTANT_KEYWORDS):
                summary.important_comments.append(comment.strip())

        return summary

    def _summarize_js(self, file_path: Path, content: str) -> FileSummary:
        """Summarize JavaScript/TypeScript file."""
        ext = file_path.suffix.lower()
        language = "typescript" if ext in ['.ts', '.tsx'] else "javascript"

        summary = FileSummary(
            path=str(file_path),
            language=language,
            purpose=""
        )

        # Extract file-level JSDoc
        file_doc_match = self.JS_JSDOC.search(content[:2000])
        if file_doc_match:
            doc = self._clean_jsdoc(file_doc_match.group(1))
            summary.module_docstring = doc
            summary.purpose = doc.split('.')[0].strip()

        if not summary.purpose:
            summary.purpose = self._infer_file_purpose(file_path)

        # Extract classes
        for class_match in self.JS_CLASS.finditer(content):
            class_name = class_match.group('name')
            extends = class_match.group('extends') or ""
            line_num = content[:class_match.start()].count('\n') + 1

            # Find preceding JSDoc
            class_docstring = ""
            preceding = content[max(0, class_match.start() - 500):class_match.start()]
            doc_matches = list(self.JS_JSDOC.finditer(preceding))
            if doc_matches:
                class_docstring = self._clean_jsdoc(doc_matches[-1].group(1))

            class_info = ClassInfo(
                name=class_name,
                docstring=class_docstring,
                base_classes=[extends] if extends else [],
                line_number=line_num
            )
            summary.classes.append(class_info)

        # Extract functions
        for func_match in self.JS_FUNCTION.finditer(content):
            func_name = (func_match.group('name') or
                        func_match.group('name2') or
                        func_match.group('name3') or "anonymous")
            params_str = func_match.group('params') if 'params' in func_match.groupdict() else ""
            line_num = content[:func_match.start()].count('\n') + 1

            # Parse parameters
            params = []
            if params_str:
                for p in params_str.split(','):
                    p = p.strip()
                    if p:
                        # Remove type annotations and defaults
                        param_name = re.sub(r':\s*[^,=]+', '', p)
                        param_name = re.sub(r'\s*=.*$', '', param_name)
                        param_name = param_name.strip()
                        if param_name and param_name != '...':
                            params.append(param_name.lstrip('.'))

            # Find preceding JSDoc
            func_docstring = ""
            preceding = content[max(0, func_match.start() - 500):func_match.start()]
            doc_matches = list(self.JS_JSDOC.finditer(preceding))
            if doc_matches:
                func_docstring = self._clean_jsdoc(doc_matches[-1].group(1))

            func_info = FunctionInfo(
                name=func_name,
                docstring=func_docstring,
                params=params,
                line_number=line_num
            )
            summary.functions.append(func_info)

        # Extract important comments
        for comment_match in self.JS_COMMENT.finditer(content):
            comment = comment_match.group(1)
            if comment and any(kw in comment.upper() for kw in self.IMPORTANT_KEYWORDS):
                summary.important_comments.append(comment.strip())

        return summary

    def _summarize_generic(self, file_path: Path, content: str) -> FileSummary:
        """Generic summary for unknown file types."""
        summary = FileSummary(
            path=str(file_path),
            language="unknown",
            purpose=self._infer_file_purpose(file_path)
        )

        # Try to find any docblocks
        docblock_match = re.search(r'/\*\*(.*?)\*/', content[:2000], re.DOTALL)
        if docblock_match:
            summary.module_docstring = self._clean_docstring(docblock_match.group(1))

        return summary

    def _clean_docstring(self, doc: str) -> str:
        """Clean up a docstring."""
        if not doc:
            return ""
        # Remove leading/trailing whitespace per line
        lines = [line.strip() for line in doc.strip().splitlines()]
        # Remove empty lines at start/end
        while lines and not lines[0]:
            lines.pop(0)
        while lines and not lines[-1]:
            lines.pop()
        return " ".join(lines)[:500]

    def _clean_php_docblock(self, doc: str) -> str:
        """Clean up a PHP docblock."""
        if not doc:
            return ""
        # Remove * at start of lines
        lines = []
        for line in doc.strip().splitlines():
            line = line.strip()
            if line.startswith('*'):
                line = line[1:].strip()
            # Skip @param, @return, etc.
            if line.startswith('@'):
                continue
            if line:
                lines.append(line)
        return " ".join(lines)[:500]

    def _clean_jsdoc(self, doc: str) -> str:
        """Clean up a JSDoc comment."""
        return self._clean_php_docblock(doc)

    def _infer_file_purpose(self, file_path: Path) -> str:
        """Infer file purpose from filename and path."""
        name = file_path.stem.lower()
        path_str = str(file_path).lower()

        # Test files
        if 'test' in name or 'spec' in name or '/tests/' in path_str:
            subject = name.replace('test_', '').replace('_test', '').replace('.test', '').replace('.spec', '')
            return f"Tests for {subject}"

        # Config files
        if 'config' in name or 'settings' in name:
            return f"Configuration for {name.replace('config', '').replace('settings', '').strip('_')}"

        # Models
        if '/models/' in path_str or '/entities/' in path_str:
            return f"Data model for {name}"

        # Controllers
        if '/controllers/' in path_str or 'controller' in name:
            subject = name.replace('controller', '').replace('_', ' ').strip()
            return f"Handles {subject} HTTP requests"

        # Services
        if '/services/' in path_str or 'service' in name:
            subject = name.replace('service', '').replace('_', ' ').strip()
            return f"Business logic for {subject}"

        # Views/Templates
        if '/views/' in path_str or '/templates/' in path_str:
            return f"Template for {name}"

        # Middleware
        if '/middleware/' in path_str or 'middleware' in name:
            return f"Request middleware for {name.replace('middleware', '').strip('_')}"

        # Utils/Helpers
        if '/utils/' in path_str or '/helpers/' in path_str or 'util' in name or 'helper' in name:
            return f"Utility functions for {name.replace('utils', '').replace('util', '').replace('helpers', '').replace('helper', '').strip('_')}"

        # Hooks
        if '/hooks/' in path_str or 'hook' in name:
            return f"Hook for {name.replace('hook', '').replace('_', ' ').strip()}"

        # Components (React/Vue)
        if '/components/' in path_str:
            return f"UI component for {name}"

        # Default
        return f"Module for {name.replace('_', ' ')}"


# Global instance
code_summarizer = CodeSummarizer()
