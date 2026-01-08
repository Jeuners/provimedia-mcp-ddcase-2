"""
CHAINGUARD MCP Server - Checklist Module

Contains: ChecklistRunner for secure async command execution

Copyright (c) 2026 Provimedia GmbH
Licensed under the Polyform Noncommercial License 1.0.0
See LICENSE file in the project root for full license information.
"""

import shlex
import asyncio
from typing import Dict, Any, List

from .config import logger


class ChecklistRunner:
    """
    Runs checklist commands SECURELY and ASYNC.
    - No shell=True (security)
    - Uses asyncio.create_subprocess_exec (non-blocking)
    - Command whitelist enforced
    """

    # Whitelist of allowed commands
    ALLOWED_COMMANDS = {
        'test', 'grep', 'ls', 'cat', 'head', 'wc', 'find', 'stat', '[',
        'php', 'node', 'python', 'python3', 'npm', 'composer'
    }

    COMMAND_TIMEOUT = 10  # seconds

    @staticmethod
    async def run_check_async(check_command: str, project_path: str) -> Dict[str, Any]:
        """Run a check command securely and asynchronously."""
        try:
            args = shlex.split(check_command)

            if not args:
                return {"passed": False, "output": "Empty command"}

            if args[0] not in ChecklistRunner.ALLOWED_COMMANDS:
                return {"passed": False, "output": f"Command '{args[0]}' not allowed"}

            proc = await asyncio.create_subprocess_exec(
                *args,
                cwd=project_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=ChecklistRunner.COMMAND_TIMEOUT
                )
                output = (stdout.decode() if stdout else "") or (stderr.decode() if stderr else "")
                return {
                    "passed": proc.returncode == 0,
                    "output": output[:200]
                }
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                return {"passed": False, "output": "Timeout"}

        except ValueError as e:
            return {"passed": False, "output": f"Parse error: {e}"}
        except FileNotFoundError:
            return {"passed": False, "output": f"Command not found: {args[0]}"}
        except Exception as e:
            logger.error(f"Checklist error: {e}")
            return {"passed": False, "output": str(e)[:100]}

    @staticmethod
    def run_check(check_command: str, project_path: str) -> Dict[str, Any]:
        """Sync wrapper for backwards compatibility."""
        try:
            # Check if there's already a running loop
            asyncio.get_running_loop()
            # If we get here, there's a running loop - use sync subprocess fallback
            # (safer than running async in thread for simple commands)
            import subprocess
            try:
                args = shlex.split(check_command)
                if not args or args[0] not in ChecklistRunner.ALLOWED_COMMANDS:
                    return {"passed": False, "output": f"Command not allowed"}

                result = subprocess.run(
                    args, cwd=project_path, capture_output=True, text=True,
                    timeout=ChecklistRunner.COMMAND_TIMEOUT, shell=False
                )
                return {
                    "passed": result.returncode == 0,
                    "output": (result.stdout or result.stderr)[:200]
                }
            except Exception as e:
                return {"passed": False, "output": str(e)[:100]}
        except RuntimeError:
            # No running loop - safe to use asyncio.run
            return asyncio.run(
                ChecklistRunner.run_check_async(check_command, project_path)
            )

    @staticmethod
    async def run_all_async(checklist: List[Dict], project_path: str) -> Dict[str, Any]:
        """Run all checklist items asynchronously (parallel)."""
        results = {}
        passed = failed = 0

        # Run all checks in parallel
        async def run_single(item: Dict) -> tuple:
            name = item.get("item", "?")
            check = item.get("check")
            if check:
                result = await ChecklistRunner.run_check_async(check, project_path)
                return name, result
            return name, None

        tasks = [run_single(item) for item in checklist]
        completed = await asyncio.gather(*tasks)

        for name, result in completed:
            if result is not None:
                results[name] = "✓" if result["passed"] else "✗"
                if result["passed"]:
                    passed += 1
                else:
                    failed += 1

        return {
            "results": results,
            "passed": passed,
            "failed": failed,
            "total": len(checklist)
        }

    @staticmethod
    def run_all(checklist: List[Dict], project_path: str) -> Dict[str, Any]:
        """Sync wrapper - runs checks sequentially."""
        results = {}
        passed = failed = 0

        for item in checklist:
            name = item.get("item", "?")
            check = item.get("check")

            if check:
                result = ChecklistRunner.run_check(check, project_path)
                results[name] = "✓" if result["passed"] else "✗"
                if result["passed"]:
                    passed += 1
                else:
                    failed += 1

        return {
            "results": results,
            "passed": passed,
            "failed": failed,
            "total": len(checklist)
        }
