#!/usr/bin/env python3
"""
CHAINGUARD Enforcer Hook

Hard Enforcement for CHAINGUARD rules.
PreToolUse Hook for Edit/Write - blocks tool calls if rules are not met.

Copyright (c) 2026 Provimedia GmbH
Licensed under the Polyform Noncommercial License 1.0.0
See LICENSE file in the project root for full license information.

Checked Rules:
1. Schema-Dateien ohne gültigen DB-Schema-Check (TTL-basiert) → BLOCK
2. Blocking Alerts vorhanden → BLOCK
3. Kein Scope gesetzt → WARN (nicht blockieren)

v1.1: TTL-basierte Schema-Check-Validierung (10 Minuten TTL)
v1.2: infer_project_dir() - leitet Projektverzeichnis aus file_path ab
v1.3: get_project_id() - identische Logic wie MCP Server (Git Remote/Root/Path)
"""

import sys
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

# CHAINGUARD Home
CHAINGUARD_HOME = Path.home() / ".chainguard"
ENFORCEMENT_STATE_FILE = "enforcement-state.json"

# v4.18: TTL for schema check (must match config.py)
DB_SCHEMA_CHECK_TTL = 600  # 10 minutes


def get_project_id(working_dir: str) -> str:
    """
    Berechnet die Project ID wie der MCP Server.

    Reihenfolge (identisch mit project_manager.py):
    1. Git Remote URL Hash
    2. Git Root Path Hash
    3. Working Dir Path Hash (Fallback)
    """
    import subprocess

    # 1. Try git remote
    try:
        result = subprocess.run(
            ["git", "-C", working_dir, "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            return hashlib.sha256(result.stdout.strip().encode()).hexdigest()[:16]
    except Exception:
        pass

    # 2. Try git root
    try:
        result = subprocess.run(
            ["git", "-C", working_dir, "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            return hashlib.sha256(result.stdout.strip().encode()).hexdigest()[:16]
    except Exception:
        pass

    # 3. Fallback: path hash
    return hashlib.sha256(working_dir.encode()).hexdigest()[:16]


def load_enforcement_state(working_dir: str) -> Optional[Dict[str, Any]]:
    """Lädt den Enforcement-State für ein Projekt."""
    project_id = get_project_id(working_dir)
    state_file = CHAINGUARD_HOME / "projects" / project_id / ENFORCEMENT_STATE_FILE

    if not state_file.exists():
        return None

    try:
        with open(state_file) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def is_schema_file(file_path: str) -> bool:
    """Prüft ob eine Datei eine Schema-Datei ist."""
    if not file_path:
        return False

    file_lower = file_path.lower()
    schema_patterns = [
        'schema.sql',
        'migration',
        '.sql',
        'database',
        'migrate',
        '/migrations/',
        '/db/',
        'seed',
    ]
    return any(p in file_lower for p in schema_patterns)


def is_web_file(file_path: str) -> bool:
    """Prüft ob eine Datei eine Web-Datei ist (PHP, JS, TS, etc.)."""
    if not file_path:
        return False

    web_extensions = ['.php', '.js', '.ts', '.tsx', '.jsx', '.vue', '.svelte']
    return any(file_path.lower().endswith(ext) for ext in web_extensions)


def is_schema_check_valid(checked_at: str) -> Tuple[bool, int]:
    """
    v1.1: Prüft ob der Schema-Check noch gültig ist (innerhalb TTL).

    Returns:
        Tuple[bool, int]: (ist_gültig, alter_in_sekunden)
        - True, age: Check ist gültig
        - False, age: Check ist abgelaufen oder nie gemacht
        - False, -1: Nie gecheckt
    """
    if not checked_at:
        return False, -1

    try:
        check_time = datetime.fromisoformat(checked_at)
        age_seconds = int((datetime.now() - check_time).total_seconds())
        return age_seconds < DB_SCHEMA_CHECK_TTL, age_seconds
    except (ValueError, TypeError):
        return False, -1


def check_rules(tool_name: str, tool_input: Dict[str, Any], state: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Prüft alle CHAINGUARD-Regeln.

    Returns:
        Tuple[bool, str]: (erlaubt, nachricht)
        - True, "": Erlaubt, keine Nachricht
        - False, "...": Blockiert, mit Grund
    """
    file_path = ""

    # Datei aus Tool-Input extrahieren
    if tool_name == "Edit":
        file_path = tool_input.get("file_path", "")
    elif tool_name == "Write":
        file_path = tool_input.get("file_path", "")

    # Regel 1: Schema-Dateien ohne gültigen DB-Schema-Check (TTL-basiert)
    if is_schema_file(file_path):
        checked_at = state.get("db_schema_checked_at", "")
        is_valid, age = is_schema_check_valid(checked_at)

        if not is_valid:
            if age == -1:
                reason = "Du hast das DB-Schema noch nie geprüft."
            else:
                reason = f"Der Schema-Check ist abgelaufen (vor {age}s, TTL: {DB_SCHEMA_CHECK_TTL}s)."

            return False, (
                "CHAINGUARD BLOCKIERT: Schema-Datei ohne gültigen DB-Check!\n\n"
                f"{reason}\n"
                "Dies führt oft zu Fehlern wie 'Unknown column'.\n\n"
                "LÖSUNG:\n"
                "1. chainguard_db_connect(user=\"...\", password=\"...\", database=\"...\")\n"
                "2. chainguard_db_schema(refresh=True)\n"
                "3. Dann erst die Schema-Datei bearbeiten\n"
            )

    # Regel 2: Blocking Alerts
    blocking_alerts = state.get("blocking_alerts", [])
    if blocking_alerts:
        alert_msgs = "\n".join(f"  - {a}" for a in blocking_alerts[:3])
        return False, (
            f"CHAINGUARD BLOCKIERT: {len(blocking_alerts)} kritische Alerts!\n\n"
            f"Offene Alerts:\n{alert_msgs}\n\n"
            "Diese Alerts müssen zuerst gelöst werden.\n"
            "Nutze chainguard_status(ctx='🔗') für Details.\n"
        )

    # Regel 3: HTTP-Tests Pflicht für Web-Dateien (Warnung, kein Block)
    # Diese Regel wird nur in chainguard_finish() erzwungen

    # Alle Regeln erfüllt
    return True, ""


def infer_project_dir(file_path: str, cwd_fallback: str) -> str:
    """
    Leitet das Projektverzeichnis aus file_path ab.

    Sucht nach typischen Projektmarkern (.git, composer.json, package.json, etc.)
    im Pfad der bearbeiteten Datei.
    """
    if not file_path:
        return cwd_fallback

    path = Path(file_path).resolve()
    project_markers = ['.git', 'composer.json', 'package.json', '.chainguard', 'CLAUDE.md']

    # Suche vom Datei-Verzeichnis aufwärts nach Projektmarkern
    current = path.parent
    for _ in range(20):  # Max 20 Ebenen
        for marker in project_markers:
            if (current / marker).exists():
                return str(current)
        if current.parent == current:  # Root erreicht
            break
        current = current.parent

    # Fallback: Verzeichnis der Datei oder cwd
    return str(path.parent) if file_path else cwd_fallback


def main():
    """Hauptfunktion - liest Hook-Input und prüft Regeln."""
    # Hook-Input von stdin lesen
    hook_input = {}
    if not sys.stdin.isatty():
        try:
            raw_input = sys.stdin.read()
            if raw_input.strip():
                hook_input = json.loads(raw_input)
        except json.JSONDecodeError:
            pass

    # Tool-Informationen extrahieren
    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    cwd_fallback = hook_input.get("cwd", str(Path.cwd()))

    # Working Dir aus file_path ableiten (v1.2 Fix)
    working_dir = infer_project_dir(file_path, cwd_fallback)

    # Nur für Edit und Write prüfen
    if tool_name not in ["Edit", "Write"]:
        sys.exit(0)  # Andere Tools durchlassen

    # Enforcement-State laden
    state = load_enforcement_state(working_dir)

    if state is None:
        # Kein State = Kein Scope = Warnung aber kein Block
        # Der Scope-Reminder Hook kümmert sich darum
        sys.exit(0)

    # Regeln prüfen
    allowed, message = check_rules(tool_name, tool_input, state)

    if not allowed:
        # BLOCK - Exit Code 2 blockiert den Tool-Aufruf
        print(message, file=sys.stderr)
        sys.exit(2)

    # OK - Tool durchlassen
    sys.exit(0)


if __name__ == "__main__":
    main()
