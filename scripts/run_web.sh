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
unset VIRTUAL_ENV

CAMERA_SOURCE="${D435_CAMERA_SOURCE:-avfoundation}"
BRIDGE_SOCKET="${D435_BRIDGE_SOCKET:-/tmp/dex-realsense-rgb.sock}"
BRIDGE_PID=""

cleanup() {
  if [[ -n "$BRIDGE_PID" ]]; then
    kill "$BRIDGE_PID" 2>/dev/null || true
    wait "$BRIDGE_PID" 2>/dev/null || true
  fi
  if [[ "$CAMERA_SOURCE" == "realsense" && "${D435_BRIDGE_EXTERNAL:-0}" != "1" ]]; then
    rm -f "$BRIDGE_SOCKET"
  fi
}
trap cleanup EXIT
trap 'exit 130' INT TERM

if [[ "$CAMERA_SOURCE" == "realsense" && "${D435_BRIDGE_EXTERNAL:-0}" != "1" ]]; then
  BUILD_SCRIPT="${D435_BRIDGE_BUILD_SCRIPT:-$ROOT_DIR/dex-retargeting/viewer/native/build_realsense_bridge.sh}"
  export D435_BRIDGE_BINARY="${D435_BRIDGE_BINARY:-$($BUILD_SCRIPT)}"
  export D435_BRIDGE_SOCKET="$BRIDGE_SOCKET"
  SUDO_COMMAND="${D435_SUDO:-sudo}"

  echo "RealSense RGB requires macOS USB elevation."
  "$SUDO_COMMAND" -v
  "$ROOT_DIR/scripts/run_realsense_bridge.sh" &
  BRIDGE_PID=$!

  for _ in {1..100}; do
    if [[ -S "$BRIDGE_SOCKET" ]]; then
      break
    fi
    if ! kill -0 "$BRIDGE_PID" 2>/dev/null; then
      wait "$BRIDGE_PID" || true
      echo "RealSense RGB bridge exited before becoming ready" >&2
      exit 1
    fi
    sleep 0.1
  done
  if [[ ! -S "$BRIDGE_SOCKET" ]]; then
    echo "Timed out waiting for RealSense RGB bridge socket: $BRIDGE_SOCKET" >&2
    exit 1
  fi
fi

if [[ -n "${DEX_WEB_RUNNER:-}" ]]; then
  "$DEX_WEB_RUNNER" "$@"
else
  uv run python -m unified_web.run "$@"
fi
