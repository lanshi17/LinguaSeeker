#!/usr/bin/env bash
# Build, smoke-test, and push the backend container image.
#
# Run from anywhere inside the repo:
#   ./scripts/deploy/build_push_backend_image.sh
#   ./scripts/deploy/build_push_backend_image.sh --tag 20260629
#   BACKEND_IMAGE=docker.io/[redacted-user]47/lingua-seeker-backend IMAGE_TAG=latest ./scripts/deploy/build_push_backend_image.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

BACKEND_IMAGE="${BACKEND_IMAGE:-docker.io/[redacted-user]47/lingua-seeker-backend}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
LOCAL_TAG="${LOCAL_TAG:-lingua-seeker-backend:local}"
PUSH_RETRIES="${PUSH_RETRIES:-3}"

PUSH_IMAGE=1
SMOKE_TEST=1

usage() {
    cat <<'USAGE'
Usage: scripts/deploy/build_push_backend_image.sh [options]

Options:
  --image IMAGE       Backend image repository. Default: docker.io/[redacted-user]47/lingua-seeker-backend
  --tag TAG           Image tag. Default: latest
  --local-tag TAG     Local image tag. Default: lingua-seeker-backend:local
  --retries N         Push retry count. Default: 3
  --no-push           Build and smoke-test only
  --no-smoke-test     Skip runtime smoke test
  -h, --help          Show this help

Required build artifacts:
  docker-artifacts/site-packages.tar.gz
  docker-artifacts/venv-bin.tar.gz

Notes:
  Docker Hub repository visibility is controlled in Docker Hub settings.
  This script pushes the image; it cannot guarantee or change private visibility.
USAGE
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --image)
            BACKEND_IMAGE="${2:?missing value for --image}"
            shift 2
            ;;
        --tag)
            IMAGE_TAG="${2:?missing value for --tag}"
            shift 2
            ;;
        --local-tag)
            LOCAL_TAG="${2:?missing value for --local-tag}"
            shift 2
            ;;
        --retries)
            PUSH_RETRIES="${2:?missing value for --retries}"
            shift 2
            ;;
        --no-push)
            PUSH_IMAGE=0
            shift
            ;;
        --no-smoke-test)
            SMOKE_TEST=0
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "ERROR: unknown option: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

REMOTE_REF="${BACKEND_IMAGE}:${IMAGE_TAG}"

require_file() {
    local path="$1"
    if [[ ! -f "$REPO_ROOT/$path" ]]; then
        echo "ERROR: missing required file: $path" >&2
        exit 1
    fi
}

require_command() {
    local command_name="$1"
    if ! command -v "$command_name" >/dev/null 2>&1; then
        echo "ERROR: required command not found: $command_name" >&2
        exit 1
    fi
}

push_with_retries() {
    local ref="$1"
    local attempts="$2"
    local attempt=1
    local sleep_seconds

    while (( attempt <= attempts )); do
        echo "Pushing $ref (attempt $attempt/$attempts)..."
        if docker push "$ref"; then
            return 0
        fi

        if (( attempt == attempts )); then
            echo "ERROR: docker push failed after $attempts attempts: $ref" >&2
            return 1
        fi

        sleep_seconds=$(( attempt * 15 ))
        echo "Push failed; retrying in ${sleep_seconds}s..."
        sleep "$sleep_seconds"
        attempt=$(( attempt + 1 ))
    done
}

require_command docker
require_file backend/Dockerfile
require_file docker-artifacts/site-packages.tar.gz
require_file docker-artifacts/venv-bin.tar.gz

if ! docker info >/dev/null 2>&1; then
    echo "ERROR: Docker daemon is not reachable." >&2
    exit 1
fi

echo "Backend image: $REMOTE_REF"
echo "Local tag:     $LOCAL_TAG"
echo "Repo root:     $REPO_ROOT"
echo ""

cd "$REPO_ROOT"

DOCKER_BUILDKIT=1 docker build \
    -f backend/Dockerfile \
    -t "$LOCAL_TAG" \
    -t "$REMOTE_REF" \
    .

if [[ "$SMOKE_TEST" -eq 1 ]]; then
    docker run --rm --entrypoint /bin/sh "$REMOTE_REF" -c \
        'test ! -e /app/docker-artifacts && /opt/venv/bin/python -c "import uvicorn, torch; print(\"runtime-ok\")"'
fi

docker image inspect "$REMOTE_REF" \
    --format 'Built image: {{index .RepoTags 0}} id={{.Id}} size={{.Size}} created={{.Created}}'

if [[ "$PUSH_IMAGE" -eq 1 ]]; then
    push_with_retries "$REMOTE_REF" "$PUSH_RETRIES"
    echo "Pushed image: $REMOTE_REF"
    echo "Remote digest is printed by docker push above."
else
    echo "Skipping push because --no-push was set."
fi
