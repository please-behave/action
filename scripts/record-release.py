"""Record a release fact with the gateway and report the outcome in the Job Summary."""

import os
import subprocess

from summary import append_summary, command_data, escape, warning

OUTCOMES = {"Release recorded.": "Recorded", "Release already known.": "Unchanged"}
CONFLICT = "conflicts with a recorded commit"


def record(gateway_url, version, commit):
    command = ["please", "record", "release", f"--gateway-url={gateway_url}", f"--version={version}"]
    if commit:
        command.append(f"--commit={commit}")
    try:
        # Diagnostics may contain the secret origin, so only known outcomes are reported.
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding="utf-8", errors="replace", check=False)
    except (OSError, ValueError):
        return None, "Unable to start please record release."
    outcome = next((OUTCOMES[line] for line in result.stdout.splitlines() if line in OUTCOMES), None)
    if result.returncode == 0 and outcome:
        return outcome, None
    if CONFLICT in result.stderr:
        return "Conflict", "The version conflicts with a release recorded for another commit."
    return None, f"please record release exited unsuccessfully (exit status {result.returncode})."


def main():
    version = os.environ.get("PLEASE_RELEASE_VERSION", "")
    commit = os.environ.get("PLEASE_RELEASE_COMMIT", "")
    gateway_url = os.environ.pop("PLEASE_GATEWAY_URL_INPUT", "")
    if gateway_url:
        print(f"::add-mask::{command_data(gateway_url)}", flush=True)
    if not version:
        print("::error::release-version is required when release-commit is set.", flush=True)
        return 1
    heading = f"\n## Release {escape(version)}\n\n"
    failure = None
    if not gateway_url:
        print("::notice::Please Behave release not recorded: gateway-url is empty.", flush=True)
        line = "Release recording skipped: the gateway-url input is empty."
    else:
        outcome, failure = record(gateway_url, version, commit)
        line = f"Release recording: **{outcome or 'Failed'}.**" + (f" {failure}" if failure else "")
        if failure:
            print(f"::warning::Please Behave release recording failed. {command_data(failure)}", flush=True)
    try:
        append_summary([heading, line + "\n\n"])
    except Exception as error:
        warning(f"could not append GITHUB_STEP_SUMMARY: {error}")
    return 1 if failure and os.environ.get("PLEASE_PUBLISH_REQUIRED") == "true" else 0


if __name__ == "__main__":
    raise SystemExit(main())
