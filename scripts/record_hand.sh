#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${WORKSPACE_ROOT}"
if [[ -f "${WORKSPACE_ROOT}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${WORKSPACE_ROOT}/.env"
  set +a
fi
unset VIRTUAL_ENV
exec uv run python -m hand_data_collection.cli "$@"
