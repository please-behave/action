"""Refuse publication without tested main and CLI assets."""
import json
import os
from pathlib import Path
import subprocess
import sys


def gh(*args):
    return json.loads(subprocess.check_output(["gh", *args], text=True))


def verify(head, expected, remote, release, version):
    if head != expected or head != remote:
        raise ValueError("main moved since validation; dispatch the release again.")
    if release["draft"] or release["prerelease"] or release["tag_name"] != version:
        raise ValueError(f"The public stable CLI {version} release is required.")
    assets = {a["name"] for a in release["assets"] if a["state"] == "uploaded" and a["size"] > 0}
    required = {"SHA256SUMS", f"please-{version}-x86_64-unknown-linux-gnu.tar.gz",
                f"please-{version}-aarch64-unknown-linux-gnu.tar.gz"}
    if not required <= assets:
        raise ValueError(f"CLI {version} is missing required Linux release assets.")


def main():
    version = Path(".please-version").read_text().strip()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    remote = gh("api", "repos/please-behave/action/git/ref/heads/main")["object"]["sha"]
    release = gh("api", f"repos/please-behave/cli/releases/tags/{version}")
    verify(head, os.environ["GITHUB_SHA"], remote, release, version)
    print("Tested main and public CLI release assets confirmed.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        sys.exit(f"Release readiness failed: {error}")
