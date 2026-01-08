"""
Tests for chainguard.validators module.

Tests cover:
- SyntaxValidator.validate_file with various file types
- Error extraction methods for PHP, JS, Python, TS
- Command execution including timeout handling
"""

import pytest
import json
import tempfile
import asyncio
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from chainguard.validators import SyntaxValidator


# =============================================================================
# TestSyntaxValidator - validate_file tests
# =============================================================================
class TestSyntaxValidator:
    """Tests for SyntaxValidator.validate_file method."""

    @pytest.mark.asyncio
    async def test_validate_file_nonexistent(self):
        """Test that non-existent files return valid=True."""
        result = await SyntaxValidator.validate_file(
            "/nonexistent/path/file.php",
            "/project"
        )
        assert result["valid"] is True
        assert result["errors"] == []
        assert result["checked"] == "file not found"

    @pytest.mark.asyncio
    async def test_validate_file_valid_json(self, tmp_path):
        """Test validation of valid JSON file."""
        json_file = tmp_path / "valid.json"
        json_file.write_text('{"key": "value", "number": 42}')

        result = await SyntaxValidator.validate_file(
            str(json_file),
            str(tmp_path)
        )
        assert result["valid"] is True
        assert result["errors"] == []
        assert result["checked"] == ".json"

    @pytest.mark.asyncio
    async def test_validate_file_invalid_json(self, tmp_path):
        """Test validation of invalid JSON file."""
        json_file = tmp_path / "invalid.json"
        json_file.write_text('{"key": "value",}')  # Trailing comma = invalid

        result = await SyntaxValidator.validate_file(
            str(json_file),
            str(tmp_path)
        )
        assert result["valid"] is False
        assert len(result["errors"]) == 1
        assert result["errors"][0]["type"] == "JSON"
        assert "Line" in result["errors"][0]["message"]
        assert result["checked"] == ".json"

    @pytest.mark.asyncio
    async def test_validate_file_invalid_json_missing_quote(self, tmp_path):
        """Test validation of JSON with missing quote."""
        json_file = tmp_path / "broken.json"
        json_file.write_text('{"key: "value"}')

        result = await SyntaxValidator.validate_file(
            str(json_file),
            str(tmp_path)
        )
        assert result["valid"] is False
        assert len(result["errors"]) == 1
        assert result["errors"][0]["type"] == "JSON"

    @pytest.mark.asyncio
    async def test_validate_file_unknown_extension(self, tmp_path):
        """Test that unknown extensions are skipped (return valid)."""
        unknown_file = tmp_path / "file.xyz"
        unknown_file.write_text("some content")

        result = await SyntaxValidator.validate_file(
            str(unknown_file),
            str(tmp_path)
        )
        assert result["valid"] is True
        assert result["errors"] == []
        assert result["checked"] == ".xyz"

    @pytest.mark.asyncio
    async def test_validate_file_no_extension(self, tmp_path):
        """Test file without extension."""
        no_ext_file = tmp_path / "Makefile"
        no_ext_file.write_text("all: build")

        result = await SyntaxValidator.validate_file(
            str(no_ext_file),
            str(tmp_path)
        )
        assert result["valid"] is True
        assert result["errors"] == []
        # No extension returns empty string (suffix is "")
        assert result["checked"] == ""  or result["checked"] == "unknown"

    @pytest.mark.asyncio
    async def test_validate_file_relative_path(self, tmp_path):
        """Test validation with relative path."""
        subdir = tmp_path / "src"
        subdir.mkdir()
        json_file = subdir / "config.json"
        json_file.write_text('{"valid": true}')

        result = await SyntaxValidator.validate_file(
            "src/config.json",
            str(tmp_path)
        )
        assert result["valid"] is True
        assert result["checked"] == ".json"

    @pytest.mark.asyncio
    async def test_validate_php_valid(self, tmp_path):
        """Test validation of valid PHP file."""
        php_file = tmp_path / "valid.php"
        php_file.write_text("<?php\necho 'hello';\n?>")

        # Mock _run_command to return success
        with patch.object(SyntaxValidator, '_run_command', new_callable=AsyncMock) as mock_cmd:
            mock_cmd.return_value = {"returncode": 0, "stdout": "No syntax errors", "stderr": ""}

            result = await SyntaxValidator.validate_file(
                str(php_file),
                str(tmp_path)
            )
            assert result["valid"] is True
            assert result["errors"] == []
            assert result["checked"] == ".php"

    @pytest.mark.asyncio
    async def test_validate_php_invalid(self, tmp_path):
        """Test validation of invalid PHP file."""
        php_file = tmp_path / "invalid.php"
        php_file.write_text("<?php\necho 'hello'\n?>")  # Missing semicolon

        with patch.object(SyntaxValidator, '_run_command', new_callable=AsyncMock) as mock_cmd:
            mock_cmd.return_value = {
                "returncode": 1,
                "stdout": "",
                "stderr": "Parse error: syntax error, unexpected '}' in /path/file.php on line 3"
            }

            result = await SyntaxValidator.validate_file(
                str(php_file),
                str(tmp_path)
            )
            assert result["valid"] is False
            assert len(result["errors"]) == 1
            assert result["errors"][0]["type"] == "PHP Syntax"
            assert "Parse error" in result["errors"][0]["message"]

    @pytest.mark.asyncio
    async def test_validate_blade_php_skipped(self, tmp_path):
        """Test that Blade templates are skipped."""
        blade_file = tmp_path / "view.blade.php"
        blade_file.write_text("@if(true)\n<div>Hello</div>\n@endif")

        # Should not call _run_command for blade files
        with patch.object(SyntaxValidator, '_run_command', new_callable=AsyncMock) as mock_cmd:
            result = await SyntaxValidator.validate_file(
                str(blade_file),
                str(tmp_path)
            )
            mock_cmd.assert_not_called()
            assert result["valid"] is True

    @pytest.mark.asyncio
    async def test_validate_js_valid(self, tmp_path):
        """Test validation of valid JavaScript file."""
        js_file = tmp_path / "app.js"
        js_file.write_text("const x = 42;\nconsole.log(x);")

        with patch.object(SyntaxValidator, '_run_command', new_callable=AsyncMock) as mock_cmd:
            mock_cmd.return_value = {"returncode": 0, "stdout": "", "stderr": ""}

            result = await SyntaxValidator.validate_file(
                str(js_file),
                str(tmp_path)
            )
            assert result["valid"] is True
            assert result["checked"] == ".js"

    @pytest.mark.asyncio
    async def test_validate_js_invalid(self, tmp_path):
        """Test validation of invalid JavaScript file."""
        js_file = tmp_path / "bad.js"
        js_file.write_text("const x =")

        with patch.object(SyntaxValidator, '_run_command', new_callable=AsyncMock) as mock_cmd:
            mock_cmd.return_value = {
                "returncode": 1,
                "stdout": "",
                "stderr": "SyntaxError: Unexpected end of input"
            }

            result = await SyntaxValidator.validate_file(
                str(js_file),
                str(tmp_path)
            )
            assert result["valid"] is False
            assert len(result["errors"]) == 1
            assert result["errors"][0]["type"] == "JS Syntax"

    @pytest.mark.asyncio
    async def test_validate_mjs_file(self, tmp_path):
        """Test validation of .mjs (ES modules) file."""
        mjs_file = tmp_path / "module.mjs"
        mjs_file.write_text("export const value = 42;")

        with patch.object(SyntaxValidator, '_run_command', new_callable=AsyncMock) as mock_cmd:
            mock_cmd.return_value = {"returncode": 0, "stdout": "", "stderr": ""}

            result = await SyntaxValidator.validate_file(
                str(mjs_file),
                str(tmp_path)
            )
            assert result["valid"] is True
            assert result["checked"] == ".mjs"

    @pytest.mark.asyncio
    async def test_validate_python_valid(self, tmp_path):
        """Test validation of valid Python file."""
        py_file = tmp_path / "script.py"
        py_file.write_text("def hello():\n    print('Hello')\n")

        with patch.object(SyntaxValidator, '_run_command', new_callable=AsyncMock) as mock_cmd:
            mock_cmd.return_value = {"returncode": 0, "stdout": "", "stderr": ""}

            result = await SyntaxValidator.validate_file(
                str(py_file),
                str(tmp_path)
            )
            assert result["valid"] is True
            assert result["checked"] == ".py"

    @pytest.mark.asyncio
    async def test_validate_python_invalid(self, tmp_path):
        """Test validation of invalid Python file."""
        py_file = tmp_path / "bad.py"
        py_file.write_text("def hello(\n    print('Hello')\n")

        with patch.object(SyntaxValidator, '_run_command', new_callable=AsyncMock) as mock_cmd:
            mock_cmd.return_value = {
                "returncode": 1,
                "stdout": "",
                "stderr": "SyntaxError: unexpected EOF while parsing"
            }

            result = await SyntaxValidator.validate_file(
                str(py_file),
                str(tmp_path)
            )
            assert result["valid"] is False
            assert len(result["errors"]) == 1
            assert result["errors"][0]["type"] == "Python Syntax"

    @pytest.mark.asyncio
    async def test_validate_typescript_valid(self, tmp_path):
        """Test validation of valid TypeScript file."""
        ts_file = tmp_path / "app.ts"
        ts_file.write_text("const x: number = 42;")

        with patch.object(SyntaxValidator, '_run_command', new_callable=AsyncMock) as mock_cmd:
            mock_cmd.return_value = {"returncode": 0, "stdout": "", "stderr": ""}

            result = await SyntaxValidator.validate_file(
                str(ts_file),
                str(tmp_path)
            )
            assert result["valid"] is True
            assert result["checked"] == ".ts"

    @pytest.mark.asyncio
    async def test_validate_typescript_invalid(self, tmp_path):
        """Test validation of invalid TypeScript file."""
        ts_file = tmp_path / "bad.ts"
        ts_file.write_text("const x: number = ")

        with patch.object(SyntaxValidator, '_run_command', new_callable=AsyncMock) as mock_cmd:
            mock_cmd.return_value = {
                "returncode": 1,
                "stdout": "bad.ts(1,19): error TS1109: Expression expected.",
                "stderr": ""
            }

            result = await SyntaxValidator.validate_file(
                str(ts_file),
                str(tmp_path)
            )
            assert result["valid"] is False
            assert len(result["errors"]) == 1
            assert result["errors"][0]["type"] == "TS Syntax"

    @pytest.mark.asyncio
    async def test_validate_tsx_file(self, tmp_path):
        """Test validation of TSX file."""
        tsx_file = tmp_path / "Component.tsx"
        tsx_file.write_text("const Component = () => <div>Hello</div>;")

        with patch.object(SyntaxValidator, '_run_command', new_callable=AsyncMock) as mock_cmd:
            mock_cmd.return_value = {"returncode": 0, "stdout": "", "stderr": ""}

            result = await SyntaxValidator.validate_file(
                str(tsx_file),
                str(tmp_path)
            )
            assert result["valid"] is True
            assert result["checked"] == ".tsx"

    @pytest.mark.asyncio
    async def test_validate_ts_no_error_marker(self, tmp_path):
        """Test TS validation where returncode is non-zero but no 'error TS' in output."""
        ts_file = tmp_path / "edge.ts"
        ts_file.write_text("const x = 1;")

        with patch.object(SyntaxValidator, '_run_command', new_callable=AsyncMock) as mock_cmd:
            # npx might fail for other reasons (e.g., tsc not installed)
            # but if "error TS" is NOT in stdout, we don't report it as validation error
            mock_cmd.return_value = {
                "returncode": 1,
                "stdout": "Some warning without error marker",
                "stderr": ""
            }

            result = await SyntaxValidator.validate_file(
                str(ts_file),
                str(tmp_path)
            )
            # The validator only adds errors if returncode != 0 AND "error TS" in stdout
            # Since "error TS" is not in stdout, no errors should be added
            assert result["valid"] is True
            assert result["errors"] == []


