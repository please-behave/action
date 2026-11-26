"""Record a release fact with the gateway and report the outcome in the Job Summary."""

import os

from record_fact import report, run
from summary import escape

OUTCOMES = {"Release recorded.": "Recorded", "Release already known.": "Unchanged"}
FAILURES = {"conflicts with a recorded commit": ("Conflict", "The version conflicts with a release recorded for another commit.")}


def main():
    version = os.environ.get("PLEASE_RELEASE_VERSION", "")
    commit = os.environ.get("PLEASE_RELEASE_COMMIT", "")
    if not version:
        print("::error::release-version is required when release-commit is set.", flush=True)
        return 1

    def record(gateway_url):
        command = ["please", "record", "release", f"--gateway-url={gateway_url}", f"--version={version}"]
        if commit:
            command.append(f"--commit={commit}")
        return run(command, OUTCOMES, FAILURES)

    return report("release", f"\n## Release {escape(version)}\n\n", record)


if __name__ == "__main__":
    raise SystemExit(main())
