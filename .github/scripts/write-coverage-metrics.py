"""Write the coverage.py total as a metric for the Statistics workflow."""

import json
from pathlib import Path
import sys


def percentage(report):
    return round(float(report["totals"]["percent_covered"]), 2)


def write_metrics(report_path, output_dir):
    value = percentage(json.loads(report_path.read_text(encoding="utf-8"))) if report_path.exists() else None
    metric = {"id": "coverage", "label": "coverage", "value": value, "kind": "percent", "badge": True}
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "coverage.json").write_text(json.dumps(metric, indent=2) + "\n", encoding="utf-8")


def main(argv):
    if len(argv) != 3:
        print("Usage: write-coverage-metrics.py <coverage.json> <output-dir>", file=sys.stderr)
        return 2
    write_metrics(Path(argv[1]), Path(argv[2]))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except Exception as error:  # A crash is a technical failure, never a FAIL verdict.
        print(f"ERROR: {type(error).__name__}: {error}", file=sys.stderr)
        sys.exit(2)
