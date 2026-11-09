# Principles

The rules every design decision in this project follows. Each one comes from a closed ticket on the [planning map](https://github.com/chiyanram/rca-agent/issues/1); the ticket holds the full reasoning. When a new proposal breaks a principle, say so and reopen it through a ticket rather than working around it.

Terms are defined in [`CONTEXT.md`](../CONTEXT.md). Hard-to-reverse decisions have an ADR in [`adr/`](adr/).

## 1. 12-factor agents, as applied here

Source: [humanlayer/12-factor-agents](https://github.com/humanlayer/12-factor-agents). Full mapping in the [12-factor research findings](https://github.com/chiyanram/rca-agent/blob/research/12-factor-constraints/research/12-factor-constraints.md); the right-hand column is what we decided.

| # | Factor | Our rule |
|---|---|---|
| 1 | Natural language → tool calls | The model's only job per step is to choose one typed next step; our code acts on it. |
| 2 | Own your prompts | Prompts are versioned templates in the repo, one per Stage, and part of the Agent version. No framework-generated wrappers. |
| 3 | Own your context window | Our code renders every model input from the event log. Evidence arrives as summaries (Log digest, reduced metrics), redacted, with logs and code fenced as data. |
| 4 | Tools are structured outputs | A tool call describes an Action; the Action policy checks, clamps and audits it before anything runs. |
| 5 | Unify execution and business state | The Investigation **is** its append-only event log; status, UI and audit are views of it ([ADR-0002](adr/0002-event-log-is-the-source-of-truth.md)). |
| 6 | Launch / pause / resume | Simple APIs; AG-UI is one client of them, never the owner of a run. |
| 7 | Contact humans with tools | Mandatory HITL gates are enforced by the pipeline; the model may additionally ask up to 2 Human questions. |
| 8 | Own your control flow | Our own pipeline decides stage order and gates; persist-and-exit at each gate ([ADR-0001](adr/0001-own-pipeline-small-agent-per-stage.md)). |
| 9 | Compact errors | Errors come back as short events; retries are capped, then the stage is `stalled` or hands on an incomplete result. |
| 10 | Small, focused agents | One small agent per Stage (Evidence, Change, Code-locator, RCA writer, Fix proposer), each with its own budget. |
| 11 | Trigger from anywhere | **Deliberately narrowed:** an Operator always starts an Investigation; alerts never start one on their own ([ADR-0003](adr/0003-operator-always-starts-an-investigation.md)). |
| 12 | Stateless reducer | State is a fold over events, so Investigations can be replayed and forked for evaluation. |
| 13 | Pre-fetch context | The Pre-fetch Stage gathers the obvious evidence before the first model call. |

## 2. Product principles

### Humans decide
- **Every Investigation ends in an RCA report**; a Fix proposal comes only after a human approves the RCA. ([HITL gates](https://github.com/chiyanram/rca-agent/issues/9))
- **No gate approves itself**, expires into approval or is skipped.
- **The agent never touches production directly.** Restart, rollback, scale and out-of-repo config are Manual steps a human performs; the only critical Action it runs is a Recovery workflow a Setup admin confirmed ([ADR-0004](adr/0004-agent-never-changes-production-directly.md)).
- **Manual first, automate later**: a Manual step done often becomes a confirmed Recovery workflow, run only after its own approval. ([Kubernetes profile ticket](https://github.com/chiyanram/rca-agent/issues/32))
- **Never auto-merge, never release**: fixes open as draft pull requests for human review; tagging, releasing and deploying (hotfixes included) are always done by people. The agent never pushes to a protected branch and never asks to be put on a bypass list. ([hotfixes](https://github.com/chiyanram/rca-agent/issues/33))

### Evidence, not assertion
- **Every claim is a cited Finding**: a query with its range and link, or code at the Deployed commit. The RCA report rests only on recorded Findings, and our code validates that. ([pipeline stages](https://github.com/chiyanram/rca-agent/issues/16))
- **Deterministic first, model second.** What code can work out (Code facts, Log digest, Impact reach, Checks), code works out; the model cites it and never changes it. ([Code facts](https://github.com/chiyanram/rca-agent/issues/22), [Log digest](https://github.com/chiyanram/rca-agent/issues/27))
- **Simple means computes less, never computes wrongly.** A deterministic fact may report too much (labelled `heuristic`) but never silently miss something; a tool that drops results it can't resolve is not adopted. ([Code facts](https://github.com/chiyanram/rca-agent/issues/22), [graphify prototype](https://github.com/chiyanram/rca-agent/issues/45))
- **The Fix engine proposes, our Checks decide.** What an engine claims about its own work never counts. ([Fix checks](https://github.com/chiyanram/rca-agent/issues/12))
- **Gaps are named, never hidden.** A budget hit yields an incomplete result with its gaps listed; an unreachable backend makes the stage `stalled`; an unknown Deployed commit is flagged.

### Trust and security
- **Everything read is data, not instructions**: logs, traces, commit messages, code comments and Pasted alerts can never steer where the agent looks, who is told or what runs. ([security](https://github.com/chiyanram/rca-agent/issues/14), [Pasted alert](https://github.com/chiyanram/rca-agent/issues/31))
- **Redact at ingestion**, before anything reaches the event log or a model.
- **Least privilege, minted late**: read tokens scoped to one Investigation; a write token for one repo only after a Fix gate approval; revoked as soon as done. ([GitHub](https://github.com/chiyanram/rca-agent/issues/7), [token broker](https://github.com/chiyanram/rca-agent/issues/28))
- **Scopes are the control, not switches**: a CLI's or MCP server's "read-only" flag or hint never counts as a limit; only the credential's own scopes and the Action policy do. Every Plugin call is bounded, parsed by our code and redacted like any other; the model never writes a command. A personal login is allowed only in a per-person copy and is always recorded as such. ([integrations as plugins](https://github.com/chiyanram/rca-agent/issues/40))
- **Read named settings, never list them**: app settings and environment config hold secrets, so the agent reads only the one setting the Setup names (for example the deployed-commit key) and never enumerates the rest. ([Kubernetes test bed](https://github.com/chiyanram/rca-agent/issues/32))
- **Only confirmed Setup reaches the agent.** Scanned items stay drafts until a Setup admin confirms; a trust-bearing item that changes is suspended until re-confirmed. ([setup flow](https://github.com/chiyanram/rca-agent/issues/18))
- **Everything is audited**, tamper-evidently; content expires, the who-did-what record stays. ([audit log](https://github.com/chiyanram/rca-agent/issues/19))

### Neutral by design
- **Provider-neutral**: any capable model provider; nothing hard-depends on Claude or Claude Code ([ADR-0005](adr/0005-provider-neutral-models.md)).
- **Backend-neutral**: one adapter per boundary (Observability routed per signal, Source control, Build); the agent sees the same shape whichever backend answers. ([backends](https://github.com/chiyanram/rca-agent/issues/20))
- **Cloud-neutral identity**: workload identity first; credentials are references, never values.

### Measured, and bounded
- **Graded, not guessed**: Scenarios with Answer keys the agent can never read, graded by fixed checks; a model's opinion is advisory. ([test bed](https://github.com/chiyanram/rca-agent/issues/13), [evaluation](https://github.com/chiyanram/rca-agent/issues/23))
- **Test what production can actually do**: Seeded faults mirror the real hosting (Azure Functions), not every platform. ([Kubernetes profile ticket](https://github.com/chiyanram/rca-agent/issues/32))
- **Spend is capped and recorded**: $20 per Investigation, $5 per Fix run, $100 per Evaluation run; every model call is costed. No automatic model or provider switch. ([model choice](https://github.com/chiyanram/rca-agent/issues/26))

## 3. How we plan

The working rules (Wayfinder map, one ticket per session, facts looked up and decisions made by the user, glossary first) live in [`AGENTS.md`](../AGENTS.md) and [`CONTRIBUTING.md`](../CONTRIBUTING.md).
