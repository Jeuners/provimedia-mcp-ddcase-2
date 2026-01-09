"""
Unit tests for TOON (Token-Oriented Object Notation) encoder.

Tests cover:
- Basic encoding functions
- Array of objects (primary use case)
- Single objects
- Edge cases (empty, special characters, nested)
- Convenience functions for Chainguard
- Token comparison utilities
"""

import pytest
from chainguard.toon import (
    TOONConfig,
    DEFAULT_CONFIG,
    encode_toon,
    toon_array,
    toon_object,
    toon_files,
    toon_tables,
    toon_history,
    toon_projects,
    toon_criteria,
    toon_alerts,
    estimate_tokens,
    compare_formats,
    _needs_quoting,
    _escape_value,
    _inline_value,
)


class TestTOONConfig:
    """Tests for TOONConfig dataclass."""

    def test_default_config(self):
        config = TOONConfig()
        assert config.indent == "  "
        assert config.delimiter == ","
        assert config.use_tabs is False
        assert config.max_inline_length == 80
        assert config.quote_char == '"'

    def test_custom_config(self):
        config = TOONConfig(indent="    ", delimiter="\t", use_tabs=True)
        assert config.indent == "    "
        assert config.delimiter == "\t"
        assert config.use_tabs is True

    def test_default_config_singleton(self):
        assert DEFAULT_CONFIG.indent == "  "
        assert DEFAULT_CONFIG.delimiter == ","


class TestHelperFunctions:
    """Tests for internal helper functions."""

    def test_needs_quoting_empty(self):
        assert _needs_quoting("") is False

    def test_needs_quoting_simple(self):
        assert _needs_quoting("hello") is False
        assert _needs_quoting("Hello World") is False

    def test_needs_quoting_with_comma(self):
        assert _needs_quoting("hello, world") is True

    def test_needs_quoting_with_newline(self):
        assert _needs_quoting("hello\nworld") is True

    def test_needs_quoting_with_whitespace(self):
        assert _needs_quoting(" hello") is True
        assert _needs_quoting("hello ") is True

    def test_needs_quoting_custom_delimiter(self):
        assert _needs_quoting("hello;world", ";") is True
        assert _needs_quoting("hello,world", ";") is False

    def test_escape_value_none(self):
        assert _escape_value(None) == ""

    def test_escape_value_bool(self):
        assert _escape_value(True) == "true"
        assert _escape_value(False) == "false"

    def test_escape_value_numbers(self):
        assert _escape_value(42) == "42"
        assert _escape_value(3.14) == "3.14"
        assert _escape_value(-5) == "-5"

    def test_escape_value_string(self):
        assert _escape_value("hello") == "hello"
        assert _escape_value("hello, world") == '"hello, world"'

    def test_escape_value_with_quotes(self):
        # Quotes alone don't trigger quoting, only commas/newlines do
        result = _escape_value('say "hello"')
        assert result == 'say "hello"'  # No quoting needed
        # But with comma, it gets quoted
        result2 = _escape_value('say, "hello"')
        assert result2 == '"say, ""hello"""'

    def test_inline_value_list(self):
        assert _inline_value([1, 2, 3]) == "[1,2,3]"

    def test_inline_value_dict(self):
        assert _inline_value({"a": 1}) == "{a:1}"

    def test_inline_value_nested(self):
        result = _inline_value({"items": [1, 2]})
        assert result == "{items:[1,2]}"


class TestToonArray:
    """Tests for toon_array function - primary use case."""

    def test_empty_array(self):
        result = toon_array("files", [])
        assert result == "files[0]{}:"

    def test_simple_array(self):
        data = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
        result = toon_array("users", data)
        expected = "users[2]{id,name}:\n  1,Alice\n  2,Bob"
        assert result == expected

    def test_array_with_custom_fields(self):
        data = [{"name": "Alice", "id": 1}, {"name": "Bob", "id": 2}]
        result = toon_array("users", data, fields=["id", "name"])
        assert "users[2]{id,name}:" in result
        assert "1,Alice" in result

    def test_array_preserves_order(self):
        data = [
            {"a": 1, "b": 2, "c": 3},
            {"a": 4, "b": 5, "c": 6},
        ]
        result = toon_array("items", data, fields=["a", "b", "c"])
        lines = result.split("\n")
        assert lines[0] == "items[2]{a,b,c}:"
        assert lines[1] == "  1,2,3"
        assert lines[2] == "  4,5,6"

    def test_array_with_missing_fields(self):
        data = [{"a": 1, "b": 2}, {"a": 3}]  # Second item missing 'b'
        result = toon_array("items", data, fields=["a", "b"])
        assert "3," in result  # Empty value for missing field

    def test_array_with_special_chars(self):
        data = [{"name": "Hello, World", "id": 1}]
        result = toon_array("items", data)
        assert '"Hello, World"' in result

    def test_array_with_booleans(self):
        data = [{"active": True, "deleted": False}]
        result = toon_array("flags", data)
        assert "true,false" in result

    def test_array_with_tabs_config(self):
        config = TOONConfig(use_tabs=True)
        data = [{"a": 1, "b": 2}]
        result = toon_array("items", data, config=config)
        assert "\t" in result


