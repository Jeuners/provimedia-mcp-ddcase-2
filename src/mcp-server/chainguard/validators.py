"""
CHAINGUARD MCP Server - Validators Module

Contains: SyntaxValidator with full async I/O

Copyright (c) 2026 Provimedia GmbH
Licensed under the Polyform Noncommercial License 1.0.0
See LICENSE file in the project root for full license information.
"""

import json
import asyncio
from pathlib import Path
from typing import Dict, Any, List

from .config import SYNTAX_CHECK_TIMEOUT_SECONDS, logger

# Async file I/O
try:
    import aiofiles
    HAS_AIOFILES = True
except ImportError:
    HAS_AIOFILES = False


# =============================================================================
# Syntax Validation (PHP, JS, JSON, Python, TypeScript)
# =============================================================================
class SyntaxValidator:
    """
    Validates file syntax before runtime - catches errors early.

    Supported languages:
        - PHP: Uses `php -l` (lint mode)
        - JavaScript: Uses `node --check`
        - JSON: Uses Python's json.load()
        - Python: Uses `python3 -m py_compile`
        - TypeScript/TSX: Uses `npx tsc --noEmit`
    """

    @staticmethod
    async def validate_file(file_path: str, project_path: str) -> Dict[str, Any]:
        """
        Validate a file based on its extension.
        Returns: {"valid": bool, "errors": [...], "checked": str}
        """
        full_path = Path(project_path) / file_path if not Path(file_path).is_absolute() else Path(file_path)

        if not full_path.exists():
            return {"valid": True, "errors": [], "checked": "file not found"}

        ext = full_path.suffix.lower()
        errors = []

        try:
            # === PHP Validation ===
            if ext == ".php" and ".blade.php" not in str(full_path):
                result = await SyntaxValidator._run_command(
                    ["php", "-l", str(full_path)]
                )
                if result["returncode"] != 0:
                    error_msg = SyntaxValidator._extract_php_error(result["stderr"] or result["stdout"])
                    errors.append({
                        "type": "PHP Syntax",
                        "message": error_msg,
                        "file": str(file_path)
                    })

            # === JavaScript/TypeScript Validation ===
            elif ext in [".js", ".mjs", ".cjs"]:
                result = await SyntaxValidator._run_command(
                    ["node", "--check", str(full_path)]
                )
                if result["returncode"] != 0:
                    error_msg = SyntaxValidator._extract_js_error(result["stderr"])
                    errors.append({
                        "type": "JS Syntax",
                        "message": error_msg,
                        "file": str(file_path)
                    })

            # === JSON Validation (async) ===
            elif ext == ".json":
                try:
                    if HAS_AIOFILES:
                        async with aiofiles.open(full_path, 'r', encoding='utf-8') as f:
                            content = await f.read()
                            json.loads(content)
                    else:
                        with open(full_path, 'r', encoding='utf-8') as f:
                            json.load(f)
                except json.JSONDecodeError as e:
                    errors.append({
                        "type": "JSON",
                        "message": f"Line {e.lineno}: {e.msg}",
                        "file": str(file_path)
                    })

            # === Python Validation ===
            elif ext == ".py":
                result = await SyntaxValidator._run_command(
                    ["python3", "-m", "py_compile", str(full_path)]
                )
                if result["returncode"] != 0:
                    error_msg = SyntaxValidator._extract_python_error(result["stderr"])
                    errors.append({
                        "type": "Python Syntax",
                        "message": error_msg,
                        "file": str(file_path)
                    })

            # === TypeScript/TSX Validation ===
            elif ext in [".ts", ".tsx"]:
                result = await SyntaxValidator._run_command(
                    ["npx", "--yes", "tsc", "--noEmit", "--skipLibCheck",
                     "--allowJs", "--target", "ES2020", str(full_path)]
                )
                if result["returncode"] != 0 and "error TS" in result["stdout"]:
                    error_msg = SyntaxValidator._extract_ts_error(result["stdout"])
                    errors.append({
                        "type": "TS Syntax",
                        "message": error_msg,
                        "file": str(file_path)
                    })

        except Exception as e:
            logger.error(f"Validation error for {file_path}: {e}")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "checked": ext or "unknown"
        }

    @staticmethod
    async def _run_command(cmd: List[str]) -> Dict[str, Any]:
        """Run a command asynchronously."""
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=SYNTAX_CHECK_TIMEOUT_SECONDS
            )
            return {
                "returncode": proc.returncode,
                "stdout": stdout.decode() if stdout else "",
                "stderr": stderr.decode() if stderr else ""
            }
        except asyncio.TimeoutError:
            return {"returncode": -1, "stdout": "", "stderr": "Timeout"}
        except FileNotFoundError:
            return {"returncode": -1, "stdout": "", "stderr": "Command not found"}

    @staticmethod
    def _extract_php_error(output: str) -> str:
        """Extract meaningful error from PHP -l output."""
        for line in output.split('\n'):
            if 'Parse error' in line or 'Fatal error' in line or 'syntax error' in line:
                if ' in ' in line:
                    parts = line.split(' in ')
                    return parts[0].strip()
                return line.strip()[:100]
        return output.strip()[:100]

    @staticmethod
    def _extract_js_error(output: str) -> str:
        """Extract meaningful error from Node --check output."""
        for line in output.split('\n'):
            if 'SyntaxError' in line or 'Error' in line:
                return line.strip()[:100]
        return output.strip()[:100]

    @staticmethod
    def _extract_python_error(output: str) -> str:
        """Extract meaningful error from py_compile output."""
        lines = output.strip().split('\n')
        for i, line in enumerate(lines):
            if 'SyntaxError' in line or 'IndentationError' in line or 'TabError' in line:
                return line.strip()[:100]
            if 'line' in line.lower() and 'file' in line.lower():
                return line.strip()[:100]
        return output.strip()[:100] if output else "Syntax error"

    @staticmethod
    def _extract_ts_error(output: str) -> str:
        """Extract first TypeScript error from tsc output."""
        for line in output.split('\n'):
            if 'error TS' in line:
                if '): error' in line:
                    parts = line.split('): error')
                    if len(parts) > 1:
                        return f"error{parts[1][:80]}"
                return line.strip()[:100]
        return output.strip()[:100] if output else "TypeScript error"
