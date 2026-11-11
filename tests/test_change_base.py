"""Offline GitHub comparison-base tests with real local Git history."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ChangeBaseTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1",
                        ACTION_DIRECTORY=str(ROOT), PLEASE_EXECUTION_POINT_INPUT="check",
                        PLEASE_SUMMARY="false", PLEASE_CHECKS_ONLY="false", PLEASE_CHANGE_BASE="",
                        GITHUB_EVENT_PATH=str(self.root / "event.json"))
        self.git("init", "--quiet", "-b", "main")
        self.git("config", "user.name", "Fixture")
        self.git("config", "user.email", "fixture@example.com")
        self.git("commit", "--quiet", "--allow-empty", "-m", "initial")
        self.initial = self.git("rev-parse", "HEAD")
        self.git("commit", "--quiet", "--allow-empty", "-m", "main change")
        self.main = self.git("rev-parse", "HEAD")
        self.git("checkout", "--quiet", "-b", "feature", self.initial)
        self.git("commit", "--quiet", "--allow-empty", "-m", "feature change")
        self.feature = self.git("rev-parse", "HEAD")
        tool = self.root / "please"
        tool.write_text('#!/bin/sh\nprintf "%s\\n" "$PLEASE_CHANGE_BASE" > observed-base\n'
                        'printf "%s\\n" "$@" > invocation\nexit 7\n')
        tool.chmod(0o755)
        self.env["PATH"] = str(self.root) + os.pathsep + self.env["PATH"]

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.root, env=self.env, text=True).strip()

    def run_action(self, event, payload, **env):
        (self.root / "event.json").write_text(json.dumps(payload))
        (self.root / "invocation").unlink(missing_ok=True)
        return subprocess.run(["bash", str(ROOT / "scripts/run.sh")], cwd=self.root,
                              env=dict(self.env, GITHUB_EVENT_NAME=event, **env), capture_output=True, text=True)

    def test_push_pr_merge_base_and_dispatch_are_invocation_local(self):
        for event, payload, expected in (
            ("push", {"before": self.main}, self.main),
            ("pull_request", {"pull_request": {"base": {"sha": self.main},
                                                "head": {"sha": self.feature}}}, self.initial),
            ("workflow_dispatch", {}, self.feature),
        ):
            with self.subTest(event=event):
                result = self.run_action(event, payload)
                self.assertEqual(result.returncode, 7, result.stderr)
                self.assertEqual((self.root / "observed-base").read_text().strip(), expected)
                self.assertEqual((self.root / "invocation").read_text().splitlines(), ["run", "--at", "check"])

    def test_override_and_checks_only_do_not_need_event_history(self):
        for env, expected in ((dict(PLEASE_CHANGE_BASE="explicit-base"), "explicit-base"),
                              (dict(PLEASE_CHECKS_ONLY="true"), "")):
            result = self.run_action("push", {}, **env)
            self.assertEqual(result.returncode, 7, result.stderr)
            self.assertEqual((self.root / "observed-base").read_text().strip(), expected)

    def test_invalid_or_missing_event_baseline_prevents_execution(self):
        for payload in ({}, {"before": "0" * 40}, {"before": "HEAD; touch injected"}, {"before": "a" * 40}):
            result = self.run_action("push", payload)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Cannot establish review baseline", result.stderr)
            self.assertFalse((self.root / "invocation").exists())
            self.assertFalse((self.root / "injected").exists())


if __name__ == "__main__":
    unittest.main()
