"""Offline tests of the hosted E2E result verifier, run through Please Behave."""

import importlib.util
import itertools
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("action_e2e", ROOT / ".github/scripts/check-action-e2e.py")
e2e = importlib.util.module_from_spec(spec)
spec.loader.exec_module(e2e)


class ActionE2ETests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for point, status, code in (("summary-first", "PASS", 0), ("summary-second", "FAIL", 1)):
            (self.root / f"{point}.md").write_text(
                f"## Please Behave — {point.replace('-', '&#45;')}\n"
                f"CLI aggregate outcome: **{status}**. CLI exit code: **{code}**.\n"
                "| 1/1 | Hosted composite summary acceptance |\n"
            )

    def test_only_expected_raw_and_effective_outcomes_pass(self):
        expected = ("success", "success", "failure", "success")
        for observed in itertools.product(("success", "failure", "skipped", "cancelled", ""), repeat=4):
            with self.subTest(observed=observed):
                if observed == expected:
                    e2e.verify(self.root, *observed)
                else:
                    with self.assertRaises(ValueError):
                        e2e.verify(self.root, *observed)

    def test_missing_or_incorrect_summary_fails(self):
        file = self.root / "summary-second.md"
        original = file.read_text()
        for before, after in (
            ("**FAIL**", "**PASS**"),
            ("**1**", "**2**"),
            ("| 1/1 |", ""),
            ("Hosted composite summary acceptance", ""),
            ("summary&#45;second", "summary&#45;first"),
            ("## Please Behave", "## Please Behave\n## Please Behave"),
        ):
            with self.subTest(before=before):
                file.write_text(original.replace(before, after))
                with self.assertRaises(ValueError):
                    e2e.verify(self.root, "success", "success", "failure", "success")
        file.unlink()
        with self.assertRaises(FileNotFoundError):
            e2e.verify(self.root, "success", "success", "failure", "success")
