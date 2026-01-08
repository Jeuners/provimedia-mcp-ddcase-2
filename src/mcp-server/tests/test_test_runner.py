"""
Tests for chainguard.test_runner module.

Tests TestConfig, TestResult, OutputParser, and TestRunner.
"""

import pytest
from chainguard.test_runner import (
    TestConfig,
    TestResult,
    OutputParser,
    TestRunner
)


class TestTestConfig:
    """Tests for TestConfig dataclass."""

    def test_default_values(self):
        """Test default values."""
        config = TestConfig()
        assert config.command == ""
        assert config.args == ""
        assert config.timeout == 300
        assert config.working_dir == ""

    def test_with_values(self):
        """Test creating config with values."""
        config = TestConfig(
            command="./vendor/bin/phpunit",
            args="tests/ --colors=never",
            timeout=120
        )
        assert config.command == "./vendor/bin/phpunit"
        assert config.args == "tests/ --colors=never"
        assert config.timeout == 120

    def test_to_dict(self):
        """Test serialization to dict."""
        config = TestConfig(command="pytest", args="-v")
        data = config.to_dict()

        assert data["command"] == "pytest"
        assert data["args"] == "-v"

    def test_from_dict(self):
        """Test creating from dict."""
        data = {
            "command": "npm test",
            "args": "--coverage",
            "timeout": 60
        }
        config = TestConfig.from_dict(data)

        assert config.command == "npm test"
        assert config.args == "--coverage"
        assert config.timeout == 60

    def test_get_full_command(self):
        """Test building full command list."""
        config = TestConfig(
            command="./vendor/bin/phpunit",
            args="tests/ --colors=never"
        )
        cmd = config.get_full_command()

        assert cmd == ["./vendor/bin/phpunit", "tests/", "--colors=never"]

    def test_get_full_command_no_args(self):
        """Test command list without args."""
        config = TestConfig(command="pytest")
        cmd = config.get_full_command()

        assert cmd == ["pytest"]


class TestTestResult:
    """Tests for TestResult dataclass."""

    def test_default_values(self):
        """Test default values."""
        result = TestResult()
        assert result.success is False
        assert result.passed == 0
        assert result.failed == 0
        assert result.total == 0
        assert result.framework == "unknown"

    def test_to_dict(self):
        """Test serialization."""
        result = TestResult(
            success=True,
            passed=10,
            failed=0,
            total=10,
            framework="phpunit"
        )
        data = result.to_dict()

        assert data["success"] is True
        assert data["passed"] == 10
        assert data["framework"] == "phpunit"

    def test_from_dict(self):
        """Test deserialization."""
        data = {
            "success": False,
            "passed": 8,
            "failed": 2,
            "total": 10,
            "framework": "jest",
            "error_lines": ["Error: assertion failed"],
            "duration": 5.5,
            "exit_code": 1,
            "output": "test output",
            "timestamp": "2024-01-01T00:00:00"
        }
        result = TestResult.from_dict(data)

        assert result.success is False
        assert result.passed == 8
        assert result.failed == 2
        assert result.framework == "jest"


