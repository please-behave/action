// Repository contracts: Action metadata against README, package metadata, release workflow
// safety properties and local documentation links. Assertion failures are verdicts (exit 1);
// anything else is a technical error (exit 2).
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
  assert.deepEqual(Object.keys(metadata.inputs).sort(), ["checks-only", "execution-point", "install", "run", "summary", "sync", "version"]);
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
  assert.ok(readme.replaceAll("`", "").includes(`(${manifest.license})`), "README license metadata");

  const ci = yaml(".github/workflows/ci.yml");
  const release = yaml(".github/workflows/release.yml");
  assert.deepEqual(Object.keys(release.on), ["workflow_dispatch"], "Releases must remain manual");
  assert.deepEqual(release.permissions, { contents: "read" });
  assert.deepEqual(release.jobs.publish.permissions, { contents: "write" });
  assert.deepEqual(release.jobs.plan.permissions, { contents: "write" });
  assert.deepEqual(release.jobs["release-readiness"].permissions, { contents: "read", actions: "read" });
  assert.deepEqual(release.jobs.publish.needs, ["plan", "release-readiness", "release-candidate"]);
  assert.match(release.jobs.publish.if, /needs.release-readiness.result == 'success'/);
  assert.match(release.jobs.publish.if, /needs.release-candidate.result == 'success'/);
  for (const id of ["plan", "publish"]) {
    for (const step of release.jobs[id].steps) {
      assert.notEqual(step.uses, "./", "Plan and Publish must not install the governor");
      assert.doesNotMatch(step.uses ?? "", /^please-behave\/action@/);
      assert.doesNotMatch(step.run ?? "", /\bplease\b/, "Plan and Publish must not run Please Behave");
    }
  }
  const steps = release.jobs.publish.steps;
  const verify = steps.findIndex(step => step.run?.endsWith("release-evidence.py verify"));
  const publish = steps.findIndex(step => step.run === "npm run release");
  assert.ok(verify >= 0 && verify < publish, "Candidate evidence must be verified before publication");
  assert.equal(steps[publish].env.EXPECTED_RELEASE_VERSION, "${{ needs.plan.outputs.version }}");

  const policy = JSON.parse(text(".github/release-ci.json"));
  assert.deepEqual(policy.required_jobs, ci.jobs.check.strategy.matrix.os.map(os => `Check (${os})`),
    "Release CI policy must name every CI matrix job");

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
        }
        if (step.uses && !step.uses.startsWith("./")) {
          assert.match(step.uses, /@[a-f0-9]{40}$/, "External Actions require full SHA pins");
        }
      }
    }
  }

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
    console.log("Action metadata, package, release workflow and documentation contracts passed.");
  } catch (error) {
    const verdict = error instanceof assert.AssertionError;
    console.error(verdict ? error.message : `${error.name}: ${error.message}`);
    process.exitCode = verdict ? 1 : 2;
  }
}
