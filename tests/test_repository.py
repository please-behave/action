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
                     "package-lock.json", "mise.toml"):
            shutil.copy2(ROOT / name, self.root / name)
        for name in (".github", "docs"):
            shutil.copytree(ROOT / name, self.root / name)
        (self.root / ".please").mkdir()
        shutil.copy2(ROOT / ".please/release-ci.json", self.root / ".please/release-ci.json")

    def check(self):
        return subprocess.run(["node", str(ROOT / "scripts/check-repository.mjs")],
                              cwd=self.root, capture_output=True, text=True)

    def test_current_contract(self):
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_contradictions_fail(self):
        cases = [("action.yml", "using: composite", "using: node24"),
                 ("action.yml", "if: inputs.sync == 'true'", "if: inputs.sync == 'false'"),
                 ("action.yml", "      run: please sync --yes", "      run: please run --at check"),
                 ("action.yml", "        PLEASE_SUMMARY: ${{ inputs.summary }}", "        PLEASE_SUMMARY: 'false'"),
                 ("README.md", "| `summary` | No | `'true'` |", "| `summary` | No | `'false'` |"),
                 ("README.md", "| No | `check` |", "| No | `other` |"),
                 ("package-lock.json", '"node": ">=26 <27"', '"node": ">=24 <27"'),
                 (".github/workflows/release.yml", "  workflow_dispatch:", "  push:"),
                 (".github/workflows/release.yml", "    needs: [plan, release-readiness, release-candidate]", "    needs: []"),
                 (".github/workflows/release.yml", "needs.release-candidate.result == 'success'",
                  "needs.release-candidate.result == 'skipped'"),
                 (".please/release-ci.json", '"Check (ubuntu-24.04-arm)"', '"Check"'),
                 (".github/workflows/release.yml", "      - run: npm ci --ignore-scripts",
                  "      - uses: ./\n      - run: npm ci --ignore-scripts"),
                 (".github/workflows/ci.yml", "os: [ubuntu-24.04, ubuntu-24.04-arm]", "os: [ubuntu-24.04]"),
                 (".github/workflows/release.yml", '[execution_points]', '[undeclared_points]'),
                 (".github/workflows/release.yml", 'custom = ["summary-first", "summary-second"]',
                  'custom = ["summary-first"]'),
                 (".github/workflows/ci.yml", "    name: Check", "    name: Tests"),
                 (".github/workflows/ci.yml", "  check:", "  tests:"),
                 (".github/workflows/ci.yml", "          execution-point: check", "          execution-point: pre-push"),
                 (".github/workflows/release.yml", "          summary: 'true'", "          summary: 'false'"),
                 (".github/workflows/release.yml", "          checks-only: 'true'", "          checks-only: 'false'"),
                 (".github/workflows/ci.yml", "          summary: 'true'", "          summary: 'false'"),
                 (".github/workflows/ci.yml", "          summary: 'true'", "          run: 'false'"),
                 (".github/workflows/release.yml", "    name: Release Candidate (${{ matrix.os }})", "    name: Other"),
                 (".github/workflows/release.yml", "  release-candidate:", "  summaries:"),
                 
                 (".github/workflows/release.yml", "os: [ubuntu-24.04, ubuntu-24.04-arm, macos-15, macos-15-intel]",
                  "os: [ubuntu-24.04, ubuntu-24.04-arm]"),
                 (".github/workflows/release.yml", "        uses: ./", "        run: bash scripts/run.sh"),
                 (".github/workflows/release.yml", "continue-on-error: true", "continue-on-error: false"),
                 (".github/workflows/release.yml", "steps.failing.outcome", "steps.failing.conclusion"),
                 (".github/workflows/release.yml", "steps.failing.conclusion", "steps.failing.outcome"),
                 (".github/workflows/release.yml", "        if: always()", "        if: success()"),
                 
                 (".github/workflows/release.yml", "  contents: read", "  contents: write"),
                 ("README.md", "](LICENSE)", "](MISSING)")]
        for name, before, after in cases:
            with self.subTest(name=name):
                file = self.root / name
                original = file.read_text()
                self.assertIn(before, original)
                file.write_text(original.replace(before, after))
                self.assertNotEqual(self.check().returncode, 0)
                file.write_text(original)
