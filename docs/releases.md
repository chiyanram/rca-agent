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
| **Setup** | Setup screen + scripted Guided setup (no model). Plugins come with defaults, each person signs in and picks their services. Confirmed-only Setup. **Writes are off on a fresh install** and one switch turns them all off again | [setup flow](https://github.com/chiyanram/rca-agent/issues/18), [#58](https://github.com/chiyanram/rca-agent/issues/58) |
| **Plugins** | **GitHub** (`gh auth token`): read repos, open draft PRs. **Dynatrace** (bundled, pinned `dtctl`, read-only token): logs, metrics, traces, problems, runtime events. **Atlassian** (person's own MCP login): read picked runbook pages, create the RCA page after approval. **AI model**: Copilot via own login at work, Anthropic API at home. **Grafana**: home testing and the Test bed | [plugins](https://github.com/chiyanram/rca-agent/issues/40), [model choice](https://github.com/chiyanram/rca-agent/issues/26) |
| **Start** | Operator picks a live alert or Dynatrace problem, or pastes alert text, an email or an id | [pasted alert](https://github.com/chiyanram/rca-agent/issues/31) |
| **Investigation** | Pre-fetch → Evidence → Change → Code-locator → RCA writer → RCA gate → Fix proposer → Fix gate → draft PR. Log digest, Code facts (tree-sitter + ripgrep + git), code across registered repos at the Deployed commit | [stages](https://github.com/chiyanram/rca-agent/issues/16), [log digest](https://github.com/chiyanram/rca-agent/issues/27), [code facts](https://github.com/chiyanram/rca-agent/issues/22), [code across repos](https://github.com/chiyanram/rca-agent/issues/11) |
| **Runbooks** | Confluence pages the person picked at setup, read through their MCP login, read-only and version-pinned, plus runbook files in the repo. Treated as Hints; no free search | [#58](https://github.com/chiyanram/rca-agent/issues/58), [knowledge](https://github.com/chiyanram/rca-agent/issues/39) |
| **Fix** | Own Pydantic AI fix agent, full Checks, up to 3 repos with per-repo builds, draft PR opened after the Fix gate. Hotfix offer only, with no hotfix PR | [fix checks](https://github.com/chiyanram/rca-agent/issues/12), [hotfixes](https://github.com/chiyanram/rca-agent/issues/33) |
| **Recovery** | **Recovery commands**: exact commands (for example `gh workflow run …`) with inputs filled in, each citing its runbook line. The person runs them; the app never does | [#58](https://github.com/chiyanram/rca-agent/issues/58), [no-fix path](https://github.com/chiyanram/rca-agent/issues/30) |
| **Telling the team** | **Notification draft**: recipients, subject and body from the template and the approved RCA text. The person sends it | [#58](https://github.com/chiyanram/rca-agent/issues/58) |
| **RCA page** | New Confluence page under a space and parent chosen at setup, created after approval, fixed template with approved text only, never edited afterwards. Markdown download as fallback | [#58](https://github.com/chiyanram/rca-agent/issues/58) |
| **Close** | Resolution window, Manual steps, guarded outcomes, Incident record, Past Investigations list (Operator only). A Jira key may be pasted into the Operator note (no Jira call; Jira is v2) | [no-fix path](https://github.com/chiyanram/rca-agent/issues/30), [knowledge](https://github.com/chiyanram/rca-agent/issues/39) |
| **Safety** | HITL gates, Action policy, hard never-list, nothing touches production, redaction at ingestion, everything read is data, spend caps ($20 per Investigation, $5 per Fix run), a plain local event log as history | [principles](principles.md) |
| **Trust details** (from Chitti) | Shown equals sent. Checks just before every write (login still valid, branch unmoved, no PR or page already exists, approval fresh, double-click safe). Named refusals with a retry button. Ask once with real choices, never guess. Thumbs up or down plus one line per RCA | [#58](https://github.com/chiyanram/rca-agent/issues/58) |
| **Screen** | The core Investigation screen: start, live stages, RCA report with Finding chips, approval cards, copyable recovery commands and email draft | [screen prototype](https://github.com/chiyanram/rca-agent/issues/15) |
| **Testing** | Thin evaluation harness. Test bed profile A (GitHub + Grafana + Gradle) with first slice of faults 1/6/7/10/11. No-model Control probes and Canary secret in CI. Dynatrace checked on Playground and then once on a 15-day trial. A Confluence Free site for runbooks and pages | [evaluation](https://github.com/chiyanram/rca-agent/issues/23), [test bed](https://github.com/chiyanram/rca-agent/issues/13), [#58](https://github.com/chiyanram/rca-agent/issues/58) |

## v2: shared deployment (if agreed after the demo)

| Area | In v2 | Detail |
|---|---|---|
| **Hosting and identity** | Hosting platform, workload identity, OIDC sign-in, separate Operator / Setup admin / Auditor roles, GitHub App bot, Copilot bot sign-in | [security](https://github.com/chiyanram/rca-agent/issues/14), [Copilot at work](https://github.com/chiyanram/rca-agent/issues/36) |
| **Audit** | KMS, per-Investigation envelope encryption, hash chain + signed checkpoints, signed Audit bundle export, 90-day shredding | [audit log](https://github.com/chiyanram/rca-agent/issues/19) |
| **Doing, not preparing** | Confirmed Recovery workflows run by the agent after their own approval, post-checks. Notifications sent (email, Teams) | [critical actions](https://github.com/chiyanram/rca-agent/issues/17), [no-fix path](https://github.com/chiyanram/rca-agent/issues/30) |
| **Atlassian** | Service accounts for reading Knowledge pages and writing Published records, model Hints from past records, Jira link and create | [knowledge](https://github.com/chiyanram/rca-agent/issues/39), [Jira](https://github.com/chiyanram/rca-agent/issues/46), [admin asks](https://github.com/chiyanram/rca-agent/issues/47) |
| **More plugins** | ELK, GitLab + token broker, Azure Connection (deployed-commit app setting) | [backends](https://github.com/chiyanram/rca-agent/issues/20), [GitLab broker](https://github.com/chiyanram/rca-agent/issues/28), [GitLab verify](https://github.com/chiyanram/rca-agent/issues/37) |
| **Hotfixes** | Agent creates an unprotected `hotfix/<tag>` branch and a hotfix draft PR after approval | [hotfixes](https://github.com/chiyanram/rca-agent/issues/33) |
| **Testing** | Test bed profile B (GitLab CE + Elasticsearch + Maven), Attack runs, human red team, approval runs | [adaptive attacker](https://github.com/chiyanram/rca-agent/issues/34) |
| **Setup** | Setup export / import, Guided setup model helper | [per-person install](https://github.com/chiyanram/rca-agent/issues/41) |
| **Questions** | Follow-up questions on a finished RCA | [follow-ups](https://github.com/chiyanram/rca-agent/issues/21) |

## Later

- Library + consumer fixes ([#38](https://github.com/chiyanram/rca-agent/issues/38)).
- Prompt Optimisation runs ([#35](https://github.com/chiyanram/rca-agent/issues/35)).
- Function-app faults 14–16 ([#32](https://github.com/chiyanram/rca-agent/issues/32)).
- Third-party plugins, App Insights and Azure Monitor, Slack, gate reminders, per-user identity, Kotlin, jdtls, and the other code-fact upgrades. All are listed under *Not yet specified* on the [map](https://github.com/chiyanram/rca-agent/issues/1).
