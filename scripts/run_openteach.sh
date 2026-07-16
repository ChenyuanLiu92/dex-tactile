#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: ./scripts/run_openteach.sh [--live] [HYDRA_OVERRIDE ...]

  default   Receive Quest keypoints and compute targets without Modbus writes.
  --live    Enable RH56DFTP Modbus output. Stop the Web Viewer first.
EOF
}

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT_DIR/.env"
  set +a
fi

LIVE=false
if [[ "${1:-}" == "--live" ]]; then
  LIVE=true
  shift
elif [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi

if [[ -z "${OPENTEACH_HOST:-}" ]]; then
  printf 'OPENTEACH_HOST is not set. Add the Quest-reachable workstation IP to .env.\n' >&2
  exit 2
fi

args=(robot=inspire_hand)
if [[ "$LIVE" == true ]]; then
  if [[ -z "${RH56_HOST:-}" ]]; then
    printf 'RH56_HOST is not set. Add the hand IP to .env.\n' >&2
    exit 2
  fi
  printf '%s\n' 'LIVE MODBUS OUTPUT ENABLED. Stop Viewer and keep physical power removal accessible.'
  args+=(robot.operators.0.robot.dry_run=false)
else
  printf '%s\n' 'Open-Teach dry-run: no Modbus writes will be issued.'
fi

cd "$ROOT_DIR/Open-Teach"
unset VIRTUAL_ENV
exec uv run --project "$ROOT_DIR" python teleop.py "${args[@]}" "$@"
