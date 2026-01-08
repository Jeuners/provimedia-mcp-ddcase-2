#!/bin/bash
# =============================================================================
# CHAINGUARD - Project Identifier
# =============================================================================
# Identifiziert das aktuelle Projekt eindeutig, auch bei mehreren
# Claude Code Instanzen auf demselben Rechner.
#
# Gibt zurück:
#   - PROJECT_ID: Eindeutiger Hash des Projekts
#   - PROJECT_NAME: Menschenlesbarer Name
#   - PROJECT_PATH: Absoluter Pfad zum Projekt-Root
# =============================================================================

set -e

# Farben für Debug-Output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Konfiguration
CHAINGUARD_HOME="${CHAINGUARD_HOME:-$HOME/.chainguard}"

# -----------------------------------------------------------------------------
# Funktion: Findet das Git-Root des aktuellen Verzeichnisses
# -----------------------------------------------------------------------------
find_git_root() {
    git rev-parse --show-toplevel 2>/dev/null || echo ""
}

# -----------------------------------------------------------------------------
# Funktion: Holt die Git Remote URL (origin)
# -----------------------------------------------------------------------------
get_git_remote() {
    local git_root="$1"
    if [[ -n "$git_root" ]]; then
        git -C "$git_root" remote get-url origin 2>/dev/null || echo ""
    fi
}

# -----------------------------------------------------------------------------
# Funktion: Generiert einen stabilen Hash aus einem String
# -----------------------------------------------------------------------------
generate_hash() {
    local input="$1"
    echo -n "$input" | shasum -a 256 | cut -c1-16
}

# -----------------------------------------------------------------------------
# Funktion: Extrahiert einen lesbaren Projektnamen
# -----------------------------------------------------------------------------
extract_project_name() {
    local path="$1"
    local remote="$2"

    # Aus Git Remote extrahieren (z.B. user/repo aus github.com:user/repo.git)
    if [[ -n "$remote" ]]; then
        echo "$remote" | sed -E 's/.*[:/]([^/]+\/[^/]+)(\.git)?$/\1/' | tr '/' '-'
        return
    fi

    # Fallback: Letztes Verzeichnis im Pfad
    basename "$path"
}

# -----------------------------------------------------------------------------
# HAUPTLOGIK: Projekt identifizieren
# -----------------------------------------------------------------------------
identify_project() {
    local current_dir="${1:-$(pwd)}"
    local git_root=""
    local git_remote=""
    local project_path=""
    local project_id=""
    local project_name=""
    local id_source=""

    # Schritt 1: Git-Root finden
    git_root=$(cd "$current_dir" && find_git_root)

    if [[ -n "$git_root" ]]; then
        # Schritt 2: Git Remote URL holen
        git_remote=$(get_git_remote "$git_root")
        project_path="$git_root"

        if [[ -n "$git_remote" ]]; then
            # Beste Option: Hash aus Git Remote URL
            project_id=$(generate_hash "$git_remote")
            id_source="git-remote"
        else
            # Zweitbeste: Hash aus Git Root Pfad
            project_id=$(generate_hash "$git_root")
            id_source="git-root"
        fi
    else
        # Fallback: Working Directory
        project_path="$current_dir"
        project_id=$(generate_hash "$current_dir")
        id_source="working-dir"
    fi

    # Projektnamen extrahieren
    project_name=$(extract_project_name "$project_path" "$git_remote")

    # Output als sourceable Variablen
    echo "PROJECT_ID=\"$project_id\""
    echo "PROJECT_NAME=\"$project_name\""
    echo "PROJECT_PATH=\"$project_path\""
    echo "PROJECT_ID_SOURCE=\"$id_source\""
    echo "PROJECT_GIT_REMOTE=\"$git_remote\""
}

# -----------------------------------------------------------------------------
# Funktion: Gibt den Pfad zum Projekt-State-Verzeichnis zurück
# -----------------------------------------------------------------------------
get_project_state_dir() {
    eval "$(identify_project "$1")"
    local state_dir="$CHAINGUARD_HOME/projects/$PROJECT_ID"

    # Erstelle Verzeichnis falls nicht vorhanden
    mkdir -p "$state_dir"

    # Speichere Projekt-Metadaten
    cat > "$state_dir/.project-meta.json" << EOF
{
    "project_id": "$PROJECT_ID",
    "project_name": "$PROJECT_NAME",
    "project_path": "$PROJECT_PATH",
    "id_source": "$PROJECT_ID_SOURCE",
    "git_remote": "$PROJECT_GIT_REMOTE",
    "last_accessed": "$(date -Iseconds)"
}
EOF

    echo "$state_dir"
}

# -----------------------------------------------------------------------------
# CLI Interface
# -----------------------------------------------------------------------------
case "${1:-}" in
    --identify|-i)
        identify_project "${2:-}"
        ;;
    --state-dir|-s)
        get_project_state_dir "${2:-}"
        ;;
    --json|-j)
        eval "$(identify_project "${2:-}")"
        cat << EOF
{
    "project_id": "$PROJECT_ID",
    "project_name": "$PROJECT_NAME",
    "project_path": "$PROJECT_PATH",
    "id_source": "$PROJECT_ID_SOURCE"
}
EOF
        ;;
    --help|-h)
        echo "Usage: project-identifier.sh [OPTION] [PATH]"
        echo ""
        echo "Options:"
        echo "  -i, --identify    Output project variables (sourceable)"
        echo "  -s, --state-dir   Output path to project state directory"
        echo "  -j, --json        Output as JSON"
        echo "  -h, --help        Show this help"
        echo ""
        echo "If PATH is omitted, uses current working directory."
        ;;
    *)
        # Default: Output variables
        identify_project "${1:-}"
        ;;
esac
