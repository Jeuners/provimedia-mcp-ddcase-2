#!/usr/bin/env python3
"""
=============================================================================
CHAINGUARD - Deep Validator
=============================================================================
LLM-basierte tiefe Validierung des Projekt-Zustands.
Wird nur an Checkpoints aufgerufen, nicht bei jedem Tool-Call.

Verwendung:
    python deep-validator.py --project-dir /path/to/project
    python deep-validator.py --checkpoint "module-complete"
    python deep-validator.py --final-check
=============================================================================
"""

import os
import sys
import json
import argparse
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List

# Konfiguration
CHAINGUARD_HOME = Path(os.environ.get("CHAINGUARD_HOME", Path.home() / ".chainguard"))
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")


class ProjectContext:
    """Sammelt und verwaltet den Projekt-Kontext."""

    def __init__(self, project_dir: Path):
        self.project_dir = project_dir
        self.state_dir = self._get_state_dir()
        self.scope = self._load_scope()
        self.state = self._load_state()
        self.progress_log = self._load_progress_log()
        self.alerts = self._load_alerts()

    def _get_state_dir(self) -> Path:
        """Ermittelt das State-Verzeichnis für dieses Projekt."""
        result = subprocess.run(
            [str(CHAINGUARD_HOME / "hooks" / "project-identifier.sh"), "--state-dir", str(self.project_dir)],
            capture_output=True,
            text=True
        )
        return Path(result.stdout.strip())

    def _load_scope(self) -> Dict[str, Any]:
        """Lädt die Scope-Definition falls vorhanden."""
        # Zuerst im Projekt-Root suchen
        scope_file = self.project_dir / ".chainguard" / "scope.yaml"
        if scope_file.exists():
            try:
                import yaml
                with open(scope_file) as f:
                    return yaml.safe_load(f) or {}
            except ImportError:
                # Fallback: Als JSON parsen wenn kein yaml Modul
                pass

        # Dann im State-Dir suchen
        scope_json = self.state_dir / "scope.json"
        if scope_json.exists():
            with open(scope_json) as f:
                return json.load(f)

        return {}

    def _load_state(self) -> Dict[str, Any]:
        """Lädt den aktuellen State."""
        state_file = self.state_dir / "state.json"
        if state_file.exists():
            with open(state_file) as f:
                return json.load(f)
        return {"phase": "unknown", "status": "active"}

    def _load_progress_log(self, tail_lines: int = 50) -> List[str]:
        """Lädt die letzten N Zeilen des Progress-Logs."""
        log_file = self.state_dir / "progress.log"
        if not log_file.exists():
            return []

        with open(log_file) as f:
            lines = f.readlines()
        return lines[-tail_lines:]

    def _load_alerts(self) -> List[str]:
        """Lädt unbestätigte Alerts."""
        alerts_file = self.state_dir / "alerts.log"
        if not alerts_file.exists():
            return []

        with open(alerts_file) as f:
            return f.readlines()

    def get_recent_changes(self) -> List[Dict[str, Any]]:
        """Extrahiert kürzliche Dateiänderungen aus dem Log."""
        changes = []
        for line in self.progress_log:
            if "File modified:" in line:
                parts = line.split("File modified:")
                if len(parts) > 1:
                    changes.append({
                        "type": "file_change",
                        "file": parts[1].strip(),
                        "timestamp": line.split("]")[0].strip("[")
                    })
        return changes[-20:]  # Letzte 20 Änderungen

    def to_context_string(self) -> str:
        """Konvertiert den gesamten Kontext in einen String für das LLM."""
        return f"""
## PROJEKT-KONTEXT

### Scope Definition:
```json
{json.dumps(self.scope, indent=2, default=str)}
```

### Aktueller State:
```json
{json.dumps(self.state, indent=2, default=str)}
```

### Letzte Aktivitäten (Progress Log):
```
{''.join(self.progress_log[-20:])}
```

### Offene Alerts:
```
{''.join(self.alerts) if self.alerts else 'Keine Alerts'}
```

### Kürzliche Dateiänderungen:
{json.dumps(self.get_recent_changes(), indent=2)}
"""


