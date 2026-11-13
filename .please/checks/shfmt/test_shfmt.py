"""Offline tests for the shfmt rule script: verdicts, zsh skipping and technical failures."""

import importlib.util
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("shfmt_check", ROOT / ".please/checks/shfmt/check.py")
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)


def completed(code, stdout=b"", stderr=b""):
    return subprocess.CompletedProcess([], code, stdout, stderr)


class ShfmtTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory(prefix="shfmt-")
        self.addCleanup(directory.cleanup)
        self.previous = os.getcwd()
        os.chdir(directory.name)
        self.addCleanup(os.chdir, self.previous)
        Path("bash.sh").write_text("#!/usr/bin/env bash\n")
        Path("zsh.sh").write_text("#!/usr/bin/env zsh\n")

    def run_main(self, listing, *results):
        with patch.object(subprocess, "run", side_effect=[listing, *results]) as run:
            return check.main(), run

    def test_zsh_scripts_are_skipped_and_pass_is_reported(self):
        code, run = self.run_main(completed(0, b"bash.sh\0zsh.sh\0"), completed(0))
        self.assertEqual(code, 0)
        self.assertEqual(run.call_args.args[0], ["shfmt", "-d", "--", "bash.sh"])

    def test_no_scripts_is_pass_without_running_shfmt(self):
        code, run = self.run_main(completed(0, b"zsh.sh\0"))
        self.assertEqual(code, 0)
        self.assertEqual(run.call_count, 1)

    def test_differences_fail(self):
        self.assertEqual(self.run_main(completed(0, b"bash.sh\0"), completed(1, b"--- bash.sh\n"))[0], 1)

    def test_syntax_errors_are_errors_not_differences(self):
        with self.assertRaisesRegex(RuntimeError, "unexpected token"):
            self.run_main(completed(0, b"bash.sh\0"), completed(1, b"", b"bash.sh:1:1: unexpected token"))

    def test_other_exit_codes_and_git_failures_are_errors(self):
        with self.assertRaises(RuntimeError):
            self.run_main(completed(0, b"bash.sh\0"), completed(2))
        with self.assertRaises(RuntimeError):
            self.run_main(completed(128))


if __name__ == "__main__":
    unittest.main()
