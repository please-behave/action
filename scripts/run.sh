#!/usr/bin/env bash
set -euo pipefail
args=(run --at "$PLEASE_EXECUTION_POINT_INPUT")
case "${PLEASE_CHECKS_ONLY-false}" in
  true) args+=(--checks-only) ;;
  false) ;;
  *) echo "::error::checks-only must be true or false." >&2; exit 1 ;;
esac
if [[ "$PLEASE_SUMMARY" == false ]]; then
  exec please "${args[@]}"
fi
exec python3 "$ACTION_DIRECTORY/scripts/summary.py"