# =============================================================================
# TestExtractErrors - Error extraction method tests
# =============================================================================
class TestExtractErrors:
    """Tests for error extraction methods."""

    def test_extract_php_error_parse_error(self):
        """Test extraction of PHP Parse error."""
        output = "Parse error: syntax error, unexpected '}' in /path/to/file.php on line 42"
        result = SyntaxValidator._extract_php_error(output)
        assert "Parse error" in result
        assert "syntax error" in result
        # Path should be stripped
        assert "/path/to/file.php" not in result

    def test_extract_php_error_fatal_error(self):
        """Test extraction of PHP Fatal error."""
        output = "Fatal error: Cannot redeclare function() in /path/to/file.php on line 10"
        result = SyntaxValidator._extract_php_error(output)
        assert "Fatal error" in result
        assert "/path/to/file.php" not in result

    def test_extract_php_error_syntax_error(self):
        """Test extraction of generic syntax error."""
        output = "syntax error, unexpected T_STRING in /path/file.php on line 5"
        result = SyntaxValidator._extract_php_error(output)
        assert "syntax error" in result

    def test_extract_php_error_multiline(self):
        """Test extraction from multiline output."""
        output = """Errors parsing file.php
Parse error: syntax error, unexpected ',' in /file.php on line 3
Some other output"""
        result = SyntaxValidator._extract_php_error(output)
        assert "Parse error" in result

    def test_extract_php_error_fallback(self):
        """Test fallback when no known error pattern found."""
        output = "Some unknown error message that is quite long"
        result = SyntaxValidator._extract_php_error(output)
        # Should return truncated output
        assert len(result) <= 100
        assert result == output.strip()[:100]

    def test_extract_php_error_empty(self):
        """Test with empty output."""
        output = ""
        result = SyntaxValidator._extract_php_error(output)
        assert result == ""

    def test_extract_js_error_syntax_error(self):
        """Test extraction of JS SyntaxError."""
        output = "SyntaxError: Unexpected token ';'"
        result = SyntaxValidator._extract_js_error(output)
        assert "SyntaxError" in result
        assert "Unexpected token" in result

    def test_extract_js_error_reference_error(self):
        """Test extraction of generic Error."""
        output = "ReferenceError: x is not defined"
        result = SyntaxValidator._extract_js_error(output)
        assert "Error" in result

    def test_extract_js_error_multiline(self):
        """Test extraction from multiline JS output."""
        output = """file.js:1
const x =
        ^
SyntaxError: Unexpected end of input"""
        result = SyntaxValidator._extract_js_error(output)
        assert "SyntaxError" in result

    def test_extract_js_error_fallback(self):
        """Test fallback for unknown error format."""
        output = "some other error message"
        result = SyntaxValidator._extract_js_error(output)
        assert result == output.strip()[:100]

    def test_extract_python_error_syntax_error(self):
        """Test extraction of Python SyntaxError."""
        # When SyntaxError is on its own line, it gets extracted
        output = "SyntaxError: unexpected EOF while parsing"
        result = SyntaxValidator._extract_python_error(output)
        assert "SyntaxError" in result

    def test_extract_python_error_indentation_error(self):
        """Test extraction of Python IndentationError."""
        # When IndentationError is on its own line, it gets extracted
        output = "IndentationError: unexpected indent"
        result = SyntaxValidator._extract_python_error(output)
        assert "IndentationError" in result

    def test_extract_python_error_tab_error(self):
        """Test extraction of Python TabError."""
        # When TabError is on its own line, it gets extracted
        output = "TabError: inconsistent use of tabs and spaces in indentation"
        result = SyntaxValidator._extract_python_error(output)
        assert "TabError" in result

    def test_extract_python_error_multiline_with_error_type(self):
        """Test extraction from multiline output prefers file/line info."""
        # The extractor checks for file/line info BEFORE checking for SyntaxError
        # So when both are present, file/line info is returned first
        output = """  File "script.py", line 5
    def foo(
           ^
SyntaxError: unexpected EOF while parsing"""
        result = SyntaxValidator._extract_python_error(output)
        # The implementation finds the "File ... line" first
        assert "File" in result or "line" in result

    def test_extract_python_error_file_line_info(self):
        """Test extraction with File/line info."""
        output = '  File "test.py", line 10, in module'
        result = SyntaxValidator._extract_python_error(output)
        assert "File" in result.lower() or "line" in result.lower()

    def test_extract_python_error_empty(self):
        """Test with empty output returns default message."""
        output = ""
        result = SyntaxValidator._extract_python_error(output)
        assert result == "Syntax error"

    def test_extract_python_error_fallback(self):
        """Test fallback for unknown format."""
        output = "Some unknown python error"
        result = SyntaxValidator._extract_python_error(output)
        assert result == output.strip()[:100]

    def test_extract_ts_error_basic(self):
        """Test extraction of TypeScript error."""
        output = "file.ts(1,10): error TS1109: Expression expected."
        result = SyntaxValidator._extract_ts_error(output)
        assert "error" in result
        assert "TS1109" in result

    def test_extract_ts_error_multiline(self):
        """Test extraction from multiline TS output."""
        output = """file.ts(1,10): error TS1109: Expression expected.
file.ts(2,5): error TS2304: Cannot find name 'foo'.
"""
        result = SyntaxValidator._extract_ts_error(output)
        # Should return first error
        assert "TS1109" in result

    def test_extract_ts_error_with_path(self):
        """Test TS error with full path."""
        output = "/long/path/to/file.ts(42,15): error TS2322: Type 'string' is not assignable to type 'number'."
        result = SyntaxValidator._extract_ts_error(output)
        assert "error" in result
        assert "TS2322" in result
        # Path before error should be stripped
        assert result.startswith("error")

    def test_extract_ts_error_truncation(self):
        """Test that long TS errors are truncated."""
        long_error = "error TS9999: " + "x" * 200
        output = f"file.ts(1,1): {long_error}"
        result = SyntaxValidator._extract_ts_error(output)
        # Should be truncated to ~100 chars
        assert len(result) <= 100

    def test_extract_ts_error_empty(self):
        """Test with empty output."""
        output = ""
        result = SyntaxValidator._extract_ts_error(output)
        assert result == "TypeScript error"

    def test_extract_ts_error_fallback(self):
        """Test fallback when no 'error TS' found."""
        output = "Some other tsc output"
        result = SyntaxValidator._extract_ts_error(output)
        assert result == output.strip()[:100]


