"""Offline tests of deployment recording with a mocked CLI."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
URL = "https://gateway.example.org"


class RecordDeploymentTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.output = self.root / "summary.md"
        tool = self.root / "please"
        tool.write_text(
            '#!/bin/sh\nprintf "%s\\n" "$@" > "$INVOCATION"\n'
            'printf "%s\\n" "${STDOUT:-}"\nprintf "diagnostic for %s\\n" "$3" >&2\n'
            'if [ -n "${UNKNOWN:-}" ]; then echo "Deployment target is unknown to the gateway for the authenticated sender." >&2; fi\n'
            'exit "${RESULT:-0}"\n'
        )
        tool.chmod(0o755)
        self.env = dict(
            os.environ,
            PATH=str(self.root) + os.pathsep + os.environ["PATH"],
            PLEASE_DEPLOYMENT_TARGET="prod <b>",
            PLEASE_DEPLOYMENT_REPOSITORY="github.com/example/app",
            PLEASE_DEPLOYMENT_VERSION="1.2.3",
            PLEASE_GATEWAY_URL_INPUT=URL,
            GITHUB_STEP_SUMMARY=str(self.output),
            INVOCATION=str(self.root / "invocation"),
        )
        self.env.pop("PLEASE_DEPLOYMENT_COMMIT", None)
        self.env.pop("PLEASE_PUBLISH_REQUIRED", None)

    def run_script(self, **env):
        return subprocess.run(
            ["python3", str(ROOT / "scripts/record-deployment.py")], env=dict(self.env, **env), capture_output=True, text=True
        )

    def summary(self):
        return self.output.read_text()

    def invocation(self):
        return (self.root / "invocation").read_text().splitlines()

    def test_recorded_and_unchanged_pass_arguments_and_report_outcome(self):
        for stdout, outcome in (("Deployment recorded.", "Recorded"), ("Deployment unchanged.", "Unchanged")):
            with self.subTest(outcome=outcome):
                self.output.unlink(missing_ok=True)
                result = self.run_script(STDOUT=stdout)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(
                    self.invocation(),
                    [
                        "record",
                        "deployment",
                        f"--gateway-url={URL}",
                        "--target=prod <b>",
                        "--repository=github.com/example/app",
                        "--version=1.2.3",
                    ],
                )
                self.assertIn(f"**{outcome}.**", self.summary())
                self.assertNotIn("<b>", self.summary())
                self.assertIn(f"::add-mask::{URL}", result.stdout)

    def test_commit_is_passed_instead_of_version(self):
        commit = "ab" * 20
        result = self.run_script(STDOUT="Deployment recorded.", PLEASE_DEPLOYMENT_VERSION="", PLEASE_DEPLOYMENT_COMMIT=commit)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.invocation()[-1], f"--commit={commit}")
        self.assertNotIn("--version", "".join(self.invocation()))

    def test_unknown_target_warns_and_fails_only_when_publishing_is_required(self):
        for required, code in (("false", 0), ("true", 1)):
            with self.subTest(required=required):
                self.output.unlink(missing_ok=True)
                result = self.run_script(RESULT="2", UNKNOWN="1", PLEASE_PUBLISH_REQUIRED=required)
                self.assertEqual(result.returncode, code)
                self.assertIn("::warning::Please Behave deployment recording failed.", result.stdout)
                self.assertIn("**Unknown target.**", self.summary())
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

    def test_incomplete_or_ambiguous_inputs_are_rejected(self):
        cases = (
            {"PLEASE_DEPLOYMENT_TARGET": ""},
            {"PLEASE_DEPLOYMENT_REPOSITORY": ""},
            {"PLEASE_DEPLOYMENT_VERSION": ""},
            {"PLEASE_DEPLOYMENT_COMMIT": "ab" * 20},
        )
        for case in cases:
            with self.subTest(case=case):
                result = self.run_script(**case)
                self.assertEqual(result.returncode, 1)
                self.assertIn("::error::", result.stdout)
                self.assertFalse((self.root / "invocation").exists())

    def test_action_runs_the_script_independently_of_run(self):
        metadata = (ROOT / "action.yml").read_text()
        step = metadata.split("- name: Record deployment")[1]
        self.assertIn("if: inputs.deployment-target != ''", step)
        self.assertIn("scripts/record-deployment.py", step)


if __name__ == "__main__":
    unittest.main()
