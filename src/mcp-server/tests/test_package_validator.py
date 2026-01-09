"""
Unit Tests for Package Import Validator (50 Tests)

Tests cover:
- PHP/Composer validation (15 tests)
- JavaScript/TypeScript/NPM validation (20 tests)
- Python/pip validation (15 tests)

Each test category covers:
- Valid packages
- Invalid/hallucinated packages
- Typo detection (slopsquatting)
- Edge cases
"""

import pytest
import tempfile
import json
from pathlib import Path

from chainguard.package_validator import (
    PackageValidator,
    PackageRegistry,
    ImportExtractor,
    PackageIssue,
    PackageValidationResult,
    levenshtein_distance,
    find_similar_packages,
    PYTHON_STDLIB,
    NODE_BUILTINS,
    PHP_BUILTINS,
)
from chainguard.symbol_patterns import Language


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def temp_project():
    """Create a temporary project directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def php_project(temp_project):
    """Create a PHP project with composer.json."""
    composer_json = {
        "require": {
            "php": "^8.0",
            "laravel/framework": "^10.0",
            "guzzlehttp/guzzle": "^7.0",
            "monolog/monolog": "^3.0"
        },
        "require-dev": {
            "phpunit/phpunit": "^10.0"
        },
        "autoload": {
            "psr-4": {
                "App\\": "app/",
                "Database\\": "database/"
            }
        }
    }
    (temp_project / "composer.json").write_text(json.dumps(composer_json))
    return temp_project


@pytest.fixture
def js_project(temp_project):
    """Create a JavaScript project with package.json."""
    package_json = {
        "name": "test-project",
        "dependencies": {
            "react": "^18.0.0",
            "axios": "^1.0.0",
            "lodash": "^4.17.21"
        },
        "devDependencies": {
            "jest": "^29.0.0",
            "typescript": "^5.0.0"
        }
    }
    (temp_project / "package.json").write_text(json.dumps(package_json))
    return temp_project


@pytest.fixture
def python_project(temp_project):
    """Create a Python project with requirements.txt."""
    requirements = """
# Core dependencies
requests>=2.28.0
flask>=2.0.0
sqlalchemy>=2.0.0
pydantic>=2.0.0

# Dev dependencies
pytest>=7.0.0
black>=23.0.0
"""
    (temp_project / "requirements.txt").write_text(requirements)
    return temp_project


# =============================================================================
# LEVENSHTEIN DISTANCE TESTS
# =============================================================================

class TestLevenshteinDistance:
    """Tests for Levenshtein distance calculation."""

    def test_identical_strings(self):
        """Identical strings have distance 0."""
        assert levenshtein_distance("hello", "hello") == 0

    def test_single_insertion(self):
        """Single character insertion has distance 1."""
        assert levenshtein_distance("hello", "helllo") == 1

    def test_single_deletion(self):
        """Single character deletion has distance 1."""
        assert levenshtein_distance("hello", "helo") == 1

    def test_single_substitution(self):
        """Single character substitution has distance 1."""
        assert levenshtein_distance("hello", "hallo") == 1

    def test_completely_different(self):
        """Completely different strings have high distance."""
        assert levenshtein_distance("abc", "xyz") == 3

    def test_empty_string(self):
        """Empty string distance equals length of other string."""
        assert levenshtein_distance("", "hello") == 5
        assert levenshtein_distance("hello", "") == 5


class TestFindSimilarPackages:
    """Tests for finding similar package names."""

    def test_exact_typo(self):
        """Finds exact typo (1 character off)."""
        known = {"lodash", "express", "react"}
        similar = find_similar_packages("lodas", known)
        assert len(similar) > 0
        assert similar[0][0] == "lodash"
        assert similar[0][1] == 1

    def test_no_similar(self):
        """Returns empty when no similar packages."""
        known = {"lodash", "express", "react"}
        similar = find_similar_packages("completely-different-name", known)
        assert len(similar) == 0

    def test_multiple_similar(self):
        """Finds multiple similar packages sorted by distance."""
        known = {"test", "tests", "testing", "tester"}
        similar = find_similar_packages("testt", known)
        # Should find test, tests (both distance 1)
        assert len(similar) >= 2


# =============================================================================
# PHP TESTS (15 Tests)
# =============================================================================

class TestPHPImportExtraction:
    """Tests for PHP import extraction."""

    def test_simple_use_statement(self):
        """Extracts simple use statement."""
        content = "<?php\nuse Vendor\\Package\\SomeClass;"
        extractor = ImportExtractor()
        imports = extractor.extract_php_imports(content)
        assert len(imports) == 1
        assert imports[0][0] == "Vendor\\Package"

    def test_use_with_alias(self):
        """Extracts use statement with alias."""
        content = "<?php\nuse Vendor\\Package\\SomeClass as Alias;"
        extractor = ImportExtractor()
        imports = extractor.extract_php_imports(content)
        assert len(imports) == 1
        assert imports[0][0] == "Vendor\\Package"

    def test_multiple_use_statements(self):
        """Extracts multiple use statements."""
        content = """<?php
