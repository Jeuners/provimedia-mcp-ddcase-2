# Plan: Auto-Validierung bei Task-Abschluss

## Problem

Aktuell kann man `chainguard_validate(status="PASS")` und `chainguard_set_phase(phase="done")` aufrufen, **ohne dass geprüft wird, ob die Aufgabe wirklich 100% erfüllt ist**.

Das führt zu:
- Vergessene Akzeptanzkriterien
- Unvollständige Tasks werden als "fertig" markiert
- Keine Qualitätssicherung vor Abschluss

## Lösung

### 1. Neue Methode `ProjectState.get_completion_status()`

```python
def get_completion_status(self) -> Dict[str, Any]:
    """Prüft ob alle Anforderungen für Task-Abschluss erfüllt sind."""
    issues = []

    # 1. Akzeptanzkriterien prüfen
    if self.scope and self.scope.acceptance_criteria:
        unfulfilled = [c for c in self.scope.acceptance_criteria
                       if not self.criteria_status.get(c)]
        if unfulfilled:
            issues.append({
                "type": "criteria",
                "message": f"{len(unfulfilled)} Kriterien nicht erfüllt",
                "details": unfulfilled[:3]  # Max 3 anzeigen
            })

    # 2. Checklist prüfen (falls definiert und nicht ausgeführt)
    if self.scope and self.scope.checklist:
        failed = [k for k, v in self.checklist_results.items() if v == "✗"]
        not_run = len(self.scope.checklist) - len(self.checklist_results)
        if failed:
            issues.append({
                "type": "checklist",
                "message": f"{len(failed)} Checks fehlgeschlagen",
                "details": failed
            })
        if not_run > 0:
            issues.append({
                "type": "checklist",
                "message": f"{not_run} Checks nicht ausgeführt"
            })

    # 3. Offene Alerts prüfen
    open_alerts = [a for a in self.alerts if not a.get("ack")]
    if open_alerts:
        issues.append({
            "type": "alerts",
            "message": f"{len(open_alerts)} offene Alerts",
            "details": [a["msg"][:30] for a in open_alerts[:2]]
        })

    # 4. Syntax-Fehler in Alerts prüfen
    syntax_alerts = [a for a in self.alerts if not a.get("ack") and "errors" in a]
    if syntax_alerts:
        issues.append({
            "type": "syntax",
            "message": "Syntax-Fehler nicht behoben"
        })

    return {
        "complete": len(issues) == 0,
        "issues": issues,
        "criteria_done": sum(1 for c in (self.scope.acceptance_criteria if self.scope else [])
                            if self.criteria_status.get(c)),
        "criteria_total": len(self.scope.acceptance_criteria) if self.scope else 0
    }
```

### 2. Änderung `chainguard_validate`

Bei `status="PASS"` automatisch prüfen:

```python
elif name == "chainguard_validate":
    state = await pm.get_async(working_dir)
    status = args["status"]
    note = args.get("note", "")
    force = args.get("force", False)  # NEU: Override für manuelle Bestätigung

    # NEU: Bei PASS automatisch Completion prüfen
    if status == "PASS" and not force:
        completion = state.get_completion_status()
        if not completion["complete"]:
            # Warnung ausgeben, aber nicht blockieren
            warnings = []
            for issue in completion["issues"]:
                warnings.append(f"⚠ {issue['message']}")

            state.add_action(f"VAL: PASS (mit Warnungen)")
            # Trotzdem speichern, aber warnen
            ...
            return [TextContent(type="text", text=
                f"⚠ Validation PASS mit offenen Punkten:\n" +
                "\n".join(warnings) +
                "\n\n→ force=true um ohne Prüfung abzuschließen")]
```

### 3. Änderung `chainguard_set_phase(phase="done")`

Warnung wenn nicht 100%:

```python
elif name == "chainguard_set_phase":
    state = await pm.get_async(working_dir)
    new_phase = args["phase"]

    # NEU: Bei "done" Completion prüfen
    if new_phase == "done":
        completion = state.get_completion_status()
        if not completion["complete"]:
            warnings = [f"⚠ {i['message']}" for i in completion["issues"]]
            # Phase trotzdem setzen, aber warnen
            state.phase = new_phase
            await pm.save_async(state)
            return [TextContent(type="text", text=
                f"→ done (mit Warnungen)\n" + "\n".join(warnings))]

    state.phase = new_phase
    ...
```

