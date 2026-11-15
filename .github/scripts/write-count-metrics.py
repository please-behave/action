"""Write lines of code and the unittest count as metrics for the Statistics workflow."""

import json
from pathlib import Path
import re
import sys


def lines_of_code(scc_report):
    return sum(language["Code"] for language in scc_report)


def test_count(log):
    ran = re.search(r"^Ran (\d+) tests? in ", log, re.MULTILINE)
    if not ran or not re.search(r"^OK\b", log, re.MULTILINE):
        raise ValueError("The unittest log does not show a successful run")
    return int(ran.group(1))


def write_metrics(scc_path, log_path, output_dir):
    metrics = {
        "loc": ("LOC", "loc", lines_of_code(json.loads(scc_path.read_text(encoding="utf-8")))),
        "tests": ("tests", "tests", test_count(log_path.read_text(encoding="utf-8"))),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    for metric_id, (label, kind, value) in metrics.items():
        metric = {"id": metric_id, "label": label, "value": value, "kind": kind, "badge": True}
        (output_dir / f"{metric_id}.json").write_text(json.dumps(metric, indent=2) + "\n", encoding="utf-8")


def main(argv):
    if len(argv) != 4:
        print("Usage: write-count-metrics.py <scc.json> <unittest.log> <output-dir>", file=sys.stderr)
        return 2
    write_metrics(Path(argv[1]), Path(argv[2]), Path(argv[3]))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except Exception as error:  # A crash is a technical failure, never a FAIL verdict.
        print(f"ERROR: {type(error).__name__}: {error}", file=sys.stderr)
        sys.exit(2)
