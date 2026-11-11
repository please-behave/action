"""Require the public stable CLI assets consumed by the Action."""
import json
from pathlib import Path
import subprocess
import sys
import tomllib


def gh(*args):
    return json.loads(subprocess.check_output(["gh", *args], text=True))


def verify(release, version):
    if release["draft"] or release["prerelease"] or release["tag_name"] != version:
        raise ValueError(f"The public stable CLI {version} release is required.")
    assets = {a["name"] for a in release["assets"] if a["state"] == "uploaded" and a["size"] > 0}
    required = {"SHA256SUMS", f"please-{version}-x86_64-unknown-linux-gnu.tar.gz",
                f"please-{version}-aarch64-unknown-linux-gnu.tar.gz",
                f"please-{version}-x86_64-apple-darwin.tar.gz",
                f"please-{version}-aarch64-apple-darwin.tar.gz"}
    if not required <= assets:
        raise ValueError(f"CLI {version} is missing required Linux/macOS release assets.")


def main():
    version = "v" + tomllib.loads(Path("mise.toml").read_text())["tools"]["github:please-behave/cli"]
    release = gh("api", f"repos/please-behave/cli/releases/tags/{version}")
    verify(release, version)
    print("Public stable CLI release assets confirmed.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        sys.exit(f"Release readiness failed: {error}")
