# Releases

What each release contains. **v1 is the first build: the laptop copy.** v2, the shared team deployment, comes only if the team and management agree after a v1 demo. Anything later waits on real need.

Decided in [First build: laptop copy for my work estate](https://github.com/chiyanram/rca-agent/issues/58) ([ADR-0006](adr/0006-first-build-is-the-laptop-copy.md)). Each row links the ticket that holds the detail. Terms are defined in [`CONTEXT.md`](../CONTEXT.md).

| Release | Who runs it | Gate to start it |
|---|---|---|
| **v1: laptop copy** | Anyone, on their own laptop, with their own logins | The spec is assembled |
| **v2: shared deployment** | A team, on hosting the company accepts | Team and management agree after a v1 demo |
| **Later** | Whoever needs it | A real need appears |

## v1: laptop copy (first build)

**Flow:**
1. Read the production issue.
2. Read logs, metrics, traces, code and runbooks.
3. Write the RCA report, with cited evidence.
4. You approve.
5. The app opens a draft PR and creates a Confluence RCA page. Recovery commands and an email draft are prepared for you to run and send.

Every write waits for your approval.

| Area | In v1 | Detail |
|---|---|---|
| **Install** | **Personal copy**: GHCR image + `compose.yaml` + `rca-agent up`, localhost only, one local user holds every role, personal mode fixed at install | [per-person install](https://github.com/chiyanram/rca-agent/issues/41) |
| **Setup** | Setup screen + scripted Guided setup (no model). Plugins come with defaults, each person signs in and picks their services. Confirmed-only Setup. **Writes are off on a fresh install** and one switch turns them all off again | [setup flow](https://github.com/chiyanram/rca-agent/issues/18), [#58](https://github.com/chiyanram/rca-agent/issues/58), [v1 setup steps](https://github.com/chiyanram/rca-agent/issues/63) |
| **Plugins** | **GitHub** (`gh auth token`): read repos, open draft PRs. **Dynatrace** (bundled, pinned `dtctl`, read-only token): logs, metrics, traces, problems, runtime events. **Atlassian** (person's own MCP login): read picked runbook pages, create the RCA page after approval. **AI model**: Copilot via own login at work, Anthropic API at home. **Grafana**: home testing and the Test bed | [plugins](https://github.com/chiyanram/rca-agent/issues/40), [model choice](https://github.com/chiyanram/rca-agent/issues/26) |
| **Start** | Operator picks a live alert or Dynatrace problem, or pastes alert text, an email or an id | [pasted alert](https://github.com/chiyanram/rca-agent/issues/31) |
| **Investigation** | Pre-fetch → Evidence → Change → Code-locator → RCA writer → RCA gate → Fix proposer → Fix gate → draft PR. Log digest, Code facts (tree-sitter + ripgrep + git), code across registered repos at the Deployed commit | [stages](https://github.com/chiyanram/rca-agent/issues/16), [log digest](https://github.com/chiyanram/rca-agent/issues/27), [code facts](https://github.com/chiyanram/rca-agent/issues/22), [code across repos](https://github.com/chiyanram/rca-agent/issues/11) |
| **Runbooks** | Confluence pages the person picked at setup, read through their MCP login, read-only and version-pinned, plus runbook files in the repo. Treated as Hints; no free search | [#58](https://github.com/chiyanram/rca-agent/issues/58), [knowledge](https://github.com/chiyanram/rca-agent/issues/39) |
| **Fix** | Own Pydantic AI fix agent, full Checks, up to 3 repos with per-repo **Gradle** builds (a Maven repo is read but not built, and the report says so), draft PR opened after the Fix gate. Hotfix offer only, with no hotfix PR | [fix checks](https://github.com/chiyanram/rca-agent/issues/12), [hotfixes](https://github.com/chiyanram/rca-agent/issues/33) |
| **Recovery** | **Recovery commands**: in v1 only `gh workflow run …` with inputs filled in. The runbook is the index, the code is the truth: our code checks each command every time (the workflow exists on the repo's default branch, every input is declared, it targets this service) and it cites the runbook line and the workflow line. A step that fails the check is a Manual step; a workflow found in the code but not in the runbook is still offered, labelled. The person runs them; the app never does. After one is marked done, a read-only post-check shows whether the alert stopped | [#58](https://github.com/chiyanram/rca-agent/issues/58), [no-fix path](https://github.com/chiyanram/rca-agent/issues/30) |
| **Telling the team** | **Notification draft**: recipients picked per service at setup, subject `[RCA] <service> – <one-line cause>`, body from the fixed template and the approved RCA text. Copy buttons and a `.eml` download; the person sends it. An `unresolved` close drafts it to the service's escalation contact instead | [#58](https://github.com/chiyanram/rca-agent/issues/58) |
| **RCA page** | New Confluence page under a space and parent chosen at setup, created after approval, fixed template (Summary, Impact, Timeline, Root cause, Fix, Recovery, Follow-ups) with approved text only, never edited afterwards. Markdown download in the same layout as fallback, also when the org blocks MCP writes | [#58](https://github.com/chiyanram/rca-agent/issues/58) |
| **Close** | Resolution window, Manual steps, guarded outcomes, Incident record, Past Investigations list (Operator only). A Jira key may be pasted into the Operator note (no Jira call; Jira is v2) | [no-fix path](https://github.com/chiyanram/rca-agent/issues/30), [knowledge](https://github.com/chiyanram/rca-agent/issues/39) |
| **Safety** | HITL gates, Action policy, hard never-list, nothing touches production, redaction at ingestion, everything read is data, spend caps ($20 per Investigation, $5 per Fix run; a Copilot call is costed as premium requests × model multiplier × the published price, both shown), a plain local event log as history. **Add, never change, outside the app** | [principles](principles.md) |
| **Logins** | GitHub read fresh from `gh auth token` per Investigation, never stored. Dynatrace (a read-only token made for the app) and Atlassian (browser sign-in, or an API token if the org allows) stored once in an owner-only secrets file under `~/.rca-agent/`, never in the event log. The logins are as broad as the person, so the Action policy is the only limit | [#24](https://github.com/chiyanram/rca-agent/issues/24) |
| **Data on the laptop** | The content of a closed Investigation is deleted after 90 days (plain delete) and on **Delete now**; the who-did-what record stays. No app encryption: Guided setup asks the person to confirm disk encryption and records the answer | [#24](https://github.com/chiyanram/rca-agent/issues/24) |
| **Versions and upgrades** | The Champion is a released image, cut only when its Evaluation run passes the promotion bar and the maintainer signs off. Prompts live in the image. `rca-agent update` shows the version and changelog, asks, pulls that exact image. Events carry a schema version; open Investigations carry on after an upgrade. No downgrades | [#24](https://github.com/chiyanram/rca-agent/issues/24) |
| **Copilot at work** | Uses the same data path the person already uses at work (`dtctl` output into their own Copilot), with redaction first, so it needs no new approval | [#24](https://github.com/chiyanram/rca-agent/issues/24), [own Copilot login check](https://github.com/chiyanram/rca-agent/issues/62) | [principles](principles.md) |
| **Trust details** (from Chitti) | Shown equals sent. Checks just before every write (login still valid, branch unmoved, no PR or page already exists, approval fresh, double-click safe). Named refusals with a retry button. Ask once with real choices, never guess. Thumbs up or down plus one line per RCA | [#58](https://github.com/chiyanram/rca-agent/issues/58) |
| **Screen** | The core Investigation screen: start, live stages, RCA report with Finding chips, approval cards, copyable recovery commands and email draft | [screen prototype](https://github.com/chiyanram/rca-agent/issues/15) |
| **Testing** | Thin evaluation harness. Test bed profile A (GitHub + Grafana + Gradle) with first slice of faults 1/6/7/10/11. No-model Control probes in CI, including a Canary secret, planted fake personal data (hard fail if any reaches an output), the Action policy refusing every action outside the allowed list, and past records never reaching a stage prompt. **Regression set** (gates a release: first-slice faults, fixed injected variants including a forged alert email and an attack on the fallback extractor, safety checks) run 5 times; **Capability set** (measures only) run once. A regression counts only when a flagged Scenario fails most runs again on a 5-run re-run; hard fails count at once. Evaluation run capped at $100 with an estimate shown first; an incomplete run can't sign off a release. Test bed alerts also arrive as emails so the paste path is graded. Wall-clock time per Trial and stage reported next to cost. Dynatrace checked on Playground and then once on a 15-day trial. A Confluence Free site for runbooks and pages | [evaluation](https://github.com/chiyanram/rca-agent/issues/23), [test bed](https://github.com/chiyanram/rca-agent/issues/13), [#58](https://github.com/chiyanram/rca-agent/issues/58), [#24](https://github.com/chiyanram/rca-agent/issues/24) |

## v2: shared deployment (if agreed after the demo)

| Area | In v2 | Detail |
|---|---|---|
| **Hosting and identity** | Hosting platform, workload identity, OIDC sign-in, separate Operator / Setup admin / Auditor roles (and who signs approval records), GitHub App bot, Copilot bot sign-in, data residency and org budget | [security](https://github.com/chiyanram/rca-agent/issues/14), [Copilot at work](https://github.com/chiyanram/rca-agent/issues/36) |
| **Audit** | KMS, per-Investigation envelope encryption, hash chain + signed checkpoints, signed Audit bundle export, 90-day shredding | [audit log](https://github.com/chiyanram/rca-agent/issues/19) |
| **Doing, not preparing** | Confirmed Recovery workflows run by the agent after their own approval, post-checks. Notifications sent (email, Teams) | [critical actions](https://github.com/chiyanram/rca-agent/issues/17), [no-fix path](https://github.com/chiyanram/rca-agent/issues/30) |
| **Atlassian** | Service accounts for reading Knowledge pages and writing Published records, model Hints from past records, Jira link and create | [knowledge](https://github.com/chiyanram/rca-agent/issues/39), [Jira](https://github.com/chiyanram/rca-agent/issues/46), [admin asks](https://github.com/chiyanram/rca-agent/issues/47) |
| **More plugins** | ELK, GitLab + token broker, Azure Connection (deployed-commit app setting) | [backends](https://github.com/chiyanram/rca-agent/issues/20), [GitLab broker](https://github.com/chiyanram/rca-agent/issues/28), [GitLab verify](https://github.com/chiyanram/rca-agent/issues/37) |
| **Hotfixes** | Agent creates an unprotected `hotfix/<tag>` branch and a hotfix draft PR after approval; first a live check that a pull-request-only ruleset on `hotfix/**` still lets the bot create the branch | [hotfixes](https://github.com/chiyanram/rca-agent/issues/33) |
| **Testing** | Test bed profile B (GitLab CE + Elasticsearch + Maven), Attack runs (including a planted-memory goal through past records), human red team, approval runs, sampled scoring of closed real Investigations with an alert on a drop, trends per Agent version | [adaptive attacker](https://github.com/chiyanram/rca-agent/issues/34) |
| **Setup** | Setup export / import, Guided setup model helper | [per-person install](https://github.com/chiyanram/rca-agent/issues/41) |
| **Questions** | Follow-up questions on a finished RCA | [follow-ups](https://github.com/chiyanram/rca-agent/issues/21) |

## Later

- Library + consumer fixes ([#38](https://github.com/chiyanram/rca-agent/issues/38)).
- Prompt Optimisation runs ([#35](https://github.com/chiyanram/rca-agent/issues/35)), with the held-out flag, catalog version and approval provenance; whether a significance test is added once an optimiser runs many tries.
- Judge calibration on 50–100 human-graded reports per model family before the judge may decide Grades; an evaluation screen; a nightly evaluation runner.
- Function-app faults 14–16 ([#32](https://github.com/chiyanram/rca-agent/issues/32)).
- Third-party plugins, App Insights and Azure Monitor, Slack, gate reminders, per-user identity, Kotlin, jdtls, and the other code-fact upgrades. All are listed under *Not yet specified* on the [map](https://github.com/chiyanram/rca-agent/issues/1).
