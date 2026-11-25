"""Offline tests of release recording with a mocked CLI."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
URL = "https://gateway.example.org"


class RecordReleaseTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.output = self.root / "summary.md"
        tool = self.root / "please"
        tool.write_text(
            '#!/bin/sh\nprintf "%s\\n" "$@" > "$INVOCATION"\n'
            'printf "%s\\n" "${STDOUT:-}"\nprintf "diagnostic for %s\\n" "$3" >&2\n'
            'if [ -n "${CONFLICT:-}" ]; then echo "Release version conflicts with a recorded commit." >&2; fi\n'
            'exit "${RESULT:-0}"\n'
        )
        tool.chmod(0o755)
        self.env = dict(
            os.environ,
            PATH=str(self.root) + os.pathsep + os.environ["PATH"],
            PLEASE_RELEASE_VERSION="2026.11 <b>",
            PLEASE_GATEWAY_URL_INPUT=URL,
            GITHUB_STEP_SUMMARY=str(self.output),
            INVOCATION=str(self.root / "invocation"),
        )
        self.env.pop("PLEASE_RELEASE_COMMIT", None)
        self.env.pop("PLEASE_PUBLISH_REQUIRED", None)

    def run_script(self, **env):
        return subprocess.run(
            ["python3", str(ROOT / "scripts/record-release.py")], env=dict(self.env, **env), capture_output=True, text=True
        )

    def summary(self):
        return self.output.read_text()

    def test_recorded_and_unchanged_pass_arguments_and_report_outcome(self):
        for stdout, outcome in (("Release recorded.", "Recorded"), ("Release already known.", "Unchanged")):
            with self.subTest(outcome=outcome):
                self.output.unlink(missing_ok=True)
                commit = "ab" * 20
                result = self.run_script(STDOUT=stdout, PLEASE_RELEASE_COMMIT=commit)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(
                    (self.root / "invocation").read_text().splitlines(),
                    ["record", "release", f"--gateway-url={URL}", "--version=2026.11 <b>", f"--commit={commit}"],
                )
                self.assertIn(f"**{outcome}.**", self.summary())
                self.assertNotIn("<b>", self.summary())
                self.assertIn(f"::add-mask::{URL}", result.stdout)

    def test_commit_is_omitted_by_default(self):
        self.assertEqual(self.run_script(STDOUT="Release recorded.").returncode, 0)
        self.assertNotIn("--commit", (self.root / "invocation").read_text())

    def test_conflict_warns_and_fails_only_when_publishing_is_required(self):
        for required, code in (("false", 0), ("true", 1)):
            with self.subTest(required=required):
                self.output.unlink(missing_ok=True)
                result = self.run_script(RESULT="2", CONFLICT="1", PLEASE_PUBLISH_REQUIRED=required)
                self.assertEqual(result.returncode, code)
                self.assertIn("::warning::Please Behave release recording failed.", result.stdout)
                self.assertIn("**Conflict.**", self.summary())
                self.assertNotIn(URL, result.stdout.replace(f"::add-mask::{URL}", "") + result.stderr + self.summary())

    def test_failure_warns_and_fails_only_when_publishing_is_required(self):
        for required, code in (("false", 0), ("true", 1)):
            with self.subTest(required=required):
                self.output.unlink(missing_ok=True)
                result = self.run_script(RESULT="2", PLEASE_PUBLISH_REQUIRED=required)
                self.assertEqual(result.returncode, code)
                self.assertIn("**Failed.**", self.summary())
                self.assertIn("exit status 2", self.summary())
                self.assertNotIn("diagnostic", self.summary() + result.stdout + result.stderr)

    def test_success_without_a_known_outcome_is_a_failure(self):
        result = self.run_script(STDOUT="something else", PLEASE_PUBLISH_REQUIRED="true")
        self.assertEqual(result.returncode, 1)
        self.assertIn("**Failed.**", self.summary())

    def test_missing_gateway_url_skips_and_says_so(self):
        result = self.run_script(PLEASE_GATEWAY_URL_INPUT="", PLEASE_PUBLISH_REQUIRED="true")
        self.assertEqual(result.returncode, 0)
        self.assertFalse((self.root / "invocation").exists())
        self.assertIn("::notice::", result.stdout)
        self.assertIn("skipped", self.summary())

    def test_commit_without_version_is_rejected(self):
        result = self.run_script(PLEASE_RELEASE_VERSION="", PLEASE_RELEASE_COMMIT="ab" * 20)
        self.assertEqual(result.returncode, 1)
        self.assertIn("::error::", result.stdout)
        self.assertFalse((self.root / "invocation").exists())

    def test_action_runs_the_script_independently_of_run(self):
        metadata = (ROOT / "action.yml").read_text()
        step = metadata.split("- name: Record release")[1]
        self.assertIn("if: inputs.release-version != '' || inputs.release-commit != ''", step)
        self.assertIn("scripts/record-release.py", step)


if __name__ == "__main__":
    unittest.main()