class TestToonObject:
    """Tests for toon_object function."""

    def test_empty_object(self):
        result = toon_object("context", {})
        assert result == "context:"

    def test_simple_object(self):
        data = {"task": "Build feature", "status": "active"}
        result = toon_object("context", data)
        expected = "context:\n  task: Build feature\n  status: active"
        assert result == expected

    def test_object_without_name(self):
        data = {"x": 1, "y": 2}
        result = toon_object("", data)
        assert "x: 1" in result
        assert "y: 2" in result
        assert not result.startswith(":")

    def test_nested_object(self):
        data = {"outer": {"inner": "value"}}
        result = toon_object("root", data)
        assert "outer:" in result
        assert "inner: value" in result

    def test_object_with_array(self):
        data = {"tags": ["a", "b", "c"]}
        result = toon_object("item", data)
        assert "tags: [a,b,c]" in result

    def test_object_with_array_of_objects(self):
        data = {
            "users": [
                {"id": 1, "name": "Alice"},
                {"id": 2, "name": "Bob"}
            ]
        }
        result = toon_object("data", data)
        assert "users[2]{id,name}:" in result


class TestEncodeToon:
    """Tests for smart encode_toon function."""

    def test_encode_list_of_dicts(self):
        data = [{"a": 1}, {"a": 2}]
        result = encode_toon(data, "items")
        assert "items[2]{a}:" in result

    def test_encode_dict(self):
        data = {"x": 1, "y": 2}
        result = encode_toon(data, "point")
        assert "point:" in result
        assert "x: 1" in result

    def test_encode_simple_list(self):
        data = [1, 2, 3]
        result = encode_toon(data, "numbers")
        assert result == "numbers: [1,2,3]"

    def test_encode_simple_list_no_name(self):
        data = ["a", "b"]
        result = encode_toon(data)
        assert result == "[a,b]"

    def test_encode_primitive(self):
        assert encode_toon(42) == "42"
        assert encode_toon("hello") == "hello"
        assert encode_toon(True) == "true"


class TestConvenienceFunctions:
    """Tests for Chainguard-specific convenience functions."""

    def test_toon_files_empty(self):
        assert toon_files([]) == "files[0]{}:"

    def test_toon_files(self):
        files = [
            {"name": "auth.php", "status": "changed", "action": "edit"},
            {"name": "user.php", "status": "new", "action": "create"},
        ]
        result = toon_files(files)
        assert "files[2]{name,status,action}:" in result
        assert "auth.php,changed,edit" in result

    def test_toon_tables_empty(self):
        assert toon_tables([]) == "tables[0]{}:"

    def test_toon_tables(self):
        tables = [
            {"name": "users", "columns": 5, "rows": 100},
            {"name": "posts", "columns": 8, "rows": 500},
        ]
        result = toon_tables(tables)
        assert "tables[2]{name,columns,rows}:" in result
        assert "users,5,100" in result

    def test_toon_history_empty(self):
        assert toon_history([]) == "history[0]{}:"

    def test_toon_history(self):
        entries = [
            {"time": "10:00", "file": "auth.php", "action": "edit", "status": "ok"},
        ]
        result = toon_history(entries)
        assert "history[1]{time,file,action,status}:" in result

    def test_toon_projects_empty(self):
        assert toon_projects([]) == "projects[0]{}:"

    def test_toon_projects(self):
        projects = [
            {"id": "abc123", "path": "/app", "phase": "impl", "files": 5},
        ]
        result = toon_projects(projects)
        assert "projects[1]{id,path,phase,files}:" in result

    def test_toon_criteria_empty(self):
        assert toon_criteria([]) == "criteria[0]{}:"

    def test_toon_criteria(self):
        criteria = [
            {"criterion": "Tests pass", "fulfilled": True},
            {"criterion": "Docs updated", "fulfilled": False},
        ]
        result = toon_criteria(criteria)
        assert "criteria[2]{criterion,fulfilled}:" in result
        assert "Tests pass,true" in result
        assert "Docs updated,false" in result

    def test_toon_alerts_empty(self):
        assert toon_alerts([]) == "alerts: []"

    def test_toon_alerts(self):
        alerts = ["Error 1", "Warning 2"]
        result = toon_alerts(alerts)
        assert result == "alerts[2]: Error 1, Warning 2"


