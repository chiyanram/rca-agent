# Contributing

Thanks for helping. This project is in its **planning phase**: work happens on GitHub issues, and the repository holds the glossary, decisions and research, not application code yet.

## How work is organised

- The **map** is issue #1 (`wayfinder:map`). Each open question is a **ticket**: a sub-issue labelled `wayfinder:research`, `prototype`, `grilling` or `task`.
- Pick an open, unassigned ticket whose blockers are closed, and assign it to yourself before starting.
- Resolve it as described in [`docs/agents/issue-tracker.md`](docs/agents/issue-tracker.md): resolution comment, close, one line in the map's "Decisions so far".
- Use the terms in [`CONTEXT.md`](CONTEXT.md). A new concept gets a term there first.

AI coding agents follow [`AGENTS.md`](AGENTS.md); people may find it a useful summary too.

## Branches

| Work | Where |
|---|---|
| Glossary and docs | straight to `main` |
| Research findings | `research/<slug>` |
| Prototypes | `prototype/<slug>` |
| Code (build phase) | `feat/<slug>`, `fix/<slug>` → pull request |

## Commit messages

[Conventional Commits](https://www.conventionalcommits.org/): `type(scope): summary`, imperative, lower case, no full stop.

| Type | Use for | Release effect |
|---|---|---|
| `feat` | new capability | minor |
| `fix` | bug fix | patch |
| `docs` | glossary, docs, decisions | none |
| `refactor`, `perf`, `test` | code changes without new behaviour | none (`perf`: patch) |
| `build`, `ci`, `chore` | tooling, workflows, housekeeping | none |

A breaking change adds `!` after the type (`feat!: …`) or a `BREAKING CHANGE:` footer. Reference the ticket in the summary or footer: `docs(context): add Runtime event (#32)`.

Install the commit-message check once per clone:

```bash
pipx install pre-commit && pre-commit install --hook-type pre-commit --hook-type commit-msg
```

Pull-request titles follow the same format; a check enforces it, because squash merges use the title as the commit.

## Releases

Every push to `main` runs [python-semantic-release](https://python-semantic-release.readthedocs.io/). It reads the commits since the last tag, picks the next version (`v0.x.y` while in planning), updates [`CHANGELOG.md`](CHANGELOG.md), tags and creates a GitHub release. Nothing to do by hand.

## Security

See [`SECURITY.md`](SECURITY.md).
