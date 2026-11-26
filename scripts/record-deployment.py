"""Record a deployment fact with the gateway and report the outcome in the Job Summary."""

import os

from record_fact import report, run
from summary import escape

OUTCOMES = {"Deployment recorded.": "Recorded", "Deployment unchanged.": "Unchanged"}
FAILURES = {"Deployment target is unknown": ("Unknown target", "The target is not registered for the authenticated sender.")}


def main():
    target = os.environ.get("PLEASE_DEPLOYMENT_TARGET", "")
    repository = os.environ.get("PLEASE_DEPLOYMENT_REPOSITORY", "")
    version = os.environ.get("PLEASE_DEPLOYMENT_VERSION", "")
    commit = os.environ.get("PLEASE_DEPLOYMENT_COMMIT", "")
    if not target or not repository or bool(version) == bool(commit):
        print(
            "::error::A deployment requires deployment-target, deployment-repository and exactly one of deployment-version and deployment-commit.",
            flush=True,
        )
        return 1

    def record(gateway_url):
        command = ["please", "record", "deployment", f"--gateway-url={gateway_url}", f"--target={target}", f"--repository={repository}"]
        command.append(f"--version={version}" if version else f"--commit={commit}")
        return run(command, OUTCOMES, FAILURES)

    return report("deployment", f"\n## Deployment to {escape(target)}\n\n", record)


if __name__ == "__main__":
    raise SystemExit(main())
