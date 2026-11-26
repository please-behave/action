"""Shared delivery of recorded facts with the CLI and reporting in the Job Summary."""

import os
import subprocess

from summary import append_summary, command_data, warning


def run(command, outcomes, failures):
    """Return (outcome, failure); only known stdout lines and stderr markers are reported."""
    try:
        # Diagnostics may contain the secret origin, so only known outcomes are reported.
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding="utf-8", errors="replace", check=False)
    except (OSError, ValueError):
        return None, f"Unable to start {' '.join(command[:3])}."
    outcome = next((outcomes[line] for line in result.stdout.splitlines() if line in outcomes), None)
    if result.returncode == 0 and outcome:
        return outcome, None
    for marker, (label, message) in failures.items():
        if marker in result.stderr:
            return label, message
    return None, f"{' '.join(command[:3])} exited unsuccessfully (exit status {result.returncode})."


def report(fact, heading, record):
    """Record through `record(gateway_url)` and return the step's exit code."""
    gateway_url = os.environ.pop("PLEASE_GATEWAY_URL_INPUT", "")
    if gateway_url:
        print(f"::add-mask::{command_data(gateway_url)}", flush=True)
    failure = None
    if not gateway_url:
        print(f"::notice::Please Behave {fact} not recorded: gateway-url is empty.", flush=True)
        line = f"{fact.capitalize()} recording skipped: the gateway-url input is empty."
    else:
        outcome, failure = record(gateway_url)
        line = f"{fact.capitalize()} recording: **{outcome or 'Failed'}.**" + (f" {failure}" if failure else "")
        if failure:
            print(f"::warning::Please Behave {fact} recording failed. {command_data(failure)}", flush=True)
    try:
        append_summary([heading, line + "\n\n"])
    except Exception as error:
        warning(f"could not append GITHUB_STEP_SUMMARY: {error}")
    return 1 if failure and os.environ.get("PLEASE_PUBLISH_REQUIRED") == "true" else 0
