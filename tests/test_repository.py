"""Offline regression tests for metadata and documentation contradictions."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for name in ("action.yml", "README.md", "CONTRIBUTING.md", "LICENSE", "package.json",
                     "package-lock.json", ".please-version"):
            shutil.copy2(ROOT / name, self.root / name)
        for name in (".github", "docs"):
            shutil.copytree(ROOT / name, self.root / name)

    def check(self):
        return subprocess.run(["node", str(ROOT / "scripts/check-repository.mjs")],
                              cwd=self.root, capture_output=True, text=True)

    def test_current_contract(self):
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_contradictions_fail(self):
        cases = [("action.yml", "using: composite", "using: node24"),
                 ("README.md", "| No | `check` |", "| No | `other` |"),
                 ("package-lock.json", '"node": ">=26 <27"', '"node": ">=24 <27"'),
                 (".github/workflows/release.yml", "  workflow_dispatch:", "  push:"),
                 (".github/workflows/release.yml", "    needs: checks", "    needs: []"),
                 (".github/workflows/release.yml", "run: python3 scripts/check-release-ready.py",
                  "run: please run --at release"),
                 (".github/workflows/release.yml", "      - run: npm ci --ignore-scripts",
                  "      - uses: ./\n      - run: npm ci --ignore-scripts"),
                 (".github/workflows/ci.yml", "os: [ubuntu-24.04, ubuntu-24.04-arm]", "os: [ubuntu-24.04]"),
                 ("README.md", "](LICENSE)", "](MISSING)")]
        for name, before, after in cases:
            with self.subTest(name=name):
                file = self.root / name
                original = file.read_text()
                self.assertIn(before, original)
                file.write_text(original.replace(before, after))
                self.assertNotEqual(self.check().returncode, 0)
                file.write_text(original)
