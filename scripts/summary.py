"""Run the CLI once and append a bounded, per-invocation GitHub summary."""
import html
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

STATUSES = {"PASS", "FAIL", "ERROR", "NOT_RUN", "CANCELLED"}
SUMMARY_BYTES = 900 * 1024
REPORT_BYTES = 32 * 1024 * 1024


def warning(message):
    # Annotation commands must not receive unescaped report/environment content.
    message = str(message).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    print(f"::warning::Please Behave summary: {message}", flush=True)


def escape(value):
    value = str(value)
    if len(value) > 512:
        value = value[:512] + "… [truncated]"
    value = " ".join(value.split())
    # Encode punctuation as entities so Markdown, HTML, links and mentions are inert.
    return "".join(html.escape(c, quote=True) if c.isalnum() or c == " "
                   else f"&#{ord(c)};" for c in value)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate(report, point):
    require(isinstance(report, dict), "report must be an object")
    require(type(report.get("schema_version")) is int and report["schema_version"] == 4,
            "unsupported report schema (expected 4); select a compatible CLI release")
    plan = report.get("plan")
    require(isinstance(plan, dict) and type(plan.get("plan_schema_version")) is int
            and plan["plan_schema_version"] == 3, "unsupported plan schema (expected 3)")
    require(plan.get("at") == point, "report execution point does not match this invocation")
    require(report.get("repository") == str(Path.cwd().resolve()), "report repository does not match")
    require(report.get("overall") in {"PASS", "FAIL", "ERROR"}, "invalid aggregate outcome")
    rules, results = plan.get("scheduled"), report.get("results")
    require(isinstance(rules, list) and isinstance(results, list), "missing scheduled rules or results")
    scheduled = {}
    for rule in rules:
        require(isinstance(rule, dict), "invalid scheduled rule")
        identity = rule.get("id")
        require(isinstance(identity, str) and identity and identity not in scheduled,
                "missing or duplicate scheduled rule identity")
        require(rule.get("kind") in {"check", "review"}
                and isinstance(rule.get("description"), str)
                and (rule.get("name") is None or isinstance(rule["name"], str))
                and type(rule.get("blocking")) is bool, "invalid scheduled rule metadata")
        scheduled[identity] = rule
    matched, integrity = {}, []
    for result in results:
        require(isinstance(result, dict), "invalid result")
        identity = result.get("id")
        require(isinstance(identity, str) and identity, "missing result identity")
        require(result.get("status") in STATUSES and type(result.get("blocking")) is bool
                and type(result.get("duration_ms")) is int and result["duration_ms"] >= 0
                and isinstance(result.get("reason"), str), "invalid result metadata")
        if result.get("kind") == "integrity":
            require(identity not in scheduled and identity not in {r["id"] for r in integrity},
                    "duplicate integrity identity")
            integrity.append(result)
        else:
            require(identity in scheduled and identity not in matched, "unexpected or duplicate rule result")
            rule = scheduled[identity]
            require(result.get("kind") == rule["kind"] and result["blocking"] == rule["blocking"],
                    "result does not correspond to scheduled rule")
            matched[identity] = result
    require(set(matched) == set(scheduled), "incomplete scheduled rule results")
    return rules, matched, integrity


def render(report, point, code, elapsed):
    rules, results, integrity = validate(report, point)
    lines = [f"\n## Please Behave — {escape(point)}\n\n",
             f"CLI aggregate outcome: **{report['overall']}**. CLI exit code: **{code}**.\n\n",
             f"Total CLI execution duration: {elapsed:.3f} s (wall clock).\n\n"]
    if code != 0:
        lines.append("**Invocation exited unsuccessfully.** The saved CLI aggregate outcome is shown above.\n\n")
    if not rules:
        lines.append("No rules were scheduled for this execution point.\n\n")
    else:
        lines.append("| Plan | Status | Rule name | Description | Duration |\n"
                     "| --- | --- | --- | --- | --- |\n")
        for index, rule in enumerate(rules, 1):
            result = results[rule["id"]]
            enforcement = "" if rule["blocking"] else " (non-blocking)"
            name = rule.get("name") or rule["id"].rsplit(":", 1)[-1]
            lines.append(f"| {index}/{len(rules)} | {result['status']}{enforcement} | "
                         f"{escape(name)} | {escape(rule['description'])} | "
                         f"{result['duration_ms']} ms |\n")
        lines.append("\nNon-blocking results do not replace the CLI aggregate outcome; configuration errors can still block.\n\n")
    if integrity:
        lines.append("### Integrity diagnostics\n\n")
        for result in integrity:
            lines.append(f"- {escape(result['id'])}: **{result['status']}** — {escape(result['reason'])}\n")
    return lines


