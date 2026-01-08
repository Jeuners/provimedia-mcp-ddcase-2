"""
CHAINGUARD MCP Server - Test Runner Module

Technology-agnostic test runner for PHPUnit, Jest, pytest and others.
Executes user-defined test commands and parses the results.

Copyright (c) 2026 Provimedia GmbH
Licensed under the Polyform Noncommercial License 1.0.0
See LICENSE file in the project root for full license information.
"""

import re
import asyncio
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional

from .config import (
    TEST_RUN_TIMEOUT_SECONDS,
    TEST_OUTPUT_MAX_LENGTH,
    TEST_FAILED_LINES_MAX,
    logger
)


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class TestConfig:
    """Configuration for test execution."""
    command: str = ""              # z.B. "./vendor/bin/phpunit"
    args: str = ""                 # z.B. "--colors=never --testdox"
    timeout: int = TEST_RUN_TIMEOUT_SECONDS
    working_dir: str = ""          # Optional: Überschreibt project_path

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TestConfig":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def get_full_command(self) -> List[str]:
        """Returns command as list for subprocess."""
        parts = self.command.split()
        if self.args:
            parts.extend(self.args.split())
        return parts


@dataclass
class TestResult:
    """Result of a test run."""
    success: bool = False
    passed: int = 0
    failed: int = 0
    total: int = 0
    duration: float = 0.0
    framework: str = "unknown"
    output: str = ""
    error_lines: List[str] = field(default_factory=list)
    timestamp: str = ""
    exit_code: int = -1

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TestResult":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


# =============================================================================
# Output Parser
# =============================================================================

