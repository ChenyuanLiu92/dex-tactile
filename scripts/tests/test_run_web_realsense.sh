#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
grep -q "DEX_WEB_RUNNER" "$ROOT_DIR/scripts/run_web.sh"
TMP_DIR="$(mktemp -d /tmp/dex-run-web.XXXXXX)"
EVENTS="$TMP_DIR/events"
SOCKET_PATH="$TMP_DIR/rgb.sock"
HELPER_PID_FILE="$TMP_DIR/helper.pid"

cleanup() {
  if [[ -f "$HELPER_PID_FILE" ]]; then
    kill "$(cat "$HELPER_PID_FILE")" 2>/dev/null || true
  fi
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

cat >"$TMP_DIR/fake_sudo" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == "-v" ]]; then
  echo sudo >>"$TEST_EVENTS"
  exit 0
fi
exec "$@"
EOF

cat >"$TMP_DIR/fake_helper.py" <<'EOF'
#!/usr/bin/env python3
import os
import signal
import socket
import time

path = os.environ["D435_BRIDGE_SOCKET"]
events = os.environ["TEST_EVENTS"]
pid_file = os.environ["TEST_HELPER_PID"]
running = True

def stop(_signum, _frame):
    global running
    running = False

signal.signal(signal.SIGTERM, stop)
server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
server.bind(path)
with open(events, "a", encoding="ascii") as stream:
    stream.write("helper\n")
with open(pid_file, "w", encoding="ascii") as stream:
    stream.write(str(os.getpid()))
while running:
    time.sleep(0.01)
server.close()
EOF

cat >"$TMP_DIR/fake_build" <<EOF
#!/usr/bin/env bash
set -euo pipefail
echo "$TMP_DIR/fake_helper.py"
EOF

cat >"$TMP_DIR/fake_viewer" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
[[ -S "$D435_BRIDGE_SOCKET" ]]
for _ in {1..100}; do
  [[ -f "$TEST_HELPER_PID" ]] && break
  sleep 0.01
done
[[ -f "$TEST_HELPER_PID" ]]
echo viewer >>"$TEST_EVENTS"
EOF

chmod +x \
  "$TMP_DIR/fake_sudo" \
  "$TMP_DIR/fake_helper.py" \
  "$TMP_DIR/fake_build" \
  "$TMP_DIR/fake_viewer"

TEST_EVENTS="$EVENTS" \
TEST_HELPER_PID="$HELPER_PID_FILE" \
DEX_ENV_FILE=/dev/null \
D435_CAMERA_SOURCE=realsense \
D435_BRIDGE_SOCKET="$SOCKET_PATH" \
D435_SUDO="$TMP_DIR/fake_sudo" \
D435_BRIDGE_BUILD_SCRIPT="$TMP_DIR/fake_build" \
DEX_WEB_RUNNER="$TMP_DIR/fake_viewer" \
"$ROOT_DIR/scripts/run_web.sh"

[[ "$(cat "$EVENTS")" == $'sudo\nhelper\nviewer' ]]
[[ ! -e "$SOCKET_PATH" ]]
HELPER_PID="$(cat "$HELPER_PID_FILE")"
! kill -0 "$HELPER_PID" 2>/dev/null

echo "run_web RealSense lifecycle test passed"
