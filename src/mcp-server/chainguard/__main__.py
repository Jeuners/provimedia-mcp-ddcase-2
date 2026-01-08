"""
CHAINGUARD MCP Server - Main Entry Point

Allow running the package directly: python -m chainguard

Copyright (c) 2026 Provimedia GmbH
Licensed under the Polyform Noncommercial License 1.0.0
See LICENSE file in the project root for full license information.
"""
from .server import run

if __name__ == "__main__":
    run()