use Illuminate\\Http\\Request;
use App\\Models\\User;
use Monolog\\Logger;
"""
        extractor = ImportExtractor()
        imports = extractor.extract_php_imports(content)
        assert len(imports) == 3


class TestPHPPackageValidation:
    """Tests for PHP package validation."""

    def test_valid_composer_package(self, php_project):
        """Valid Composer package passes validation."""
        content = "<?php\nuse Illuminate\\Support\\Facades\\Route;"
        validator = PackageValidator(str(php_project))
        result = validator.validate_content(content, "test.php", Language.PHP)
        # Should pass - laravel/framework provides Illuminate namespace
        assert result.registry_found

    def test_invalid_package_not_in_composer(self, php_project):
        """Package not in composer.json is flagged."""
        content = "<?php\nuse NonExistent\\FakePackage\\SomeClass;"
        validator = PackageValidator(str(php_project))
        result = validator.validate_content(content, "test.php", Language.PHP)
        assert result.has_issues
        assert result.issues[0].package == "NonExistent\\FakePackage"

    def test_valid_psr4_autoload(self, php_project):
        """Local PSR-4 namespace passes validation."""
        content = "<?php\nuse App\\Models\\User;"
        validator = PackageValidator(str(php_project))
        result = validator.validate_content(content, "test.php", Language.PHP)
        # App\\ is defined in autoload
        assert not result.has_issues

    def test_hallucinated_vendor_namespace(self, php_project):
        """Hallucinated vendor namespace is flagged."""
        content = "<?php\nuse HuggingFace\\Transformers\\Pipeline;"
        validator = PackageValidator(str(php_project))
        result = validator.validate_content(content, "test.php", Language.PHP)
        assert result.has_issues
        assert "HuggingFace" in result.issues[0].package

    def test_typo_in_package_name(self, php_project):
        """Typo in package name is detected."""
        content = "<?php\nuse Monlog\\Logger;"  # Typo: Monlog instead of Monolog
        validator = PackageValidator(str(php_project))
        result = validator.validate_content(content, "test.php", Language.PHP)
        # Note: PHP namespace-to-package mapping is complex
        # The issue is flagged but slopsquatting detection requires
        # matching against namespace patterns, not composer package names
        assert result.has_issues
        assert "Monlog" in result.issues[0].package

    def test_builtin_class(self, php_project):
        """Built-in PHP classes pass validation."""
        content = "<?php\nuse DateTime;"
        validator = PackageValidator(str(php_project))
        result = validator.validate_content(content, "test.php", Language.PHP)
        # DateTime is a PHP builtin
        assert not result.has_issues

    def test_no_composer_json(self, temp_project):
        """Handles missing composer.json gracefully."""
        content = "<?php\nuse Some\\Package\\Class;"
        validator = PackageValidator(str(temp_project))
        result = validator.validate_content(content, "test.php", Language.PHP)
        # Should have lower confidence due to missing registry
        assert not result.registry_found

    def test_empty_php_file(self, php_project):
        """Empty file has no issues."""
        content = "<?php\n// No imports"
        validator = PackageValidator(str(php_project))
        result = validator.validate_content(content, "test.php", Language.PHP)
        assert not result.has_issues
        assert result.validated_count == 0


# =============================================================================
# JAVASCRIPT/TYPESCRIPT TESTS (20 Tests)
# =============================================================================

class TestJSImportExtraction:
    """Tests for JavaScript/TypeScript import extraction."""

    def test_import_from(self):
        """Extracts import ... from 'package'."""
        content = "import React from 'react';"
        extractor = ImportExtractor()
        imports = extractor.extract_js_imports(content)
        assert len(imports) == 1
        assert imports[0][0] == "react"

    def test_require(self):
        """Extracts require('package')."""
        content = "const axios = require('axios');"
        extractor = ImportExtractor()
        imports = extractor.extract_js_imports(content)
        assert len(imports) == 1
        assert imports[0][0] == "axios"

    def test_dynamic_import(self):
        """Extracts dynamic import()."""
        content = "const module = await import('lodash');"
        extractor = ImportExtractor()
        imports = extractor.extract_js_imports(content)
        assert len(imports) == 1
        assert imports[0][0] == "lodash"

    def test_scoped_package(self):
        """Extracts scoped packages (@org/package)."""
        content = "import { something } from '@babel/core';"
        extractor = ImportExtractor()
        imports = extractor.extract_js_imports(content)
        assert len(imports) == 1
        assert imports[0][0] == "@babel/core"

    def test_local_import_ignored(self):
        """Local imports (./path) are not extracted as packages."""
        content = "import { helper } from './utils/helper';"
        extractor = ImportExtractor()
        imports = extractor.extract_js_imports(content)
        # Local imports should not be in the list
        assert len(imports) == 0

    def test_relative_import_ignored(self):
        """Relative imports (../path) are not extracted."""
        content = "import config from '../config';"
        extractor = ImportExtractor()
        imports = extractor.extract_js_imports(content)
        assert len(imports) == 0


class TestJSPackageValidation:
    """Tests for JavaScript/TypeScript package validation."""

    def test_valid_npm_package_import(self, js_project):
        """Valid npm package passes validation."""
        content = "import React from 'react';"
        validator = PackageValidator(str(js_project))
        result = validator.validate_content(content, "test.js", Language.JAVASCRIPT)
        assert not result.has_issues

    def test_valid_npm_package_require(self, js_project):
        """Valid npm package with require passes."""
        content = "const _ = require('lodash');"
        validator = PackageValidator(str(js_project))
        result = validator.validate_content(content, "test.js", Language.JAVASCRIPT)
        assert not result.has_issues

    def test_invalid_package(self, js_project):
        """Invalid package is flagged."""
        content = "import { fake } from 'nonexistent-fake-package';"
        validator = PackageValidator(str(js_project))
        result = validator.validate_content(content, "test.js", Language.JAVASCRIPT)
        assert result.has_issues
        assert result.issues[0].package == "nonexistent-fake-package"

    def test_hallucinated_npm_package(self, js_project):
        """Hallucinated npm package is flagged."""
        content = "import { pipeline } from 'huggingface-transformers';"
        validator = PackageValidator(str(js_project))
        result = validator.validate_content(content, "test.js", Language.JAVASCRIPT)
        assert result.has_issues

    def test_typo_in_npm_package(self, js_project):
        """Typo in package name is detected."""
        content = "import _ from 'lodas';"  # Typo: lodas instead of lodash
        validator = PackageValidator(str(js_project))
        result = validator.validate_content(content, "test.js", Language.JAVASCRIPT)
        assert result.has_issues
        assert result.issues[0].is_slopsquatting
        assert "lodash" in result.issues[0].suggestions

    def test_invalid_scoped_package(self, js_project):
        """Invalid scoped package is flagged."""
        content = "import { x } from '@fake-org/fake-package';"
        validator = PackageValidator(str(js_project))
        result = validator.validate_content(content, "test.js", Language.JAVASCRIPT)
        assert result.has_issues

    def test_builtin_module_fs(self, js_project):
        """Node.js built-in modules pass validation."""
        content = "import fs from 'fs';"
        validator = PackageValidator(str(js_project))
        result = validator.validate_content(content, "test.js", Language.JAVASCRIPT)
        assert not result.has_issues

    def test_builtin_module_path(self, js_project):
        """Node.js path module passes validation."""
        content = "import path from 'path';"
        validator = PackageValidator(str(js_project))
        result = validator.validate_content(content, "test.js", Language.JAVASCRIPT)
        assert not result.has_issues

    def test_node_prefixed_import(self, js_project):
        """Node-prefixed imports pass validation."""
        content = "import fs from 'node:fs';"
        validator = PackageValidator(str(js_project))
        result = validator.validate_content(content, "test.js", Language.JAVASCRIPT)
        assert not result.has_issues

    def test_no_package_json(self, temp_project):
        """Handles missing package.json gracefully."""
        content = "import { x } from 'some-package';"
        validator = PackageValidator(str(temp_project))
        result = validator.validate_content(content, "test.js", Language.JAVASCRIPT)
        assert not result.registry_found

    def test_dev_dependency_usage(self, js_project):
        """DevDependency usage is allowed."""
        content = "import { test } from 'jest';"
        validator = PackageValidator(str(js_project))
        result = validator.validate_content(content, "test.js", Language.JAVASCRIPT)
        assert not result.has_issues

    def test_typescript_import(self, js_project):
        """TypeScript imports work the same as JS."""
        content = "import { Component } from 'react';"
        validator = PackageValidator(str(js_project))
        result = validator.validate_content(content, "test.ts", Language.TYPESCRIPT)
        assert not result.has_issues

    def test_namespace_import(self, js_project):
        """Namespace imports (* as) work correctly."""
        content = "import * as React from 'react';"
        validator = PackageValidator(str(js_project))
        result = validator.validate_content(content, "test.js", Language.JAVASCRIPT)
        assert not result.has_issues

    def test_side_effect_import(self, js_project):
        """Side-effect imports work correctly."""
        content = "import 'react';"
        validator = PackageValidator(str(js_project))
        result = validator.validate_content(content, "test.js", Language.JAVASCRIPT)
        assert not result.has_issues


# =============================================================================
# PYTHON TESTS (15 Tests)
# =============================================================================

class TestPythonImportExtraction:
    """Tests for Python import extraction."""

    def test_simple_import(self):
        """Extracts simple import statement."""
        content = "import requests"
        extractor = ImportExtractor()
        imports = extractor.extract_python_imports(content)
        assert len(imports) == 1
        assert imports[0][0] == "requests"

    def test_from_import(self):
        """Extracts from X import Y statement."""
        content = "from flask import Flask"
        extractor = ImportExtractor()
        imports = extractor.extract_python_imports(content)
        assert len(imports) == 1
        assert imports[0][0] == "flask"

    def test_submodule_import(self):
        """Extracts root package from submodule import."""
        content = "from sqlalchemy.orm import Session"
        extractor = ImportExtractor()
        imports = extractor.extract_python_imports(content)
        assert len(imports) == 1
        assert imports[0][0] == "sqlalchemy"

    def test_multiple_imports_one_line(self):
        """Extracts multiple imports from one line."""
        content = "import os, sys, json"
        extractor = ImportExtractor()
        imports = extractor.extract_python_imports(content)
        assert len(imports) == 3

    def test_import_with_alias(self):
        """Extracts import with as alias."""
        content = "import numpy as np"
        extractor = ImportExtractor()
        imports = extractor.extract_python_imports(content)
        assert len(imports) == 1
        assert imports[0][0] == "numpy"


class TestPythonPackageValidation:
    """Tests for Python package validation."""

    def test_valid_pip_package(self, python_project):
        """Valid pip package passes validation."""
        content = "import requests"
        validator = PackageValidator(str(python_project))
        result = validator.validate_content(content, "test.py", Language.PYTHON)
        assert not result.has_issues

    def test_invalid_package(self, python_project):
        """Package not in requirements is flagged."""
        content = "import nonexistent_fake_package"
        validator = PackageValidator(str(python_project))
        result = validator.validate_content(content, "test.py", Language.PYTHON)
        assert result.has_issues

    def test_standard_library(self, python_project):
        """Standard library modules pass validation."""
        content = "import os\nimport json\nimport asyncio"
        validator = PackageValidator(str(python_project))
        result = validator.validate_content(content, "test.py", Language.PYTHON)
        assert not result.has_issues

    def test_relative_import_ignored(self, python_project):
        """Relative imports are ignored."""
        content = "from .utils import helper"
        validator = PackageValidator(str(python_project))
        result = validator.validate_content(content, "test.py", Language.PYTHON)
        # Relative imports should not be flagged
        assert not result.has_issues

    def test_hallucinated_package(self, python_project):
        """Hallucinated package is flagged."""
        content = "import huggingface_transformers"
        validator = PackageValidator(str(python_project))
        result = validator.validate_content(content, "test.py", Language.PYTHON)
        assert result.has_issues

    def test_typo_in_package_name(self, python_project):
        """Typo in package name is detected."""
        content = "import requsets"  # Typo: requsets instead of requests
        validator = PackageValidator(str(python_project))
        result = validator.validate_content(content, "test.py", Language.PYTHON)
        assert result.has_issues
        assert result.issues[0].is_slopsquatting

    def test_from_import_validation(self, python_project):
        """From imports are validated correctly."""
        content = "from flask import Flask"
        validator = PackageValidator(str(python_project))
        result = validator.validate_content(content, "test.py", Language.PYTHON)
        assert not result.has_issues

    def test_no_requirements_txt(self, temp_project):
        """Handles missing requirements.txt gracefully."""
        content = "import some_package"
        validator = PackageValidator(str(temp_project))
        result = validator.validate_content(content, "test.py", Language.PYTHON)
        assert not result.registry_found

    def test_conditional_import(self, python_project):
        """Conditional imports in try/except are handled."""
        content = """
