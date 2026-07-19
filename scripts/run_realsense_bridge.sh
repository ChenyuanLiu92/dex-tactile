#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

ENV_FILE="${DEX_ENV_FILE:-$ROOT_DIR/.env}"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ENV_FILE"
  set +a
fi

BUILD_SCRIPT="${D435_BRIDGE_BUILD_SCRIPT:-$ROOT_DIR/dex-retargeting/viewer/native/build_realsense_bridge.sh}"
BINARY="${D435_BRIDGE_BINARY:-}"
if [[ -z "$BINARY" ]]; then
  BINARY="$($BUILD_SCRIPT)"
fi

SOCKET_PATH="${D435_BRIDGE_SOCKET:-/tmp/dex-realsense-rgb.sock}"
WIDTH="${D435_WIDTH:-1280}"
HEIGHT="${D435_HEIGHT:-720}"
FPS="${D435_FPS:-30}"
JPEG_QUALITY="${D435_JPEG_QUALITY:-82}"
SUDO_COMMAND="${D435_SUDO:-sudo}"

args=(
  --socket "$SOCKET_PATH"
  --width "$WIDTH"
  --height "$HEIGHT"
  --fps "$FPS"
  --jpeg-quality "$JPEG_QUALITY"
)
if [[ -n "${D435_SERIAL:-}" ]]; then
  args+=(--serial "$D435_SERIAL")
fi

exec "$SUDO_COMMAND" "$BINARY" "${args[@]}"
