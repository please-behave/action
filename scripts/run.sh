#!/usr/bin/env bash
set -euo pipefail
if [[ "$PLEASE_SUMMARY" == false ]]; then
  exec please run --at "$PLEASE_EXECUTION_POINT_INPUT"
fi
exec python3 "$ACTION_DIRECTORY/scripts/summary.py"
