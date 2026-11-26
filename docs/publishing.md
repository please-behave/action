# Publishing from GitHub Actions

Use an Action ref that supports `gateway-url` and Please Behave CLI `v0.22.0`
or later for GitHub OIDC. In the project's `.please/config.toml`, select
GitHub OIDC authentication for publishing and registration.

```toml
[publish]
auth = "github-oidc"
```

Set the GitHub Actions secret `PLEASE_GATEWAY_URL` to the gateway origin. The
origin must be an HTTP or HTTPS URL with no credentials, query, fragment or path
other than `/`. The CLI requests an ID token whose audience is the lowercase
gateway scheme and authority, including any explicit port and with no trailing
slash, for example `https://gateway.example.org`. The gateway must allow the
workflow repository and configure that exact audience.

Grant the delivery job `id-token: write` so GitHub provides the token request
environment variables. The Action passes them through to the CLI. No API key
secret is needed. The checkout's network Git remote named `origin` supplies
the repository identity unless the project sets `publish.repository`. With
OIDC, the identity must match the repository running the workflow.

```yaml
name: Verify and publish
on:
  push:
    branches: [main]
permissions:
  contents: read
  id-token: write

jobs:
  verify:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v7
        with:
          persist-credentials: false
      - uses: please-behave/action@<action-tag>
        with:
          version: v0.22.0
          checks-only: 'true'
          gateway-url: ${{ secrets.PLEASE_GATEWAY_URL }}
```

Replace `<action-tag>` with a release that includes the publishing inputs.
For a CLI already on PATH, set `install: 'false'` and use a compatible version.

An empty or omitted `gateway-url` skips delivery. With a URL, the Action invokes
`please publish` after a run saves a report, including when the verdict is
`FAIL` or `ERROR`. The CLI checks that the report describes the current
committed checkout. If the invocation produces no new report, the Action
reports a delivery failure.

Delivery failures produce a warning and a Job Summary entry, even with
`summary: 'false'`. Set `publish-required: 'true'` to make a delivery failure
fail a step whose run succeeded. A nonzero governance exit code takes
precedence, and publishing preserves the saved verdict.

## Registering rules and Rule Sets

Set `register: 'true'` in a workflow that runs in the repository that owns the
rules and Rule Sets. Use the same gateway origin and OIDC configuration as for
publishing and an Action release with the `register` input. Rule Set
registration requires CLI `v0.23.0` or later. With GitHub OIDC, CLI
`v0.22.0` and `v0.22.1` register rule versions only.

```yaml
name: Verify and register rules and Rule Sets
on:
  push:
    branches: [main]
permissions:
  contents: read
  id-token: write

jobs:
  verify:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v7
        with:
          persist-credentials: false
      - uses: please-behave/action@<action-tag>
        with:
          version: v0.23.0
          checks-only: 'true'
          gateway-url: ${{ secrets.PLEASE_GATEWAY_URL }}
          register: 'true'
```

Replace `<action-tag>` with a release that includes the registration input,
and use your default branch in the push trigger. After governance succeeds, the
Action runs `please register` once. The CLI registers committed local rules
first, then the Rule Sets defined in the same repository. Each rule needs a
version and a `rule.yaml`. Each Rule Set needs a version and a `ruleset.yaml`
alongside its definition.

The Job Summary lists created, unchanged, and conflicting registrations even
when `summary: 'false'`. If you changed a rule or Rule Set and get a conflict,
raise the version of the conflicting definition before retrying. Any registration
failure fails the step, and attestation delivery follows its own policy.

With CLI `v0.25.0` or later, `register: 'true'` also registers the deployment
targets configured in the repository, after the Rule Sets. Register targets
before recording deployments to them.

## Recording a release

Set `release-version` to report a release to the gateway, for example from a
release workflow. Use the same gateway origin and authentication as for
publishing and an Action release with the `release-version` input. The input
requires CLI `v0.24.0` or later. The step runs `please record release` without
a governance run, so `run: 'false'` is enough. The version is an opaque string
and need not be a Git tag. The commit defaults to `HEAD`; set `release-commit`
to a full Git object ID to record another commit.

```yaml
      - uses: please-behave/action@<action-tag>
        with:
          version: v0.24.0
          run: 'false'
          gateway-url: ${{ secrets.PLEASE_GATEWAY_URL }}
          release-version: ${{ github.ref_name }}
```

Without a gateway URL the step does nothing and says so in a notice and the Job
Summary. The Job Summary shows whether the release was recorded, was already
known (unchanged) or conflicts with a commit recorded for the same version,
even with `summary: 'false'`. Any other failure, including a conflict, produces
a warning and a Job Summary entry. Set `publish-required: 'true'` to make it
fail the step.

## Recording a deployment

Set `deployment-target` to report that software was deployed, for example from
a deployment workflow. Use the same gateway origin and authentication as for
publishing and an Action release with the deployment inputs. The inputs require
CLI `v0.25.0` or later. The step runs `please record deployment` without a
governance run, so `run: 'false'` is enough. The target must be registered for
the authenticated sender. `deployment-repository` identifies the deployed
software, not the workflow repository, and has no default. Set exactly one of
`deployment-version` and `deployment-commit`; the commit must be a full Git
object ID. The Action derives neither the target nor the version.

```yaml
      - uses: please-behave/action@<action-tag>
        with:
          version: v0.25.0
          run: 'false'
          gateway-url: ${{ secrets.PLEASE_GATEWAY_URL }}
          deployment-target: production
          deployment-repository: github.com/example/app
          deployment-version: ${{ github.ref_name }}
```

Without a gateway URL the step does nothing and says so in a notice and the Job
Summary. The Job Summary shows whether the deployment was recorded, was
unchanged or went to an unknown target, even with `summary: 'false'`. Any other
failure, including an unknown target, produces a warning and a Job Summary
entry. Set `publish-required: 'true'` to make it fail the step. Missing or
ambiguous inputs fail the step.

## Using an API key

API key authentication is the CLI default. Use CLI `v0.20.0` or later for
publishing, `v0.21.0` or later for rule registration, and `v0.23.0` or later
for Rule Set registration. Configure the name of the environment variable that
holds the key in `.please/config.toml`. If you previously configured OIDC,
remove `auth = "github-oidc"` from `[publish]`.

```toml
[publish]
key_env = "PLEASE_GATEWAY_KEY"
```

Store the gateway API key in the GitHub Actions secret `PLEASE_GATEWAY_KEY`.
Keep `contents: read`, omit `id-token: write`, and add the following environment
mapping to the Action step. Supply `gateway-url` as shown in the workflows above.

```yaml
env:
  PLEASE_GATEWAY_KEY: ${{ secrets.PLEASE_GATEWAY_KEY }}
```