### 4. Neues Tool `chainguard_finish`

All-in-One Abschluss mit vollständiger Prüfung:

```python
Tool(
    name="chainguard_finish",
    description="Vollständiger Task-Abschluss: Prüft Kriterien, Checklist, Alerts. Blockiert bei Fehlern.",
    inputSchema={
        "type": "object",
        "properties": {
            "working_dir": {"type": "string"},
            "force": {"type": "boolean", "description": "Abschluss erzwingen trotz offener Punkte"}
        },
        "required": []
    }
)
```

Implementierung:
```python
elif name == "chainguard_finish":
    state = await pm.get_async(working_dir)
    force = args.get("force", False)

    # Vollständige Prüfung
    completion = state.get_completion_status()

    # Checklist ausführen falls nicht geschehen
    if state.scope and state.scope.checklist and not state.checklist_results:
        results = ChecklistRunner.run_all(state.scope.checklist, state.project_path)
        state.checklist_results = results["results"]
        # Completion neu prüfen
        completion = state.get_completion_status()

    lines = []
    lines.append(f"## Task-Abschluss: {state.scope.description if state.scope else 'Unbekannt'}")
    lines.append("")

    # Kriterien-Status
    lines.append(f"**Kriterien:** {completion['criteria_done']}/{completion['criteria_total']}")

    # Issues anzeigen
    if completion["issues"]:
        lines.append("")
        lines.append("**Offene Punkte:**")
        for issue in completion["issues"]:
            lines.append(f"- {issue['message']}")

    if completion["complete"]:
        # Alles OK - abschließen
        state.validations_passed += 1
        state.files_since_validation = 0
        state.phase = "done"
        state.last_validation = datetime.now().isoformat()
        state.add_action("FINISH: PASS")
        await pm.save_async(state, immediate=True)

        lines.append("")
        lines.append("✓ **Task erfolgreich abgeschlossen!**")
        return [TextContent(type="text", text="\n".join(lines))]

    elif force:
        # Erzwungen abschließen
        state.validations_passed += 1
        state.files_since_validation = 0
        state.phase = "done"
        state.last_validation = datetime.now().isoformat()
        state.add_action("FINISH: FORCED")
        await pm.save_async(state, immediate=True)

        lines.append("")
        lines.append("⚠ **Task abgeschlossen (erzwungen)**")
        return [TextContent(type="text", text="\n".join(lines))]

    else:
        # Nicht abschließen - offene Punkte
        lines.append("")
        lines.append("✗ **Kann nicht abschließen** - offene Punkte beheben oder `force=true`")
        return [TextContent(type="text", text="\n".join(lines))]
```

## Implementierungsreihenfolge

1. **`get_completion_status()`** in `ProjectState` hinzufügen (Zeile ~720)
2. **`chainguard_validate`** anpassen (Zeile ~1604)
3. **`chainguard_set_phase`** anpassen (Zeile ~1550)
4. **`chainguard_finish`** Tool hinzufügen (Tool-Liste + Handler)
5. **Testen** mit echtem Workflow

## Testplan

1. Scope setzen mit 2 Kriterien
2. `chainguard_finish` aufrufen → sollte blockieren
3. Kriterien erfüllen
4. `chainguard_finish` aufrufen → sollte durchgehen
5. `force=true` testen bei offenen Punkten

## Risiken

- Bestehende Workflows könnten "brechen" wenn sie nie Kriterien gesetzt haben
  → Lösung: Keine Kriterien = automatisch "complete"
- Performance bei vielen Kriterien
  → Kein Problem, ist O(n) mit kleinem n

## Geschätzter Umfang

- ~50 Zeilen für `get_completion_status()`
- ~20 Zeilen Änderung in `chainguard_validate`
- ~15 Zeilen Änderung in `chainguard_set_phase`
- ~60 Zeilen für `chainguard_finish`
- **Total: ~150 Zeilen**
