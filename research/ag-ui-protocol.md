# AG-UI protocol: events, state, and human-in-the-loop interrupts

Research for issue #2. Researched 2026-11-04.

**Sources.** The `docs/` folder of [ag-ui-protocol/ag-ui](https://github.com/ag-ui-protocol/ag-ui) at commit `08eae9d` (2026-11-03). That folder is the source of https://docs.ag-ui.com, and I spot-checked it against the live site. Package registries (npm, PyPI) were checked the same day. Paths below are relative to the repo root unless they are full URLs.

**Versions at time of writing.**

| Artifact | Version | Released |
|---|---|---|
| Protocol | **1.0**, the first release with a normative spec. Schema: `docs/spec/1.0/schema.json` | 1.0.0 on 2026-09-17 |
| `@ag-ui/core`, `@ag-ui/client`, `@ag-ui/encoder` (TS) | 1.0.3 | 2026-10-16 (npm) |
| `ag-ui-protocol` (Python) | 1.0.0 | 2026-09-17 (PyPI). Before that, 0.1.9 (2025-09) |
| `ag-ui-claude-sdk` (Python adapter) | 0.2.3 | 2026-10-21 (`integrations/claude-agent-sdk/python/CHANGELOG.md`) |
| `@ag-ui/claude-agent-sdk` (TS adapter) | 0.0.8 | — |
| Java SDK (community, `com.ag-ui.community`) | 0.1.1 core. 4.1.0 Spring modules | `docs/sdk/java/overview.mdx` |
| `@copilotkit/react-core` | 1.84.1 (npm). The AG-UI Dojo pins 1.81.0 | — |
| Repo releases | Date-tagged, about every 1–3 days (latest `release/2026-11-03`) | `gh release list` |

---

## 1. What AG-UI is, in one paragraph

AG-UI is an event protocol between an agent backend and a user-facing app. The client POSTs a `RunAgentInput` containing `threadId`, `runId`, `messages`, `state`, `tools`, `context`, `forwardedProps` and `resume`. The agent answers with a stream of typed events for that **run**. The default transport is HTTP POST answered by Server-Sent Events, with one JSON event per SSE `data:` frame. 1.0 also specifies an HTTP + Protobuf binding (`docs/spec/1.0/basic/transports/http-sse.mdx`, `.../http-protobuf.mdx`). The protocol is backend-agnostic, so any server that emits the events is a valid agent.

## 2. Event types (1.0)

Source: `docs/concepts/events.mdx`, `docs/spec/1.0/events/*`. Every event carries `type`, plus optional `timestamp`, `rawEvent` and `metadata`.

| Family | Events | Notes |
|---|---|---|
| **Lifecycle** | `RUN_STARTED`, `RUN_FINISHED`, `RUN_ERROR`, `STEP_STARTED`, `STEP_FINISHED` | `RUN_STARTED` has `threadId`, `runId`, an optional `parentRunId` (branching and time travel), an optional echoed `input`, and `protocolVersion`, which a 1.0 producer MUST set. `RUN_FINISHED` has an optional `result` and an optional **`outcome`**: `success`, `interrupt` or `cancelled`. `RUN_FINISHED` and `RUN_ERROR` MAY carry per-provider token `usage`. `RUN_ERROR` is the only error event. Steps are named sub-phases. |
| **Text** | `TEXT_MESSAGE_START` / `_CONTENT` / `_END`, `TEXT_MESSAGE_CHUNK` | Streamed by `messageId`. The chunk form is a shorthand that the client expands. |
| **Tool calls** | `TOOL_CALL_START` / `_ARGS` / `_END`, `TOOL_CALL_RESULT`, `TOOL_CALL_CHUNK` | Args stream as JSON fragments. In 1.0, a result's `content` can be a string or a list of content parts (text, image, document, and so on). Tool calls can carry `metadata`. |
| **State** | `STATE_SNAPSHOT`, `STATE_DELTA`, `MESSAGES_SNAPSHOT` | A snapshot replaces the whole value. A delta is an RFC 6902 JSON Patch. `MESSAGES_SNAPSHOT` reconciles the conversation by message id. |
| **Activity** (new in 1.0) | `ACTIVITY_SNAPSHOT`, `ACTIVITY_DELTA` | Structured progress messages with a `messageId`, an `activityType` (for example `"PLAN"` or `"SEARCH"`) and JSON content amended by patch. |
| **Reasoning** (new in 1.0) | `REASONING_START`/`_END`, `REASONING_MESSAGE_START`/`_CONTENT`/`_END`/`_CHUNK`, `REASONING_ENCRYPTED_VALUE` | Replaces the 0.x `THINKING_*` events. The client translates `THINKING_*` until 2027-09-17 (`DEPRECATIONS.md`). Encrypted values carry opaque provider artifacts, such as Claude thinking signatures, that the client stores and sends back. |
| **Subagents** (new in 1.0) | `SUBAGENT_STARTED`, `SUBAGENT_FINISHED`, `SUBAGENT_ERROR` | Delegated work is attributed through `subagentRunId` on events. `SUBAGENT_FINISHED.outcome` can be `suspended` (waiting on an interrupt). |
| **Special** | `RAW`, `CUSTOM` (`name`, `value`) | Escape hatches. |
| Draft | `META_EVENT` | Not in 1.0. |

Rules worth knowing (`docs/spec/1.0/changelog.mdx`):

- **Unknown and malformed are treated differently.** A consumer drops unknown events and fields with a warning. A malformed value of a known type is fatal.
- **Absent means absent.** Optional fields are omitted, never sent as `null`.
- **Capabilities are declared up front.** An agent can publish `AgentCapabilities`, including `humanInTheLoop.{supported, approvals, interventions, feedback, interrupts, approveWithEdits}` (`docs/concepts/capabilities.mdx`). These declarations are informative only; the event stream is what counts.

## 3. State

Source: `docs/concepts/state.mdx`, `docs/spec/1.0/basic/patterns/snapshots.mdx`.

- State is a single JSON object per thread. Both sides can see it. The client sends the current state in `RunAgentInput.state`, and the agent streams it back as snapshots and deltas.
- A consumer MUST replace its copy of the state with a snapshot (snapshots never merge). Deltas are JSON Patch applied in order. On any inconsistency, the consumer falls back to the next snapshot.
- **Rule at the interrupt boundary:** before a `RUN_FINISHED` that carries an interrupt, the agent MUST emit every piece of state the resume needs as `STATE_SNAPSHOT` and `MESSAGES_SNAPSHOT`. This makes resume work the same way for agents that replay history and agents that restore a checkpoint (`docs/concepts/interrupts.mdx`).
- **No stream resumption.** SSE `Last-Event-ID` is not used, and a broken stream cannot be re-entered (`http-sse.mdx`). To recover, the client starts a new request. The producer can replay the thread's history at the start of that stream as several runs, and any history the client already holds MUST be restated as snapshots so the replay is idempotent (`docs/spec/1.0/events/lifecycle.mdx`, "Several runs on one stream").

## 4. Human-in-the-loop: how pausing is expressed

The protocol has **no mid-run channel from client to agent** (`docs/spec/1.0/events/tool-calls.mdx`, "Frontend tools"). Every human answer therefore crosses a **run boundary**: the run ends, and a new run on the same `threadId` carries the answer. There are two mechanisms.

### 4a. Interrupt outcome (new in 1.0; the main mechanism for approval gates)

Source: `docs/concepts/interrupts.mdx`, `docs/spec/1.0/basic/patterns/interrupt-resume.mdx`.

1. The agent emits its snapshots, then `RUN_FINISHED { outcome: { type: "interrupt", interrupts: [Interrupt, ...] } }`.
2. An `Interrupt` has these fields:
   - `id`: the correlation key.
   - `reason`: one of the core values `tool_call`, `input_required` or `confirmation`, or a custom `ns:name`.
   - `message`: fallback text the UI can show.
   - `toolCallId`: links the interrupt to a proposed tool call.
   - **`responseSchema`**: JSON Schema for the answer.
   - `expiresAt`: TTL.
   - `metadata`.
   - `subagentRunId`.
3. The client starts the next run with `resume: [{ interruptId, status: "resolved" | "cancelled", payload?, metadata? }]`.
   - A denial goes inside the payload, for example `{ approved: false }`.
   - `resume[].metadata` can carry a signature or audit envelope.
4. Contract rules:
   - The resume uses the same thread.
   - **All open interrupts must be answered at once.** Partial resumes are not supported.
   - **A thread with pending interrupts rejects any input that doesn't resume them**, with `RUN_ERROR`.
   - Resumes are idempotent on `(threadId, interruptId, status, payload)`.
   - A resume after `expiresAt`, or one whose payload fails the schema, is answered with `RUN_ERROR`.
5. **Approve-with-edits** is standardised:
   - The `responseSchema` is `{ approved: boolean, editedArgs?: object }`, where `editedArgs` is a full replacement for the tool arguments.
   - The presence of `editedArgs` in the schema is the signal that the UI can offer editing.
   - The audit trail is: `TOOL_CALL_ARGS` in run N (the proposal), then `resume.payload.editedArgs` in run N+1 (the human's edit), then `TOOL_CALL_RESULT` in run N+1 against the original `toolCallId` (the execution).
6. Parallel interrupts are supported. For example, the client can approve two and cancel one in a single resume.
7. `metadata: { "ag-ui:tool-execution": "server" }` marks a tool that the server owns. The client sends only the decision, and the server executes the tool. The spec notes that this marker is not an authorization credential, so the server must still validate the decision.

### 4b. Frontend tools (the older mechanism; still supported)

- The client lists tools in `RunAgentInput.tools`. When the agent calls one, the agent MUST NOT answer it. The run ends as **success** with `pendingToolCallIds`, never as an interrupt.
- The client runs the tool and then starts a new run with the tool-result message.
- This is how CopilotKit's `useFrontendTool` and `useHumanInTheLoop` work (`docs/concepts/tools.mdx`).
- It fits UI actions, such as showing a chart or navigating, better than gates. It carries no schema-typed approval, expiry or audit linkage.

### Framework support for interrupts

| Integration | Interrupt support |
|---|---|
| LangGraph | Off by default: opt in with `emit_interrupt_outcome`. A legacy `CUSTOM on_interrupt` event is emitted by default. |
| AWS Strands | Forwards native interrupts as outcome interrupts. |
| Mastra, CrewAI, .NET (Microsoft Agent Framework) | Dojo has interrupt and tool-approval pages for these (`apps/dojo/e2e/tests/*/interruptPage.spec.ts`). .NET emits the server-execution marker. |
| **Claude Agent SDK adapter** | Native permission approvals are emitted as outcome interrupts. The client answers with `resume: [{interruptId: <original tool_use id>, status: "resolved", payload: {behavior: "allow" \| "deny", updatedInput?, message?}}]`. This follows the SDK's own permission-hook contract rather than the `approved`/`editedArgs` convention. Frontend tools pause the run for execution on the client. Recovery across process restarts requires a durable `session_binding_store`, and the README labels it "PNI-659, unreleased". Tested with Claude Agent SDK (Python) 0.2.166, CLI 2.1.299, AG-UI 1.0 (`integrations/claude-agent-sdk/python/README.md`). |

## 5. Frontend options

- **CopilotKit** (React) is the first-party frontend and the one the AG-UI team builds.
  - The v2 API (`@copilotkit/react-core/v2`) includes `useAgent`, `useFrontendTool`, `useHumanInTheLoop`, `useRenderTool`, `useCoAgent` (shared state) and **`useInterrupt({ agentId, enabled, render: ({event, resolve}) => ... })`**.
  - `useInterrupt` renders an approval card in the chat, and calling `resolve(payload)` sends the resume. See `apps/dojo/src/app/[integrationId]/feature/(v2)/tool_approval/page.tsx`.
  - It also renders A2UI and MCP Apps generative UI.
  - There is a CopilotKit "channels-sdk" for Slack and Teams, which is relevant to the later "Other HITL channels" item.
- **Custom UI.** `@ag-ui/client` provides `HttpAgent`, an event pipeline, a run state machine and subscribers, all framework-free. Because the protocol is plain SSE + JSON with a published JSON Schema, a hand-rolled client in any stack is practical.
- **AG-UI Dojo** (`apps/dojo`, https://dojo.ag-ui.com) is the reference playground. It is a Next.js app with feature pages per integration (agentic chat, shared state, HITL, interrupt, tool approval, generative UI). **It is the fastest way to prototype the HITL UI**: point it at our endpoint, or copy a page.
- **Other clients** listed on the integrations page: a terminal client, React Native, and Slack/Teams through channels-sdk.

## 6. Server SDK maturity

| SDK | Status | What it gives you |
|---|---|---|
| **TypeScript** (`@ag-ui/core`, `client`, `encoder`, `proto`, `cli`) | First-party. Reference implementation. 1.0.3 | Generated types, an encoder (SSE and proto), the client, and `AbstractAgent` for building a server agent. Many integrations (Mastra, LangGraph JS, ADK-JS, Claude Agent SDK TS) are built on it. |
| **Python** (`ag-ui-protocol`) | First-party. 1.0.0 | Only `ag_ui.core` (generated Pydantic types, `PROTOCOL_VERSION`) and `ag_ui.encoder` (`EventEncoder` for SSE). **No server framework.** Each integration adds its own FastAPI endpoint, for example `add_claude_fastapi_endpoint`. Writing a FastAPI or Starlette SSE endpoint yourself is a few dozen lines. |
| .NET (`AGUI.Server`) | First-party (in `sdks/dotnet`) | Builds `RUN_STARTED` automatically and supports the server-execution marker. Used by Microsoft Agent Framework. |
| **Java** | Community. 0.1.1 | Java 17. JDK `Flow.Publisher<Event>` with sealed records. Server modules for the JDK `HttpServer`, **Spring WebFlux, Spring WebMVC and Spring AI**, which require Spring Boot 4.1 and Spring AI 2.x. The models include interrupts. |
| Kotlin, Go, Rust, Dart, Ruby, C++, Swift | Community | Of varying depth. |

The protocol types in every SDK are now generated from one schema (`docs/migrating-to-1-0.mdx`), so type drift between SDKs is no longer a concern.

## 7. Agent frameworks with first-party integrations

The repo has an `integrations/` folder for each of these:

- LangGraph and LangChain
- Mastra
- Pydantic AI
- Google ADK (Python middleware and JS)
- Google Antigravity
- AWS Strands
- Microsoft Agent Framework (Python and .NET)
- CrewAI
- LlamaIndex
- Agno
- AG2
- Langroid
- Vercel AI SDK
- watsonx
- A2A middleware
- Oracle Agent Spec
- **Claude Agent SDK** (Python 0.2.3, TS 0.0.8)
- **Claude Managed Agents** (TS, Python, .NET)

Community integrations: Spring AI, Genkit, Cloudflare Agents, Omnara.

Infrastructure: Amazon Bedrock AgentCore runtime hosts AG-UI natively (announced 2026-03).

Sources: `docs/integrations.mdx` and the `integrations/` directory.

## 8. Implications for the RCA agent

These are inputs for the downstream decisions. They are not decisions.

- **HITL gates map directly onto the interrupt outcome.**
  - Each gate is a `RUN_FINISHED` interrupt with a `responseSchema`. Examples: approve the RCA report, approve the Fix proposal, approve a risky tool call, or ask the human for missing context (`input_required`).
  - "Approve / reject / edit" is the standard `{approved, editedArgs}` pattern.
  - `expiresAt`, idempotent resumes, and the run → resume → run audit trail match the CONTEXT.md definition of a HITL gate.
  - This also matches 12-factor "launch/pause/resume" and "contact humans with tools": a run is a stateless step, and state is restated as snapshots at every pause.
- **The RCA report can be live shared state.** Hypotheses, evidence and suspect code locations can live in `STATE_SNAPSHOT`/`STATE_DELTA`. Investigation progress can use `ACTIVITY_*` (`"PLAN"`, `"SEARCH"`) and `STEP_*`. Small focused agents can be attributed with `SUBAGENT_*`.
- **Long Investigations need durable state on the server.** SSE has no resumption and a dropped stream cannot be re-entered. The agent must persist thread state and pending interrupts itself, so that a reconnecting UI gets the history replayed as snapshots and a gate survives a server restart. Neither the protocol nor the Python SDK supplies a store.
- **Runtime choice.**
  - The protocol doesn't constrain language.
  - TS is the reference implementation and has the richest tooling.
  - Python offers the types and encoder only.
  - The Claude Agent SDK adapter works, but it is young (0.x) and its approval payload is Claude-specific (`behavior: allow/deny`). Its restart recovery is unreleased.
  - Owning the loop, per 12-factor, on the raw Claude API and emitting AG-UI events ourselves is straightforward with either the TS or the Python SDK.
- **UI prototype.** Start from the AG-UI Dojo, or a minimal Next.js + CopilotKit v2 app, using `useInterrupt` for gates and `useCoAgent`/`useAgent` for rendering the report state. A custom React UI on `@ag-ui/client` is a viable fallback if CopilotKit's opinions get in the way.
