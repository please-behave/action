# Working on Please Behave Action

## Principles

Prioritize consistency with existing conventions and the smallest coherent implementation. Avoid unnecessary complexity and AI-generated boilerplate.

- Follow established architecture, decisions and conventions. Keep code, tests,
  configuration and documentation consistent.
- Implement only requested behavior. Avoid speculative features, unnecessary
  dependencies, abstractions, duplication and boilerplate.
- Test Action scripts offline through Please Behave. Preserve secure CLI
  installation, checksum verification and minimal workflow permissions.
- Use Please Behave for governance. Define repository-specific rules in
  `.please/` and reuse external rulesets without duplicating their behavior.
- Keep the root for the Action. Rule scripts and their tests live in their
  `.please/checks/<rule>/` directory; scripts used only by workflows live in
  `.github/scripts/` with their tests.
- Review changes for inconsistencies, stale references and unnecessary additions.
- Ask before making significant architectural changes or modifying release behavior.

## Validation

Git hooks are authoritative.

- Do not manually run tests, linters, builds or validation commands.
- Let the installed Git hooks perform validation during Git operations.
- Read hook failures, fix their causes and retry the Git operation.
- Use `please status --details` to inspect reports without rerunning checks.
- Never bypass Git hooks or weaken checks merely to make validation pass.

## Git workflow

- Work on `main`. Commit and push coherent changes without requesting approval.
- Follow `CONTRIBUTING.md` and the configured commit-message rules.
- Stage only relevant files and preserve unrelated changes.
- Never force-push or rewrite history without explicit authorization.
- Do not tag or publish releases without explicit authorization.
- If validation, commit or push fails, retain the changes and report the failure.

## Remote workflows

- Do not monitor or poll GitHub Actions unless explicitly requested.
- If further work depends on a workflow result, ask the user to provide it.
