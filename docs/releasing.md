# Release contract

The Action has its own version, independent of the selected CLI version.
Only the manually dispatched Release workflow on `main` publishes. It follows
Plan → parallel Release Readiness and Release Candidate → Publish. Every phase
uses the dispatched source revision. No release-worthy commits means no readiness,
candidate or publication work.

Plan uses a Semantic Release dry run to determine the next version and source SHA
without creating tags, commits or releases. Readiness uses the published governor
pinned in `.please-version` at `release-readiness --checks-only`. The pinned
external `release/releasable-project` ruleset verifies successful push CI for that exact
commit in `please-behave/action`, on `main`, in `.github/workflows/ci.yml`, including
`Check (ubuntu-24.04)` and `Check (ubuntu-24.04-arm)`. Source security,
license and npm audit results are reused from CI without an age limit.
The local CLI dependency check requires unchanged main and the pinned public stable
CLI release with all four native archives and SHA256SUMS. API failures block publication.

Readiness does not restart or wait for CI. Its policy is `.please/release-ci.json`.
The newest matching CI run must succeed; missing, running, failed or incomplete
proof blocks. Partial reruns may retain successful jobs from earlier attempts of
that same run; unrelated runs cannot combine. CI remains independent of Release.

Release Candidate runs the checked-out
composite Action on Ubuntu 24.04 x64/ARM64 and macOS ARM64/Intel. All four entries
must succeed. It produces no native artifacts: the Action publishes its tested source tree. Publish
requires Plan, Readiness and the entire Candidate matrix to succeed. Semantic
Release rechecks the planned version, local HEAD, dispatched SHA and remote main
in its `verifyRelease` hook before tagging. If main or the planned version changes,
publication is refused; dispatch again from the latest main. These checks are not
an atomic lock against concurrent changes.

Semantic Release creates the tag and GitHub Release. It publishes no npm package,
native assets, changelog, generated version file, release commit or moving major
tag. Its standard first release is v1.0.0 without any seed tag or adapter.
Later versions follow Conventional Commits:

| Change | Increment |
| --- | --- |
| Breaking change (`!` or `BREAKING CHANGE:`), any accepted type | Major |
| `feat` | Minor |
| `fix`, `perf`, effective `revert` | Patch |
| `build`, `chore`, `ci`, `config`, `docs`, `refactor`, `style`, `test` | None unless breaking |

Use `fix` for runtime security fixes, including `fix(deps)` for runtime dependency
fixes. Use `chore(deps)` for development dependency updates. Select types according
to the effect of a change; documentation and development tooling alone do not
warrant a release. Reverted commit pairs cancel when both are unreleased.

Acceptance criteria:

- Summary input defaults to true and accepts only true/false. Disabled summaries
  bypass report processing; install-only mode is unchanged. The CLI exit code
  survives missing, stale, malformed, unsupported reports and rendering errors.
- Summary rows follow the scheduled plan and match technical identities. Status,
  enforcement, names, descriptions and durations come from the saved report.
  Rule cells omit technical IDs, unnamed rules use the final ID segment, and
  only non-blocking rules carry an enforcement label. Integrity
  diagnostics are separate; empty plans and unsuccessful exits are explicit.
- Offline tests cover report isolation/restoration, independent sequential runs,
  escaping and bounded output. Hosted composite tests verify repeated invocation
  summaries and checks-only failure behavior on all four supported runner platforms.

- The offline Semantic Release lifecycle starts from an empty isolated bare Git
  remote, publishes 1.0.0, then 1.0.1, 1.1.0 and 2.0.0 for fix, feature and breaking
  commits. Documentation alone and repeated publication create no tag or commit.
- Policy tests cover breaking syntax, maintenance types, security fixes and reverts.
- Offline release tests verify an inert dry run and reject changed planned versions,
  dispatched SHAs and remote main before tagging; no-release previews publish nothing.
- Offline installer tests verify checksums, invalid inputs/platforms, failed
  downloads, PATH export, cleanup, argument boundaries and exit-code propagation.
- macOS installation selects the matching native archive and verifies its checksum
  with shasum; Linux retains sha256sum. Missing or corrupt assets block installation.
- `checks-only` defaults to false and accepts only true/false. Enabled execution
  passes `--checks-only` once, preserving summaries and the CLI exit code.
- The Action execution command passes the execution point as one argument and
  propagates success and failure exit codes unchanged. The default point is
  `check`; install-only mode installs without invoking the CLI or requiring
  `.please/` configuration.