def append_summary(lines):
    target = Path(os.environ["GITHUB_STEP_SUMMARY"])
    available = SUMMARY_BYTES - (target.stat().st_size if target.exists() else 0)
    suffix = "\n\nSummary truncated to fit the Job Summary limit; consult the saved CLI report.\n"
    output = []
    used = len(suffix.encode())
    for line in lines:
        size = len(line.encode())
        if used + size > available:
            output.append(suffix)
            warning("output truncated; consult .please/reports/last.json for complete results")
            break
        output.append(line)
        used += size
    require(available >= len(suffix.encode()), "step summary is already full; use the CLI logs/report")
    with target.open("a", encoding="utf-8") as stream:
        stream.write("".join(output))


def main():
    point = os.environ["PLEASE_EXECUTION_POINT_INPUT"]
    slot = Path.cwd() / ".please/reports/last.json"
    backup = None
    isolated = False
    diagnostic = None
    try:
        for component in (slot.parent.parent, slot.parent, slot):
            require(not component.is_symlink(), "cannot isolate a symlinked report path")
        if slot.exists():
            require(slot.is_file(), "report slot is not a regular file")
            backup = Path(tempfile.mkdtemp(prefix=".summary-", dir=slot.parent))
            slot.rename(backup / "last.json")
        isolated = True
    except (OSError, ValueError) as error:
        diagnostic = f"Report isolation failed: {error}. Current results cannot be identified safely."
        warning(diagnostic)
    command = ["please", "run", "--at", point]
    if os.environ.get("PLEASE_CHECKS_ONLY", "false") == "true":
        command.append("--checks-only")
    start = time.monotonic()
    try:
        code = subprocess.run(command, check=False).returncode
        if code < 0:
            code = 128 - code
    except OSError as error:
        print(f"::error::Unable to execute Please Behave: {error}", flush=True)
        code = 127 if isinstance(error, FileNotFoundError) else 126
    elapsed = time.monotonic() - start
    try:
        try:
            require(isolated, diagnostic)
            require(not slot.parent.parent.is_symlink() and not slot.parent.is_symlink(),
                    "current report directory is symlinked")
            require(not slot.is_symlink() and slot.is_file(), "current invocation produced no regular report")
            with slot.open("rb") as stream:
                data = stream.read(REPORT_BYTES + 1)
            require(len(data) <= REPORT_BYTES, "report exceeds summary reader size limit")
            lines = render(json.loads(data), point, code, elapsed)
        except (OSError, ValueError, TypeError, KeyError, RecursionError) as error:
            warning(f"{error}; inspect CLI logs and .please/reports/last.json")
            lines = [f"\n## Please Behave — {escape(point)}\n\n",
                     f"CLI exit code: **{code}**. Summary unavailable: {escape(error)}.\n"]
        append_summary(lines)
    except Exception as error:
        warning(f"could not append GITHUB_STEP_SUMMARY: {error}; inspect CLI logs/report")
    finally:
        if backup is not None:
            try:
                previous = backup / "last.json"
                if previous.exists() and not os.path.lexists(slot):
                    previous.rename(slot)
                shutil.rmtree(backup)
            except OSError as error:
                warning(f"could not restore/clean previous report at {backup}: {error}")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
