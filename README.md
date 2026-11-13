# Please Behave Action

A lightweight composite GitHub Action that installs and invokes the
[Please Behave CLI](https://github.com/please-behave/cli). The CLI evaluates
repository rules; this Action provides installation, optional synchronization,
GitHub review context and per-invocation Job Summaries.

## Usage

Replace the Action ref and CLI version in the examples with the releases you adopt.
macOS and `checks-only` support require Action `v1.2.0` or later.
Use CLI `v0.1.0` or a compatible later stable release. The Action ref and CLI
version are independent.

```yaml
permissions:
  contents: read

jobs:
  check:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v7
        with:
          persist-credentials: false
      - uses: please-behave/action@<action-tag>
        with:
          version: <cli-tag>
          execution-point: check
```

Check out a Git repository with `.please/` configuration and prepare the tools
and credentials required by its rules before running the Action.

## Inputs

| Input | Required | Default | Meaning |
| --- | --- | --- | --- |
| `version` | No | None | Required when `install: 'true'`: exact stable CLI tag `vMAJOR.MINOR.PATCH`. No `latest`, ranges or prereleases. Ignored when installation is disabled. |
| `install` | No | `'true'` | Download the selected CLI; `'false'` uses `please` already on PATH without downloading or checking its version. |
| `sync` | No | `'false'` | `'true'` runs `please sync --yes` before execution, including when `run: 'false'`. |
| `execution-point` | No | `check` | Point passed as one argument to `please run --at`. |
| `checks-only` | No | `'false'` | `'true'` adds `--checks-only`, omitting reviews while retaining Job Summaries. Only exact true/false values are accepted. |
| `run` | No | `'true'` | `'true'` executes after preparation; `'false'` skips execution. Other values fail. |
| `summary` | No | `'true'` | `'true'` appends a Job Summary for this execution; `'false'` bypasses summary processing. Only these exact values are accepted. |

Boolean inputs accept only the exact strings `true` and `false`.

There are no Action outputs. The installed `please` executable is available on
PATH to subsequent steps in the same job, including with `run: 'false'`.

## Installation and execution

Supported runners are GitHub-hosted Ubuntu 24.04 x64 (`ubuntu-24.04`) and ARM64
(`ubuntu-24.04-arm`), and macOS ARM64 (`macos-15`) and Intel (`macos-15-intel`).
The installer selects the matching `x86_64` or `aarch64` archive for
`unknown-linux-gnu` or `apple-darwin`. Other OS or architecture values fail.
It relies on the hosted runner's Bash, curl, awk, tar and install tools,
sha256sum on Linux or shasum on macOS, and Python 3 for summaries and automatic review comparison bases. No additional packages or permissions
are required for summaries.

Each invocation downloads `please-<tag>-<target>.tar.gz` and `SHA256SUMS` from
`please-behave/cli` GitHub release assets. It requires exactly one matching
checksum entry, verifies SHA-256 and extracts the regular `please` executable
from the archive's matching top-level directory. Failed downloads, verification
or extraction fail the step without exporting PATH. Temporary downloads are
removed. No GitHub token is needed for these public downloads.

By default, the next step invokes `please run --at <execution-point>` from
`GITHUB_WORKSPACE` and propagates its exit code. The consuming repository must
be checked out at the workspace root. Job-level `defaults.run.working-directory`
does not override composite Action execution. The default `check` point runs
only rules assigned to `check`, not every configured check. Installation never executes
rules. The Action does not initialize configuration, install rule dependencies or
provision provider credentials. Set `sync: 'true'` to reconcile declared imports
and hooks before execution; synchronization failure prevents execution.
Normal CLI behavior applies, including hook reconciliation at Git-backed points.

Use `checks-only: 'true'` for deterministic release gates and other points that
should omit reviews. Each execution still produces its own summary by default.
Prepare any required services before invoking the Action. For example, headless
GUI checks can start Xvfb in a preceding step and set `DISPLAY` on the Action step; the Action continues to own CLI execution and summary generation.

### Tools managed by mise

When mise already installs the published CLI, keep its version solely in
`mise.toml`. The `install` and `sync` inputs require Action v1.3.0 or later:

```yaml
- uses: actions/checkout@v7
  with:
    persist-credentials: false
    fetch-depth: 0
- uses: jdx/mise-action@v5
- uses: please-behave/action@<full-commit-sha> # <action-tag>
  with:
    install: 'false'
    sync: 'true'
    execution-point: check
  env:
    GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
```

Prepare any project dependencies before the Action. It uses the installed CLI
as supplied; the caller owns its version, provenance and compatibility.
This mode neither reads mise configuration nor introduces a second version pin.
Installation remains the default for consumers that supply `version`.

### Review comparison base

For review-enabled runs, the Action sets `PLEASE_CHANGE_BASE` for that invocation:
push events use the event's `before` commit; pull requests use the merge base of
the event's base and head commits; manual dispatch uses the checked-out HEAD.
A nonempty `PLEASE_CHANGE_BASE` supplied by the caller takes precedence.
Checks-only runs need no comparison history. Other events retain normal CLI
behavior; supply `PLEASE_CHANGE_BASE` explicitly when change-triggered reviews need it.

Use `fetch-depth: 0` to make comparison history available. The Action fetches a
missing event commit from `origin` when necessary. Invalid, missing or inaccessible
baselines fail before governance runs; a new-branch push with an all-zero `before`
requires an explicit comparison base. It never guesses `HEAD^` or silently skips
reviews. The resolved base is not exported to later workflow steps.

For an alternate checkout path, install-only mode makes the CLI available for
manual execution. Direct CLI execution does not produce an Action Job Summary:

```yaml
steps:
  - uses: actions/checkout@v7
    with:
      path: source
      persist-credentials: false
  - uses: please-behave/action@<action-tag>
    with:
      version: <cli-tag>
      run: 'false'
  - run: please run --at check
    working-directory: source
```

## Job Summaries

Execution appends a separate Markdown summary to the current step's
`GITHUB_STEP_SUMMARY`, including the execution point in the heading. Repeated
Action invocations keep independent summaries, including within one job. Existing
summary content is preserved; reports are never aggregated across points.
Use `summary: 'false'` to bypass all summary processing. Install-only mode
(`run: 'false'`) produces no summary and does not touch reports.

The summary shows the CLI aggregate outcome, exact exit code, measured CLI wall
clock duration and a table in `plan.scheduled` order. Each row shows its plan
position, CLI status, rule name, description and saved duration in milliseconds.
Only non-blocking rules carry an enforcement label: `PASS (non-blocking)`, for
example. Blocking is the default and has no label. Names fall back to the final
segment of the technical ID when unnamed; full IDs remain in the saved report.
Results match by technical ID and kind, so duplicate names and parallel completion cannot change row identity
or order. PASS, FAIL, ERROR, NOT_RUN and CANCELLED remain CLI statuses. Non-blocking
failures stay visible; the CLI aggregate outcome remains authoritative. Integrity
diagnostics appear separately, and empty plans are labeled explicitly.

Review details include the CLI status, reason and up to 20 findings with source
locations. Reviews omitted because their change trigger did not match are labeled
as not selected. NOT_RUN and ERROR remain visible without being relabeled as PASS.
All displayed review text is bounded and escaped; prompts and captured provider
output are not included. This applies to every review, without project-specific scripts.

The renderer supports report schema 4 and plan schema 3. It validates execution
point, repository, rule identities, result correspondence and displayed metadata.
Missing, malformed, incompatible or inconsistent reports produce a diagnostic
instead of a rule table. A nonzero CLI exit is always displayed as unsuccessful,
even if a saved report says PASS. Summary failures emit warnings without changing
the CLI exit code or triggering another governance run.

Before execution, an existing regular `.please/reports/last.json` is moved to a
private temporary directory alongside the report. Only a report produced after
this isolation is eligible for rendering; timestamps and plan IDs are not used
as freshness evidence. If execution produces no report, the previous report is
restored after summary processing. A new report replaces the old one, even when
malformed. Unsafe paths or isolation failures disable report rendering for that
invocation and emit a diagnostic. Concurrent CLI invocations sharing a checkout
are unsupported. Hard cancellation, runner termination and workflow cancellation
can prevent summary generation and report restoration; leftover `.summary-*`
directories may contain the preserved report.

Report input is bounded to 32 MiB. Summary output, including existing content,
is bounded to 900 KiB, below GitHub's 1 MiB per-step limit. Displayed text fields
are limited to 512 characters and escaped for Markdown and HTML; oversized output
is visibly truncated. Consult the CLI logs and saved report for full details.
GitHub displays at most 20 step summaries per job.

## Version selection and pinning

`uses: please-behave/action@<action-tag>` selects the Action implementation;
`with.version: <cli-tag>` selects the downloaded CLI. Updating one does not update
the other. With installation enabled, the Action has no default CLI version and accepts
only exact stable CLI tags. Consult the CLI release notes before changing the selected version.

For stronger reproducibility, pin the Action to the full 40-character commit SHA
resolved from a published tag:

```sh
gh api repos/please-behave/action/git/ref/tags/<action-tag> --jq .object.sha
```

Use that SHA in `uses: please-behave/action@<full-commit-sha>` and record the
release tag in a comment. Action releases use lightweight tags. SHA pinning fixes
the Action source; the CLI download remains selected by its release tag and
verified against checksums from that release. No moving `v1` or `latest` Action
refs are maintained.

## Action releases

The manually dispatched Release workflow requires Please Behave quality checks
and Action E2E tests on both supported architectures, plus release readiness
checks before Semantic Release can publish a Git tag and GitHub Release.
Versions start at `1.0.0`
without seed tags. Features increment minor; fixes, performance improvements,
effective reverts, `chore`, `refactor`, `build` and `config` changes increment patch;
breaking changes increment major. `ci`, `docs`, `style` and `test` changes alone do
not release. Classify security fixes to runtime code or dependencies as `fix`,
including `fix(deps)`; development dependency updates use `chore(deps)`. No release commit, changelog, npm package or native
artifact is generated. See the [release contract](docs/releasing.md) for the
complete policy. Action and CLI release numbers evolve independently.

Published releases are immutable: their tags and release assets are protected by
GitHub release immutability. Exact version refs and full commit SHA pins are supported.

## Limitations

Matching CLI release assets must exist and support `please run --at`; predecessor
CLI releases are incompatible. Checksums come from the same release as the
archive and provide integrity verification, not an independent signature.
The installer has no persistent cache, installed-version detection or version comparison;
`install: 'false'` deliberately delegates installation to the caller. There is no
Windows support or support guarantee for self-hosted runners. The installer
checks runner OS/architecture metadata; it does not detect the Ubuntu version.
Offline tests cover installation, execution, report isolation and summary failure
handling with fixtures. Release Candidate exercises the local
composite Action with two sequential invocations on all four supported hosted runners,
checking independent
summaries and ordinary governance failure propagation.

The repository uses the released CLI pinned in `mise.toml` to govern its
own development through `.please/`. `mise install` installs the configured tools;
`mise prepare` fetches locked npm dependencies without running checks,
`mise verify` runs the deterministic checks and stops at the first blocker and
`mise format` formats Python and shell sources. Python is exactly pinned in `mise.toml` for
local and CI scripts. CI invokes one published Action step with
`install: 'false'` and `sync: 'true'` to run `check` with summaries on both
supported architectures in its `Check` matrix job. Release reuses successful push
CI for the exact source and runs hosted Action tests as its four-platform Candidate
matrix. Its synthetic fixture lives in `.github/scripts/prepare-action-e2e.sh`.
Hosted tests run only during release preparation. Readiness reuses source
security, license and npm audit results from CI and verifies the public CLI assets.
The only project custom execution point is `release`, for the CLI dependency
check. Exact-source CI proof and candidate evidence are workflow tooling.
Workflow tooling records candidate evidence and verifies all four
source/version/run/attempt manifests before publication. Publish checks the
planned version and source again before tagging. It never installs or invokes
Please Behave, synchronizes governance, or installs Git hooks.

Release jobs install only their required mise tools: Node for planning,
Python/the governor for readiness and native candidates, Python/Node for publishing.
The installer acceptance test forwards the resolved governor version from the
mise Action's outputs; it does not parse configuration in the workflow.
`mise release` dispatches Release for remote main using an authenticated host `gh`
CLI, without waiting for completion. It is equivalent to
`gh workflow run release.yml --ref main`.

Commit messages are checked only by the managed local Git hook;
CI does not validate commit history or PR titles. See
[Contributing](CONTRIBUTING.md) for preparation and execution points.

## License

[PolyForm Noncommercial License 1.0.0](LICENSE)
(`PolyForm-Noncommercial-1.0.0`).

Public availability does not imply unrestricted commercial use. Use is governed
by the permissions and conditions in the license.
