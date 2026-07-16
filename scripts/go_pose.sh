#!/usr/bin/env bash
set -euo pipefail

usage() {
  printf 'Usage: ./scripts/go_pose.sh {home|open}\n' >&2
  exit 2
}

[[ $# -eq 1 ]] || usage
case "$1" in
  home|open) POSE="$1" ;;
  *) usage ;;
esac

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PROJECT_ROOT="${WORKSPACE_ROOT}/dex-retargeting"
BASE_URL="${RH56_VIEWER_URL:-http://127.0.0.1:8787/vision}"

cd "${WORKSPACE_ROOT}"
if [[ -f "${WORKSPACE_ROOT}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${WORKSPACE_ROOT}/.env"
  set +a
fi
unset VIRTUAL_ENV
export PYTHONPATH="${PROJECT_ROOT}${PYTHONPATH:+:${PYTHONPATH}}"
exec uv run python -m viewer.backend.preset_cli \
  "${POSE}" --viewer-url "${BASE_URL%/}"
