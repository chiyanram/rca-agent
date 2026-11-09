# AGENTS

Root-cause-analysis agent for Java services on Azure: Operator starts an Investigation from an alert, the agent reads logs/metrics/traces and code across repos, writes an RCA report, and after human approval opens a draft fix PR.

**Status: planning.** This repo holds decisions, not code. The goal is a build-ready spec with the MVP slice marked; every session produces decisions, not deliverables.

## Where things are

- **Map**: GitHub issue #1 (`wayfinder:map`). Its body is the low-res view: Destination, Notes, Decisions so far (one line per closed ticket), Not yet specified, Out of scope.
- **Tickets**: sub-issues of the map, labelled `wayfinder:research|prototype|grilling|task`. Every `gh` operation → `docs/agents/issue-tracker.md`.
- **Glossary**: `CONTEXT.md`, single-context. How to read and extend it → `docs/agents/domain.md`.
- **Triage labels**: the five default roles → `docs/agents/triage-labels.md`.
- **Research findings**: `research/<slug>.md` on branch `research/<slug>`, linked from the ticket's resolution.
- **Prototypes**: branch `prototype/<slug>`.
- **ADRs**: `docs/adr/`, created with the first one.
- **Local drafts**: `.scratch/` (git-ignored).

## Working a ticket

1. **Claim** it (assign) before any work. One ticket per session; list anything else you notice as a follow-up.
2. **Load**: the map body, the ticket's full body, `CONTEXT.md`. Fetch closed tickets only when you need their detail.
3. **Work** by ticket type:
   - `grilling`: `grilling` + `domain-modeling` skills. Ask in rounds, numbered, each with your recommended answer. Look up facts yourself (subagents); the user makes every decision.
   - `research`: `research` skill; findings on a `research/<slug>` branch.
   - `prototype`: throwaway code on a `prototype/<slug>` branch.
4. **Resolve** — done when all of these hold:
   - resolution comment posted and the ticket closed;
   - one Decisions-so-far line appended to the map, just before `## Not yet specified` (re-fetch the body right before editing: other sessions edit it concurrently);
   - inputs posted on dependent open tickets;
   - new tickets created, attached to the map and wired with blocking edges;
   - settled terms in `CONTEXT.md`, committed and pushed.

## Writing for the user

- Name tickets by their linked title, never a bare number.
- Use the `CONTEXT.md` terms exactly; a new concept gets a term there.
- Short sentences, tables for comparisons. The user's messages are often short and typo-heavy: read for intent.

## Boundaries

- **Provider-neutral**: the design runs on any capable model provider (Claude, Copilot, Azure OpenAI…); nothing hard-depends on Claude or Claude Code.
- **Read-only reference**: the sibling `ncs-sdlc-poc-master` project is for reading and analysis only; its files, commits and remotes stay untouched.
- **Credentials** stay out of the repo, tickets and comments; refer to them by name.

## Commits

- Short imperative subject (`CONTEXT: add Runtime event (#32)`).
- `CONTEXT.md` and `docs/` changes go straight to `main`; research and prototypes on their own branch.
- Several sessions share this checkout: commit only the files you changed, and leave the branch, stash and working tree as you found them.

## Build phase (once the spec is assembled)

Python, one `src/rca_agent` package, `uv`, FastAPI, Pydantic AI per stage. Setup, test and lint commands will be listed here when the first code lands.
