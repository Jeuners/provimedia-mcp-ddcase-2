"""
TOON (Token-Oriented Object Notation) Encoder for Chainguard MCP Server.

TOON is a compact, human-readable data format that reduces token consumption
by 30-60% compared to JSON, specifically designed for LLM input.

Key features:
- YAML-style indentation for nested objects
- CSV-style tabular layout for uniform arrays
- Eliminates repetitive keys and excessive punctuation

Reference: https://github.com/toon-format/toon

Usage:
    from chainguard.toon import encode_toon, toon_array, toon_object

    # Encode array of objects (best savings)
    data = [
        {"name": "auth.php", "status": "changed", "lines": 45},
        {"name": "user.php", "status": "changed", "lines": 23},
    ]
    result = toon_array("files", data)
    # Output:
    # files[2]{name,status,lines}:
    #   auth.php,changed,45
    #   user.php,changed,23
"""

from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass


@dataclass
class TOONConfig:
    """Configuration for TOON encoding."""
    indent: str = "  "  # Two spaces
    delimiter: str = ","  # Field delimiter
    use_tabs: bool = False  # Use tabs for max efficiency
    max_inline_length: int = 80  # Max length before wrapping
    quote_char: str = '"'  # Quote character for special values


# Default configuration
DEFAULT_CONFIG = TOONConfig()


def _needs_quoting(value: str, delimiter: str = ",") -> bool:
    """Check if a string value needs quoting."""
    if not value:
        return False
    # Quote if contains delimiter, newlines, or leading/trailing whitespace
    return (
        delimiter in value or
        "\n" in value or
        "\r" in value or
        value != value.strip() or
        value.startswith('"') or
        value.startswith("'")
    )


