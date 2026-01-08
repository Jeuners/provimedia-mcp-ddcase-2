#!/bin/bash
# =============================================================================
# CHAINGUARD - Observer Hook
# =============================================================================
# Dieser Hook wird von Claude Code bei Tool-Aufrufen ausgeführt.
# Er beobachtet passiv und sammelt Kontext, unterbricht aber NICHT.
#
# WICHTIG: Dieser Hook gibt IMMER 0 zurück (allow), außer bei
# kritischen Fehlern die vom Deep Validator erkannt werden.
# =============================================================================

set -e

# Konfiguration
CHAINGUARD_HOME="${CHAINGUARD_HOME:-$HOME/.chainguard}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source project identifier
source "$SCRIPT_DIR/project-identifier.sh" 2>/dev/null || {
    # Fallback wenn nicht gefunden
    source "$CHAINGUARD_HOME/hooks/project-identifier.sh"
}

# -----------------------------------------------------------------------------
# Projekt identifizieren und State-Verzeichnis holen
# -----------------------------------------------------------------------------
PROJECT_STATE_DIR=$(get_project_state_dir)
LOG_FILE="$PROJECT_STATE_DIR/progress.log"
STATE_FILE="$PROJECT_STATE_DIR/state.json"
ALERTS_FILE="$PROJECT_STATE_DIR/alerts.log"

# Stelle sicher dass die Dateien existieren
touch "$LOG_FILE" "$ALERTS_FILE"
[[ -f "$STATE_FILE" ]] || echo '{"phase":"unknown","status":"active"}' > "$STATE_FILE"

# -----------------------------------------------------------------------------
# Hook-Input von Claude Code lesen (JSON von stdin)
# -----------------------------------------------------------------------------
HOOK_INPUT=""
if [[ ! -t 0 ]]; then
    HOOK_INPUT=$(cat)
fi

# Tool-Name und Session-ID extrahieren (falls verfügbar)
TOOL_NAME=$(echo "$HOOK_INPUT" | jq -r '.tool_name // "unknown"' 2>/dev/null || echo "unknown")
SESSION_ID=$(echo "$HOOK_INPUT" | jq -r '.session_id // "unknown"' 2>/dev/null || echo "$$")
TOOL_INPUT=$(echo "$HOOK_INPUT" | jq -r '.tool_input // {}' 2>/dev/null || echo "{}")

# Timestamp
TIMESTAMP=$(date -Iseconds)

# -----------------------------------------------------------------------------
# Logging-Funktionen
# -----------------------------------------------------------------------------
log_event() {
    local level="$1"
    local message="$2"
    echo "[$TIMESTAMP] [$level] [$TOOL_NAME] $message" >> "$LOG_FILE"
}

log_alert() {
    local severity="$1"
    local message="$2"
    echo "[$TIMESTAMP] [$severity] $message" >> "$ALERTS_FILE"
}

# -----------------------------------------------------------------------------
# State-Management
# -----------------------------------------------------------------------------
read_state() {
    local key="$1"
    jq -r ".$key // empty" "$STATE_FILE" 2>/dev/null
}

update_state() {
    local key="$1"
    local value="$2"
    local tmp_file=$(mktemp)
    jq --arg k "$key" --arg v "$value" '.[$k] = $v' "$STATE_FILE" > "$tmp_file" && mv "$tmp_file" "$STATE_FILE"
}

increment_counter() {
    local key="$1"
    local current=$(jq -r ".$key // 0" "$STATE_FILE" 2>/dev/null)
    local new=$((current + 1))
    update_state "$key" "$new"
}

# -----------------------------------------------------------------------------
# Tool-spezifische Observer-Logik
# -----------------------------------------------------------------------------
observe_tool() {
    case "$TOOL_NAME" in
        Edit|Write)
            # Dateiänderung tracken
            local file_path=$(echo "$TOOL_INPUT" | jq -r '.file_path // "unknown"' 2>/dev/null)
            log_event "INFO" "File modified: $file_path"
            increment_counter "files_modified"

            # Prüfen ob es eine Test-Datei ist
            if [[ "$file_path" == *"test"* ]] || [[ "$file_path" == *"Test"* ]] || [[ "$file_path" == *"spec"* ]]; then
                log_event "INFO" "Test file touched"
                increment_counter "test_files_touched"
            fi
            ;;

        TodoWrite)
            # Todo-Änderungen tracken - wichtig für Checkpoint-Erkennung
            local todos=$(echo "$TOOL_INPUT" | jq -r '.todos // []' 2>/dev/null)
            local completed_count=$(echo "$todos" | jq '[.[] | select(.status == "completed")] | length' 2>/dev/null || echo "0")
            local in_progress=$(echo "$todos" | jq -r '.[] | select(.status == "in_progress") | .content' 2>/dev/null | head -1)

            log_event "INFO" "Todos updated: $completed_count completed"
            update_state "current_task" "$in_progress"
            update_state "completed_todos" "$completed_count"

            # Checkpoint-Trigger: Wenn ein Todo abgeschlossen wurde
            if [[ "$completed_count" -gt 0 ]]; then
                log_event "CHECKPOINT" "Task completed - potential validation point"
                # Hier könnte der Deep Validator getriggert werden
            fi
            ;;

        Bash)
            # Bash-Befehle loggen (für Kontext)
            local command=$(echo "$TOOL_INPUT" | jq -r '.command // "unknown"' 2>/dev/null)
            log_event "INFO" "Bash executed: ${command:0:100}..."
            increment_counter "bash_commands"

            # Spezielle Befehle erkennen
            if [[ "$command" == *"npm test"* ]] || [[ "$command" == *"pytest"* ]] || [[ "$command" == *"phpunit"* ]]; then
                log_event "INFO" "Tests executed"
                update_state "last_test_run" "$TIMESTAMP"
            fi
            ;;

        Read|Glob|Grep)
            # Lesezugriffe minimal loggen (zu viel Noise sonst)
            increment_counter "read_operations"
            ;;

        *)
            # Andere Tools
            log_event "DEBUG" "Tool called: $TOOL_NAME"
            ;;
    esac
}

# -----------------------------------------------------------------------------
# Leichtgewichtige Validierungen (kein LLM, schnell)
# -----------------------------------------------------------------------------
quick_validate() {
    local warnings=0

    # Check 1: Lange Session ohne Tests?
    local bash_count=$(read_state "bash_commands")
    local last_test=$(read_state "last_test_run")
    if [[ "${bash_count:-0}" -gt 20 ]] && [[ -z "$last_test" ]]; then
        log_alert "WARN" "20+ Bash commands without running tests"
        ((warnings++))
    fi

    # Check 2: Viele Dateiänderungen ohne Commit?
    local files_mod=$(read_state "files_modified")
    if [[ "${files_mod:-0}" -gt 15 ]]; then
        log_alert "WARN" "15+ files modified - consider committing"
        ((warnings++))
    fi

    # Diese Warnungen unterbrechen NICHT, sie werden nur geloggt
    return 0
}

# -----------------------------------------------------------------------------
# Hauptausführung
# -----------------------------------------------------------------------------
main() {
    # Event beobachten und loggen
    observe_tool

    # Schnelle Validierungen (non-blocking)
    quick_validate

    # Update last activity
    update_state "last_activity" "$TIMESTAMP"
    update_state "last_tool" "$TOOL_NAME"

    # IMMER erlauben - Observer unterbricht nie
    exit 0
}

# Ausführen
main "$@"
