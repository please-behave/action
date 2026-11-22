"""Run governance, optionally register rule versions and publish the report, and summarize the results."""

import html
import json
import os
from pathlib import Path
import re
import subprocess
import time

STATUSES = {"PASS", "FAIL", "ERROR", "NOT_RUN", "CANCELLED"}
SUMMARY_BYTES = 900 * 1024
REPORT_BYTES = 32 * 1024 * 1024
REPORT_NAME = re.compile(r"([1-9][0-9]*)\.json")
REPORTS = Path(".please/reports")


def command_data(value):
    # Annotation commands must not receive unescaped report/environment content.
    return str(value).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def warning(message):
    print(f"::warning::Please Behave summary: {command_data(message)}", flush=True)


def escape(value):
    value = str(value)
    if len(value) > 512:
        value = value[:512] + "… [truncated]"
    value = " ".join(value.split())
    # Encode punctuation as entities so Markdown, HTML, links and mentions are inert.
    return "".join(html.escape(c, quote=True) if c.isalnum() or c == " " else f"&#{ord(c)};" for c in value)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate(report, point):
    require(isinstance(report, dict), "report must be an object")
    require(
        type(report.get("schema_version")) is int and report["schema_version"] in (0, 1),
        "unsupported report schema (expected 0 or 1); select a compatible CLI release",
    )
    plan = report.get("plan")
    require(
        isinstance(plan, dict) and type(plan.get("plan_schema_version")) is int and plan["plan_schema_version"] in (0, 1),
        "unsupported plan schema (expected 0 or 1)",
    )
    require(plan.get("at") == point, "report execution point does not match this invocation")
    require(report.get("repository") == str(Path.cwd().resolve()), "report repository does not match")
    require(report.get("overall") in {"PASS", "FAIL", "ERROR"}, "invalid aggregate outcome")
    rules, results = plan.get("scheduled"), report.get("results")
    require(isinstance(rules, list) and isinstance(results, list), "missing scheduled rules or results")
    scheduled = {}
    for rule in rules:
        require(isinstance(rule, dict), "invalid scheduled rule")
        identity = rule.get("id")
        require(isinstance(identity, str) and identity and identity not in scheduled, "missing or duplicate scheduled rule identity")
        require(
            rule.get("kind") in {"check", "review"}
            and isinstance(rule.get("description"), str)
            and (rule.get("name") is None or isinstance(rule["name"], str))
            and type(rule.get("blocking")) is bool,
            "invalid scheduled rule metadata",
        )
        scheduled[identity] = rule
    matched, integrity = {}, []
    for result in results:
        require(isinstance(result, dict), "invalid result")
        identity = result.get("id")
        require(isinstance(identity, str) and identity, "missing result identity")
        require(
            result.get("status") in STATUSES
            and type(result.get("blocking")) is bool
            and type(result.get("duration_ms")) is int
            and result["duration_ms"] >= 0
            and isinstance(result.get("reason"), str),
            "invalid result metadata",
        )
        if result.get("kind") == "integrity":
            require(identity not in scheduled and identity not in {r["id"] for r in integrity}, "duplicate integrity identity")
            integrity.append(result)
        else:
            require(identity in scheduled and identity not in matched, "unexpected or duplicate rule result")
            rule = scheduled[identity]
            require(
                result.get("kind") == rule["kind"] and result["blocking"] == rule["blocking"],
                "result does not correspond to scheduled rule",
            )
            matched[identity] = result
    require(set(matched) == set(scheduled), "incomplete scheduled rule results")
    return rules, matched, integrity


def render(report, point, code, elapsed):
    rules, results, integrity = validate(report, point)
    lines = [
        f"\n## Please Behave — {escape(point)}\n\n",
        f"CLI aggregate outcome: **{report['overall']}**. CLI exit code: **{code}**.\n\n",
        f"Total CLI execution duration: {elapsed:.3f} s (wall clock).\n\n",
    ]
    if code != 0:
        lines.append("**Invocation exited unsuccessfully.** The saved CLI aggregate outcome is shown above.\n\n")
    if not rules:
        lines.append("No rules were scheduled for this execution point.\n\n")
    else:
        lines.append("| Plan | Status | Rule name | Description | Duration |\n| --- | --- | --- | --- | --- |\n")
        for index, rule in enumerate(rules, 1):
            result = results[rule["id"]]
            enforcement = "" if rule["blocking"] else " (non-blocking)"
            name = rule.get("name") or rule["id"].rsplit(":", 1)[-1]
            lines.append(
                f"| {index}/{len(rules)} | {result['status']}{enforcement} | "
                f"{escape(name)} | {escape(rule['description'])} | "
                f"{result['duration_ms']} ms |\n"
            )
        lines.append("\nNon-blocking results do not replace the CLI aggregate outcome; configuration errors can still block.\n\n")
    reviews = [rule for rule in rules if rule["kind"] == "review"]
    if reviews:
        lines.append("### Review details\n\n")
        for rule in reviews:
            result = results[rule["id"]]
            name = rule.get("name") or rule["id"].rsplit(":", 1)[-1]
            lines.append(f"#### {escape(name)} — {result['status']}\n\n{escape(result['reason'])}\n\n")
            findings = result.get("findings", [])
            require(isinstance(findings, list), "invalid review findings")
            for finding in findings[:20]:
                require(isinstance(finding, dict) and isinstance(finding.get("message"), str), "invalid review finding")
                location = finding.get("path") or "No source location"
                if finding.get("line") is not None:
                    location = f"{location}:{finding['line']}"
                lines.append(f"- {escape(location)}: {escape(finding['message'])}\n")
            if len(findings) > 20:
                lines.append("\nFindings truncated; consult the saved CLI report.\n")
    omitted = report["plan"].get("omitted", [])
    require(isinstance(omitted, list), "invalid omitted rules")
    for item in omitted:
        require(isinstance(item, dict) and isinstance(item.get("rule"), dict), "invalid omitted rule")
        rule = item["rule"]
        if rule.get("kind") == "review" and item.get("reason") == "trigger_not_matched":
            require(isinstance(rule.get("id"), str), "invalid omitted review identity")
            name = rule.get("name") or rule["id"].rsplit(":", 1)[-1]
            lines.append(f"\nReview {escape(name)}: not selected because its change trigger did not match.\n")
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
            warning("output truncated; consult the saved CLI reports in .please/reports for complete results")
            break
        output.append(line)
        used += size
    require(available >= len(suffix.encode()), "step summary is already full; use the CLI logs/report")
    with target.open("a", encoding="utf-8") as stream:
        stream.write("".join(output))


