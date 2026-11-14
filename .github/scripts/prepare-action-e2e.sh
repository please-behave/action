#!/usr/bin/env bash
# Build the isolated governance fixture and capture each candidate invocation summary.
set -euo pipefail

echo "REAL_PYTHON=$(command -v python3)" >>"$GITHUB_ENV"
mv .please "$RUNNER_TEMP/original-please"
mkdir -p .please/checks/fixture "$RUNNER_TEMP/summary-tools"
cat >.please/config.toml <<'EOF'
project = "Summary acceptance"
[execution_points]
custom = ["summary-first", "summary-second"]
EOF
cat >.please/checks/fixture/rule.toml <<'EOF'
id = "fixture"
description = "Hosted composite summary acceptance"
run_at = ["summary-first", "summary-second"]
[check]
command = "bash -c 'exit ${FIXTURE_RESULT:-0}'"
EOF
# Preserve a copy of the actual composite step summary before runner upload.
cat >"$RUNNER_TEMP/summary-tools/python3" <<'EOF'
#!/usr/bin/env bash
"$REAL_PYTHON" "$@"
result=$?
if [[ "$1" == */scripts/summary.py ]]; then
  cp "$GITHUB_STEP_SUMMARY" "$RUNNER_TEMP/$PLEASE_EXECUTION_POINT_INPUT.md"
fi
exit "$result"
EOF
chmod +x "$RUNNER_TEMP/summary-tools/python3"
echo "$RUNNER_TEMP/summary-tools" >>"$GITHUB_PATH"
