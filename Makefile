# =============================================================================
# CHAINGUARD - Makefile
# =============================================================================
# Einfache Befehle für Installation, Test und Entwicklung
#
# Verwendung:
#   make install      - Lokale Installation
#   make verify       - Installation verifizieren
#   make uninstall    - Deinstallation
#   make test         - Tests ausführen
#   make lint         - Code-Qualität prüfen
#   make clean        - Build-Artefakte entfernen
# =============================================================================

.PHONY: all install install-dev verify uninstall test lint format clean help

# Standard-Ziel
all: help

# =============================================================================
# Installation
# =============================================================================

## Installiert Chainguard (Standard-Installation)
install:
	@echo "Installing Chainguard..."
	@chmod +x installer/install.sh
	@./installer/install.sh

## Installiert Chainguard ohne Hooks
install-minimal:
	@echo "Installing Chainguard (minimal)..."
	@chmod +x installer/install.sh
	@./installer/install.sh --no-hooks

## Installiert Chainguard mit Entwickler-Abhängigkeiten
install-dev:
	@echo "Installing Chainguard (development)..."
	@pip3 install -e ".[dev,full]"
	@chmod +x installer/install.sh
	@./installer/install.sh

## Verifiziert die Installation
verify:
	@echo "Verifying installation..."
	@chmod +x installer/verify.sh
	@./installer/verify.sh

## Verifiziert und repariert die Installation
verify-fix:
	@echo "Verifying and fixing installation..."
	@chmod +x installer/verify.sh
	@./installer/verify.sh --fix

## Deinstalliert Chainguard
uninstall:
	@echo "Uninstalling Chainguard..."
	@chmod +x installer/uninstall.sh
	@./installer/uninstall.sh

## Deinstalliert Chainguard (ohne Bestätigung)
uninstall-force:
	@echo "Force uninstalling Chainguard..."
	@chmod +x installer/uninstall.sh
	@./installer/uninstall.sh --force

# =============================================================================
# Python Dependencies
# =============================================================================

## Installiert Python-Abhängigkeiten
deps:
	@echo "Installing Python dependencies..."
	@pip3 install -r requirements.txt

## Installiert alle Abhängigkeiten (inkl. optionale)
deps-full:
	@echo "Installing all Python dependencies..."
	@pip3 install -r requirements.txt
	@pip3 install pyyaml anthropic

## Aktualisiert Python-Abhängigkeiten
deps-update:
	@echo "Updating Python dependencies..."
	@pip3 install --upgrade -r requirements.txt

# =============================================================================
# Entwicklung
# =============================================================================

## Führt alle Tests aus
test:
	@echo "Running tests..."
	@python3 -m pytest tests/ -v

## Führt Tests mit Coverage aus
test-cov:
	@echo "Running tests with coverage..."
	@python3 -m pytest tests/ -v --cov=src --cov-report=html

## Prüft Code-Qualität (Linting)
lint:
	@echo "Linting code..."
	@python3 -m ruff check src/ tests/ || true
	@python3 -m mypy src/ --ignore-missing-imports || true

## Formatiert Code
format:
	@echo "Formatting code..."
	@python3 -m black src/ tests/
	@python3 -m ruff check --fix src/ tests/

## Prüft Python-Syntax aller Dateien
syntax-check:
	@echo "Checking Python syntax..."
	@python3 -m py_compile src/mcp-server/chainguard_mcp.py
	@python3 -m py_compile src/deep-validator.py
	@echo "Syntax OK"

# =============================================================================
# Build & Release
# =============================================================================

## Erstellt Distribution-Pakete
build:
	@echo "Building distribution packages..."
	@python3 -m build

## Bereinigt Build-Artefakte
clean:
	@echo "Cleaning build artifacts..."
	@rm -rf build/ dist/ *.egg-info
	@rm -rf .pytest_cache/ .mypy_cache/ .ruff_cache/
	@rm -rf htmlcov/ .coverage
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true

# =============================================================================
# Dokumentation
# =============================================================================

## Generiert Dokumentation
docs:
	@echo "Generating documentation..."
	@echo "TODO: Documentation generation"

# =============================================================================
# Hilfe
# =============================================================================

## Zeigt diese Hilfe
help:
	@echo ""
	@echo "CHAINGUARD - Makefile"
	@echo "====================="
	@echo ""
	@echo "Installation:"
	@echo "  make install         - Standard-Installation"
	@echo "  make install-minimal - Installation ohne Hooks"
	@echo "  make install-dev     - Installation mit Dev-Dependencies"
	@echo "  make verify          - Installation verifizieren"
	@echo "  make verify-fix      - Installation verifizieren und reparieren"
	@echo "  make uninstall       - Deinstallation"
	@echo ""
	@echo "Dependencies:"
	@echo "  make deps            - Python-Dependencies installieren"
	@echo "  make deps-full       - Alle Dependencies (inkl. optionale)"
	@echo "  make deps-update     - Dependencies aktualisieren"
	@echo ""
	@echo "Entwicklung:"
	@echo "  make test            - Tests ausführen"
	@echo "  make test-cov        - Tests mit Coverage"
	@echo "  make lint            - Code-Qualität prüfen"
	@echo "  make format          - Code formatieren"
	@echo "  make syntax-check    - Python-Syntax prüfen"
	@echo ""
	@echo "Build:"
	@echo "  make build           - Distribution erstellen"
	@echo "  make clean           - Build-Artefakte entfernen"
	@echo ""
