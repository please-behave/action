import assert from "node:assert/strict";
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
  assert.deepEqual(Object.keys(metadata.inputs).sort(), ["execution-point", "run", "summary", "version"]);
  assert.equal(metadata.inputs.summary.default, "true");
  const execution = metadata.runs.steps.find(step => step.name === "Run Please Behave");
  assert.equal(execution.if, "inputs.run == 'true'");
  assert.equal(execution.env.PLEASE_SUMMARY, "${{ inputs.summary }}");
  assert.equal(execution.run, 'bash "$ACTION_DIRECTORY/scripts/run.sh"');
  assert.equal(metadata.runs.steps[0].env.PLEASE_SUMMARY, "${{ inputs.summary }}");
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
  const lock = JSON.parse(text("package-lock.json"));
  assert.equal(lock.name, manifest.name, "Lockfile package name");
  for (const key of ["name", "license", "engines", "devDependencies"]) {
    assert.deepEqual(lock.packages[""][key], manifest[key], `Lockfile ${key}`);
  }
  assert.equal(manifest.license, "PolyForm-Noncommercial-1.0.0");
  assert.ok(readme.replaceAll("`", "").includes(`(${manifest.license})`), "README license metadata");
  assert.equal(manifest.scripts.test, "please run --at pre-push");
  const version = text(".please-version").trim();
  assert.match(version, /^v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/);
  const ci = yaml(".github/workflows/ci.yml");
  const e2e = yaml(".github/workflows/action-e2e.yml");
  const release = yaml(".github/workflows/release.yml");
  assert.deepEqual(Object.keys(release.on), ["workflow_dispatch"], "Releases must remain manual");
  assert.deepEqual(Object.keys(release.jobs).sort(), ["action-e2e", "checks", "publish"]);
  assert.deepEqual(release.jobs.publish.needs, ["checks", "action-e2e"]);
  assert.equal(release.jobs.publish["runs-on"], "ubuntu-24.04");
  for (const step of release.jobs.publish.steps) {
    assert.notEqual(step.uses, "./", "Publish must not install the governor");
    assert.doesNotMatch(step.uses ?? "", /^please-behave\/action@/, "Publish must not install the governor");
    assert.doesNotMatch(step.run ?? "", /\bplease\b/, "Publish must not run Please Behave");
  }
  assert.equal(release.jobs.checks.uses, "./.github/workflows/ci.yml");
  assert.equal(release.jobs.checks.if, "github.ref == 'refs/heads/main'");
  assert.equal(release.jobs["action-e2e"].uses, "./.github/workflows/action-e2e.yml");
  assert.equal(release.jobs["action-e2e"].if, "github.ref == 'refs/heads/main'");
  for (const [workflow, name, id, display] of [[ci, "CI", "check", "Check"], [e2e, "Action E2E", "test", "Test"]]) {
    assert.equal(workflow.name, name);
    assert.deepEqual(Object.keys(workflow.jobs), [id]);
    assert.equal(workflow.jobs[id].name, display);
    assert.equal(workflow.jobs[id].needs, undefined, "CI and Action E2E run independently");
    assert.deepEqual(workflow.on, { push: { branches: ["main"] }, pull_request: null, workflow_call: null });
    assert.deepEqual(workflow.permissions, { contents: "read" });
    assert.deepEqual(workflow.jobs[id].strategy.matrix.os, ["ubuntu-24.04", "ubuntu-24.04-arm"]);
    assert.equal(workflow.jobs[id].strategy["fail-fast"], false);
    assert.equal(workflow.jobs[id]["runs-on"], "${{ matrix.os }}");
  }
  assert.deepEqual(ci.jobs.check.steps.filter(step => step.run).map(step => step.name),
    ["Prepare validation dependencies", "Synchronize governance", "Run quality gates"],
    "Regular checks must run through Please Behave");
  assert.ok(ci.jobs.check.steps.every(step => step.uses !== "./"), "Real Action tests belong in Action E2E");
  assert.deepEqual(e2e.jobs.test.steps.filter(step => step.run).map(step => step.name),
    ["Prepare isolated summary acceptance fixture", "Verify Action outcomes and independent summaries"]);
  assert.deepEqual(release.permissions, { contents: "read" });
  assert.deepEqual(release.jobs.publish.permissions, { contents: "write" });
  const invocations = e2e.jobs.test.steps.filter(step => step.uses === "./");
  assert.deepEqual(invocations.map(step => step.with["execution-point"]), ["summary-first", "summary-second"]);
  const fixture = e2e.jobs.test.steps.find(step => step.name === "Prepare isolated summary acceptance fixture");
  const customPoints = fixture.run.match(/\[execution_points\]\s+custom = (\[[^\n]+\])/);
  assert.ok(customPoints, "Summary fixture must declare its custom execution points");
  assert.deepEqual(JSON.parse(customPoints[1]), invocations.map(step => step.with["execution-point"]),
    "Summary fixture declarations must match the Action invocations");
  assert.equal(invocations[0].id, "passing");
  assert.equal(invocations[0]["continue-on-error"], undefined);
  assert.equal(invocations[1].id, "failing");
  assert.equal(invocations[1]["continue-on-error"], true);
  assert.equal(invocations[1].env.FIXTURE_RESULT, "1");
  const verification = e2e.jobs.test.steps.at(-1);
  assert.equal(verification.if, "always()");
  assert.equal(verification.run, "python3 scripts/check-action-e2e.py");
  assert.deepEqual(verification.env, {
    PASSING_OUTCOME: "${{ steps.passing.outcome }}",
    PASSING_CONCLUSION: "${{ steps.passing.conclusion }}",
    FAILING_OUTCOME: "${{ steps.failing.outcome }}",
    FAILING_CONCLUSION: "${{ steps.failing.conclusion }}",
  });
  for (const workflow of [ci, e2e, release]) {
    for (const job of Object.values(workflow.jobs)) {
      let checkedOut = false;
      for (const step of job.steps ?? []) {
        if (step.uses?.startsWith("actions/checkout@")) {
          checkedOut = true;
          assert.equal(step.with["persist-credentials"], false);
        }
        if (step.uses === "./" || step.uses?.startsWith("please-behave/action@")) {
          assert.ok(checkedOut, "Checkout must precede the governor Action");
          assert.equal(step.with.version, version, "CLI pin must match .please-version");
        }
        if (step.uses && !step.uses.startsWith("./")) {
          assert.match(step.uses, /@[a-f0-9]{40}$/, "External Actions require full SHA pins");
        }
      }
    }
  }
  assert.ok(ci.jobs.check.steps.some(step => step.run === "please run --at check"));
  assert.ok(release.jobs.publish.steps.some(step => step.run === "python3 scripts/check-release-ready.py"));
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