def _escape_value(value: Any, config: TOONConfig = DEFAULT_CONFIG) -> str:
    """Convert a value to TOON-safe string representation."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        if _needs_quoting(value, config.delimiter):
            # Escape quotes and wrap
            escaped = value.replace(config.quote_char, config.quote_char * 2)
            return f'{config.quote_char}{escaped}{config.quote_char}'
        return value
    if isinstance(value, (list, dict)):
        # Nested structures - use compact inline format
        return _inline_value(value)
    return str(value)


def _inline_value(value: Any) -> str:
    """Convert nested value to compact inline format."""
    if isinstance(value, list):
        items = [_inline_value(v) for v in value]
        return f"[{','.join(items)}]"
    if isinstance(value, dict):
        pairs = [f"{k}:{_inline_value(v)}" for k, v in value.items()]
        return f"{{{','.join(pairs)}}}"
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        if "," in value or ":" in value or "{" in value or "[" in value:
            return f'"{value}"'
        return value
    return str(value)


def toon_array(
    name: str,
    items: List[Dict[str, Any]],
    fields: Optional[List[str]] = None,
    config: TOONConfig = DEFAULT_CONFIG
) -> str:
    """
    Encode a list of uniform objects to TOON format.

    This is where TOON shines - uniform arrays get ~60% token reduction.

    Args:
        name: Array name
        items: List of dictionaries with same keys
        fields: Optional field order (auto-detected if not provided)
        config: TOON configuration

    Returns:
        TOON-formatted string

    Example:
        >>> data = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
        >>> print(toon_array("users", data))
        users[2]{id,name}:
          1,Alice
          2,Bob
    """
    if not items:
        return f"{name}[0]{{}}:"

    # Auto-detect fields from first item if not provided
    if fields is None:
        fields = list(items[0].keys())

    delimiter = "\t" if config.use_tabs else config.delimiter
    indent = config.indent

    # Header: arrayName[count]{field1,field2,...}:
    header = f"{name}[{len(items)}]{{{delimiter.join(fields)}}}:"

    # Rows: indented comma-separated values
    rows = []
    for item in items:
        values = [_escape_value(item.get(f, ""), config) for f in fields]
        rows.append(f"{indent}{delimiter.join(values)}")

    return header + "\n" + "\n".join(rows)


def toon_object(
    name: str,
    obj: Dict[str, Any],
    config: TOONConfig = DEFAULT_CONFIG
) -> str:
    """
    Encode a single object to TOON format.

    For single objects, savings are moderate (~20-30%).

    Args:
        name: Object name (can be empty for root object)
        obj: Dictionary to encode
        config: TOON configuration

    Returns:
        TOON-formatted string

    Example:
        >>> data = {"task": "Build feature", "status": "active"}
        >>> print(toon_object("context", data))
        context:
          task: Build feature
          status: active
    """
    indent = config.indent
    lines = []

    if name:
        lines.append(f"{name}:")
        prefix = indent
    else:
        prefix = ""

    for key, value in obj.items():
        if isinstance(value, dict):
            # Nested object
            nested = toon_object(key, value, config)
            # Indent nested content
            nested_lines = nested.split("\n")
            lines.append(f"{prefix}{nested_lines[0]}")
            for nl in nested_lines[1:]:
                lines.append(f"{prefix}{nl}")
        elif isinstance(value, list) and value and isinstance(value[0], dict):
            # Array of objects - use tabular format
            arr = toon_array(key, value, config=config)
            arr_lines = arr.split("\n")
            lines.append(f"{prefix}{arr_lines[0]}")
            for al in arr_lines[1:]:
                lines.append(f"{prefix}{al}")
        elif isinstance(value, list):
            # Simple array
            items = [_escape_value(v, config) for v in value]
            lines.append(f"{prefix}{key}: [{config.delimiter.join(items)}]")
        else:
            # Simple value
            lines.append(f"{prefix}{key}: {_escape_value(value, config)}")

    return "\n".join(lines)


def encode_toon(
    data: Union[Dict[str, Any], List[Dict[str, Any]]],
    name: str = "",
    config: TOONConfig = DEFAULT_CONFIG
) -> str:
    """
    Smart TOON encoder - automatically chooses best encoding.

    Args:
        data: Dictionary or list of dictionaries
        name: Optional name for the data
        config: TOON configuration

    Returns:
        TOON-formatted string

    Example:
        >>> # Array of objects
        >>> encode_toon([{"a": 1}, {"a": 2}], "items")
        'items[2]{a}:\\n  1\\n  2'

        >>> # Single object
        >>> encode_toon({"x": 1, "y": 2}, "point")
        'point:\\n  x: 1\\n  y: 2'
    """
    if isinstance(data, list):
        if data and isinstance(data[0], dict):
            return toon_array(name or "items", data, config=config)
        else:
            # Simple list
            items = [_escape_value(v, config) for v in data]
            if name:
                return f"{name}: [{config.delimiter.join(items)}]"
            return f"[{config.delimiter.join(items)}]"
    elif isinstance(data, dict):
        return toon_object(name, data, config=config)
    else:
        return _escape_value(data, config)


# =============================================================================
# Convenience functions for Chainguard-specific use cases
# =============================================================================

def toon_files(files: List[Dict[str, Any]]) -> str:
    """Encode file list in TOON format."""
    if not files:
        return "files[0]{}:"
    return toon_array("files", files, fields=["name", "status", "action"])


def toon_tables(tables: List[Dict[str, Any]]) -> str:
    """Encode database tables in TOON format."""
    if not tables:
        return "tables[0]{}:"
    return toon_array("tables", tables, fields=["name", "columns", "rows"])


def toon_history(entries: List[Dict[str, Any]]) -> str:
    """Encode history entries in TOON format."""
    if not entries:
        return "history[0]{}:"
    return toon_array("history", entries, fields=["time", "file", "action", "status"])


def toon_projects(projects: List[Dict[str, Any]]) -> str:
    """Encode project list in TOON format."""
    if not projects:
        return "projects[0]{}:"
    return toon_array("projects", projects, fields=["id", "path", "phase", "files"])


def toon_criteria(criteria: List[Dict[str, Any]]) -> str:
    """Encode acceptance criteria in TOON format."""
    if not criteria:
        return "criteria[0]{}:"
    return toon_array("criteria", criteria, fields=["criterion", "fulfilled"])


def toon_alerts(alerts: List[str]) -> str:
    """Encode alerts in compact TOON format."""
    if not alerts:
        return "alerts: []"
    return f"alerts[{len(alerts)}]: " + ", ".join(alerts)


# =============================================================================
# Token counting utilities
# =============================================================================

def estimate_tokens(text: str) -> int:
    """
    Rough token estimate (4 chars ≈ 1 token for English text).

    This is a simplified estimation. For exact counts, use tiktoken.
    """
    return len(text) // 4 + 1


def compare_formats(data: Any, name: str = "") -> Dict[str, Any]:
    """
    Compare JSON vs TOON token usage for given data.

    Returns dict with token counts and savings percentage.
    """
    import json

    json_str = json.dumps(data, separators=(",", ":"))
    toon_str = encode_toon(data, name)

    json_tokens = estimate_tokens(json_str)
    toon_tokens = estimate_tokens(toon_str)
    savings = ((json_tokens - toon_tokens) / json_tokens * 100) if json_tokens > 0 else 0

    return {
        "json_tokens": json_tokens,
        "toon_tokens": toon_tokens,
        "savings_percent": round(savings, 1),
        "json_chars": len(json_str),
        "toon_chars": len(toon_str)
    }
