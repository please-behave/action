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

## Registering rule versions

Set `register: 'true'` in a workflow that runs in the repository that owns the
rules. Use the same gateway origin and OIDC configuration as for publishing,
CLI `v0.22.0` or later, and an Action release with the `register` input.

```yaml
name: Verify and register rules
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
          register: 'true'
```

Replace `<action-tag>` with a release that includes the registration input,
and use your default branch in the push trigger. The Action runs registration
only after governance succeeds. The CLI registers committed local rules, which
need a version and a `rule.yaml`. The Job Summary lists per-rule outcomes even when
`summary: 'false'`. A conflict means you need to raise the rule version before
retrying. Any registration failure fails the step, and attestation delivery
continues to follow its own policy.

## Using an API key

API key authentication is the CLI default. Use CLI `v0.20.0` or later for
publishing and `v0.21.0` or later for registration. Configure the name of the
environment variable that holds the key in `.please/config.toml`. If you
previously configured OIDC, remove `auth = "github-oidc"` from `[publish]`.

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
