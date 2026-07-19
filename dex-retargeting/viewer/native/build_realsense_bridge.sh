#!/usr/bin/env bash
set -euo pipefail

NATIVE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="$NATIVE_DIR/build"
SOURCE="$NATIVE_DIR/realsense_rgb_bridge.cpp"
OUTPUT="$BUILD_DIR/realsense_rgb_bridge"
REALSENSE_PREFIX="$(brew --prefix librealsense)"
JPEG_PREFIX="$(brew --prefix jpeg-turbo)"

mkdir -p "$BUILD_DIR"

clang++ \
  -std=c++17 \
  -O2 \
  -Wall \
  -Wextra \
  -Werror \
  "$SOURCE" \
  -isystem "$REALSENSE_PREFIX/include" \
  -isystem "$JPEG_PREFIX/include" \
  -L"$REALSENSE_PREFIX/lib" \
  -L"$JPEG_PREFIX/lib" \
  -Wl,-rpath,"$REALSENSE_PREFIX/lib" \
  -Wl,-rpath,"$JPEG_PREFIX/lib" \
  -lrealsense2 \
  -lturbojpeg \
  -o "$OUTPUT"

echo "$OUTPUT"
