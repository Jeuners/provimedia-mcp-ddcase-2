"""
CHAINGUARD MCP Server - Main Server Module

Entry point for the MCP server.

Copyright (c) 2026 Provimedia GmbH
Licensed under the Polyform Noncommercial License 1.0.0
See LICENSE file in the project root for full license information.
"""

import sys
import asyncio
from typing import List, Dict, Any, Optional

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent, Resource, Prompt, PromptMessage, PromptArgument
except ImportError:
    print("MCP package not installed. Run: pip install mcp", file=sys.stderr)
    sys.exit(1)

from .config import VERSION, logger
from .tools import get_tool_definitions
from .handlers import handle_tool_call
from .project_manager import project_manager as pm

# Check for aiofiles
try:
    import aiofiles
    HAS_AIOFILES = True
except ImportError:
    HAS_AIOFILES = False


# =============================================================================
# MCP Server Instance
# =============================================================================
server = Server("chainguard")


# =============================================================================
# Tool Registration
# =============================================================================
@server.list_tools()
async def list_tools() -> List[Tool]:
    return await get_tool_definitions()


@server.call_tool()
async def call_tool(name: str, args: Dict[str, Any]) -> List[TextContent]:
    return await handle_tool_call(name, args)


# =============================================================================
# Resources
# =============================================================================
@server.list_resources()
async def list_resources() -> List[Resource]:
    return [Resource(
        uri="chainguard://status",
        name="Chainguard Status",
        description="Current project status",
        mimeType="text/plain"
    )]


@server.read_resource()
async def read_resource(uri: str) -> str:
    if uri == "chainguard://status":
        projects = await pm.list_all_projects_async()
        if not projects:
            return "No active projects"
        return "\n".join(f"{p['name']}|{p['phase']}" for p in projects[:5])
    return "Unknown resource"


# =============================================================================
# Prompts
# =============================================================================
@server.list_prompts()
async def list_prompts() -> List[Prompt]:
    return [
        Prompt(
            name="start",
            description="Start new task with scope",
            arguments=[PromptArgument(name="task", description="Task description", required=True)]
        ),
        Prompt(
            name="check",
            description="Quick status check",
            arguments=[]
        ),
        Prompt(
            name="finish",
            description="Complete task with validation",
            arguments=[]
        )
    ]


@server.get_prompt()
async def get_prompt(name: str, arguments: Optional[Dict[str, Any]] = None) -> List[PromptMessage]:
    if name == "start":
        task = arguments.get("task", "New task") if arguments else "New task"
        return [PromptMessage(
            role="user",
            content=f"Start task: {task}\n\n1. chainguard_set_scope(description=\"{task}\", modules=[...], acceptance_criteria=[...])\n2. chainguard_set_phase(phase=\"implementation\")\n3. Work, calling chainguard_track(file=\"...\") after edits"
        )]
    elif name == "check":
        return [PromptMessage(role="user", content="Run chainguard_status for one-line status")]
    elif name == "finish":
        return [PromptMessage(
            role="user",
            content="1. chainguard_check_criteria - verify all done\n2. chainguard_run_checklist - run checks\n3. chainguard_validate(status=\"PASS/FAIL\")\n4. chainguard_set_phase(phase=\"done\")"
        )]
    return [PromptMessage(role="user", content=f"Unknown: {name}")]


# =============================================================================
# Main Entry Point
# =============================================================================
async def main():
    """Start the MCP server."""
    logger.info(f"Chainguard MCP Server v{VERSION} starting...")
    logger.info(f"Async I/O: {'aiofiles' if HAS_AIOFILES else 'sync fallback'}")

    try:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())
    finally:
        logger.info("Flushing pending saves...")
        try:
            await pm.flush()
            logger.info("Chainguard MCP Server shutdown complete")
        except RuntimeError as e:
            # Some writes failed - log but don't crash (data stays in dirty set)
            logger.error(f"Shutdown with errors: {e}")
            logger.warning("Some project states may not have been saved")


def run():
    """Entry point for console script."""
    asyncio.run(main())


if __name__ == "__main__":
    run()
