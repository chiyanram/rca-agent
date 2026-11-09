# Security policy

## Reporting a vulnerability

Report it privately through GitHub: **Security → Report a vulnerability** on this repository. Do not open a public issue or pull request.

Include what you found, where, and how to reproduce it. You will get an answer within 5 working days.

## Handling secrets

- Credentials never go into the repository, issues, comments or commit messages; refer to them by name.
- If a secret is committed by mistake, revoke it first, then remove it from history.

## Scope

The agent's own security model (credentials, data sent to the LLM, prompt injection from logs) is specified in the planning tickets; see "Security and trust boundaries" on the map (issue #1).
