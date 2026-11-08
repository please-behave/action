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
  assert.deepEqual(Object.keys(metadata.inputs).sort(), ["execution-point", "run", "version"]);
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
  const release = yaml(".github/workflows/release.yml");
  assert.deepEqual(Object.keys(release.on), ["workflow_dispatch"], "Releases must remain manual");
  assert.deepEqual(Object.keys(release.jobs).sort(), ["checks", "publish"]);
  assert.equal(release.jobs.publish.needs, "checks");
  assert.equal(release.jobs.publish["runs-on"], "ubuntu-24.04");
  for (const step of release.jobs.publish.steps) {
    assert.notEqual(step.uses, "./", "Publish must not install the governor");
    assert.doesNotMatch(step.uses ?? "", /^please-behave\/action@/, "Publish must not install the governor");
    assert.doesNotMatch(step.run ?? "", /\bplease\b/, "Publish must not run Please Behave");
  }
  assert.equal(release.jobs.checks.uses, "./.github/workflows/ci.yml");
  assert.equal(release.jobs.checks.if, "github.ref == 'refs/heads/main'");
  assert.deepEqual(ci.permissions, { contents: "read" });
  assert.deepEqual(release.permissions, { contents: "read" });
  assert.deepEqual(release.jobs.publish.permissions, { contents: "write" });
  assert.deepEqual(ci.jobs.tests.strategy.matrix.os, ["ubuntu-24.04", "ubuntu-24.04-arm"]);
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
          assert.equal(step.with.version, version, "CLI pin must match .please-version");
        }
        if (step.uses && !step.uses.startsWith("./")) {
          assert.match(step.uses, /@[a-f0-9]{40}$/, "External Actions require full SHA pins");
        }
      }
    }
  }
  assert.ok(ci.jobs.tests.steps.some(step => step.run === "please run --at check"));
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
