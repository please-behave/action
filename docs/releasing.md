# Release contract

The Action has its own version, independent of the selected CLI version.
Only the manually dispatched Release workflow on `main` publishes. It calls CI
at the dispatched revision before its publication job receives `contents: write`.
The `check` execution point must succeed on Ubuntu 24.04 x64 and ARM64.
The publisher refuses an outdated revision and requires the public CLI release
pinned in `.please-version`, both Linux archives plus SHA256SUMS. These publication
conditions run directly through `python3 scripts/check-release-ready.py`.

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

- The offline Semantic Release lifecycle starts from an empty isolated bare Git
  remote, publishes 1.0.0, then 1.0.1, 1.1.0 and 2.0.0 for fix, feature and breaking
  commits. Documentation alone and repeated publication create no tag or commit.
- Policy tests cover breaking syntax, maintenance types, security fixes and reverts.
- Offline installer tests verify checksums, invalid inputs/platforms, failed
  downloads, PATH export, cleanup, argument boundaries and exit-code propagation.
- The Action execution command passes the execution point as one argument and
  propagates success and failure exit codes unchanged. The default point is
  `check`; install-only mode installs without invoking the CLI or requiring
  `.please/` configuration.
- Tests exercise the installer script and execution command offline. They do not
  provide an end-to-end test of the Action on a GitHub Actions runner. CLI rule
  selection, configuration validation and exit-code normalization belong to the CLI.

Install development dependencies with `npm ci --ignore-scripts` (Node 26), the
released governor pinned in `.please-version`, and the tools listed in
[Contributing](../CONTRIBUTING.md). Install managed hooks and synchronize external
rules with `sh scripts/setup-git-hooks.sh --yes`. CI installs the governor through
the published Action pinned to the full commit SHA for `v1.0.0` after checkout,
synchronizes imports and runs `check` through Please Behave. The Release workflow
has two jobs: `checks` calls this reusable CI
workflow, and `publish` depends on it through `needs: checks`. The publish job uses
a fresh runner, prepares Node dependencies and runs the release-readiness script
before invoking Semantic Release. It does not install or configure Please Behave
or Git hooks.

The imported local `commit-msg` hook validates messages. CI does not validate
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
`main`, with dependency PRs from Renovate. Publishing always requires the `tests`
job on both architectures through the reusable CI workflow, regardless of branch
protection settings. Repository protection settings are managed separately;
do not restrict release tags or `refs/notes/*`.

## Publication procedure

After reviewing CI results and confirming the CLI dependency, an authorized
maintainer can dispatch:

```sh
gh workflow run release.yml --ref main --repo please-behave/action
```

The workflow reruns CI; it cannot skip validation via dispatch inputs. Publication
is serialized and does not cancel an active release. GitHub's default concurrency
queue can replace a pending dispatch. No branch write or protection bypass is
required. A publication failure can leave a tag without a GitHub Release; inspect
both remote states before retrying. Published immutable releases cannot be repaired
by moving a tag or replacing assets; publish a new version when needed.

After publication, inspect the actual GitHub Release, resolve its tag to the
tested SHA and check action.yml, scripts/install.sh and README.md in that tree.
CI checks the checkout before publication; it cannot prove that an unpublished
remote Action tag resolves correctly. Verify the published ref in a
consumer workflow after publication. Do not publish while the CLI dependency is
unavailable.
