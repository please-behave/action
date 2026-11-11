# Contributing

Follow the existing composite Action architecture and keep changes focused.
Run `mise trust` and `mise install` to prepare the exact Node, Python, ShellCheck,
actionlint and Gitleaks versions in `mise.toml`. Bash and Git remain host prerequisites.
Install the released Please Behave version pinned in `.please-version`; never
use a candidate CLI build as the governor. Prepare Node dependencies with
`mise run setup`, then install managed Git hooks and synchronize the
pinned external rulesets with `mise exec -- sh scripts/setup-git-hooks.sh --yes`.
Setup needs network access; pre-commit and pre-push use prepared dependencies offline.
Use `mise exec -- please run --at pre-commit` or `mise exec -- please run --at pre-push`
for manual checks. Run Git as `mise exec -- git commit` and `mise exec -- git push`
so managed hooks inherit the configured tools without shell activation.
Plain commands require mise shell activation or equivalent PATH setup;
`mise install` alone does not activate tools. Keep the separately installed
published governor on PATH and supply credentials externally.

Please Behave owns the repository's quality gates:

| Execution point | Checks |
| --- | --- |
| `pre-commit` | Repository metadata/documentation contracts and standalone shell scripts |
| `commit-msg` | Imported Conventional Commits Check and advisory header wording Review |
| `pre-push` | Offline Python and Node tests, workflow/shell/contract checks, imported security and license checks |
| `check` | The same quality gates as `pre-push`, on the CI checkout |
| `release-readiness` | Exact-commit CI proof, committed-source security/license, current npm audit and public CLI assets |

Commit and push to run validation through the installed hooks. `npm test`
delegates to `please run --at pre-push`; it does not define a second test suite.
Coding agents use the Git hooks for validation. Inspect failures with
`please status --details`, fix the cause and retry the Git operation.
Keep new repository checks in `.please/` and reuse the configured external rules.

The imported `rulesets/commit-msg/repository-conventions` ruleset is the authoritative message validator.
Scopes are optional and configured in `.please/commit-scopes.txt`: action, ci,
deps, docs, git, release and tests. There is no additional local message policy.
The shared advisory Review evaluates only the header for specific English
imperative wording, without the diff, body or repository files. Its
`gemini-flash-lite` provider is independently imported from
`providers/gemini-flash-lite` in the same external repository; no adapter is copied
locally. All four Rule Sets and the provider share one immutable revision.
Export GEMINI_API_KEY in the shell running Git. Review FAIL and ERROR, including
missing credentials, remain visible without blocking commits. The adapter allows
three attempts with 1/3-second waits, 20 seconds per request and a 70-second
provider deadline.
Commit-message validation runs only in the managed local `commit-msg` hook;
CI checks neither history nor PR titles. This repository uses direct maintainer
pushes to `main`, with dependency PRs from Renovate.

Renovate applies a minimum release age of seven days, or fourteen days for major
updates. This is best effort: updates without a release timestamp may proceed.
GitHub tag timestamps may not reflect republished content, and this policy does
not guarantee the age of every transitive lockfile dependency.

The `python-tests` check covers installation, checksum verification, input
validation, execution-point argument handling, exit-code propagation and
install-only behavior using offline archives and the Action execution command.
Other Python tests cover repository contracts and release readiness guards.
Node tests cover release policy and publication in isolated Git repositories.
These checks run at `pre-push` and `check`; CI runs them on Linux x64 and ARM64.
The independent Action E2E workflow runs the actual composite Action through
`uses: ./` on Linux x64/ARM64 and macOS ARM64/Intel, with repeated invocations,
independent Job Summaries and an expected failed checks-only governance execution.
CI has one matrix job,
`check` / `Check (RUNNER)`; Action E2E has one matrix job, `test` / `Test`. Both workflows
run on pushes to main, pull requests and reusable workflow calls. Neither waits
for the other during normal development.

The negative E2E step uses `continue-on-error: true`. The verifier requires its
raw `outcome` to be `failure` and its effective `conclusion` to be `success`;
the positive invocation must report success for both. It also verifies each
summary's execution point, aggregate outcome, exact exit code, rule row and
isolation. Unexpected success, unexpected failure, skipped invocations and
missing summaries fail the test. Verification runs even after an earlier failure.
GitHub can still emit a native nonzero-exit annotation for the expected failure;
this is labeled explicitly in the step name. Suppressing it by masking the Action
exit code would invalidate the outcome test. Offline tests of the verifier and
workflow contracts remain part of Please Behave's regular quality checks.
Tests must not invoke providers, live reviews or paid APIs.

Local hooks are bypassable. General checks evaluate working files, which may
include unstaged edits; imported security and license checks read `HEAD` at
pre-push. Clean CI checkouts provide the release gate. Security scans cover a
snapshot, not all historical commits or every pushed ref.

Release plans the next version, then runs Readiness and the E2E Candidate in
parallel. Readiness uses the pinned external
`rulesets/multi-point/releasable-open-source-software` ruleset to verify both
explicitly named CI matrix entries for the dispatched commit, reusing source
security, license and npm audit results. Local rules check the public CLI assets.
It reuses existing push CI rather than rerunning general checks. Plan and
Publish run no Please Behave or hooks. Publication refuses a changed planned
version or source revision before tagging. See the release contract for CI reruns
and readiness prerequisites.

See [the release contract](docs/releasing.md) for versioning and publication.
Contributions use the [PolyForm Noncommercial License 1.0.0](LICENSE).