# =============================================================================
# TestRunCommand - Command execution tests
# =============================================================================
class TestRunCommand:
    """Tests for _run_command method."""

    @pytest.mark.asyncio
    async def test_run_command_not_found(self):
        """Test handling of command not found."""
        result = await SyntaxValidator._run_command(
            ["nonexistent_command_xyz", "--version"]
        )
        assert result["returncode"] == -1
        assert result["stderr"] == "Command not found"
        assert result["stdout"] == ""

    @pytest.mark.asyncio
    async def test_run_command_timeout(self):
        """Test timeout handling."""
        # Patch the timeout constant to be very short
        with patch('chainguard.validators.SYNTAX_CHECK_TIMEOUT_SECONDS', 0.1):
            # Run a command that will take longer than timeout
            result = await SyntaxValidator._run_command(
                ["sleep", "10"]
            )
            assert result["returncode"] == -1
            assert result["stderr"] == "Timeout"

    @pytest.mark.asyncio
    async def test_run_command_success(self):
        """Test successful command execution."""
        result = await SyntaxValidator._run_command(
            ["echo", "hello"]
        )
        assert result["returncode"] == 0
        assert "hello" in result["stdout"]
        assert result["stderr"] == ""

    @pytest.mark.asyncio
    async def test_run_command_with_stderr(self):
        """Test command with stderr output."""
        # Use Python to write to stderr
        result = await SyntaxValidator._run_command(
            ["python3", "-c", "import sys; sys.stderr.write('error message')"]
        )
        assert result["returncode"] == 0
        assert "error message" in result["stderr"]

    @pytest.mark.asyncio
    async def test_run_command_nonzero_exit(self):
        """Test command with non-zero exit code."""
        result = await SyntaxValidator._run_command(
            ["python3", "-c", "exit(42)"]
        )
        assert result["returncode"] == 42

    @pytest.mark.asyncio
    async def test_run_command_captures_both_streams(self):
        """Test that both stdout and stderr are captured."""
        result = await SyntaxValidator._run_command(
            ["python3", "-c", "import sys; print('out'); sys.stderr.write('err')"]
        )
        assert "out" in result["stdout"]
        assert "err" in result["stderr"]