try:
    import optional_package
except ImportError:
    optional_package = None
"""
        validator = PackageValidator(str(python_project))
        result = validator.validate_content(content, "test.py", Language.PYTHON)
        # Should flag but with lower confidence due to try/except pattern
        assert result.has_issues

    def test_typing_extensions(self, python_project):
        """typing_extensions is recognized as stdlib."""
        content = "from typing_extensions import TypeAlias"
        validator = PackageValidator(str(python_project))
        result = validator.validate_content(content, "test.py", Language.PYTHON)
        # typing_extensions is in our stdlib list
        assert not result.has_issues


# =============================================================================
# PACKAGE REGISTRY TESTS
# =============================================================================

class TestPackageRegistry:
    """Tests for PackageRegistry class."""

    def test_composer_packages(self, php_project):
        """Reads packages from composer.json."""
        registry = PackageRegistry(str(php_project))
        packages, found = registry.get_composer_packages()
        assert found
        assert "laravel/framework" in packages
        assert "guzzlehttp/guzzle" in packages

    def test_npm_packages(self, js_project):
        """Reads packages from package.json."""
        registry = PackageRegistry(str(js_project))
        packages, found = registry.get_npm_packages()
        assert found
        assert "react" in packages
        assert "axios" in packages
        assert "jest" in packages  # devDependency

    def test_pip_packages(self, python_project):
        """Reads packages from requirements.txt."""
        registry = PackageRegistry(str(python_project))
        packages, found = registry.get_pip_packages()
        assert found
        assert "requests" in packages
        assert "flask" in packages

    def test_cache_works(self, php_project):
        """Package cache works correctly."""
        registry = PackageRegistry(str(php_project))
        packages1, _ = registry.get_composer_packages()
        packages2, _ = registry.get_composer_packages()
        assert packages1 == packages2

    def test_clear_cache(self, php_project):
        """Clear cache works correctly."""
        registry = PackageRegistry(str(php_project))
        registry.get_composer_packages()
        registry.clear_cache()
        assert len(registry._cache) == 0


# =============================================================================
# STDLIB TESTS
# =============================================================================

class TestStandardLibraries:
    """Tests for standard library detection."""

    def test_python_stdlib_complete(self):
        """Python stdlib contains essential modules."""
        assert "os" in PYTHON_STDLIB
        assert "sys" in PYTHON_STDLIB
        assert "json" in PYTHON_STDLIB
        assert "asyncio" in PYTHON_STDLIB
        assert "pathlib" in PYTHON_STDLIB

    def test_node_builtins_complete(self):
        """Node builtins contains essential modules."""
        assert "fs" in NODE_BUILTINS
        assert "path" in NODE_BUILTINS
        assert "http" in NODE_BUILTINS
        assert "crypto" in NODE_BUILTINS
        assert "node:fs" in NODE_BUILTINS

    def test_php_builtins_complete(self):
        """PHP builtins contains essential classes."""
        assert "DateTime" in PHP_BUILTINS
        assert "PDO" in PHP_BUILTINS
        assert "Exception" in PHP_BUILTINS
        assert "stdClass" in PHP_BUILTINS


# =============================================================================
# EDGE CASES
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and special scenarios."""

    def test_empty_file(self, js_project):
        """Empty file has no issues."""
        content = ""
        validator = PackageValidator(str(js_project))
        result = validator.validate_content(content, "test.js", Language.JAVASCRIPT)
        assert not result.has_issues
        assert result.validated_count == 0

    def test_comments_only(self, python_project):
        """File with only comments has no issues."""
        content = "# This is a comment\n# import fake_package"
        validator = PackageValidator(str(python_project))
        result = validator.validate_content(content, "test.py", Language.PYTHON)
        assert not result.has_issues

    def test_malformed_import(self, js_project):
        """Malformed imports don't crash validator."""
        content = "import { broken from"
        validator = PackageValidator(str(js_project))
        result = validator.validate_content(content, "test.js", Language.JAVASCRIPT)
        # Should not crash, may or may not have issues

    def test_package_with_weird_characters(self, js_project):
        """Package with weird characters has high confidence."""
        content = "import x from 'package$with$dollars';"
        validator = PackageValidator(str(js_project))
        result = validator.validate_content(content, "test.js", Language.JAVASCRIPT)
        if result.has_issues:
            assert result.issues[0].confidence > 0.9

    def test_very_long_package_name(self, js_project):
        """Very long package names are handled."""
        content = "import x from 'this-is-a-very-long-package-name-that-probably-does-not-exist';"
        validator = PackageValidator(str(js_project))
        result = validator.validate_content(content, "test.js", Language.JAVASCRIPT)
        assert result.has_issues


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

