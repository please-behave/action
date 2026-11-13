"""Offline tests for publication readiness guards."""

import copy
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import call, patch

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("readiness", ROOT / ".please/checks/cli-release/check.py")
readiness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(readiness)


class ReleaseReadyTests(unittest.TestCase):
    def setUp(self):
        self.release = dict(
            tag_name="v0.1.0",
            draft=False,
            prerelease=False,
            assets=[
                dict(name=name, state="uploaded", size=1)
                for name in (
                    "SHA256SUMS",
                    "please-v0.1.0-x86_64-unknown-linux-gnu.tar.gz",
                    "please-v0.1.0-aarch64-unknown-linux-gnu.tar.gz",
                    "please-v0.1.0-x86_64-apple-darwin.tar.gz",
                    "please-v0.1.0-aarch64-apple-darwin.tar.gz",
                )
            ],
        )

    def verify(self, **changes):
        args = dict(release=self.release, version="v0.1.0")
        readiness.verify(**dict(args, **changes))

    def test_ready_revision(self):
        self.verify()

    def test_release_must_be_public_stable_and_exact(self):
        for change in ({"draft": True}, {"prerelease": True}, {"tag_name": "v9.9.9"}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.verify(release=dict(self.release, **change))

    def test_missing_or_incomplete_assets(self):
        for index in range(len(self.release["assets"])):
            for field, value in (("state", "new"), ("size", 0), ("name", "unexpected")):
                release = copy.deepcopy(self.release)
                release["assets"][index][field] = value
                with self.subTest(index=index, field=field), self.assertRaises(ValueError):
                    self.verify(release=release)

    def test_main_queries_only_the_public_cli_release(self):
        with (
            patch.object(readiness.Path, "read_text", return_value='[tools]\n"github:please-behave/cli" = "0.1.0"\n'),
            patch.object(readiness, "gh", side_effect=[self.release]) as gh,
            patch("builtins.print") as output,
        ):
            readiness.main()
        self.assertEqual(gh.call_args_list, [call("api", "repos/please-behave/cli/releases/tags/v0.1.0")])
        output.assert_called_once_with("Public stable CLI release assets confirmed.")
