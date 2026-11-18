#!/bin/sh
set -eu
set -- run --at "$PLEASE_EXECUTION_POINT_INPUT"
case "${PLEASE_CHECKS_ONLY-false}" in
true) set -- "$@" --checks-only ;;
false) ;;
*)
  echo "::error::checks-only must be true or false." >&2
  exit 1
  ;;
esac
# GitHub event interpretation belongs to the Action, not the CLI or consuming project.
if [ "${PLEASE_CHECKS_ONLY-false}" = false ] && [ -z "${PLEASE_CHANGE_BASE:-}" ]; then
  case "${GITHUB_EVENT_NAME:-}" in
  push | pull_request | workflow_dispatch)
    PLEASE_CHANGE_BASE="$(python3 "$ACTION_DIRECTORY/scripts/change-base.py")"
    export PLEASE_CHANGE_BASE
    ;;
  esac
fi
if [ "$PLEASE_SUMMARY" = false ]; then
  exec please "$@"
fi
exec python3 "$ACTION_DIRECTORY/scripts/summary.py"
