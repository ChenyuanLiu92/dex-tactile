#!/usr/bin/env bash
set -euo pipefail

NATIVE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_SCRIPT="$NATIVE_DIR/build_realsense_bridge.sh"
BINARY="$NATIVE_DIR/build/realsense_rgb_bridge"
SOCKET_PATH="/tmp/dex-rgb-invalid-$$.sock"

"$BUILD_SCRIPT"

"$BINARY" --help | grep -q "RealSense RGB bridge"

if "$BINARY" --socket "$SOCKET_PATH" --jpeg-quality 101 >/dev/null 2>&1; then
  echo "invalid JPEG quality unexpectedly succeeded" >&2
  exit 1
fi

if [[ -e "$SOCKET_PATH" ]]; then
  echo "invalid arguments left a socket behind" >&2
  exit 1
fi

echo "RealSense bridge CLI smoke test passed"