def saved_numbers(directory):
    for component in (directory.parent, directory):
        require(not component.is_symlink(), "report directory is symlinked")
    if not directory.exists():
        return set()
    require(directory.is_dir(), "report directory is not a directory")
    return {int(match[1]) for entry in directory.iterdir() if (match := REPORT_NAME.fullmatch(entry.name))}


def current_report(directory, previous, diagnostic, publishing):
    require(diagnostic is None, diagnostic)
    saved = saved_numbers(directory)
    created = saved - previous
    require(created, "current invocation saved no report")
    number = max(created)
    if publishing:
        require(number == max(saved), "newest report predates the current invocation")
    slot = directory / f"{number}.json"
    require(not slot.is_symlink() and slot.is_file(), "current invocation saved no regular report")
    return slot


def run_summary(slot, diagnostic, point, code, elapsed):
    try:
        require(diagnostic is None, diagnostic)
        with slot.open("rb") as stream:
            data = stream.read(REPORT_BYTES + 1)
        require(len(data) <= REPORT_BYTES, "report exceeds summary reader size limit")
        return render(json.loads(data), point, code, elapsed)
    except (OSError, ValueError, TypeError, KeyError, RecursionError) as error:
        warning(f"{error}; inspect CLI logs and .please/reports")
        return [f"\n## Please Behave — {escape(point)}\n\n", f"CLI exit code: **{code}**. Summary unavailable: {escape(error)}.\n"]


def publish(gateway_url, slot):
    if slot is None:
        return "The current invocation did not save an identifiable report."
    try:
        # CLI or transport diagnostics may contain the secret origin.
        result = subprocess.run(
            ["please", "publish", "--gateway-url", gateway_url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False
        )
    except (OSError, ValueError):
        return "Unable to start please publish."
    if result.returncode != 0:
        return f"please publish exited unsuccessfully (exit status {result.returncode})."
    return None


def register(gateway_url):
    lines = ["\n## Rule version registration\n\n"]
    if not gateway_url:
        return lines, "The gateway-url input is required when register is true."
    try:
        result = subprocess.run(
            ["please", "register", "--gateway-url", gateway_url],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except (OSError, ValueError):
        return lines, "Unable to start please register."
    for outcome in result.stdout.splitlines():
        # The CLI emits outcomes on stdout and diagnostics on stderr. Only render
        # outcome lines as inert Markdown, since they contain local rule paths.
        if outcome.startswith(("created ", "unchanged ", "conflict ")) or outcome == "No rule directories to register.":
            lines.append(f"- {escape(outcome.replace(gateway_url, '[redacted]'))}\n")
    lines.append("\n")
    error = f"please register exited unsuccessfully (exit status {result.returncode})." if result.returncode else None
    return lines, error


def main():
    point = os.environ["PLEASE_EXECUTION_POINT_INPUT"]
    summarize = os.environ.get("PLEASE_SUMMARY", "true") == "true"
    gateway_url = os.environ.pop("PLEASE_GATEWAY_URL_INPUT", "")
    if gateway_url:
        print(f"::add-mask::{command_data(gateway_url)}", flush=True)
    directory = Path.cwd() / REPORTS
    previous = set()
    diagnostic = None
    try:
        previous = saved_numbers(directory)
    except (OSError, ValueError) as error:
        diagnostic = f"Saved report numbers cannot be read: {error}. Current results cannot be identified safely."
        if summarize:
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

    registration_lines, registration_error = [], None
    if code == 0 and os.environ.get("PLEASE_REGISTER") == "true":
        registration_lines, registration_error = register(gateway_url)
        if registration_error:
            registration_lines.append(f"**Failed.** {registration_error}\n\n")
            print(f"::error::Please Behave rule registration failed. {registration_error}", flush=True)

    slot = None
    try:
        slot = current_report(directory, previous, diagnostic, publishing=bool(gateway_url))
    except (OSError, ValueError) as error:
        diagnostic = error

    delivery_error = publish(gateway_url, slot) if gateway_url else None
    if delivery_error:
        print(f"::warning::Please Behave attestation delivery failed. {delivery_error}", flush=True)

    try:
        lines = registration_lines
        if summarize:
            lines.extend(run_summary(slot, diagnostic, point, code, elapsed))
        if delivery_error:
            lines.insert(0, f"\nAttestation delivery: **Failed.** {delivery_error}\n\n")
        elif gateway_url and summarize:
            lines.insert(0, "\nAttestation delivery: **Accepted.**\n\n")
        if lines:
            append_summary(lines)
    except Exception as error:
        warning(f"could not append GITHUB_STEP_SUMMARY: {error}; inspect CLI logs/report")
    if code == 0 and (registration_error or (delivery_error and os.environ.get("PLEASE_PUBLISH_REQUIRED") == "true")):
        return 1
    return code


if __name__ == "__main__":
    raise SystemExit(main())