class TestOutputParser:
    """Tests for OutputParser."""

    # PHPUnit tests
    def test_detect_phpunit(self):
        """Test PHPUnit detection."""
        output = "PHPUnit 10.0.0 by Sebastian Bergmann.\n\n...\n\nOK (3 tests, 5 assertions)"
        assert OutputParser.detect_framework(output) == "phpunit"

    def test_parse_phpunit_success(self):
        """Test parsing PHPUnit success output."""
        output = """PHPUnit 10.0.0 by Sebastian Bergmann.

...............

Time: 00:00.123, Memory: 10.00 MB

OK (15 tests, 42 assertions)"""

        result = OutputParser.parse(output, exit_code=0)

        assert result.success is True
        assert result.passed == 15
        assert result.total == 15
        assert result.failed == 0
        assert result.framework == "phpunit"

    def test_parse_phpunit_failure(self):
        """Test parsing PHPUnit failure output."""
        output = """PHPUnit 10.0.0 by Sebastian Bergmann.

.F.

FAILURES!
Tests: 3, Assertions: 5, Failures: 1."""

        result = OutputParser.parse(output, exit_code=1)

        assert result.success is False
        assert result.total == 3
        assert result.failed == 1
        assert result.passed == 2
        assert result.framework == "phpunit"

    # Jest tests
    def test_detect_jest(self):
        """Test Jest detection."""
        output = "PASS src/test.js\nTest Suites: 1 passed\nTests: 5 passed, 5 total"
        assert OutputParser.detect_framework(output) == "jest"

    def test_parse_jest_success(self):
        """Test parsing Jest success output."""
        output = """PASS src/components/Button.test.js
PASS src/utils/helper.test.js

Test Suites: 2 passed, 2 total
Tests:       8 passed, 8 total
Snapshots:   0 total
Time:        2.5 s"""

        result = OutputParser.parse(output, exit_code=0)

        assert result.success is True
        assert result.passed == 8
        assert result.total == 8
        assert result.framework == "jest"

    def test_parse_jest_failure(self):
        """Test parsing Jest failure output."""
        output = """FAIL src/test.js
  ✕ should work (5 ms)

Tests:  1 failed, 3 passed, 4 total"""

        result = OutputParser.parse(output, exit_code=1)

        assert result.success is False
        assert result.failed == 1
        assert result.passed == 3
        assert result.total == 4
        assert result.framework == "jest"

    # pytest tests
    def test_detect_pytest(self):
        """Test pytest detection."""
        output = "===== 5 passed in 0.12s ====="
        assert OutputParser.detect_framework(output) == "pytest"

    def test_parse_pytest_success(self):
        """Test parsing pytest success output."""
        output = """======================== test session starts ========================
collected 10 items

tests/test_main.py ..........                                     [100%]

========================= 10 passed in 0.45s ========================="""

        result = OutputParser.parse(output, exit_code=0)

        assert result.success is True
        assert result.passed == 10
        assert result.framework == "pytest"

    def test_parse_pytest_failure(self):
        """Test parsing pytest failure output."""
        output = """======================== test session starts ========================
collected 5 items

tests/test_main.py ...F.                                          [100%]

FAILED tests/test_main.py::test_something

========================= 1 failed, 4 passed in 0.32s ========================="""

        result = OutputParser.parse(output, exit_code=1)

        assert result.success is False
        assert result.passed == 4
        assert result.failed == 1
        assert result.framework == "pytest"

    # mocha tests
    def test_detect_mocha(self):
        """Test mocha detection."""
        output = "  3 passing (15ms)"
        assert OutputParser.detect_framework(output) == "mocha"

    def test_parse_mocha_success(self):
        """Test parsing mocha success output."""
        output = """
  User API
    ✓ should return users
    ✓ should create user
    ✓ should delete user

  3 passing (45ms)"""

        result = OutputParser.parse(output, exit_code=0)

        assert result.success is True
        assert result.passed == 3
        assert result.framework == "mocha"

    def test_parse_mocha_failure(self):
        """Test parsing mocha failure output."""
        output = """
  User API
    ✓ should return users
    1) should create user

  1 passing (30ms)
  1 failing"""

        result = OutputParser.parse(output, exit_code=1)

        assert result.success is False
        assert result.passed == 1
        assert result.failed == 1
        assert result.framework == "mocha"

    # Generic/fallback tests
    def test_parse_generic_success(self):
        """Test generic parsing with exit code 0."""
        output = "All tests completed successfully"
        result = OutputParser.parse(output, exit_code=0)

        assert result.success is True
        assert result.framework == "generic"

    def test_parse_generic_failure(self):
        """Test generic parsing with non-zero exit code."""
        output = "Some error occurred"
        result = OutputParser.parse(output, exit_code=1)

        assert result.success is False
        assert result.framework == "generic"

    # Error extraction tests
    def test_extract_error_lines(self):
        """Test error line extraction."""
        output = """
FAILED tests/test_main.py::test_login
AssertionError: Expected 200, got 401
    at test_login (tests/test_main.py:45:12)
"""
        result = OutputParser.parse(output, exit_code=1)

        assert len(result.error_lines) > 0
        assert any("FAILED" in line or "AssertionError" in line
                   for line in result.error_lines)


class TestTestRunnerFormat:
    """Tests for TestRunner formatting methods."""

    def test_format_result_success(self):
        """Test formatting successful result."""
        result = TestResult(
            success=True,
            passed=10,
            failed=0,
            total=10,
            framework="phpunit",
            duration=2.5
        )
        output = TestRunner.format_result(result)

        assert "✓" in output
        assert "10/10" in output
        assert "phpunit" in output
        assert "2.5" in output or "2.50" in output

    def test_format_result_failure(self):
        """Test formatting failed result."""
        result = TestResult(
            success=False,
            passed=8,
            failed=2,
            total=10,
            framework="jest",
            duration=3.0,
            error_lines=["Error: test failed", "at line 42"]
        )
        output = TestRunner.format_result(result)

        assert "✗" in output
        assert "8/10" in output
        assert "2 failed" in output
        assert "Errors:" in output

    def test_format_status(self):
        """Test status formatting."""
        result = TestResult(
            success=True,
            passed=5,
            failed=0,
            total=5
        )
        status = TestRunner.format_status(result)

        assert "✓" in status
        assert "5/5" in status

    def test_format_status_with_timestamp(self):
        """Test status with recent timestamp."""
        from datetime import datetime

        result = TestResult(
            success=True,
            passed=5,
            failed=0,
            total=5
        )
        last_run = datetime.now().isoformat()
        status = TestRunner.format_status(result, last_run)

        assert "5/5" in status
        # Should include time indicator
        assert "s ago" in status or "m ago" in status or "h ago" in status
