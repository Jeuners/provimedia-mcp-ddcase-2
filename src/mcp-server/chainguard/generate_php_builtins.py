#!/usr/bin/env python3
"""
PHP Built-in Functions Generator (v1.0)

Extracts all PHP built-in function names from JetBrains phpstorm-stubs
and saves them as a JSON file for use in hallucination prevention.

Usage:
    python generate_php_builtins.py [--output path/to/output.json]

Source: https://github.com/JetBrains/phpstorm-stubs
"""

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Set, Dict, List
from datetime import datetime


# =============================================================================
# CONFIGURATION
# =============================================================================

PHPSTORM_STUBS_REPO = "https://github.com/JetBrains/phpstorm-stubs.git"
PHPSTORM_STUBS_BRANCH = "master"

# Extensions to skip (test files, meta files, etc.)
SKIP_DIRS = {
    '.git', '.github', 'tests', 'meta', '.idea',
}

# Extensions to include (stubs for these PHP extensions)
# Leave empty to include all
INCLUDE_EXTENSIONS: Set[str] = set()  # Empty = all

# Regex patterns to extract function names
FUNCTION_PATTERNS = [
    # Standard function: function name(...)
    r'^\s*function\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(',
    # Function with return type: function name(...): type
    r'^\s*function\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\([^)]*\)\s*:',
]

# Regex patterns to extract class/interface names
CLASS_PATTERNS = [
    r'^\s*(?:abstract\s+)?class\s+([A-Z][a-zA-Z0-9_]*)',
    r'^\s*interface\s+([A-Z][a-zA-Z0-9_]*)',
    r'^\s*trait\s+([A-Z][a-zA-Z0-9_]*)',
]

# Regex patterns to extract method names from classes
METHOD_PATTERNS = [
    r'^\s*(?:public|protected|private)?\s*(?:static\s+)?function\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(',
]

# Regex patterns to extract constants
CONSTANT_PATTERNS = [
    r"^\s*define\s*\(\s*['\"]([A-Z_][A-Z0-9_]*)['\"]",
    r'^\s*const\s+([A-Z_][A-Z0-9_]*)\s*=',
]


# =============================================================================
# EXTRACTOR
# =============================================================================

class PHPStubsExtractor:
    """Extracts PHP symbols from phpstorm-stubs."""

    def __init__(self, stubs_path: Path):
        self.stubs_path = stubs_path
        self.functions: Set[str] = set()
        self.classes: Set[str] = set()
        self.methods: Set[str] = set()
        self.constants: Set[str] = set()

        # Compile patterns
        self._function_patterns = [re.compile(p, re.MULTILINE) for p in FUNCTION_PATTERNS]
        self._class_patterns = [re.compile(p, re.MULTILINE) for p in CLASS_PATTERNS]
        self._method_patterns = [re.compile(p, re.MULTILINE) for p in METHOD_PATTERNS]
        self._constant_patterns = [re.compile(p, re.MULTILINE) for p in CONSTANT_PATTERNS]

    def extract_all(self) -> Dict[str, List[str]]:
        """Extract all symbols from stubs."""
        php_files = list(self.stubs_path.rglob('*.php'))

        print(f"Found {len(php_files)} PHP files to process...")

        for i, php_file in enumerate(php_files):
            # Skip excluded directories
            if any(skip in php_file.parts for skip in SKIP_DIRS):
                continue

            # Filter by extension if specified
            if INCLUDE_EXTENSIONS:
                ext_name = php_file.parent.name
                if ext_name not in INCLUDE_EXTENSIONS:
                    continue

            self._extract_from_file(php_file)

            # Progress indicator
            if (i + 1) % 100 == 0:
                print(f"  Processed {i + 1}/{len(php_files)} files...")

        return {
            'functions': sorted(self.functions),
            'classes': sorted(self.classes),
            'methods': sorted(self.methods),
            'constants': sorted(self.constants),
        }

    def _extract_from_file(self, file_path: Path) -> None:
        """Extract symbols from a single PHP file."""
        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
        except Exception as e:
            print(f"  Warning: Could not read {file_path}: {e}")
            return

        # Extract functions
        for pattern in self._function_patterns:
            for match in pattern.finditer(content):
                name = match.group(1)
                if self._is_valid_function_name(name):
                    self.functions.add(name)

        # Extract classes
        for pattern in self._class_patterns:
            for match in pattern.finditer(content):
                name = match.group(1)
                self.classes.add(name)

        # Extract methods
        for pattern in self._method_patterns:
            for match in pattern.finditer(content):
                name = match.group(1)
                if self._is_valid_function_name(name):
                    self.methods.add(name)

        # Extract constants
        for pattern in self._constant_patterns:
            for match in pattern.finditer(content):
                name = match.group(1)
                self.constants.add(name)

    def _is_valid_function_name(self, name: str) -> bool:
        """Check if name is a valid function name (not a keyword)."""
        keywords = {
            'if', 'else', 'elseif', 'while', 'do', 'for', 'foreach',
            'switch', 'case', 'default', 'break', 'continue', 'return',
            'try', 'catch', 'finally', 'throw', 'class', 'interface',
            'trait', 'extends', 'implements', 'public', 'protected',
            'private', 'static', 'abstract', 'final', 'const', 'function',
            'new', 'clone', 'instanceof', 'use', 'namespace', 'echo',
            'print', 'die', 'exit', 'include', 'include_once', 'require',
            'require_once', 'global', 'var', 'list', 'array', 'callable',
            'self', 'parent', 'true', 'false', 'null', 'and', 'or', 'xor',
            'as', 'yield', 'match', 'fn', 'readonly', 'enum',
        }
        return name.lower() not in keywords and len(name) >= 2


