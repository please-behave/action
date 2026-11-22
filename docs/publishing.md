# Publishing from GitHub Actions

Use an Action ref that supports `gateway-url` and Please Behave CLI `v0.20.0`
or later. In the project's `.please/config.toml`, configure the environment
variable that holds the gateway API key.

```toml
[publish]
key_env = "PLEASE_GATEWAY_KEY"
```

Store the gateway origin and API key in GitHub Actions secrets. The origin
must be an HTTP or HTTPS URL with no credentials, query, fragment or path
other than `/`. The checkout's network Git remote named `origin` supplies the
repository identity unless the project sets `publish.repository`.

```yaml
name: Verify and publish
on:
  push:
    branches: [main]
permissions:
  contents: read

jobs:
  verify:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v7
        with:
          persist-credentials: false
      - uses: please-behave/action@<action-tag>
        with:
          version: v0.20.0
          checks-only: 'true'
          gateway-url: ${{ secrets.PLEASE_GATEWAY_URL }}
        env:
          PLEASE_GATEWAY_KEY: ${{ secrets.PLEASE_GATEWAY_KEY }}
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
rules. Use the same gateway origin and key configuration as for publishing.
Use CLI `v0.21.0` or later and an Action release with the `register` input.

```yaml
name: Verify and register rules
on:
  push:
    branches: [main]
permissions:
  contents: read

jobs:
  verify:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v7
        with:
          persist-credentials: false
      - uses: please-behave/action@<action-tag>
        with:
          version: <cli-tag>
          checks-only: 'true'
          gateway-url: ${{ secrets.PLEASE_GATEWAY_URL }}
          register: 'true'
        env:
          PLEASE_GATEWAY_KEY: ${{ secrets.PLEASE_GATEWAY_KEY }}
```

Replace the tag placeholders with the releases you adopt, and use your default
branch in the push trigger. The Action runs registration only after governance
succeeds. The CLI registers committed local rules, which need a version and a
`rule.yaml`. The Job Summary lists per-rule outcomes even when
`summary: 'false'`. A conflict means you need to raise the rule version before
retrying. Any registration failure fails the step, and attestation delivery
continues to follow its own policy.