class OutputParser:
    """
    Parst Test-Output von verschiedenen Frameworks.
    Erkennt automatisch das Framework anhand des Outputs.
    """

    # Framework-spezifische Patterns
    PATTERNS = {
        "phpunit": {
            "success": re.compile(r"OK \((\d+) tests?, (\d+) assertions?\)"),
            "failure": re.compile(r"FAILURES!\s*Tests: (\d+),.*?Failures: (\d+)", re.DOTALL),
            "error": re.compile(r"ERRORS!\s*Tests: (\d+),.*?Errors: (\d+)", re.DOTALL),
            "tests_line": re.compile(r"Tests: (\d+),.*?(?:Failures: (\d+))?", re.DOTALL),
            "indicators": ["PHPUnit", "phpunit", ".phpunit"],
        },
        "jest": {
            "success": re.compile(r"Tests:\s+(\d+) passed,\s+(\d+) total"),
            "failure": re.compile(r"Tests:\s+(\d+) failed,\s+(\d+) passed,\s+(\d+) total"),
            "indicators": ["PASS ", "FAIL ", "jest", "Test Suites:"],  # Space to avoid matching PASSED/FAILED
        },
        "pytest": {
            "success": re.compile(r"(\d+) passed"),
            "failure": re.compile(r"(\d+) failed"),
            "total": re.compile(r"(\d+) passed|(\d+) failed|(\d+) error"),
            "indicators": ["pytest", "===", "PASSED", "FAILED"],
        },
        "mocha": {
            "success": re.compile(r"(\d+) passing"),
            "failure": re.compile(r"(\d+) failing"),
            "indicators": ["passing", "failing", "mocha"],
        },
        "vitest": {
            "success": re.compile(r"(\d+) passed"),
            "failure": re.compile(r"(\d+) failed"),
            "indicators": ["VITEST", "vitest"],
        },
    }

    # Patterns für Fehlerzeilen
    ERROR_PATTERNS = [
        re.compile(r"(?:FAILED|FAILURE|ERROR|Error|Failed).*", re.IGNORECASE),
        re.compile(r"(?:Expected|Actual|AssertionError).*", re.IGNORECASE),
        re.compile(r"at .*:\d+:\d+"),  # Stack traces
        re.compile(r"✗.*|✕.*"),  # Unicode failure markers
    ]

    @classmethod
    def detect_framework(cls, output: str) -> str:
        """Erkennt das Test-Framework anhand des Outputs."""
        for framework, info in cls.PATTERNS.items():
            for indicator in info.get("indicators", []):
                if indicator in output:
                    return framework
        return "generic"

    @classmethod
    def parse(cls, output: str, exit_code: int) -> TestResult:
        """
        Parst den Test-Output und gibt ein TestResult zurück.
        """
        result = TestResult(
            timestamp=datetime.now().isoformat(),
            exit_code=exit_code,
            output=output[:TEST_OUTPUT_MAX_LENGTH]
        )

        # Framework erkennen
        framework = cls.detect_framework(output)
        result.framework = framework

        # Framework-spezifisches Parsing
        if framework in cls.PATTERNS:
            result = cls._parse_framework(output, result, framework)

        # Fallback: Exit-Code basiert
        if result.total == 0:
            result.success = exit_code == 0
            result.passed = 1 if exit_code == 0 else 0
            result.failed = 0 if exit_code == 0 else 1
            result.total = 1

        # Fehlerzeilen extrahieren
        if not result.success or exit_code != 0:
            result.error_lines = cls._extract_error_lines(output)

        return result

    @classmethod
    def _parse_framework(cls, output: str, result: TestResult, framework: str) -> TestResult:
        """Parst Output für ein spezifisches Framework."""
        patterns = cls.PATTERNS[framework]

        # PHPUnit
        if framework == "phpunit":
            success_match = patterns["success"].search(output)
            if success_match:
                result.success = True
                result.passed = int(success_match.group(1))
                result.total = result.passed
                result.failed = 0
                return result

            failure_match = patterns["failure"].search(output)
            if failure_match:
                result.success = False
                result.total = int(failure_match.group(1))
                result.failed = int(failure_match.group(2))
                result.passed = result.total - result.failed
                return result

        # Jest
        elif framework == "jest":
            success_match = patterns["success"].search(output)
            if success_match:
                result.success = True
                result.passed = int(success_match.group(1))
                result.total = int(success_match.group(2))
                result.failed = result.total - result.passed
                return result

            failure_match = patterns["failure"].search(output)
            if failure_match:
                result.success = False
                result.failed = int(failure_match.group(1))
                result.passed = int(failure_match.group(2))
                result.total = int(failure_match.group(3))
                return result

        # pytest
        elif framework == "pytest":
            passed_match = patterns["success"].search(output)
            failed_match = patterns["failure"].search(output)

            result.passed = int(passed_match.group(1)) if passed_match else 0
            result.failed = int(failed_match.group(1)) if failed_match else 0
            result.total = result.passed + result.failed
            result.success = result.failed == 0 and result.passed > 0

        # mocha/vitest
        elif framework in ["mocha", "vitest"]:
            passed_match = patterns["success"].search(output)
            failed_match = patterns["failure"].search(output)

            result.passed = int(passed_match.group(1)) if passed_match else 0
            result.failed = int(failed_match.group(1)) if failed_match else 0
            result.total = result.passed + result.failed
            result.success = result.failed == 0 and result.passed > 0

        return result

    @classmethod
    def _extract_error_lines(cls, output: str) -> List[str]:
        """Extrahiert relevante Fehlerzeilen aus dem Output."""
        error_lines = []
        lines = output.split('\n')

        for line in lines:
            line = line.strip()
            if not line:
                continue

            for pattern in cls.ERROR_PATTERNS:
                if pattern.search(line):
                    # Zeile bereinigen und kürzen
                    clean_line = line[:100]
                    if clean_line not in error_lines:
                        error_lines.append(clean_line)
                    break

            if len(error_lines) >= TEST_FAILED_LINES_MAX:
                break

        return error_lines


# =============================================================================
# Test Runner
# =============================================================================

