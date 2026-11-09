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

The scope is required. A breaking change adds `!` after the scope (`feat(api)!: …`) or a `BREAKING CHANGE:` footer. Name the ticket at the end of the summary: `docs(context): add Runtime event (#32)`, or `(chiyanram/skills#276)` for another repo. Only Dependabot (scope `deps`) and the release commit name no ticket. chiyanram/skills and chiyanram/agent-factory use the same rule (#48).

Install the commit-message check once per personal clone (not in a checkout shared by several agent sessions: there the CI check on push does this job):

```bash
pipx install pre-commit && pre-commit install --hook-type pre-commit --hook-type commit-msg
```

Pull-request titles follow the same format; a check enforces it, because squash merges use the title as the commit. The CI check on push to `main` enforces it for direct commits.

## Releases

Releases are manual during the dev phase (#48). A push to `main` does not release. To release, open **Actions → Release → Run workflow** on `main`, or run `gh workflow run release.yml --ref main`. [python-semantic-release](https://python-semantic-release.readthedocs.io/) then reads the commits since the last tag, picks the next version (`v0.x.y` while in planning), updates [`CHANGELOG.md`](CHANGELOG.md), tags and creates a GitHub release. The notes group changes under ⚠️ Breaking changes, ✨ Features, 🐛 Fixes, ⚡ Performance and ⏪ Reverts, the same sections as chiyanram/skills and chiyanram/agent-factory; other types ship nothing and are not listed. The templates are in `templates/`: the python-semantic-release defaults, with only `.components/changes.md.j2` changed.

While the repo is in planning, almost every commit is `docs:`, so the version stays at `v0.1.x`. The PR-title check and `CODEOWNERS` only take effect once `main` is protected and changes go through pull requests; until then the commit-lint CI check on push is the gate.

## Agent instruction files

`AGENTS.md` follows the shape common to well-rated open-source repos: overview → where things are → commands → style → testing → commits → boundaries → pointers. It is kept under ~200 lines (the surveyed median was about 175) and points to `CONTRIBUTING.md`, `CONTEXT.md` and `docs/` rather than copying them. `CLAUDE.md` only imports it.

## Security

See [`SECURITY.md`](SECURITY.md).