# =============================================================================
# Integration tests - Full validation flow
# =============================================================================
class TestValidationIntegration:
    """Integration tests for validation workflow."""

    @pytest.mark.asyncio
    async def test_json_with_comments_fails(self, tmp_path):
        """Test that JSON with comments fails validation."""
        json_file = tmp_path / "with_comments.json"
        json_file.write_text('{\n  // This is a comment\n  "key": "value"\n}')

        result = await SyntaxValidator.validate_file(
            str(json_file),
            str(tmp_path)
        )
        assert result["valid"] is False

    @pytest.mark.asyncio
    async def test_json_with_unicode(self, tmp_path):
        """Test JSON with unicode characters."""
        json_file = tmp_path / "unicode.json"
        json_file.write_text('{"message": "Hello World!"}')

        result = await SyntaxValidator.validate_file(
            str(json_file),
            str(tmp_path)
        )
        assert result["valid"] is True

    @pytest.mark.asyncio
    async def test_empty_json_file(self, tmp_path):
        """Test empty JSON file fails validation."""
        json_file = tmp_path / "empty.json"
        json_file.write_text('')

        result = await SyntaxValidator.validate_file(
            str(json_file),
            str(tmp_path)
        )
        assert result["valid"] is False

    @pytest.mark.asyncio
    async def test_json_array(self, tmp_path):
        """Test JSON array is valid."""
        json_file = tmp_path / "array.json"
        json_file.write_text('[1, 2, 3, "four"]')

        result = await SyntaxValidator.validate_file(
            str(json_file),
            str(tmp_path)
        )
        assert result["valid"] is True

    @pytest.mark.asyncio
    async def test_nested_json(self, tmp_path):
        """Test deeply nested JSON."""
        json_file = tmp_path / "nested.json"
        json_file.write_text('{"a": {"b": {"c": {"d": [1, 2, 3]}}}}')

        result = await SyntaxValidator.validate_file(
            str(json_file),
            str(tmp_path)
        )
        assert result["valid"] is True

    @pytest.mark.asyncio
    async def test_validation_exception_handling(self, tmp_path):
        """Test that exceptions during validation are caught."""
        json_file = tmp_path / "test.json"
        json_file.write_text('{"key": "value"}')

        # Mock json.loads to raise an unexpected exception
        with patch('chainguard.validators.json.loads', side_effect=RuntimeError("Unexpected error")):
            result = await SyntaxValidator.validate_file(
                str(json_file),
                str(tmp_path)
            )
            # Should handle gracefully and return valid (error is logged)
            assert result["valid"] is True