class DeepValidator:
    """Führt LLM-basierte Validierungen durch."""

    def __init__(self, context: ProjectContext, api_key: str = ""):
        self.context = context
        self.api_key = api_key or ANTHROPIC_API_KEY

    def _call_llm(self, prompt: str) -> Dict[str, Any]:
        """Ruft die Claude API auf."""
        if not self.api_key:
            return {
                "status": "SKIP",
                "reason": "No API key configured",
                "recommendations": []
            }

        try:
            import anthropic
            client = anthropic.Anthropic(api_key=self.api_key)

            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}]
            )

            # Parse die Antwort
            content = response.content[0].text
            return self._parse_llm_response(content)

        except ImportError:
            # Fallback: curl verwenden
            return self._call_llm_curl(prompt)
        except Exception as e:
            return {
                "status": "ERROR",
                "reason": str(e),
                "recommendations": []
            }

    def _call_llm_curl(self, prompt: str) -> Dict[str, Any]:
        """Fallback: LLM via curl aufrufen."""
        import subprocess
        import json

        payload = {
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}]
        }

        try:
            result = subprocess.run(
                [
                    "curl", "-s", "https://api.anthropic.com/v1/messages",
                    "-H", "Content-Type: application/json",
                    "-H", f"x-api-key: {self.api_key}",
                    "-H", "anthropic-version: 2023-06-01",
                    "-d", json.dumps(payload)
                ],
                capture_output=True,
                text=True,
                timeout=30
            )

            response = json.loads(result.stdout)
            content = response.get("content", [{}])[0].get("text", "")
            return self._parse_llm_response(content)

        except Exception as e:
            return {
                "status": "ERROR",
                "reason": str(e),
                "recommendations": []
            }

    def _parse_llm_response(self, content: str) -> Dict[str, Any]:
        """Parst die LLM-Antwort in ein strukturiertes Format."""
        # Versuche JSON zu extrahieren
        try:
            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0]
                return json.loads(json_str)
            elif "{" in content and "}" in content:
                start = content.index("{")
                end = content.rindex("}") + 1
                return json.loads(content[start:end])
        except:
            pass

        # Fallback: Text-basierte Analyse
        status = "PASS"
        if "FAIL" in content.upper() or "KRITISCH" in content.upper():
            status = "FAIL"
        elif "WARN" in content.upper() or "WARNUNG" in content.upper():
            status = "WARN"

        return {
            "status": status,
            "reason": content[:500],
            "recommendations": []
        }

    def validate_checkpoint(self, checkpoint_type: str = "general") -> Dict[str, Any]:
        """Validiert einen Checkpoint."""
        prompt = f"""Du bist ein Code-Review-Assistent. Analysiere den folgenden Projekt-Kontext und prüfe ob alles korrekt läuft.

{self.context.to_context_string()}

## CHECKPOINT-TYP: {checkpoint_type}

## DEINE AUFGABE:
1. Prüfe ob die Änderungen zum definierten Scope passen
2. Identifiziere offensichtliche Fehler oder Auslassungen
3. Prüfe ob wichtige Schritte fehlen (Tests, Routen, Imports, etc.)

## WICHTIG:
- Sei NICHT zu streng bei Zwischenschritten
- Wenn der State "in_progress" zeigt, erwarte keine Vollständigkeit
- Nur bei ECHTEN Problemen "FAIL" zurückgeben

Antworte NUR mit JSON in diesem Format:
```json
{{
    "status": "PASS|WARN|FAIL",
    "reason": "Kurze Begründung",
    "recommendations": ["Empfehlung 1", "Empfehlung 2"],
    "missing_items": ["Falls etwas fehlt"],
    "confidence": 0.0-1.0
}}
```
"""
        return self._call_llm(prompt)

    def validate_final(self) -> Dict[str, Any]:
        """Finale Validierung am Ende eines Tasks."""
        prompt = f"""Du bist ein Code-Review-Assistent. Führe eine FINALE Validierung durch.

{self.context.to_context_string()}

## FINALE PRÜFUNG - Checklist:

1. **Vollständigkeit**: Wurden alle Scope-Punkte umgesetzt?
2. **Tests**: Wurden Tests geschrieben/ausgeführt?
3. **Offensichtliche Fehler**:
   - Fehlende Imports?
   - Nicht registrierte Routen?
   - Falsche Funktionsnamen?
   - Fehlende Dateien?
4. **Best Practices**: Grobe Verstöße?

## WICHTIG:
- Bei einer finalen Prüfung sei gründlich
- Liste ALLE gefundenen Probleme auf
- Auch kleine Dinge wie fehlende Imports erwähnen

Antworte NUR mit JSON:
```json
{{
    "status": "PASS|WARN|FAIL",
    "summary": "Zusammenfassung der Prüfung",
    "issues": [
        {{"severity": "HIGH|MEDIUM|LOW", "description": "Beschreibung", "file": "optional/pfad.py"}}
    ],
    "checklist": {{
        "scope_complete": true/false,
        "tests_present": true/false,
        "no_obvious_errors": true/false
    }},
    "recommendations": ["Empfehlung 1"]
}}
```
"""
        return self._call_llm(prompt)

    def validate_scope_adherence(self) -> Dict[str, Any]:
        """Prüft ob der aktuelle Verlauf dem Scope entspricht."""
        if not self.context.scope:
            return {
                "status": "SKIP",
                "reason": "Kein Scope definiert",
                "recommendations": ["Definiere einen Scope in .chainguard/scope.yaml"]
            }

        prompt = f"""Prüfe ob die Entwicklung im definierten Scope bleibt.

{self.context.to_context_string()}

## FRAGE:
Weichen die aktuellen Aktivitäten vom definierten Scope ab?

Antworte mit JSON:
```json
{{
    "status": "PASS|WARN|FAIL",
    "in_scope": true/false,
    "deviations": ["Liste von Abweichungen falls vorhanden"],
    "reason": "Begründung"
}}
```
"""
        return self._call_llm(prompt)


