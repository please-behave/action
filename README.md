# Please Behave Action

A lightweight composite GitHub Action that installs and invokes the
[Please Behave CLI](https://github.com/please-behave/cli). The CLI evaluates
repository rules; this Action only provides installation and optional execution.

## Usage

The first Action release is `v1.0.0` and requires CLI `v0.1.0` or a compatible
later stable CLI release. The example below targets those versions; use it only
after both repositories list their releases. The Action ref and CLI version are
independent.

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
      - uses: please-behave/action@v1.0.0
        with:
          version: v0.1.0
          execution-point: check
```

Check out a Git repository with `.please/` configuration and prepare the tools
and credentials required by its rules before running the Action.

## Inputs

| Input | Required | Default | Meaning |
| --- | --- | --- | --- |
| `version` | Yes | None | Exact stable CLI release tag: `vMAJOR.MINOR.PATCH`. No `latest`, ranges or prereleases. |
| `execution-point` | No | `check` | Point passed as one argument to `please run --at`. |
| `run` | No | `'true'` | `'true'` executes after installation; `'false'` installs only. Other values fail. |

There are no Action outputs. The installed `please` executable is available on
PATH to subsequent steps in the same job, including with `run: 'false'`.

## Installation and execution

Supported runners are GitHub-hosted Ubuntu 24.04 x64 (`ubuntu-24.04`) and ARM64
(`ubuntu-24.04-arm`). The installer maps these to `x86_64-unknown-linux-gnu` and
`aarch64-unknown-linux-gnu`, respectively. Other OS or architecture values fail.
It relies on the hosted runner's Bash, curl, awk, sha256sum, tar and install tools.

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
rules. The Action does not initialize configuration, install rule dependencies,
provision provider credentials or explicitly synchronize external rule sources.
For imports requiring synchronization, install with `run: 'false'`, run
`please sync --yes`, then invoke `please run --at check` in later steps.
Normal CLI behavior applies, including hook reconciliation at Git-backed points.

For an alternate checkout path, use install-only mode and invoke the CLI from
that repository's root explicitly:

```yaml
steps:
  - uses: actions/checkout@v7
    with:
      path: source
      persist-credentials: false
  - uses: please-behave/action@v1.0.0
    with:
      version: v0.1.0
      run: 'false'
  - run: please run --at check
    working-directory: source
```

## Version selection and pinning

`uses: please-behave/action@v1.0.0` selects the Action implementation;
`with.version: v0.1.0` selects the downloaded CLI. Updating one does not update
the other. The Action has no default CLI version and accepts only exact stable
CLI tags. Consult the CLI release notes before changing the selected version.

For stronger reproducibility, pin the Action to the full 40-character commit SHA
resolved from a published tag:

```sh
gh api repos/please-behave/action/git/ref/tags/v1.0.0 --jq .object.sha
```

Use that SHA in `uses: please-behave/action@<full-commit-sha>` and record the
release tag in a comment. Action releases use lightweight tags. SHA pinning fixes
the Action source; the CLI download remains selected by its release tag and
verified against checksums from that release. No moving `v1` or `latest` Action
refs are maintained.

## Action releases

The manually dispatched Release workflow requires Please Behave quality checks
on both supported architectures and release readiness checks before Semantic
Release can publish a Git tag and GitHub Release. Versions start at `1.0.0`
without seed tags. Features increment minor; fixes, performance improvements and
effective reverts increment patch; breaking changes increment major. Documentation
and development tooling changes alone do not release. Classify security fixes to
runtime code or dependencies as `fix`, including `fix(deps)`; development dependency
updates use `chore(deps)`. No release commit, changelog, npm package or native
artifact is generated. See the [release contract](docs/releasing.md) for the
complete policy. Action and CLI release numbers evolve independently.

Published releases are immutable: their tags and release assets are protected by
GitHub release immutability. Exact version refs and full commit SHA pins are supported.

## Limitations

Matching CLI release assets must exist and support `please run --at`; predecessor
CLI releases are incompatible. Checksums come from the same release as the
archive and provide integrity verification, not an independent signature.
There is no persistent cache, installed-version detection, version comparison,
Windows/macOS support or support guarantee for self-hosted runners. The installer
checks runner OS/architecture metadata; it does not detect the Ubuntu version.
Offline tests cover the installer and execution command with fixture archives.
They do not provide an end-to-end test of `uses: ./` on a GitHub Actions runner.

The repository uses the released CLI pinned in `.please-version` to govern its
own development through `.please/`. CI bootstraps with `uses: ./`, synchronizes
external rulesets and runs offline quality gates through Please Behave on both
supported architectures. The separate publish job verifies release readiness
directly without installing Please Behave or Git hooks.
Commit messages are checked only by the managed local Git hook;
CI does not validate commit history or PR titles. See
[Contributing](CONTRIBUTING.md) for preparation and execution points.

## License

[PolyForm Noncommercial License 1.0.0](LICENSE)
(`PolyForm-Noncommercial-1.0.0`).

Public availability does not imply unrestricted commercial use. Use is governed
by the permissions and conditions in the license.
