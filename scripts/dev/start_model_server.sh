#!/usr/bin/env bash
# ── Lingua Seeker Model Server ──────────────────────────────────────────────
# Unified launcher for the model server (embedding, rerank, VLM, doc-parse).
# Supports two modes:
#   local  — run directly via uv (single-process, shares one GPU)
#   docker — start 4 independent containers via docker compose
#
# Usage:
#   # ── Local mode (default) ──
#   ./scripts/start_model_server.sh                         # port 8001
#   ./scripts/start_model_server.sh --port 8002             # custom port
#   ./scripts/start_model_server.sh --mode local --port 8002
#
#   # ── Docker mode ──
#   ./scripts/start_model_server.sh --mode docker up        # start all containers
#   ./scripts/start_model_server.sh --mode docker up -d     # detached
#   ./scripts/start_model_server.sh --mode docker down      # stop all containers
#   ./scripts/start_model_server.sh --mode docker logs -f   # follow logs
#   ./scripts/start_model_server.sh --mode docker status    # show container status
#   ./scripts/start_model_server.sh --mode docker ps        # alias for status
#
#   # Selective service startup (docker mode only):
#   ./scripts/start_model_server.sh --mode docker up embedding rerank
#   ./scripts/start_model_server.sh --mode docker logs vlm
#
# Available docker services: embedding, rerank, vlm, doc-parse
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
MODEL_SERVER_DIR="$PROJECT_ROOT/services/model-server"
COMPOSE_FILE="$MODEL_SERVER_DIR/docker-compose.model-server.yml"

# ── Defaults ────────────────────────────────────────────────────────────────
MODE="local"
ACTION=""
SERVICES=()
EXTRA_ARGS=()

# ── Docker service name mapping ─────────────────────────────────────────────
# Maps short names to compose service names.
resolve_service_name() {
    case "$1" in
        embedding)   echo "model-embedding" ;;
        rerank)      echo "model-rerank" ;;
        vlm)         echo "model-vlm" ;;
        doc-parse)   echo "model-doc-parse" ;;
        model-*)     echo "$1" ;;  # already full name
        *)           echo "$1" ;;  # pass through, compose will validate
    esac
}

# ── Parse arguments ─────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case "$1" in
        --mode)
            MODE="$2"
            shift 2
            ;;
        --mode=*)
            MODE="${1#--mode=}"
            shift
            ;;
        # Docker subcommands — everything after is either a service name or extra arg
        up|down|logs|restart|ps|status)
            ACTION="$1"
            shift
            # Remaining args: service short names or docker compose flags
            while [[ $# -gt 0 ]]; do
                case "$1" in
                    embedding|rerank|vlm|doc-parse)
                        SERVICES+=("$(resolve_service_name "$1")")
                        shift
                        ;;
                    model-embedding|model-rerank|model-vlm|model-doc-parse)
                        SERVICES+=("$1")
                        shift
                        ;;
                    -d|--build|--force-recreate|--remove-orphans|-f|--follow|--tail|--no-color)
                        EXTRA_ARGS+=("$1")
                        shift
                        ;;
                    *)
                        EXTRA_ARGS+=("$1")
                        shift
                        ;;
                esac
            done
            ;;
        *)
            EXTRA_ARGS+=("$1")
            shift
            ;;
    esac
done

# ── Validate mode ───────────────────────────────────────────────────────────
if [[ "$MODE" != "local" && "$MODE" != "docker" ]]; then
    echo "Error: --mode must be 'local' or 'docker', got '$MODE'" >&2
    exit 1
fi

# ── Docker mode ─────────────────────────────────────────────────────────────
if [[ "$MODE" == "docker" ]]; then
    if [[ ! -f "$COMPOSE_FILE" ]]; then
        echo "Error: compose file not found: $COMPOSE_FILE" >&2
        exit 1
    fi

    # Default action
    if [[ -z "$ACTION" ]]; then
        ACTION="up"
        EXTRA_ARGS+=("-d")
    fi

    # Detect docker compose v2 plugin vs legacy docker-compose v1
    if docker compose version &>/dev/null; then
        COMPOSE_CMD=(docker compose -f "$COMPOSE_FILE")
    elif command -v docker-compose &>/dev/null; then
        COMPOSE_CMD=(docker-compose -f "$COMPOSE_FILE")
    else
        echo "Error: neither 'docker compose' (v2 plugin) nor 'docker-compose' (v1) found." >&2
        exit 1
    fi

    case "$ACTION" in
        up)
            echo "Starting model server containers..."
            "${COMPOSE_CMD[@]}" up "${EXTRA_ARGS[@]}" "${SERVICES[@]}"
            if [[ " ${EXTRA_ARGS[*]} " == *" -d "* ]] || [[ " ${EXTRA_ARGS[*]} " == *" --detach "* ]]; then
                echo ""
                echo "Containers started. Check status with:"
                echo "  $0 --mode docker status"
                echo "  $0 --mode docker logs -f"
            fi
            ;;
        down)
            echo "Stopping model server containers..."
            "${COMPOSE_CMD[@]}" down "${EXTRA_ARGS[@]}"
            ;;
        logs)
            "${COMPOSE_CMD[@]}" logs "${EXTRA_ARGS[@]}" "${SERVICES[@]}"
            ;;
        restart)
            echo "Restarting model server containers..."
            "${COMPOSE_CMD[@]}" restart "${EXTRA_ARGS[@]}" "${SERVICES[@]}"
            ;;
        status|ps)
            echo "── Model Server Containers ──"
            "${COMPOSE_CMD[@]}" ps "${EXTRA_ARGS[@]}" "${SERVICES[@]}"
            ;;
        *)
            echo "Error: unknown docker action '$ACTION'" >&2
            echo "Available actions: up, down, logs, restart, status" >&2
            exit 1
            ;;
    esac
    exit 0
fi

# ── Local mode ──────────────────────────────────────────────────────────────
cd "$MODEL_SERVER_DIR"
exec uv run python main.py "${EXTRA_ARGS[@]}"
