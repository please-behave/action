"""Offline candidate evidence checks without installing or invoking governance."""

import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("evidence", ROOT / ".github/scripts/release-evidence.py")
evidence = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evidence)


class ReleaseEvidenceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.head = "a" * 40
        self.policy = evidence.policy_from(ROOT / ".github/release-artifacts.json")
        self.env = dict(
            EXPECTED_RELEASE_VERSION="1.3.0",
            GITHUB_SHA=self.head,
            GITHUB_REF="refs/heads/main",
            GITHUB_REPOSITORY="please-behave/action",
            GITHUB_WORKFLOW_REF="please-behave/action/.github/workflows/release.yml@refs/heads/main",
            GITHUB_RUN_ID="123",
            GITHUB_RUN_ATTEMPT="1",
        )
        previous = Path.cwd()
        os.chdir(self.root)
        self.addCleanup(os.chdir, previous)
        for name in set(sum(self.policy["targets"].values(), [])):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("tested source")
        for target in self.policy["targets"]:
            evidence.record(self.policy, dict(self.env, RELEASE_TARGET=target), self.head)

    def test_policy_and_evidence_accept_zero_and_one_without_weakening_identity(self):
        path = Path("policy.json")
        for version in (0, 1):
            policy = dict(self.policy, schema_version=version)
            path.write_text(json.dumps(policy))
            self.assertEqual(evidence.policy_from(path), policy)
            for target in self.policy["targets"]:
                receipt = Path(f"release-evidence/{target}.json")
                data = json.loads(receipt.read_text())
                data["schema_version"] = version
                receipt.write_text(json.dumps(data))
            evidence.verify(policy, self.env, self.head)
        receipt = next(Path("release-evidence").iterdir())
        original = json.loads(receipt.read_text())
        for version in (True, False, -1, 2, 1.0, "0", None):
            path.write_text(json.dumps(dict(self.policy, schema_version=version)))
            with self.subTest(policy=version), self.assertRaises(ValueError):
                evidence.policy_from(path)
            receipt.write_text(json.dumps(dict(original, schema_version=version)))
            with self.subTest(evidence=version), self.assertRaises(ValueError):
                evidence.verify(self.policy, self.env, self.head)

    def test_all_four_candidates_verify_without_running_governance(self):
        with patch.object(evidence.subprocess, "run", side_effect=AssertionError("No governance invocation")):
            evidence.verify(self.policy, self.env, self.head)
        self.assertFalse((self.root / ".git/hooks").exists())
        for receipt in (self.root / "release-evidence").iterdir():
            self.assertEqual(json.loads(receipt.read_text())["schema_version"], 0)

    def test_missing_extra_mismatched_or_modified_evidence_is_rejected(self):
        path = next((self.root / "release-evidence").iterdir())
        original = path.read_text()
        for field, value in (
            ("version", "9.9.9"),
            ("source_sha", "b" * 40),
            ("run_id", "456"),
            ("run_attempt", "2"),
            ("repository", "other/repository"),
            ("target", "other"),
            ("workflow", ".github/workflows/other.yml"),
            ("artifacts", {}),
        ):
            with self.subTest(field=field):
                data = json.loads(original)
                data[field] = value
                path.write_text(json.dumps(data))
                with self.assertRaises(ValueError):
                    evidence.verify(self.policy, self.env, self.head)
                path.write_text(original)
        path.unlink()
        with self.assertRaises(ValueError):
            evidence.verify(self.policy, self.env, self.head)
        path.write_text(original)
        extra = path.with_name("unexpected.json")
        extra.write_text(original)
        with self.assertRaises(ValueError):
            evidence.verify(self.policy, self.env, self.head)
        extra.unlink()
        (self.root / "scripts/change-base.py").write_text("changed after testing")
        with self.assertRaises(ValueError):
            evidence.verify(self.policy, self.env, self.head)


if __name__ == "__main__":
    unittest.main()
