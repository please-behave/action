import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("count_metrics", ROOT / ".github/scripts/write-count-metrics.py")
count_metrics = importlib.util.module_from_spec(spec)
spec.loader.exec_module(count_metrics)

SCC = [{"Name": "Python", "Code": 1200}, {"Name": "Shell", "Code": 34}]
LOG = "..........\n----------------------------------------------------------------------\nRan 42 tests in 1.234s\n\nOK\n"


class WriteCountMetricsTest(unittest.TestCase):
    def test_writes_lines_of_code_and_test_counts_as_badge_metrics(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "scc.json").write_text(json.dumps(SCC), encoding="utf-8")
            (root / "unittest.log").write_text(LOG, encoding="utf-8")
            count_metrics.write_metrics(root / "scc.json", root / "unittest.log", root / "out")
            loc = json.loads((root / "out" / "loc.json").read_text())
            tests = json.loads((root / "out" / "tests.json").read_text())
        self.assertEqual(loc, {"id": "loc", "label": "LOC", "value": 1234, "kind": "loc", "badge": True})
        self.assertEqual(tests, {"id": "tests", "label": "tests", "value": 42, "kind": "tests", "badge": True})

    def test_counts_a_single_test(self):
        self.assertEqual(count_metrics.test_count("Ran 1 test in 0.001s\n\nOK\n"), 1)

    def test_rejects_a_failed_run(self):
        with self.assertRaises(ValueError):
            count_metrics.test_count("Ran 3 tests in 0.1s\n\nFAILED (failures=1)\n")

    def test_rejects_a_log_without_a_summary(self):
        with self.assertRaises(ValueError):
            count_metrics.test_count("")


if __name__ == "__main__":
    unittest.main()
