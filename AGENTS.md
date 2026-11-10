# AGENTS

Root-cause-analysis agent for Java services on Azure: Operator starts an Investigation from an alert, the agent reads logs/metrics/traces and code across repos, writes an RCA report, and after human approval opens a draft fix PR.

**Status: planning.** This repo holds decisions, not code. The goal is a build-ready spec with the v1 (laptop copy) slice marked; every session produces decisions, not deliverables.

## Where things are

- **Map**: GitHub issue #1 (`wayfinder:map`). Its body is the low-res view: Destination, Notes, Decisions so far (one line per closed ticket), Not yet specified, Out of scope.
- **Tickets**: sub-issues of the map, labelled `wayfinder:research|prototype|grilling|task`. Every `gh` operation → `docs/agents/issue-tracker.md`.
- **Glossary**: `CONTEXT.md`, single-context. How to read and extend it → `docs/agents/domain.md`.
- **Triage labels**: the five default roles → `docs/agents/triage-labels.md`.
- **Research findings**: `research/<slug>.md` on branch `research/<slug>`, linked from the ticket's resolution.
- **Prototypes**: branch `prototype/<slug>`.
- **Principles**: `docs/principles.md`. Check every proposal and recommended answer against it; one that breaks a principle says so and names which.
- **ADRs**: `docs/adr/`, for hard-to-reverse decisions (format → `docs/agents/domain.md`).
- **Local drafts**: `.scratch/` (git-ignored).

## Working a ticket

1. **Claim** it (assign) before any work. One ticket per session; list anything else you notice as a follow-up.
2. **Load**: the map body, the ticket's full body, `CONTEXT.md`. Fetch closed tickets only when you need their detail.
3. **Work** by ticket type:
   - `grilling`: `grilling` + `domain-modeling` skills. Ask **one question at a time**, conversationally: a line of plain-English context first, then the question with your recommended answer. Use numbered rounds only if the user asks for them. If the user is lost, re-explain from scratch in simple words. Look up facts yourself (subagents); the user makes every decision.
   - `research`: `research` skill; findings on a `research/<slug>` branch.
   - `prototype`: throwaway code on a `prototype/<slug>` branch.
4. **Resolve** — done when all of these hold:
   - resolution comment posted and the ticket closed;
   - one Decisions-so-far line appended to the map, just before `## Not yet specified` (re-fetch the body right before editing: other sessions edit it concurrently);
   - inputs posted on dependent open tickets;
   - new tickets created, attached to the map and wired with blocking edges;
   - settled terms in `CONTEXT.md`; a new standing rule in `docs/principles.md`; a hard-to-reverse decision as an ADR; the README "Key decisions" table and the principles tables updated when the decision changes them — all committed and pushed;
   - open items the user must act on (reviews, confirmations) recorded on a ticket, never left only in chat.

## Writing for the user

- Name tickets by their linked title, never a bare number.
- Use the `CONTEXT.md` terms exactly; a new concept gets a term there.
- Short sentences, tables for comparisons. The user's messages are often short and typo-heavy: read for intent.

## Boundaries

- **Provider-neutral**: the design runs on any capable model provider (Claude, Copilot, Azure OpenAI…); nothing hard-depends on Claude or Claude Code.
- **Read-only reference**: the sibling `ncs-sdlc-poc-master` project is for reading and analysis only; its files, commits and remotes stay untouched.
- **Credentials** stay out of the repo, tickets and comments; refer to them by name.

## Commits

- [Conventional Commits](https://www.conventionalcommits.org/): `type(scope): summary (#ticket)`, scope required, lower case, imperative (`docs(context): add Runtime event (#32)`). Format, PR description and `cz commit` → `CONTRIBUTING.md#commit-messages`. Releases, tags and `CHANGELOG.md` come from python-semantic-release when a release is run by hand; leave them to it.
- `CONTEXT.md` and `docs/` changes go straight to `main`; research and prototypes on their own branch. During planning this is deliberate even though `main` now has required checks: the maintainer's account bypasses them, and the user chose to keep direct pushes for docs (2026-11-10). Code changes go through pull requests.
- Several sessions share this checkout: commit only the files you changed, and leave the branch, stash and working tree as you found them.
- **Pull before you push** (`git pull --rebase`): the release bot commits to `main` when a release is run by hand.
- The local `commit-msg` hook is **not installed** in this shared checkout, because it would reject other sessions' commits mid-flight; a CI check lints commit messages on every push to `main` instead.
- `CLAUDE.md` is a one-line `@AGENTS.md` import, not a symlink: imports are the documented Claude Code way and symlinks break on Windows checkouts. Edit `AGENTS.md` only.

## Build phase (once the spec is assembled)

Python, one `src/rca_agent` package, `uv`, FastAPI, Pydantic AI per stage. Setup, test and lint commands will be listed here when the first code lands; the `[project]` table then joins the release config in `pyproject.toml`.

Before finishing any change: `pre-commit run --all-files`.
