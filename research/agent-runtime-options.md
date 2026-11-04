# Agent runtime options with AG-UI + Claude

Research for issue #4. Researched on 2026-11-04. Versions are the latest published on PyPI/npm that day.

**Question.** Which runtimes can host the RCA agent with Claude as the model and AG-UI as the frontend protocol? How does each score on the 12-factor principles: own your control flow, context window, and prompts, and pause/resume at HITL gates?

**Short answer.** All five options can serve AG-UI with Claude. The main difference between them is who owns the loop.

- **Python custom loop**, **Pydantic AI** and **LangGraph** all give you strong control and a mature, protocol-native HITL path.
- **Claude Agent SDK** gives you the most capability for free, but you own the least of the loop. Its AG-UI bridge is a young community adapter, and that adapter's restart-durable HITL is still marked unreleased.
- **TypeScript (Mastra or a custom loop)** is viable. It only pays off if the team wants a single-language stack with the frontend.

The final choice belongs to #8.

---

## 1. What AG-UI requires of a runtime

AG-UI 1.0 standardises HITL as **interrupts**. This defines the HITL contract every option has to meet ([docs.ag-ui.com/concepts/interrupts](https://docs.ag-ui.com/concepts/interrupts)):

- **Pausing.** A run pauses by ending with `RUN_FINISHED` carrying `outcome: {type: "interrupt", interrupts: [...]}`. Before that it emits `StateSnapshot` and `MessagesSnapshot`. There is no separate interrupt event.
- **Interrupt fields.** Each interrupt has `id`, `reason` (`tool_call` | `input_required` | `confirmation` | namespaced custom), `message`, `toolCallId`, `responseSchema`, `expiresAt` and `metadata`.
- **Resuming.** The next `RunAgentInput` on the same thread carries `resume: [{interruptId, status: "resolved"|"cancelled", payload}]`. It must address every open interrupt.
- **Statelessness.** The protocol is stateless between runs. Durability across a pause is the runtime's job, through a checkpointer, session store or snapshot store.

The **integration tiers** on the AG-UI integrations list ([docs.ag-ui.com](https://docs.ag-ui.com/introduction)) are:

- **Partnership:** LangGraph, CrewAI.
- **1st party (built in by the framework):** Mastra, Pydantic AI, plus MS Agent Framework, Google ADK, AWS Strands and others.
- **Community:** Claude Agent SDK and Claude Managed Agents, both maintained in the ag-ui repo.
- **Direct to LLM:** supported, with docs hosted by CopilotKit.

The page has no standalone "Anthropic SDK" integration. For a custom loop you use the protocol SDKs directly:

- Python: `ag-ui-protocol` 1.0.0 (2026-09-17), with Pydantic event models and an SSE `EventEncoder` ([sdks/python](https://github.com/ag-ui-protocol/ag-ui/tree/main/sdks/python)).
- TypeScript: `@ag-ui/core` / `@ag-ui/client` 1.0.3 (2026-10-16).

## 2. Comparison table

| Option | AG-UI integration (status, package, version) | Claude support | HITL pause/resume via AG-UI interrupts | Durable state across pause/restart | Control flow you own | Maturity / risk |
|---|---|---|---|---|---|---|
| **A. Custom Python loop**: `anthropic` SDK + `ag-ui-protocol` + FastAPI | Protocol SDK only (`ag-ui-protocol` 1.0.0). You write the event emission and the `resume[]` handling yourself. | Native and first-party (`anthropic` 2.4.0, 2026-11-02). Optional `tool_runner` helper for the inner loop. | Whatever you build: you map your own gate to `RUN_FINISHED.outcome=interrupt`. | Whatever you build, e.g. a Postgres row per Investigation (thread state + pending gate). | **All of it**: the 12-factor ideal. The loop is a `while` over `messages.create` with your own switch on tool calls. | Low library risk, highest build cost. You re-implement streaming event mapping, tool-call arg streaming and state snapshots. |
| **B. Pydantic AI** (Python) | **1st party** in the framework: `pydantic-ai-slim[ag-ui]` 2.66.0 (2026-11-04). `AGUIAdapter.run_stream()` / `dispatch_request()` mounts in FastAPI. | First-class Anthropic model provider. | **Native**: tools with `requires_approval=True` end the run with `outcome.type="interrupt"`. The resume `payload` takes `{approved, editedArgs, reason}` and maps to `ToolApproved`/`ToolDenied`. Needs `DeferredToolRequests` in `output_type`. | Typed `StateDeps[Model]` for shared AG-UI state. Durable execution engines include **Temporal, DBOS, Prefect, Restate, Azure Durable Task**, pgtask, AWS Lambda and others. | High. Typed tools, deps and outputs. `agent.iter()` steps the graph node by node. You can drop to `pydantic-graph` for explicit flow. The framework still runs the inner tool loop. | Very active, with near-daily releases; the frequent minor-version churn is the risk. Same team as Pydantic/Logfire. |
| **C. LangGraph** (Python or TS) | **Partnership**: `ag-ui-langgraph` 0.0.47 (2026-10-08), `@ag-ui/langgraph` 0.0.45. Docs hosted by CopilotKit. | Via `langchain-anthropic` 1.7.9. | `interrupt()` inside a node, then `Command(resume=...)`. The AG-UI standard `outcome`/`resume[]` is **opt-in** (`emit_interrupt_outcome=True`, default `False`) because CopilotKit clients still used a legacy channel. A node re-runs from its start on resume, so code before `interrupt()` must be idempotent. | **Best built-in**: checkpointer per `thread_id` (`langgraph-checkpoint-postgres` 3.2.0). Pause and resume survive restarts by design. | High at the graph level: you draw the nodes and edges explicitly. Indirection through LangChain message and model abstractions works against "own your prompts". | Most mature graph runtime (langgraph 1.2.19, 2026-10-30). The integration packages are still 0.0.x. Heavier dependency tree. |
| **D. Claude Agent SDK** (Python or TS) | **Community**: `ag-ui-claude-sdk` 0.2.3 (PyPI, 2026-10-21, maintained by Red Hat's Ambient Code Platform), `@ag-ui/claude-agent-sdk` 0.0.8 (npm). Pins `claude-agent-sdk==0.2.170`. | Claude only. It is the Claude Code harness: `claude-agent-sdk` 0.2.178 (py) and 0.3.318 (TS), both 2026-11-03/04. It spawns the bundled Claude Code CLI as a subprocess. | Frontend-tool halting works in memory. Native permission approvals map to AG-UI interrupts and resume via `resume=[{interruptId, payload:{behavior:"allow"\|"deny"}}]`. **Restart-durable recovery is labelled "PNI-659, unreleased"**, supports **one tool call at a time**, and needs a host `session_binding_store`. | The SDK keeps transcripts in `.claude/` (a volume) or a pluggable `SessionStore`. The SDK ships reference Postgres/Redis/S3 adapters that are explicitly marked not production-maintained. | **Lowest.** The SDK owns the loop, the default system prompt, context compaction and the built-in tools. You steer it with options, hooks (`PreToolUse`…), `can_use_tool` and MCP tools. Conflicts with "own your control flow / context window". | Very capable: file and code tools, subagents, compaction. These are useful for code-reading and fix-PR work. The AG-UI bridge is young and churning (breaking changes in 0.2.2). The CLI subprocess model complicates hosting. Breaks the "thin model interface", because the model is locked to Claude. |
| **E1. TypeScript + Mastra** | **1st party**: `@ag-ui/mastra` 2.0.2 (2026-10-30). Mastra `@mastra/core` 1.82.0 (2026-11-04). | Via AI SDK `@ai-sdk/anthropic` 4.0.96. | **Native**: tool `suspend()` and `requireApproval` are bridged to `outcome.interrupt`. At most **one interrupt per run**. Resume goes to `resumeStream`. | Snapshot storage on the Mastra instance (e.g. `@mastra/pg` 1.35.0) is required. The default in-memory store loses snapshots on exit. `listSuspendedRuns()` handles recovery. Workflows have a separate `suspend()/resume()`. | Medium-high. Workflows give explicit steps. Agents run the inner loop for you. | Mature, fast-moving TS framework. Shares a language with a React/CopilotKit frontend. Every other part of the stack (Java targets, Python ML tooling) is not TS. |
| **E2. TypeScript custom loop**: `@anthropic-ai/sdk` + `@ag-ui/client` | Protocol SDK (`@ag-ui/core`/`@ag-ui/client` 1.0.3). Extend `AbstractAgent`. | `@anthropic-ai/sdk` 1.4.0 (first-party). | You build it, same as A. | You build it, same as A. | All of it. | Same trade-off as A, in TS. |

## 3. 12-factor scoring (own control flow / context / prompts / pause-resume)

| | Own control flow | Own context window | Own prompts | Pause/resume as first-class | Thin model interface |
|---|---|---|---|---|---|
| A / E2 custom loop | ★★★ | ★★★ | ★★★ | ★★ (yours to build; the protocol gives you the shape) | ★★★ |
| B Pydantic AI | ★★½ | ★★½ (message history is plain data you can rewrite and pass in) | ★★★ | ★★★ (deferred tools map directly to AG-UI interrupts, plus durable engines) | ★★★ (model-agnostic) |
| C LangGraph | ★★★ (explicit graph) | ★★ (state reducers; LangChain message types) | ★★ | ★★★ (checkpointer); AG-UI standard outcome is opt-in | ★★½ |
| D Claude Agent SDK | ★ | ★ (the SDK compacts and manages it) | ★½ (custom prompt possible, harness behaviour remains) | ★½ today (in memory); ★★½ once PNI-659 ships | ✗ (Claude-only) |
| E1 Mastra | ★★ | ★★ | ★★½ | ★★½ (one interrupt per run) | ★★★ (AI SDK providers) |

The stars are a judgement based on the cited docs, not a measurement.

## 4. Observations that matter for this project

- **HITL gates in this project are coarse.** They are "approve RCA report" and "approve Fix proposal", not "approve every tool call". All options can express a coarse gate as a single interrupt. The one-interrupt-per-run limits in Mastra and the Claude adapter don't bite for coarse gates.
- **Gates must survive restarts.** An Investigation can wait hours for a human. That points to a runtime with a real persistent checkpoint:
  - LangGraph checkpointers
  - Pydantic AI durable engines (Azure Durable Task fits the Azure hosting question)
  - Mastra storage
  - your own table in a custom loop

  The Claude Agent SDK adapter's durable path is the least proven.
- **A hybrid is plausible.** The RCA loop runs on an owned runtime (A/B/C). A Claude Agent SDK session is invoked as a **tool or subagent** for the code-reading and patch-writing step (Fix proposal), where its file and code tools are strongest. This keeps the outer control flow and HITL gates under your control.
- **Language.** Python has the richest set of AG-UI integrations (1st party, partnership and community all present). TypeScript wins only on frontend code sharing. The Java target services don't favour either language.
- **"Direct to LLM" (CopilotKit)** is not a runtime option. It skips an agent backend, so it can't host durable gates.

## 5. Shortlist for #8

1. **Pydantic AI (Python).** The best fit on paper:
   - 1st-party AG-UI
   - native AG-UI interrupt mapping for approvals
   - model-agnostic Claude support
   - durable engines including Azure Durable Task
   - high control without writing protocol plumbing
2. **Custom Python loop** (`anthropic` + `ag-ui-protocol`). The purest 12-factor fit and the fewest dependencies. You pay for it in event-mapping and persistence code.
3. **LangGraph (Python).** Strongest built-in checkpointed pause/resume and an explicit graph. On the other side: LangChain abstractions, 0.0.x AG-UI bridge packages, and an opt-in standard interrupt outcome.

Candidates **not** shortlisted as the primary runtime:

- **Claude Agent SDK.** Consider it instead as the engine for the fix-PR sub-step.
- **Mastra / TS.** Revisit if the team prefers a single-language TS stack.

## 6. Open questions to carry into grilling (#8)

- Should HITL gates be coarse only (RCA, Fix proposal), or also per-tool (e.g. approving any write to GitHub)? This changes how much the per-run interrupt limits matter.
- Where does Investigation state live: a framework checkpointer, or our own `investigation` table? This depends on the "where the agent runs" decision.
- Is a Claude Agent SDK subagent for the Fix proposal acceptable? It needs the CLI subprocess plus a working directory per repo.
- Which frontend client will we use (CopilotKit vs a raw `@ag-ui/client`)? CopilotKit LangGraph hooks still used the legacy resume channel, which is why LangGraph's standard outcome is opt-in.

## Sources

- AG-UI integrations list: https://docs.ag-ui.com/introduction
- AG-UI interrupts: https://docs.ag-ui.com/concepts/interrupts
- AG-UI repo integrations (READMEs read 2026-11-04): https://github.com/ag-ui-protocol/ag-ui/tree/main/integrations (`claude-agent-sdk/python/README.md` + `CHANGELOG.md`, `langgraph/python/README.md`, `mastra/typescript/README.md`), `sdks/python/README.md`
- Pydantic AI AG-UI: https://pydantic.dev/docs/ai/integrations/ui/ag-ui/
- Pydantic AI durable execution: https://pydantic.dev/docs/ai/capabilities/durable_execution/overview/
- LangGraph interrupts: https://docs.langchain.com/oss/python/langgraph/interrupts
- Mastra agent approval: https://mastra.ai/docs/agents/agent-approval ; workflows suspend/resume: https://mastra.ai/docs/workflows/suspend-and-resume
- Claude Agent SDK (Python) README and session store examples: https://github.com/anthropics/claude-agent-sdk-python (`README.md`, `examples/session_stores/README.md`)
- Anthropic Python SDK tool runner: https://github.com/anthropics/anthropic-sdk-python/blob/main/tools.md
- Package versions: PyPI JSON API and npm registry, queried 2026-11-04.