class TestRunner:
    """
    Führt Tests asynchron aus.

    Beispiel:
        config = TestConfig(command="./vendor/bin/phpunit", args="tests/")
        result = await TestRunner.run_async(config, "/path/to/project")
    """

    @staticmethod
    async def run_async(
        config: TestConfig,
        project_path: str
    ) -> TestResult:
        """
        Führt Tests mit der gegebenen Konfiguration aus.

        Args:
            config: Test-Konfiguration mit Command und Args
            project_path: Projekt-Verzeichnis

        Returns:
            TestResult mit geparsten Ergebnissen
        """
        result = TestResult(timestamp=datetime.now().isoformat())

        if not config.command:
            result.error_lines = ["Kein Test-Command konfiguriert"]
            return result

        # Working directory bestimmen
        cwd = config.working_dir if config.working_dir else project_path

        # Command aufbauen
        cmd = config.get_full_command()

        logger.info(f"Running tests: {' '.join(cmd)} in {cwd}")

        start_time = datetime.now()

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=config.timeout
                )

                # Output zusammenführen
                output = stdout.decode(errors='replace')
                if stderr:
                    output += "\n" + stderr.decode(errors='replace')

                result = OutputParser.parse(output, proc.returncode or 0)
                result.duration = (datetime.now() - start_time).total_seconds()

            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                result.success = False
                result.error_lines = [f"Test-Timeout nach {config.timeout}s"]
                result.exit_code = -1
                logger.warning(f"Test timeout after {config.timeout}s")

        except FileNotFoundError:
            result.success = False
            result.error_lines = [f"Command nicht gefunden: {cmd[0]}"]
            result.exit_code = -1
            logger.error(f"Command not found: {cmd[0]}")

        except Exception as e:
            result.success = False
            result.error_lines = [f"Fehler: {str(e)[:80]}"]
            result.exit_code = -1
            logger.error(f"Test execution error: {e}")

        result.duration = (datetime.now() - start_time).total_seconds()
        return result

    @staticmethod
    def run(config: TestConfig, project_path: str) -> TestResult:
        """Sync wrapper für backwards compatibility."""
        try:
            # Check if there's already a running loop
            asyncio.get_running_loop()
            # If we get here, there's a running loop - we can't use run_until_complete
            # Run in a new thread with its own event loop
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(
                    asyncio.run,
                    TestRunner.run_async(config, project_path)
                )
                return future.result(timeout=config.timeout + 5)
        except RuntimeError:
            # No running loop - safe to use asyncio.run
            return asyncio.run(
                TestRunner.run_async(config, project_path)
            )

    @staticmethod
    def format_result(result: TestResult) -> str:
        """Formatiert das Ergebnis für die Ausgabe."""
        lines = []

        # Status-Zeile
        if result.success:
            lines.append(f"✓ {result.framework}: {result.passed}/{result.total} tests passed")
        else:
            lines.append(f"✗ {result.framework}: {result.passed}/{result.total} tests ({result.failed} failed)")

        # Duration
        lines.append(f"  Duration: {result.duration:.2f}s")

        # Fehler anzeigen
        if result.error_lines:
            lines.append("")
            lines.append("  Errors:")
            for err in result.error_lines[:5]:
                lines.append(f"  • {err}")
            if len(result.error_lines) > 5:
                lines.append(f"  ... +{len(result.error_lines) - 5} more")

        return "\n".join(lines)

    @staticmethod
    def format_status(result: TestResult, last_run: str = "") -> str:
        """Formatiert einen kompakten Status."""
        status = "✓" if result.success else "✗"
        time_str = ""

        if last_run:
            try:
                run_time = datetime.fromisoformat(last_run)
                delta = datetime.now() - run_time
                if delta.seconds < 60:
                    time_str = f" ({delta.seconds}s ago)"
                elif delta.seconds < 3600:
                    time_str = f" ({delta.seconds // 60}m ago)"
                else:
                    time_str = f" ({delta.seconds // 3600}h ago)"
            except ValueError:
                pass

        return f"{status} {result.passed}/{result.total}{time_str}"
