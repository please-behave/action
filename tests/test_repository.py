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
                 ("action.yml", "        PLEASE_SUMMARY: ${{ inputs.summary }}", "        PLEASE_SUMMARY: 'false'"),
                 ("README.md", "| `summary` | No | `'true'` |", "| `summary` | No | `'false'` |"),
                 ("README.md", "| No | `check` |", "| No | `other` |"),
                 ("package-lock.json", '"node": ">=26 <27"', '"node": ">=24 <27"'),
                 (".github/workflows/release.yml", "  workflow_dispatch:", "  push:"),
                 (".github/workflows/release.yml", "    needs: [checks, action-e2e]", "    needs: []"),
                 (".github/workflows/release.yml", "run: python3 scripts/check-release-ready.py",
                  "run: please run --at release"),
                 (".github/workflows/release.yml", "      - run: npm ci --ignore-scripts",
                  "      - uses: ./\n      - run: npm ci --ignore-scripts"),
                 (".github/workflows/ci.yml", "os: [ubuntu-24.04, ubuntu-24.04-arm]", "os: [ubuntu-24.04]"),
                 (".github/workflows/action-e2e.yml", '[execution_points]', '[undeclared_points]'),
                 (".github/workflows/action-e2e.yml", 'custom = ["summary-first", "summary-second"]',
                  'custom = ["summary-first"]'),
                 (".github/workflows/ci.yml", "    name: Check", "    name: Tests"),
                 (".github/workflows/ci.yml", "  check:", "  tests:"),
                 (".github/workflows/ci.yml", "run: please run --at check", "run: python3 -m unittest discover"),
                 (".github/workflows/action-e2e.yml", "name: Action E2E", "name: CI"),
                 (".github/workflows/action-e2e.yml", "  test:", "  summaries:"),
                 (".github/workflows/action-e2e.yml", "    name: Test", "    name: Summaries"),
                 (".github/workflows/action-e2e.yml", "os: [ubuntu-24.04, ubuntu-24.04-arm]", "os: [ubuntu-24.04]"),
                 (".github/workflows/action-e2e.yml", "        uses: ./", "        run: bash scripts/run.sh"),
                 (".github/workflows/action-e2e.yml", "continue-on-error: true", "continue-on-error: false"),
                 (".github/workflows/action-e2e.yml", "steps.failing.outcome", "steps.failing.conclusion"),
                 (".github/workflows/action-e2e.yml", "steps.failing.conclusion", "steps.failing.outcome"),
                 (".github/workflows/action-e2e.yml", "        if: always()", "        if: success()"),
                 (".github/workflows/action-e2e.yml", "  pull_request:", "  workflow_dispatch:"),
                 (".github/workflows/action-e2e.yml", "  contents: read", "  contents: write"),
                 ("README.md", "](LICENSE)", "](MISSING)")]
        for name, before, after in cases:
            with self.subTest(name=name):
                file = self.root / name
                original = file.read_text()
                self.assertIn(before, original)
                file.write_text(original.replace(before, after))
                self.assertNotEqual(self.check().returncode, 0)
                file.write_text(original)
