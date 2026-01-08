#!/usr/bin/env python3
"""
Chainguard - Automatische Qualitätskontrolle für Claude Code
============================================================

Installation:
    pip install .

Oder für Entwicklung:
    pip install -e .
"""

from setuptools import setup, find_packages
from pathlib import Path

# Projektverzeichnis
HERE = Path(__file__).parent

# README laden
README = (HERE / "README.md").read_text(encoding="utf-8") if (HERE / "README.md").exists() else ""

# Version aus Datei oder Fallback
VERSION = "4.2.0"

setup(
    name="chainguard",
    version=VERSION,
    description="High-End optimierte Qualitätskontrolle für Claude Code",
    long_description=README,
    long_description_content_type="text/markdown",
    author="Chainguard Team",
    author_email="team@chainguard.dev",
    url="https://github.com/your-org/chainguard",
    license="MIT",

    # Python Version
    python_requires=">=3.8",

    # Packages
    packages=find_packages(where="src"),
    package_dir={"": "src"},

    # Daten-Dateien einschließen
    include_package_data=True,
    package_data={
        "": [
            "*.sh",
            "*.yaml",
            "*.yml",
            "*.md",
        ],
    },

    # Abhängigkeiten
    install_requires=[
        "mcp>=0.9.0",
        "aiofiles>=23.0.0",  # Async I/O für High-End Performance
        "aiohttp>=3.9.0",    # HTTP Client für Endpoint-Testing (v4.2)
    ],

    # Optionale Abhängigkeiten
    extras_require={
        "full": [
            "pyyaml>=6.0",
            "anthropic>=0.18.0",
        ],
        "minimal": [
            # Ohne aiofiles - funktioniert mit sync fallback
            "mcp>=0.9.0",
        ],
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "mypy>=1.0.0",
            "black>=23.0.0",
            "ruff>=0.1.0",
        ],
    },

    # Entry Points für CLI
    entry_points={
        "console_scripts": [
            "chainguard-install=installer.install:main",
        ],
    },

    # Klassifikatoren
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Quality Assurance",
        "Topic :: Software Development :: Testing",
    ],

    # Schlüsselwörter
    keywords=[
        "claude",
        "claude-code",
        "mcp",
        "quality-assurance",
        "validation",
        "ai-assistant",
    ],
)
