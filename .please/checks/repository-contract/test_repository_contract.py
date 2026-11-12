"""Offline regression tests for metadata and documentation contradictions."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for name in ("action.yml", "README.md", "CONTRIBUTING.md", "LICENSE", "package.json",
                     "package-lock.json"):
            shutil.copy2(ROOT / name, self.root / name)
        for name in (".github", "docs"):
            shutil.copytree(ROOT / name, self.root / name)

    def check(self):
        return subprocess.run(["node", str(ROOT / ".please/checks/repository-contract/check.mjs")],
                              cwd=self.root, capture_output=True, text=True)

    def test_current_contract(self):
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_contradictions_fail(self):
        cases = [("action.yml", "using: composite", "using: node24"),
                 ("README.md", "| `summary` | No | `'true'` |", "| `summary` | No | `'false'` |"),
                 ("README.md", "| No | `check` |", "| No | `other` |"),
                 ("package-lock.json", '"node": ">=26 <27"', '"node": ">=24 <27"'),
                 (".github/workflows/release.yml", "  workflow_dispatch:", "  push:"),
                 (".github/workflows/release.yml", "    needs: [plan, release-readiness, release-candidate]", "    needs: []"),
                 (".github/workflows/release.yml", "needs.release-candidate.result == 'success'",
                  "needs.release-candidate.result == 'skipped'"),
                 (".github/release-ci.json", '"Check (ubuntu-24.04-arm)"', '"Check"'),
                 (".github/workflows/ci.yml", "os: [ubuntu-24.04, ubuntu-24.04-arm]", "os: [ubuntu-24.04]"),
                 (".github/workflows/release.yml", "      - run: npm ci --ignore-scripts",
                  "      - uses: ./\n      - run: npm ci --ignore-scripts"),
                 (".github/workflows/release.yml", "  contents: read", "  contents: write"),
                 (".github/workflows/release.yml", "      - name: Publish semantic Action release",
                  "      - run: please sync --yes\n      - name: Publish semantic Action release"),
                 ("README.md", "](LICENSE)", "](MISSING)")]
        for name, before, after in cases:
            with self.subTest(name=name):
                file = self.root / name
                original = file.read_text()
                self.assertIn(before, original)
                file.write_text(original.replace(before, after))
                self.assertEqual(self.check().returncode, 1)
                file.write_text(original)

    def test_a_missing_file_is_a_technical_error(self):
        (self.root / "action.yml").unlink()
        self.assertEqual(self.check().returncode, 2)
