# Contributing

Follow the existing composite Action architecture and keep changes focused.
Use Node 26, Python 3, Bash, Git, ShellCheck, actionlint and Gitleaks 8.30.1.
Install the released Please Behave version pinned in `.please-version`; never
use a candidate CLI build as the governor. Prepare Node dependencies with
`npm ci --ignore-scripts`, then install managed Git hooks and synchronize the
pinned external rulesets with `sh scripts/setup-git-hooks.sh --yes`.
Setup needs network access; local validation uses prepared dependencies offline.

Please Behave owns the repository's quality gates:

| Execution point | Checks |
| --- | --- |
| `pre-commit` | Repository metadata/documentation contracts and standalone shell scripts |
| `commit-msg` | Imported Conventional Commits validator |
| `pre-push` | Offline Python and Node tests, workflow/shell/contract checks, imported security and license checks |
| `check` | The same quality gates as `pre-push`, on the CI checkout |

Commit and push to run validation through the installed hooks. `npm test`
delegates to `please run --at pre-push`; it does not define a second test suite.
Coding agents use the Git hooks for validation. Inspect failures with
`please status --details`, fix the cause and retry the Git operation.
Keep new repository checks in `.please/` and reuse the configured external rules.

The imported `conventional-commits` ruleset is the authoritative message validator.
Scopes are optional and configured in `.please/commit-scopes.txt`: action, ci,
deps, docs, git, release and tests. There is no additional local message policy.
Commit-message validation runs only in the managed local `commit-msg` hook;
CI checks neither history nor PR titles. This repository uses direct maintainer
pushes to `main`, with dependency PRs from Renovate.

The `python-tests` check covers installation, checksum verification, input
validation, execution-point argument handling, exit-code propagation and
install-only behavior using offline archives and the Action execution command.
Other Python tests cover repository contracts and release readiness guards.
Node tests cover release policy and publication in isolated Git repositories.
These checks run at `pre-push` and `check`; CI runs them on x64 and ARM64.
The independent Action E2E workflow runs the actual composite Action through
`uses: ./` on both architectures, with repeated invocations, independent Job
Summaries and an expected failed governance execution. CI has one matrix job,
`check` / `Check`; Action E2E has one matrix job, `test` / `Test`. Both workflows
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

The publish job runs the release-readiness script directly to verify the tested
main revision and public CLI assets without installing Please Behave or hooks.

See [the release contract](docs/releasing.md) for versioning and publication.
Contributions use the [PolyForm Noncommercial License 1.0.0](LICENSE).
