"""Offline per-invocation report isolation, rendering and exit-code regressions."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("summary", ROOT / "scripts/summary.py")
summary = importlib.util.module_from_spec(spec)
spec.loader.exec_module(summary)


class SummaryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.slot = self.root / ".please/reports/last.json"
        self.slot.parent.mkdir(parents=True)
        self.output = self.root / "summary.md"
        self.fixture = self.root / "fixture.json"
        tool = self.root / "please"
        tool.write_text('#!/bin/sh\nprintf "%s\\n" "$@" >> "$INVOCATIONS"\n'
                        'if [ -f "$FIXTURE" ]; then cp "$FIXTURE" .please/reports/last.json; fi\n'
                        'exit "${RESULT:-0}"\n')
        tool.chmod(0o755)
        self.env = dict(os.environ, PATH=str(self.root) + os.pathsep + os.environ["PATH"],
                        ACTION_DIRECTORY=str(ROOT), PLEASE_SUMMARY="true",
                        PLEASE_EXECUTION_POINT_INPUT="check", GITHUB_STEP_SUMMARY=str(self.output),
                        FIXTURE=str(self.fixture), INVOCATIONS=str(self.root / "invocations"))
        self.report = {"schema_version": 4, "repository": str(self.root.resolve()), "overall": "PASS",
                       "plan": {"plan_schema_version": 3, "at": "check", "scheduled": []}, "results": []}
        for i, status in enumerate(("PASS", "FAIL", "ERROR", "NOT_RUN", "CANCELLED")):
            self.report["plan"]["scheduled"].append(dict(id=f"rule-{i}", name="Same name", kind="check",
                                                          description=f"Description {i}", blocking=i != 1))
            self.report["results"].insert(0, dict(id=f"rule-{i}", kind="check", status=status,
                                                  blocking=i != 1, duration_ms=i * 123, reason=""))
        self.report["overall"] = "ERROR"

    def run_action(self, code=0, **env):
        return subprocess.run(["bash", str(ROOT / "scripts/run.sh")], cwd=self.root,
                              env=dict(self.env, RESULT=str(code), **env), capture_output=True, text=True)

    def save(self, report=None):
        self.fixture.write_text(json.dumps(self.report if report is None else report))

    def test_plan_order_statuses_names_descriptions_and_integrity(self):
        self.report["results"].append(dict(id="please-snapshot", kind="integrity", status="ERROR",
                                           blocking=True, duration_ms=0, reason="Incomplete <snapshot>"))
        self.save()
        result = self.run_action(2)
        self.assertEqual(result.returncode, 2, result.stderr)
        text = self.output.read_text()
        self.assertIn("**ERROR**", text)
        self.assertIn("Total CLI execution duration:", text)
        for i, status in enumerate(("PASS", "FAIL", "ERROR", "NOT_RUN", "CANCELLED")):
            self.assertIn(f"| {i+1}/5 | {status}", text)
            self.assertIn(f"Description {i} | {i*123} ms", text)
        self.assertIn("FAIL (non-blocking)", text)
        self.assertLess(text.index("Description 0"), text.index("Description 4"))
        self.assertIn("| 1/5 | PASS | Same name |", text)
        self.assertNotIn("(blocking)", text)
        self.assertIn("### Integrity diagnostics", text)
        self.assertIn("Incomplete &#60;snapshot&#62;", text)
        self.assertEqual((self.root / "invocations").read_text().splitlines(), ["run", "--at", "check"])

    def test_checks_only_preserves_arguments_exit_and_summary(self):
        self.report["plan"]["at"] = "release-candidate"
        self.save()
        for enabled in ("true", "false"):
            for code in (0, 1, 2):
                with self.subTest(summary=enabled, code=code):
                    (self.root / "invocations").unlink(missing_ok=True)
                    self.output.unlink(missing_ok=True)
                    result = self.run_action(code, PLEASE_CHECKS_ONLY="true", PLEASE_SUMMARY=enabled,
                                             PLEASE_EXECUTION_POINT_INPUT="release-candidate")
                    self.assertEqual(result.returncode, code, result.stderr)
                    self.assertEqual((self.root / "invocations").read_text().splitlines(),
                                     ["run", "--at", "release-candidate", "--checks-only"])
                    self.assertEqual(self.output.exists(), enabled == "true")
                    if enabled == "true":
                        self.assertIn("Please Behave — release&#45;candidate", self.output.read_text())
                        self.assertIn("Description 0", self.output.read_text())

    def test_invalid_checks_only_does_not_execute_or_summarize(self):
        result = self.run_action(PLEASE_CHECKS_ONLY="yes")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / "invocations").exists())
        self.assertFalse(self.output.exists())

    def test_success_and_advisory_failure_use_cli_aggregate(self):
        self.report["plan"]["scheduled"] = self.report["plan"]["scheduled"][:2]
        self.report["results"] = self.report["results"][-2:]
        self.report["overall"] = "PASS"
        self.save()
        self.assertEqual(self.run_action().returncode, 0)
        self.assertIn("**PASS**", self.output.read_text())
        self.assertIn("FAIL (non-blocking)", self.output.read_text())

    def test_external_id_is_hidden_and_unnamed_rules_use_short_id(self):
        identity = "git:" + "a" * 64 + ":multi-point/security:1:secret-scan"
        self.report["plan"]["scheduled"][0].update(id=identity, name="Secret scan")
        self.report["results"][-1]["id"] = identity
        unnamed = "git:" + "b" * 64 + ":multi-point/security:1:sensitive-files"
        self.report["plan"]["scheduled"][1].update(id=unnamed, name=None)
        self.report["results"][-2]["id"] = unnamed
        self.save()
        self.assertEqual(self.run_action().returncode, 0)
        text = self.output.read_text()
        self.assertIn("| PASS | Secret scan | Description 0 |", text)
        self.assertIn("| FAIL (non-blocking) | sensitive&#45;files | Description 1 |", text)
        self.assertNotIn("git&#58;", text)
        self.assertNotIn("technical ID", text)

    def test_stale_report_is_restored_and_never_rendered(self):
        self.slot.write_bytes(b"previous report")
        for code in (0, 1, 2, 7, 126):
            result = self.run_action(code)
            self.assertEqual(result.returncode, code)
            self.assertIn("::warning::", result.stdout)
            self.assertNotIn("previous report", self.output.read_text())
            self.assertIn("produced no regular report", self.output.read_text())
            self.assertEqual(self.slot.read_bytes(), b"previous report")
            self.assertFalse(list(self.slot.parent.glob(".summary-*")))

    def test_new_report_replaces_previous_and_repeated_calls_append(self):
        self.slot.write_text("stale")
        self.output.write_text("Other tool\n")
        for point in ("check", "custom"):
            self.report["plan"]["at"] = point
            self.save()
            self.assertEqual(self.run_action(1, PLEASE_EXECUTION_POINT_INPUT=point).returncode, 1)
        text = self.output.read_text()
        self.assertTrue(text.startswith("Other tool\n"))
        self.assertEqual(text.count("## Please Behave"), 2)
        self.assertIn("— check", text)
        self.assertIn("— custom", text)
        self.assertEqual(json.loads(self.slot.read_text())["plan"]["at"], "custom")

    def test_bad_reports_produce_diagnostics_and_preserve_exit(self):
        variants = [None, [], {**self.report, "schema_version": 999}]
        for field, value in (("plan_schema_version", 99), ("at", "wrong")):
            report = copy.deepcopy(self.report)
            report["plan"][field] = value
            variants.append(report)
        report = copy.deepcopy(self.report)
        report["results"].pop()
        variants.append(report)
        report = copy.deepcopy(self.report)
        report["results"].append(report["results"][0])
        variants.append(report)
        report = copy.deepcopy(self.report)
        report["results"][0]["blocking"] = False
        variants.append(report)
        report = copy.deepcopy(self.report)
        report["results"][0]["status"] = "SKIPPED"
        variants.append(report)
        report = copy.deepcopy(self.report)
        report["plan"]["scheduled"][0]["id"] = "unknown"
        variants.append(report)
        for report in variants:
            with self.subTest(report=report):
                self.fixture.write_text("{broken" if report is None else json.dumps(report))
                self.output.unlink(missing_ok=True)
                self.assertEqual(self.run_action(7).returncode, 7)
                self.assertIn("Summary unavailable", self.output.read_text())
                self.assertNotIn("| Plan |", self.output.read_text())

    def test_empty_plan_and_unsuccessful_exit_cannot_claim_success(self):
        self.save({**self.report, "overall": "PASS", "results": [],
                   "plan": {"plan_schema_version": 3, "at": "check", "scheduled": []}})
        self.assertEqual(self.run_action(2).returncode, 2)
        text = self.output.read_text()
        self.assertIn("No rules were scheduled", text)
        self.assertIn("Invocation exited unsuccessfully", text)

    def test_disabled_summary_does_not_touch_report_or_summary(self):
        self.slot.write_text("stale")
        self.assertEqual(self.run_action(7, PLEASE_SUMMARY="false").returncode, 7)
        self.assertEqual(self.slot.read_text(), "stale")
        self.assertFalse(self.output.exists())
        self.assertFalse(list(self.slot.parent.glob(".summary-*")))

    def test_isolation_and_append_failures_do_not_change_exit(self):
        self.slot.symlink_to(self.fixture)
        self.fixture.write_text("stale")
        # No new report, and a symlink must never be used as current evidence.
        self.fixture.unlink()
        result = self.run_action(1)
        self.assertEqual(result.returncode, 1)
        self.assertIn("Report isolation failed", self.output.read_text())
        self.slot.unlink()
        self.save()
        for code in (0, 2, 7):
            result = self.run_action(code, GITHUB_STEP_SUMMARY=str(self.root))
            self.assertEqual(result.returncode, code)
            self.assertIn("could not append", result.stdout)

    def test_rendering_failure_is_diagnostic_and_original_exit_is_retained(self):
        self.save()
        with patch.dict(os.environ, self.env), patch.object(summary, "render", side_effect=ValueError("render failed")):
            previous = Path.cwd()
            try:
                os.chdir(self.root)
                self.assertEqual(summary.main(), 0)
            finally:
                os.chdir(previous)
        self.assertIn("render failed", self.output.read_text())

    def test_escaping_and_byte_limit(self):
        escaped = summary.escape("<img>|[link](url)\n@user & `code`")
        self.assertIn("&#60;img&#62;&#124;&#91;link&#93;", escaped)
        self.assertIn("&#64;user", escaped)
        self.assertNotIn("\n", escaped)
        self.report["plan"]["scheduled"][0].update(name="<img>|[link](url)\n@user", description="🦊" * 2000)
        self.save()
        self.output.write_text("x" * (summary.SUMMARY_BYTES - 4000))
        self.assertEqual(self.run_action().returncode, 0)
        text = self.output.read_text()
        self.assertNotIn("<img>", text)
        self.assertNotIn("[link](url)", text)
        self.assertLessEqual(self.output.stat().st_size, summary.SUMMARY_BYTES)
        self.assertIn("truncated", text)


if __name__ == "__main__":
    unittest.main()
