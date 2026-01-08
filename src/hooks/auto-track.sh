#!/bin/bash
# =============================================================================
# CHAINGUARD Auto-Track Hook v3.0
# =============================================================================
# Wird automatisch nach Edit/Write aufgerufen und queued Events für den MCP.
# Leichtgewichtig - schreibt nur in eine Queue-Datei.
# =============================================================================

CHAINGUARD_HOME="${CHAINGUARD_HOME:-$HOME/.chainguard}"

# Hook-Input von Claude Code lesen (JSON von stdin)
HOOK_INPUT=""
if [[ ! -t 0 ]]; then
    HOOK_INPUT=$(cat)
fi

# Extrahiere relevante Infos
TOOL_NAME=$(echo "$HOOK_INPUT" | jq -r '.tool_name // "unknown"' 2>/dev/null || echo "unknown")
FILE_PATH=$(echo "$HOOK_INPUT" | jq -r '.tool_input.file_path // ""' 2>/dev/null || echo "")
TIMESTAMP=$(date -Iseconds)

# Nur bei Edit/Write tracken
if [[ "$TOOL_NAME" != "Edit" && "$TOOL_NAME" != "Write" ]]; then
    exit 0
fi

# Working Directory ermitteln (aus file_path oder cwd)
if [[ -n "$FILE_PATH" ]]; then
    WORK_DIR=$(dirname "$FILE_PATH")
else
    WORK_DIR=$(pwd)
fi

# Project ID berechnen (vereinfacht - wie im MCP)
PROJECT_ID=$(echo "$WORK_DIR" | shasum -a 256 | cut -c1-16)

# Event in Queue schreiben
QUEUE_DIR="$CHAINGUARD_HOME/projects/$PROJECT_ID"
QUEUE_FILE="$QUEUE_DIR/pending_events.jsonl"

mkdir -p "$QUEUE_DIR"

# Event als JSONL (eine Zeile pro Event)
echo "{\"timestamp\":\"$TIMESTAMP\",\"event\":\"FILE_CHANGED\",\"file\":\"$FILE_PATH\",\"tool\":\"$TOOL_NAME\"}" >> "$QUEUE_FILE"

exit 0
