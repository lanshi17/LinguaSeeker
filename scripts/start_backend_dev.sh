#!/usr/bin/env bash
# ── Lingua Seeker Backend — Development Server ──────────────────────────────
# Starts uvicorn with hot-reload, excluding files that change during pipeline
# execution (logs, temp data, migrations) so that editing state_persistence
# or running a pipeline doesn't kill in-flight requests.
#
# Optionally starts Postgres and Redis containers before the backend.
#
# Usage:
#   ./scripts/start_backend_dev.sh                        # uvicorn only, default port 8000
#   ./scripts/start_backend_dev.sh --port 8001            # custom port
#   ./scripts/start_backend_dev.sh --with-infra           # start postgres + redis, then uvicorn
#   ./scripts/start_backend_dev.sh --with-infra --port 8001
#
#   # Infra management only (no backend):
#   ./scripts/start_backend_dev.sh --infra up -d          # start postgres + redis
#   ./scripts/start_backend_dev.sh --infra down            # stop postgres + redis
#   ./scripts/start_backend_dev.sh --infra logs -f         # follow infra logs
#   ./scripts/start_backend_dev.sh --infra status           # show infra status
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="$PROJECT_ROOT/deploy/compose/dev-infra/docker-compose.yml"

WITH_INFRA=false
INFRA_ONLY=false
INFRA_ACTION=""
INFRA_ARGS=()

# ── Detect docker compose command ───────────────────────────────────────────
detect_compose() {
    if docker compose version &>/dev/null; then
        echo "docker compose"
    elif command -v docker-compose &>/dev/null; then
        echo "docker-compose"
    else
        echo ""
    fi
}

# ── Start infra containers and wait for health ──────────────────────────────
start_infra() {
    local compose_cmd
    compose_cmd="$(detect_compose)"
    if [[ -z "$compose_cmd" ]]; then
        echo "Error: neither 'docker compose' (v2) nor 'docker-compose' (v1) found." >&2
        exit 1
    fi

    echo "Starting dev infrastructure (Postgres + Redis)..."
    $compose_cmd -f "$COMPOSE_FILE" up -d

    # Wait for both services to become healthy
    echo -n "Waiting for Postgres"
    local retries=30
    while (( retries > 0 )); do
        if $compose_cmd -f "$COMPOSE_FILE" ps postgres 2>/dev/null | grep -q "(healthy)"; then
            echo " ✓"
            break
        fi
        sleep 1
        (( retries-- ))
        echo -n "."
    done
    if (( retries == 0 )); then
        echo " ✗ (timeout)" >&2
        echo "Check logs: $compose_cmd -f $COMPOSE_FILE logs postgres" >&2
        exit 1
    fi

    echo -n "Waiting for Redis"
    retries=30
    while (( retries > 0 )); do
        if $compose_cmd -f "$COMPOSE_FILE" ps redis 2>/dev/null | grep -q "(healthy)"; then
            echo " ✓"
            break
        fi
        sleep 1
        (( retries-- ))
        echo -n "."
    done
    if (( retries == 0 )); then
        echo " ✗ (timeout)" >&2
        echo "Check logs: $compose_cmd -f $COMPOSE_FILE logs redis" >&2
        exit 1
    fi

    echo "Dev infrastructure is ready."
}

# ── Run infra subcommand ────────────────────────────────────────────────────
run_infra_cmd() {
    local compose_cmd
    compose_cmd="$(detect_compose)"
    if [[ -z "$compose_cmd" ]]; then
        echo "Error: neither 'docker compose' (v2) nor 'docker-compose' (v1) found." >&2
        exit 1
    fi

    case "$INFRA_ACTION" in
        up)
            start_infra
            ;;
        down)
            echo "Stopping dev infrastructure..."
            $compose_cmd -f "$COMPOSE_FILE" down "${INFRA_ARGS[@]}"
            ;;
        logs)
            $compose_cmd -f "$COMPOSE_FILE" logs "${INFRA_ARGS[@]}"
            ;;
        restart)
            echo "Restarting dev infrastructure..."
            $compose_cmd -f "$COMPOSE_FILE" restart "${INFRA_ARGS[@]}"
            ;;
        status|ps)
            echo "── Dev Infrastructure ──"
            $compose_cmd -f "$COMPOSE_FILE" ps "${INFRA_ARGS[@]}"
            ;;
        *)
            echo "Error: unknown infra action '$INFRA_ACTION'" >&2
            echo "Available actions: up, down, logs, restart, status" >&2
            exit 1
            ;;
    esac
}

# ── Parse arguments ─────────────────────────────────────────────────────────
UVICORN_ARGS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --with-infra)
            WITH_INFRA=true
            shift
            ;;
        --infra)
            INFRA_ONLY=true
            shift
            # Capture the action and remaining args for infra
            if [[ $# -gt 0 ]]; then
                INFRA_ACTION="$1"
                shift
                while [[ $# -gt 0 ]]; do
                    case "$1" in
                        -d|--build|--force-recreate|--remove-orphans|-f|--follow|--tail|--no-color)
                            INFRA_ARGS+=("$1")
                            shift
                            ;;
                        *)
                            INFRA_ARGS+=("$1")
                            shift
                            ;;
                    esac
                done
            fi
            ;;
        *)
            UVICORN_ARGS+=("$1")
            shift
            ;;
    esac
done

# ── Infra-only mode ────────────────────────────────────────────────────────
if [[ "$INFRA_ONLY" == true ]]; then
    if [[ -z "$INFRA_ACTION" ]]; then
        echo "Error: --infra requires an action (up, down, logs, restart, status)" >&2
        exit 1
    fi
    run_infra_cmd
    exit 0
fi

# ── Start infra if requested ───────────────────────────────────────────────
if [[ "$WITH_INFRA" == true ]]; then
    start_infra
fi

# ── Start backend dev server ───────────────────────────────────────────────
cd "$PROJECT_ROOT/backend"

exec uv run uvicorn app.main:app \
    --host 127.0.0.1 \
    --reload \
    --reload-dir src \
    --reload-dir app \
    --reload-exclude "logs/*" \
    --reload-exclude "*.log" \
    --reload-exclude "__pycache__" \
    --reload-exclude ".venv" \
    --reload-exclude "database/migrations/*" \
    --reload-exclude "*.pyc" \
    --timeout-graceful-shutdown 120 \
    "${UVICORN_ARGS[@]}"
