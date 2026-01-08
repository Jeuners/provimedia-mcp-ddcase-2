#!/usr/bin/env python3
"""
CHAINGUARD MCP Server - Wrapper

This file wraps the modular chainguard package.
The actual implementation is in the chainguard/ subdirectory.

Copyright (c) 2026 Provimedia GmbH
Licensed under the Polyform Noncommercial License 1.0.0
See LICENSE file in the project root for full license information.

Usage:
    python chainguard_mcp.py

Or directly:
    python -m chainguard
"""

import sys
from pathlib import Path

# Add chainguard package to path
sys.path.insert(0, str(Path(__file__).parent))

# Import and run
from chainguard.server import run

if __name__ == "__main__":
    run()