def main():
    parser = argparse.ArgumentParser(description="Chainguard Deep Validator")
    parser.add_argument("--project-dir", "-p", default=os.getcwd(),
                        help="Projekt-Verzeichnis")
    parser.add_argument("--checkpoint", "-c", default=None,
                        help="Checkpoint-Typ (module-complete, phase-end, etc.)")
    parser.add_argument("--final-check", "-f", action="store_true",
                        help="Finale Validierung durchführen")
    parser.add_argument("--scope-check", "-s", action="store_true",
                        help="Scope-Einhaltung prüfen")
    parser.add_argument("--output", "-o", choices=["json", "text"], default="text",
                        help="Output-Format")

    args = parser.parse_args()

    # Kontext laden
    project_dir = Path(args.project_dir).resolve()
    context = ProjectContext(project_dir)
    validator = DeepValidator(context)

    # Validierung durchführen
    if args.final_check:
        result = validator.validate_final()
    elif args.scope_check:
        result = validator.validate_scope_adherence()
    elif args.checkpoint:
        result = validator.validate_checkpoint(args.checkpoint)
    else:
        result = validator.validate_checkpoint("general")

    # Output
    if args.output == "json":
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        status = result.get("status", "UNKNOWN")
        reason = result.get("reason", result.get("summary", "Keine Details"))

        status_icons = {"PASS": "✓", "WARN": "⚠", "FAIL": "✗", "SKIP": "○", "ERROR": "!"}
        icon = status_icons.get(status, "?")

        print(f"\n{icon} CHAINGUARD VALIDATION: {status}")
        print(f"  {reason}")

        if result.get("recommendations"):
            print("\n  Empfehlungen:")
            for rec in result["recommendations"]:
                print(f"    - {rec}")

        if result.get("issues"):
            print("\n  Gefundene Probleme:")
            for issue in result["issues"]:
                sev = issue.get("severity", "?")
                desc = issue.get("description", "?")
                print(f"    [{sev}] {desc}")

    # Exit-Code basierend auf Status
    exit_codes = {"PASS": 0, "WARN": 0, "FAIL": 1, "SKIP": 0, "ERROR": 2}
    sys.exit(exit_codes.get(result.get("status", "ERROR"), 2))


if __name__ == "__main__":
    main()