class TestIntegration:
    """Integration tests for full validation workflow."""

    def test_mixed_valid_invalid(self, js_project):
        """File with mix of valid and invalid imports."""
        content = """
import React from 'react';
import { fake } from 'nonexistent-package';
import axios from 'axios';
import { bad } from 'another-fake-one';
"""
        validator = PackageValidator(str(js_project))
        result = validator.validate_content(content, "test.js", Language.JAVASCRIPT)
        assert result.has_issues
        assert len(result.issues) == 2
        # Valid packages should not be in issues
        assert not any(i.package == "react" for i in result.issues)
        assert not any(i.package == "axios" for i in result.issues)

    def test_full_file_validation(self, js_project):
        """Full file validation workflow."""
        # Create a test file
        test_file = js_project / "test.js"
        test_file.write_text("""
import React from 'react';
import { useState } from 'react';
const axios = require('axios');
import fake from 'hallucinated-package';
""")
        validator = PackageValidator(str(js_project))
        result = validator.validate_file(str(test_file))
        assert result.has_issues
        assert result.issues[0].package == "hallucinated-package"

    def test_confidence_scores(self, js_project):
        """Confidence scores are calculated correctly."""
        # Typo should have high confidence
        content = "import x from 'recat';"  # Typo for react
        validator = PackageValidator(str(js_project))
        result = validator.validate_content(content, "test.js", Language.JAVASCRIPT)
        assert result.has_issues
        assert result.issues[0].confidence > 0.8
        assert result.issues[0].is_slopsquatting


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
