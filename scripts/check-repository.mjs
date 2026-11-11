import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { load } from "js-yaml";

export function checkRepository(root) {
  const text = file => readFileSync(path.join(root, file), "utf8");
  const yaml = file => load(text(file));
  const metadata = yaml("action.yml");
  const readme = text("README.md");
  assert.equal(metadata.runs.using, "composite", "Action must remain composite");
  assert.deepEqual(Object.keys(metadata.inputs).sort(), ["checks-only", "execution-point", "install", "run", "summary", "sync", "version"]);
  assert.equal(metadata.inputs.summary.default, "true");
  assert.equal(metadata.inputs["checks-only"].default, "false");
  for (const step of metadata.runs.steps.filter(step => step.env)) {
    assert.equal(step.env.PLEASE_CHECKS_ONLY, "${{ inputs.checks-only }}");
  }
  const execution = metadata.runs.steps.find(step => step.name === "Run Please Behave");
  assert.equal(execution.if, "inputs.run == 'true'");
  assert.equal(execution.env.PLEASE_SUMMARY, "${{ inputs.summary }}");
  assert.equal(execution.run, 'bash "$ACTION_DIRECTORY/scripts/run.sh"');
  assert.equal(metadata.runs.steps[0].env.PLEASE_SUMMARY, "${{ inputs.summary }}");
  assert.equal(metadata.inputs.install.default, "true");
  assert.equal(metadata.inputs.sync.default, "false");
  assert.equal(metadata.inputs.version.required, false);
  assert.equal(metadata.runs.steps[0].env.PLEASE_INSTALL, "${{ inputs.install }}");
  assert.equal(metadata.runs.steps[0].env.PLEASE_SYNC, "${{ inputs.sync }}");
  const sync = metadata.runs.steps.find(step => step.name === "Synchronize governance");
  assert.equal(sync.if, "inputs.sync == 'true'");
  assert.equal(sync.run, "please sync --yes");
  assert.ok(metadata.runs.steps.indexOf(sync) < metadata.runs.steps.indexOf(execution));
  assert.equal(metadata.outputs, undefined, "Documented Action has no outputs");
  for (const [name, input] of Object.entries(metadata.inputs)) {
    const row = readme.split("\n").find(line => line.startsWith(`| \`${name}\` |`));
    assert.ok(row, `Missing README input: ${name}`);
    const cells = row.split("|").map(cell => cell.trim());
    assert.equal(cells[2], input.required ? "Yes" : "No", `Required input: ${name}`);
    const documented = cells[3].replaceAll("`", "").replaceAll("'", "");
    assert.equal(documented, input.default ?? "None", `Default input: ${name}`);
  }
  const manifest = JSON.parse(text("package.json"));
  assert.equal(manifest.scripts["release:plan"], "node scripts/release-plan.mjs");
  assert.equal(manifest.scripts.release, "node scripts/publish-release.mjs");
  const lock = JSON.parse(text("package-lock.json"));
  assert.equal(lock.name, manifest.name, "Lockfile package name");
  for (const key of ["name", "license", "engines", "devDependencies"]) {
    assert.deepEqual(lock.packages[""][key], manifest[key], `Lockfile ${key}`);
  }
  assert.equal(manifest.license, "PolyForm-Noncommercial-1.0.0");
  assert.ok(readme.replaceAll("`", "").includes(`(${manifest.license})`), "README license metadata");
  assert.equal(manifest.scripts.test, "please run --at pre-push");
  const version = execFileSync("python3", ["-c", 'import pathlib,tomllib; print("v" + tomllib.loads(pathlib.Path("mise.toml").read_text())["tools"]["github:please-behave/cli"])'], { cwd: root, encoding: "utf8" }).trim();
  assert.match(version, /^v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/);
  const ci = yaml(".github/workflows/ci.yml");
  const release = yaml(".github/workflows/release.yml");
  const candidate = release.jobs["release-candidate"];
  assert.deepEqual(Object.keys(release.on), ["workflow_dispatch"], "Releases must remain manual");
  assert.deepEqual(Object.keys(release.jobs).sort(), ["plan", "publish", "release-candidate", "release-readiness"]);
  assert.deepEqual(release.jobs.publish.needs, ["plan", "release-readiness", "release-candidate"]);
  assert.equal(release.jobs.plan.if, "github.ref == 'refs/heads/main'");
  assert.equal(release.jobs.plan.outputs.source_sha, "${{ steps.plan.outputs.source_sha }}");
  assert.equal(release.jobs.plan.outputs.version, "${{ steps.plan.outputs.version }}");
  assert.equal(release.jobs.plan.outputs.release, "${{ steps.plan.outputs.release }}");
  for (const id of ["release-readiness", "release-candidate"]) {
    assert.equal(release.jobs[id].needs, "plan");
    assert.equal(release.jobs[id].if, "needs.plan.outputs.release == 'true'");
  }
  assert.equal(candidate.name, "Release Candidate (${{ matrix.os }})");
  assert.deepEqual(candidate.strategy.matrix.os, ["ubuntu-24.04", "ubuntu-24.04-arm", "macos-15", "macos-15-intel"]);
  assert.equal(candidate.strategy["fail-fast"], false);
  assert.equal(candidate["runs-on"], "${{ matrix.os }}");
  assert.ok(!existsSync(path.join(root, ".github/workflows/action-e2e.yml")));
  assert.match(release.jobs.publish.if, /needs.release-readiness.result == 'success'/);
  assert.match(release.jobs.publish.if, /needs.release-candidate.result == 'success'/);
  assert.equal(release.jobs.publish["runs-on"], "ubuntu-24.04");
  for (const id of ["plan"]) {
    const steps = release.jobs[id].steps;
    for (const step of steps) {
      assert.notEqual(step.uses, "./", "Plan and Publish must not install the governor");
      assert.doesNotMatch(step.uses ?? "", /^please-behave\/action@/);
      assert.doesNotMatch(step.run ?? "", /\bplease\b/, "Plan and Publish must not run Please Behave");
    }
    assert.equal(steps[0].with.ref, id === "plan" ? "${{ github.sha }}" : "${{ needs.plan.outputs.source_sha }}");
  }
  assert.ok(release.jobs.plan.steps.some(step => step.run === "npm run release:plan"));
  const publication = release.jobs.publish.steps.find(step => step.run === "npm run release");
  assert.equal(publication.env.EXPECTED_RELEASE_VERSION, "${{ needs.plan.outputs.version }}");
  const readiness = release.jobs["release-readiness"];
  assert.deepEqual(readiness.permissions, { contents: "read", actions: "read" });
  assert.equal(readiness.steps[0].with.ref, "${{ needs.plan.outputs.source_sha }}");
  const readinessExecution = readiness.steps.find(step => step.with?.["execution-point"] === "release-readiness");
  assert.ok(readinessExecution, "Readiness executes through the published Action");
  assert.deepEqual(readinessExecution.with, {
    version: "${{ steps.governor.outputs.version }}", "execution-point": "release-readiness",
    "checks-only": "true", summary: "true",
  });
  assert.ok(readiness.steps.every(step => !/\bplease run\b/.test(step.run ?? "")));
  const policy = JSON.parse(text(".please/release-ci.json"));
  assert.deepEqual(policy, {
    schema_version: 1, repository: "please-behave/action", workflow: ".github/workflows/ci.yml",
    event: "push", branch: "main", required_jobs: ["Check (ubuntu-24.04)", "Check (ubuntu-24.04-arm)"],
  });
  for (const [workflow, name, id, display] of [[ci, "CI", "check", "Check (${{ matrix.os }})"]]) {
    assert.equal(workflow.name, name);
    assert.deepEqual(Object.keys(workflow.jobs), [id]);
    assert.equal(workflow.jobs[id].name, display);
    assert.equal(workflow.jobs[id].needs, undefined, "CI and Action E2E run independently");
    assert.deepEqual(workflow.on, { push: { branches: ["main"] }, pull_request: null, workflow_call: null });
    assert.deepEqual(workflow.permissions, { contents: "read" });
    assert.deepEqual(workflow.jobs[id].strategy.matrix.os, workflow === ci
      ? ["ubuntu-24.04", "ubuntu-24.04-arm"]
      : ["ubuntu-24.04", "ubuntu-24.04-arm", "macos-15", "macos-15-intel"]);
    assert.equal(workflow.jobs[id].strategy["fail-fast"], false);
    assert.equal(workflow.jobs[id]["runs-on"], "${{ matrix.os }}");
  }
  assert.deepEqual(ci.jobs.check.steps.filter(step => step.run).map(step => step.name),
    ["Prepare validation dependencies", "Read pinned governor version", "Synchronize governance"],
    "Regular checks must run through Please Behave");
  assert.ok(ci.jobs.check.steps.every(step => step.uses !== "./"), "Real Action tests belong in Release Candidate");
  assert.deepEqual(candidate.steps.filter(step => step.run).map(step => step.name),
    ["Read pinned governor version", "Prepare isolated summary acceptance fixture", "Verify Action outcomes and independent summaries", "Restore project governance"]);
  assert.deepEqual(release.permissions, { contents: "read" });
  assert.deepEqual(release.jobs.publish.permissions, { contents: "write" });
  assert.deepEqual(release.jobs.plan.permissions, { contents: "write" });
  const invocations = candidate.steps.filter(step => step.uses === "./");
  assert.deepEqual(invocations.map(step => step.with["execution-point"]), ["summary-first", "summary-second"]);
  const fixture = candidate.steps.find(step => step.name === "Prepare isolated summary acceptance fixture");
  const customPoints = fixture.run.match(/\[execution_points\]\s+custom = (\[[^\n]+\])/);
  assert.ok(customPoints, "Summary fixture must declare its custom execution points");
  assert.deepEqual(JSON.parse(customPoints[1]), invocations.map(step => step.with["execution-point"]),
    "Summary fixture declarations must match the Action invocations");
  assert.equal(invocations[0].id, "passing");
  assert.equal(invocations[0]["continue-on-error"], undefined);
  assert.equal(invocations[1].id, "failing");
  assert.equal(invocations[1]["continue-on-error"], true);
  assert.equal(invocations[1].env.FIXTURE_RESULT, "1");
  assert.equal(invocations[1].with["checks-only"], "true");
  assert.equal(invocations[1].with.install, "false");
  assert.equal(invocations[1].with.sync, "true");
  assert.equal(invocations[1].with.version, undefined);
  const verification = candidate.steps.find(step => step.name === "Verify Action outcomes and independent summaries");
  assert.equal(verification.if, "always()");
  assert.equal(verification.run, "python3 scripts/check-action-e2e.py");
  assert.deepEqual(verification.env, {
    PASSING_OUTCOME: "${{ steps.passing.outcome }}",
    PASSING_CONCLUSION: "${{ steps.passing.conclusion }}",
    FAILING_OUTCOME: "${{ steps.failing.outcome }}",
    FAILING_CONCLUSION: "${{ steps.failing.conclusion }}",
  });
  for (const workflow of [ci, release]) {
    for (const job of Object.values(workflow.jobs)) {
      let checkedOut = false;
      for (const step of job.steps ?? []) {
        if (step.uses?.startsWith("actions/checkout@")) {
          checkedOut = true;
          assert.equal(step.with["persist-credentials"], false);
        }
        if (step.uses === "./" || step.uses?.startsWith("please-behave/action@")) {
          assert.ok(checkedOut, "Checkout must precede the governor Action");
          if (step.with.install !== "false") {
            assert.equal(step.with.version, "${{ steps.governor.outputs.version }}", "CLI pin must match mise.toml");
          }
        }
        if (step.uses && !step.uses.startsWith("./")) {
          assert.match(step.uses, /@[a-f0-9]{40}$/, "External Actions require full SHA pins");
        }
      }
    }
  }
  const quality = ci.jobs.check.steps.find(step => step.name === "Run quality gates");
  const installation = ci.jobs.check.steps.find(step => step.name === "Install published governor");
  assert.match(quality.uses, /^please-behave\/action@[a-f0-9]{40}$/);
  assert.equal(quality.uses, installation.uses, "Installation and execution use the same published Action");
  assert.equal(readinessExecution.uses, quality.uses);
  assert.deepEqual(quality.with, { version: "${{ steps.governor.outputs.version }}", "execution-point": "check", summary: "true" });
  assert.equal(installation.with.run, "false");
  const synchronization = ci.jobs.check.steps.findIndex(step => step.run === "please sync --yes");
  assert.ok(ci.jobs.check.steps.indexOf(installation) < synchronization);
  assert.ok(synchronization < ci.jobs.check.steps.indexOf(quality));

  const record = candidate.steps.find(step => step.with?.["execution-point"] === "release-record");
  assert.ok(record && candidate.steps.indexOf(record) > candidate.steps.indexOf(verification));
  assert.equal(record.env.RELEASE_TARGET, "${{ matrix.os }}");
  const evidence = candidate.steps.find(step => step.name === "Upload release candidate evidence");
  assert.match(evidence.with.name, /github.run_attempt/);
  assert.equal(evidence.with["if-no-files-found"], "error");
  const verify = release.jobs.publish.steps.find(step => step.with?.["execution-point"] === "release-verify");
  assert.ok(verify && release.jobs.publish.steps.indexOf(verify) < release.jobs.publish.steps.indexOf(publication));
  assert.equal(verify.with["checks-only"], "true");
  assert.equal(verify.with.summary, "true");

  for (const file of ["README.md", "CONTRIBUTING.md", "docs/releasing.md"]) {
    for (const match of text(file).matchAll(/\[[^\]]*\]\(([^)]+)\)/g)) {
      const target = match[1].split("#")[0];
      if (!target || /^[a-z]+:/i.test(target)) continue;
      assert.ok(existsSync(path.resolve(root, path.dirname(file), decodeURIComponent(target))),
        `Missing local link in ${file}: ${target}`);
    }
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try {
    checkRepository(process.cwd());
    console.log("Action metadata, documentation, lockfile and workflow contracts passed.");
  } catch (error) {
    console.error(error.message);
    process.exitCode = 1;
  }
}
