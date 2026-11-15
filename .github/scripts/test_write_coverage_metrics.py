import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("coverage_metrics", ROOT / ".github/scripts/write-coverage-metrics.py")
coverage_metrics = importlib.util.module_from_spec(spec)
spec.loader.exec_module(coverage_metrics)


class WriteCoverageMetricsTest(unittest.TestCase):
    def run_with(self, report):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            if report is not None:
                (root / "coverage.json").write_text(json.dumps(report), encoding="utf-8")
            coverage_metrics.write_metrics(root / "coverage.json", root / "out")
            return json.loads((root / "out" / "coverage.json").read_text())

    def test_writes_the_report_total_as_badge_metric(self):
        result = self.run_with({"totals": {"percent_covered": 87.3456}})
        self.assertEqual(result, {"id": "coverage", "label": "coverage", "value": 87.35, "kind": "percent", "badge": True})

    def test_writes_null_without_a_report(self):
        self.assertIsNone(self.run_with(None)["value"])

    def test_rejects_a_report_without_totals(self):
        with self.assertRaises(KeyError):
            self.run_with({})


if __name__ == "__main__":
    unittest.main()
