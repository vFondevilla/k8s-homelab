#!/usr/bin/env bash
set -Eeuo pipefail

# Override these defaults with environment variables when launching the script.
HALOGEN_IMAGE="${HALOGEN_IMAGE:-ghcr.io/peonist-ai/halogen-flash-server:0.18.5}"
HALOGEN_DOWNLOAD="${HALOGEN_DOWNLOAD:-peonist-ai/halogen-qwen3.8-flash-next}"
HALOGEN_MODELS_DIR="${HALOGEN_MODELS_DIR:-${HOME:?HOME must be set}/halogen-models}"
HALOGEN_PORT="${HALOGEN_PORT:-8731}"
HALOGEN_CONTAINER_NAME="${HALOGEN_CONTAINER_NAME:-halogen-server}"
HALOGEN_STOP_TIMEOUT="${HALOGEN_STOP_TIMEOUT:-60}"

die() {
    printf 'Error: %s\n' "$*" >&2
    exit 1
}

ACTION="${1:-start}"
[[ $# -le 1 && "$ACTION" =~ ^(start|restart|stop)$ ]] || die "Usage: $0 [start|restart|stop]"
[[ "$HALOGEN_STOP_TIMEOUT" =~ ^[0-9]{1,5}$ ]] || die 'HALOGEN_STOP_TIMEOUT must be a number of seconds between 0 and 99999.'
HALOGEN_STOP_TIMEOUT="$((10#$HALOGEN_STOP_TIMEOUT))"

command -v podman >/dev/null 2>&1 || die 'Podman is required but was not found in PATH.'

stop_server() {
    printf 'Stopping %s gracefully (timeout: %s seconds)\n' "$HALOGEN_CONTAINER_NAME" "$HALOGEN_STOP_TIMEOUT"
    podman stop --ignore --time "$HALOGEN_STOP_TIMEOUT" "$HALOGEN_CONTAINER_NAME"
}

if [[ "$ACTION" == stop ]]; then
    stop_server
    exit 0
fi

[[ -c /dev/kfd ]] || die '/dev/kfd is missing; check that the AMD GPU driver is loaded.'
[[ -d /dev/dri ]] || die '/dev/dri is missing; check that GPU devices are available.'

# Bound the length before arithmetic to avoid overflow or interpreting expressions.
[[ "$HALOGEN_PORT" =~ ^[0-9]{1,5}$ ]] || die 'HALOGEN_PORT must be an integer between 1 and 65535.'
(( 10#$HALOGEN_PORT >= 1 && 10#$HALOGEN_PORT <= 65535 )) || die 'HALOGEN_PORT must be between 1 and 65535.'
HALOGEN_PORT="$((10#$HALOGEN_PORT))"

mkdir -p -- "$HALOGEN_MODELS_DIR" || die "Cannot create model directory: $HALOGEN_MODELS_DIR"
# Resolve relative paths so Podman always receives a host directory mount.
HALOGEN_MODELS_DIR="$(cd -- "$HALOGEN_MODELS_DIR" && pwd -P)"
[[ -w "$HALOGEN_MODELS_DIR" ]] || die "Model directory is not writable: $HALOGEN_MODELS_DIR"
[[ "$HALOGEN_MODELS_DIR" != *:* ]] || die 'The model directory path cannot contain a colon.'

# Complete startup checks before stopping the current server. Podman waits for
# shutdown and sends SIGKILL only if the graceful shutdown timeout expires.
if [[ "$ACTION" == restart ]]; then
    stop_server
fi

printf 'Starting Halogen on port %s using %s\n' "$HALOGEN_PORT" "$HALOGEN_IMAGE"
printf 'Model: %s\nModel directory: %s\n' "$HALOGEN_DOWNLOAD" "$HALOGEN_MODELS_DIR"

# Replace the shell so interrupt/termination signals reach Podman directly.
exec podman run --rm \
    --name "$HALOGEN_CONTAINER_NAME" \
    --stop-signal SIGTERM \
    --stop-timeout "$HALOGEN_STOP_TIMEOUT" \
    --publish "${HALOGEN_PORT}:8731" \
    --device /dev/kfd \
    --device /dev/dri \
    --group-add keep-groups \
    --ipc=host \
    --ulimit memlock=-1:-1 \
    --env "HALOGEN_DOWNLOAD=${HALOGEN_DOWNLOAD}" \
    --volume "${HALOGEN_MODELS_DIR}:/models" \
    "$HALOGEN_IMAGE"
