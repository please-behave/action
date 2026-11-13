"""Run shfmt in diff mode on all tracked *.sh files except zsh scripts; no scripts means PASS."""

import os
import subprocess
import sys


def is_zsh(path):
    """shfmt cannot parse zsh, so scripts declaring it in their shebang are skipped."""
    with open(path, "rb") as handle:
        first = handle.readline(256)
    return first.startswith(b"#!") and b"zsh" in first


def main():
    listed = subprocess.run(["git", "ls-files", "-z", "--", "*.sh"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if listed.returncode:
        raise RuntimeError("git ls-files failed")
    paths = sorted(os.fsdecode(path) for path in listed.stdout.split(b"\0") if path)
    scripts = [path for path in paths if os.path.isfile(path) and not is_zsh(path)]
    if not scripts:
        print("PASS: no shell scripts to format")
        return 0
    result = subprocess.run(["shfmt", "-d", "--", *scripts])
    if result.returncode == 0:
        print(f"PASS: shfmt found no formatting differences in {len(scripts)} scripts")
        return 0
    if result.returncode == 1:  # shfmt reports differences with exit 1.
        print("FAIL: shfmt reported formatting differences; run mise format")
        return 1
    raise RuntimeError(f"shfmt failed (exit {result.returncode})")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(2)
    except Exception as exc:  # A crash is a technical failure, never a FAIL verdict.
        print(f"ERROR: unexpected {type(exc).__name__}", file=sys.stderr)
        sys.exit(2)