class TestTokenUtilities:
    """Tests for token counting and comparison."""

    def test_estimate_tokens_empty(self):
        assert estimate_tokens("") == 1

    def test_estimate_tokens_simple(self):
        # ~4 chars per token
        assert estimate_tokens("hello world") == 3  # 11 chars / 4 + 1

    def test_estimate_tokens_longer(self):
        text = "a" * 100
        assert estimate_tokens(text) == 26  # 100 / 4 + 1

    def test_compare_formats_simple(self):
        data = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
        result = compare_formats(data, "users")

        assert "json_tokens" in result
        assert "toon_tokens" in result
        assert "savings_percent" in result
        assert result["toon_tokens"] < result["json_tokens"]
        assert result["savings_percent"] > 0

    def test_compare_formats_shows_savings(self):
        # Larger dataset should show significant savings
        data = [{"id": i, "name": f"User{i}", "email": f"user{i}@example.com"}
                for i in range(10)]
        result = compare_formats(data, "users")

        # TOON should save at least 30% on uniform arrays
        assert result["savings_percent"] >= 30


class TestEdgeCases:
    """Tests for edge cases and special scenarios."""

    def test_unicode_values(self):
        data = [{"name": "Müller", "city": "東京"}]
        result = toon_array("users", data)
        assert "Müller" in result
        assert "東京" in result

    def test_empty_string_values(self):
        data = [{"name": "", "id": 1}]
        result = toon_array("items", data)
        assert ",1" in result  # Empty value before comma

    def test_numeric_string_values(self):
        data = [{"code": "123", "name": "test"}]
        result = toon_array("items", data)
        assert "123,test" in result

    def test_very_long_values(self):
        long_value = "x" * 200
        data = [{"desc": long_value}]
        result = toon_array("items", data)
        assert long_value in result

    def test_special_characters_in_values(self):
        data = [{"formula": "a + b = c", "regex": ".*"}]
        result = toon_array("items", data)
        assert "a + b = c" in result
        assert ".*" in result

    def test_mixed_types_in_array(self):
        data = [
            {"val": 1},
            {"val": "two"},
            {"val": True},
            {"val": None},
        ]
        result = toon_array("mixed", data)
        assert "1" in result
        assert "two" in result
        assert "true" in result

    def test_deeply_nested_inline(self):
        data = {"config": {"db": {"host": "localhost", "port": 3306}}}
        result = toon_object("app", data)
        assert "config:" in result
        assert "db:" in result
        assert "host: localhost" in result


class TestRealWorldScenarios:
    """Tests simulating real Chainguard use cases."""

    def test_db_schema_output(self):
        """Simulate chainguard_db_schema output."""
        tables = [
            {"name": "users", "columns": 5, "rows": 1000},
            {"name": "posts", "columns": 8, "rows": 5000},
            {"name": "comments", "columns": 4, "rows": 15000},
        ]
        result = toon_tables(tables)
        comparison = compare_formats(tables, "tables")

        assert "tables[3]" in result
        assert comparison["savings_percent"] >= 35  # ~39% typical

    def test_history_output(self):
        """Simulate chainguard_history output."""
        history = [
            {"time": "10:00:01", "file": "Controller.php", "action": "edit", "status": "ok"},
            {"time": "10:00:15", "file": "Model.php", "action": "edit", "status": "ok"},
            {"time": "10:00:30", "file": "View.php", "action": "create", "status": "ok"},
            {"time": "10:00:45", "file": "Routes.php", "action": "edit", "status": "error"},
        ]
        result = toon_history(history)
        comparison = compare_formats(history, "history")

        assert "history[4]" in result
        assert comparison["savings_percent"] > 40

    def test_context_output(self):
        """Simulate chainguard_context output."""
        context = {
            "project": "myapp",
            "phase": "implementation",
            "scope": {
                "description": "Build user authentication",
                "modules": ["auth", "users"],
            },
            "files": [
                {"name": "auth.php", "status": "changed", "action": "edit"},
                {"name": "login.php", "status": "new", "action": "create"},
            ],
            "criteria": [
                {"criterion": "Login works", "fulfilled": True},
                {"criterion": "Logout works", "fulfilled": False},
            ]
        }
        result = encode_toon(context, "context")

        assert "project: myapp" in result
        assert "phase: implementation" in result
        # Arrays should be in tabular format
        assert "files[2]" in result
        assert "criteria[2]" in result
