# Per-person install: logins, Copilot token, Chitti patterns

Research for [How does a person install their own copy with a guided "ask me" setup until there is a shared deployment?](https://github.com/chiyanram/rca-agent/issues/41). Facts only; the decisions are in the ticket's resolution comment.

## 1. `dtctl` logins inside a container

Source: [dynatrace-oss/dtctl](https://github.com/dynatrace-oss/dtctl) (`docs/CONFIGURATION.md`, `sdk/session`).

| Login kind | How | Works read-only in a container? |
|---|---|---|
| Browser OAuth (`dtctl auth login`) | Tokens in the OS keyring by default; `DTCTL_TOKEN_STORAGE=file` → `$XDG_DATA_HOME/dtctl/oauth-tokens/` (0600 JSON) | **No.** Refresh writes the token back and takes a lock file in `os.TempDir()`; the keyring is not reachable from a container. |
| OAuth client credentials | `DTCTL_CLIENT_ID`, `DTCTL_CLIENT_SECRET`, `DTCTL_ACCOUNT_URN`; 300 s token, no refresh token | Yes, but it is a shared client, not a personal login. |
| Platform token (`dt0s16.*`) | Config entry `token: ${DT_PLATFORM_TOKEN}` (env expansion), selected by `DTCTL_CONFIG` / `DTCTL_CONTEXT` | **Yes.** Ordinary commands don't write the config. |

- Config lookup order: `--config` → `DTCTL_CONFIG` → `.dtctl.yaml` walked up from the current folder (untrusted: inline tokens and `$` references rejected) → `$XDG_CONFIG_HOME/dtctl/config`.
- There is no `DT_TOKEN`-style variable and no credential-command helper; env expansion in an app-written config is the safe pattern.
- Consequence: mounting the host's `dtctl` login read-only does not work for browser logins and would hand the whole login over. A read-only platform token passed as an env var does.

## 2. `gh auth token`

Sources: [gh auth token](https://cli.github.com/manual/gh_auth_token), [gh environment](https://cli.github.com/manual/gh_help_environment).

- Prints the active account's token (`gho_…` for a browser login) for the default host; `-h` / `-u` pick host or account. Reads the keyring, falls back to `hosts.yml`.
- `GH_TOKEN` beats `GITHUB_TOKEN`, both beat stored credentials; GHES uses `GH_ENTERPRISE_TOKEN`.

## 3. Copilot as the model with a personal login

- **Copilot SDK** ([github/copilot-sdk](https://github.com/github/copilot-sdk), GA 2026-06-02): accepts `gho_` (what `gh auth token` returns), `ghu_` and fine-grained PATs; not classic `ghp_`. Env order `COPILOT_GITHUB_TOKEN` → `GH_TOKEN` → `GITHUB_TOKEN`. Server-to-server via a GitHub App with "Copilot Requests". Also supports bring-your-own-key.
- **Pydantic AI `github-copilot:`** (from [LLM providers research](https://github.com/chiyanram/rca-agent/blob/research/llm-providers-without-claude/research/llm-providers-without-claude.md)): takes a GitHub OAuth user token or a Copilot API token; fine-grained PATs got 401; no token refresh. **Unverified:** whether the `gho_` token from `gh auth token` is accepted. Test belongs to [Using Copilot at work](https://github.com/chiyanram/rca-agent/issues/36).
- The undocumented `copilot_internal/v2/token` exchange works but is internal and carries terms risk: not advisable.

## 4. Chitti ("Ask Me") patterns, from the user's ADRs 0021 and 0022

From the user's other project (ADR-0021 "reads a copy and writes through the gate", ADR-0022 phone status changes):

- **Reads a copy, never production**: separate read-only database with an include-list of tables and private columns dropped; tells the person how old the figures are.
- **Model only proposes**: sealed container, no write credential, reply is a JSON envelope with one of `confirm`, `choose`, `display`.
- **Confirm cards**: nothing changes until Confirm; "Fix something" corrects the card; missing facts asked all at once as taps, never guessed.
- **The gate**: ordered checks, each with a named refusal (owner, write mode, still pending, shown = sent, ≤15 min old, catalogue allows for role, not a duplicate, large amounts retyped, live figures still hold, spent on first tap); the write then goes through the app's own REST route with the person's token, so the same audit applies.
- **Read mode by default**: write actions are never described to the model in Read mode; safety rules are code, not persona text.
- **Fixed catalogue**: one entry per job, reusing the route's own schema as prompt, validation, card template and allow-list.
- **Tiers**: the app answers simple input itself; a cheap model normalises unclear text; the full model only for judgement.
- **Feedback**: thumbs up/down, "couldn't understand" reports, per-turn cost log.
- **Install**: no first-run wizard; a script installs the API key; sidecars only when enabled.

## 5. Already decided elsewhere that the per-person copy hits

- Setup: YAML import exists, export was "later"; trust-bearing items import as pending unless `--confirm` ([setup flow](https://github.com/chiyanram/rca-agent/issues/18)).
- KMS: pluggable, with "a local key file for the developer demo" ([audit log](https://github.com/chiyanram/rca-agent/issues/19)).
- Personal credential rules: marked personal, recorded as the person, excess power warns, `write` under the person's name, Recovery off, never counts for a shared setup ([plugins](https://github.com/chiyanram/rca-agent/issues/40)).
- Personal Copilot login only for a trial on a developer's own machine ([model choice](https://github.com/chiyanram/rca-agent/issues/26)).