- Tests exercise the installer script and execution command offline. Hosted
  composite acceptance tests on all four platforms cover repeated
  invocations, independent summaries and ordinary governance failures. CLI rule
  selection, configuration validation and exit-code normalization belong to the CLI.

Install development dependencies with `npm ci --ignore-scripts` (Node 26), the
released governor pinned in `.please-version`, and the tools listed in
[Contributing](../CONTRIBUTING.md). Install managed hooks and synchronize external
rules with `sh scripts/setup-git-hooks.sh --yes`. CI installs the governor through
the published Action pinned to the full commit SHA for `v1.2.0` after checkout,
synchronizes imports and invokes the same published Action to run `check` with
a Job Summary. Installation-only mode remains necessary before synchronization;
the execution invocation installs the same CLI version again. Readiness installs
the same pinned governor and prepares npm dependencies and Gitleaks before rule
execution, then invokes the published Action with `checks-only` and summaries
enabled. Plan and Publish prepare only Node dependencies and never install
Please Behave or Git hooks. Plan needs `contents: write` because Semantic Release
verifies push access even during a dry run; Publish needs it to create release tags
and the GitHub Release. Readiness needs `contents: read` and `actions: read`;
Candidate needs only `contents: read`.

The managed `commit-msg` hook runs the imported syntax Check and advisory
header-only wording Review through the independently imported Gemini provider.
The published v0.5.0 governor supports both imports. CI does not validate
commit ranges or PR titles. Semantic Release still analyzes commits for version
selection; that publication operation is separate from message validation.

## Repository protections

GitHub Immutable Releases must be enabled as a repository configuration prerequisite
under Settings > General > Releases > Enable release immutability. Release readiness
checks do not query this setting. Published release tags and assets become immutable;
commit-SHA pinning remains supported. No custom tag protection or moving `v1`
tag is used. Semantic Release writes release tags and Git notes, not `main`.

The active `main` branch ruleset prevents deletion. It currently permits history
replacement and has no required status checks. The maintainer pushes directly to
`main`, with dependency PRs from Renovate. Publishing always requires exact-commit
CI proof and Action E2E on both architectures, regardless of branch protection
settings. Repository protection settings are managed separately;
do not restrict release tags or `refs/notes/*`.

If required status checks are configured, replace references to the old `tests`
and `summaries` jobs with the CI `Check (ubuntu-24.04)` and
`Check (ubuntu-24.04-arm)` checks checks. Hosted candidate tests run only during Release, so they are not PR status checks. This refactor does not change remote branch
protection settings.

## Publication procedure

After reviewing CI results and confirming the CLI dependency,
an authorized maintainer can dispatch:

```sh
gh workflow run release.yml --ref main --repo please-behave/action
```

The workflow reuses successful push-CI proof and runs hosted Action tests after planning;
it cannot skip validation via dispatch inputs. If CI is not ready, let the
independent CI workflow finish and dispatch Release again. Publication is serialized
and does not cancel an active release. GitHub's default concurrency
queue can replace a pending dispatch. No branch write or protection bypass is
required. A publication failure can leave a tag without a GitHub Release; inspect
both remote states before retrying. Published immutable releases cannot be repaired
by moving a tag or replacing assets; publish a new version when needed.

Repository CI and Readiness use published Action v1.2.0 pinned to
`722d5967c094e5ac4bfe25e9f82b020ff34e9487`, with summaries enabled.
The Action repository's own governance uses the published release; local Action
invocations remain confined to acceptance tests.

After publication, inspect the actual GitHub Release, resolve its tag to the
tested SHA and check action.yml, scripts/install.sh and README.md in that tree.
CI checks the checkout before publication; it cannot prove that an unpublished
remote Action tag resolves correctly. Verify the published ref in a
consumer workflow after publication. Do not publish while the CLI dependency is
unavailable.

## Common candidate evidence

Each successful hosted candidate restores project governance and uses the external
`release-contract` Check at `release-record` to hash the tested Action metadata and
runtime scripts. Publish uses the same published governor at `release-verify` to
require all four current-run/current-attempt manifests and matching source hashes.
The internal manifests follow `.please/release-artifacts.json`; no native or public
release asset is added. Plan installs no governor; Publish installs no build tools.

Before tagging, thin local Semantic Release adapters load the cached external
publication guard exported by `release-verify`. The shared implementation checks
the recalculated version, checkout, dispatched SHA, repository, main branch and
current remote main. Custom prerelease/image publication reuses that source guard.
Offline lifecycle fixtures exercise the actual pinned external module from cache.