# =============================================================================
# MAIN
# =============================================================================

def clone_stubs(target_dir: Path) -> Path:
    """Clone phpstorm-stubs repository."""
    print(f"Cloning phpstorm-stubs to {target_dir}...")

    # Shallow clone for speed
    subprocess.run([
        'git', 'clone',
        '--depth', '1',
        '--branch', PHPSTORM_STUBS_BRANCH,
        PHPSTORM_STUBS_REPO,
        str(target_dir)
    ], check=True, capture_output=True)

    return target_dir


def generate_builtins(output_path: Path, stubs_path: Path = None) -> Dict:
    """Generate PHP builtins JSON file."""

    # Use temp directory if no stubs path provided
    cleanup_needed = False
    if stubs_path is None:
        temp_dir = Path(tempfile.mkdtemp(prefix='phpstorm-stubs-'))
        stubs_path = clone_stubs(temp_dir)
        cleanup_needed = True

    try:
        # Extract symbols
        extractor = PHPStubsExtractor(stubs_path)
        symbols = extractor.extract_all()

        # Build output
        output = {
            'meta': {
                'generated_at': datetime.utcnow().isoformat() + 'Z',
                'source': PHPSTORM_STUBS_REPO,
                'branch': PHPSTORM_STUBS_BRANCH,
                'version': '1.0',
            },
            'stats': {
                'functions': len(symbols['functions']),
                'classes': len(symbols['classes']),
                'methods': len(symbols['methods']),
                'constants': len(symbols['constants']),
                'total_unique': len(
                    set(symbols['functions']) |
                    set(symbols['classes']) |
                    set(symbols['methods'])
                ),
            },
            'symbols': symbols,
        }

        # Write output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        print(f"\n✓ Generated {output_path}")
        print(f"  Functions: {output['stats']['functions']}")
        print(f"  Classes:   {output['stats']['classes']}")
        print(f"  Methods:   {output['stats']['methods']}")
        print(f"  Constants: {output['stats']['constants']}")
        print(f"  Total unique symbols: {output['stats']['total_unique']}")

        return output

    finally:
        if cleanup_needed and stubs_path.exists():
            print(f"\nCleaning up temp directory...")
            shutil.rmtree(stubs_path.parent)


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Generate PHP built-in functions JSON from phpstorm-stubs'
    )
    parser.add_argument(
        '--output', '-o',
        type=Path,
        default=Path(__file__).parent / 'data' / 'php_builtins.json',
        help='Output JSON file path'
    )
    parser.add_argument(
        '--stubs-path', '-s',
        type=Path,
        default=None,
        help='Path to existing phpstorm-stubs clone (skips download)'
    )

    args = parser.parse_args()

    try:
        generate_builtins(args.output, args.stubs_path)
    except subprocess.CalledProcessError as e:
        print(f"Error: Git clone failed: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
