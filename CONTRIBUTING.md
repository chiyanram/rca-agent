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

One format in chiyanram/skills, chiyanram/agent-factory and chiyanram/rca-agent (#51). It has the commitizen
sections:

```
type(scope): lower-case summary (#issue)

Why the change is needed, in 1–3 sentences.

BREAKING CHANGE: what breaks and what to do instead
Refs #12
```

- **Title**: a type, a required lower-case scope, an imperative lower-case summary with no full stop, and the issue as
  `(#N)` or `(owner/repo#N)`, such as `docs(context): add Runtime event (#32)`. Add `!` after the scope for a breaking change. Only Dependabot
  (scope `deps`) and the release commit name no issue.
- **Body**: why, not what; the diff shows what. Optional footers: `BREAKING CHANGE:`, `Closes #N` to close the issue on
  merge, and `Refs #N` for other issues.
- **No tool or co-author lines**: no `Co-Authored-By`, no "Generated with" line.

Pull requests are squash-merged. The commit on `main` is the **PR title** (GitHub adds `(#pr)`) and the **PR
description** as its body, so write the description as the commit body. The branch commits are dropped, so they can be
anything. CI checks the PR title. Commits pushed straight to `main` (glossary and docs) follow the same format, and a CI check
on push to `main` enforces it.

To get the prompts, install [commitizen](https://commitizen-tools.github.io/commitizen/) once (`pipx install
commitizen`) and run `cz commit`. `.cz.toml` holds the prompts; it is the same file in all three repos. commitizen only
writes the message: semantic-release still cuts the releases.

| Type | Use for | Release effect |
|---|---|---|
| `feat` | new capability | minor |
| `fix` | bug fix | patch |
| `docs` | glossary, docs, decisions | none |
| `refactor`, `perf`, `test` | code changes without new behaviour | none (`perf`: patch) |
| `build`, `ci`, `chore` | tooling, workflows, housekeeping | none |

Install the commit-message check once per personal clone (not in a checkout shared by several agent sessions: there the CI check on push does this job):

```bash
pipx install pre-commit && pre-commit install --hook-type pre-commit --hook-type commit-msg
```

## Releases

Releases are manual during the dev phase (#48). A push to `main` does not release. To release, open **Actions → Release → Run workflow** on `main`, or run `gh workflow run release.yml --ref main`. [python-semantic-release](https://python-semantic-release.readthedocs.io/) then reads the commits since the last tag, picks the next version (`v0.x.y` while in planning), updates [`CHANGELOG.md`](CHANGELOG.md), tags and creates a GitHub release. The notes group changes under ⚠️ Breaking changes, ✨ Features, 🐛 Fixes, ⚡ Performance and ⏪ Reverts, the same sections as chiyanram/skills and chiyanram/agent-factory; other types ship nothing and are not listed. The templates are in `templates/`: the python-semantic-release defaults, with only `.components/changes.md.j2` changed.

While the repo is in planning, almost every commit is `docs:`, so the version stays at `v0.1.x`. The PR-title check and `CODEOWNERS` only take effect once `main` is protected and changes go through pull requests; until then the commit-lint CI check on push is the gate.

## Agent instruction files

`AGENTS.md` follows the shape common to well-rated open-source repos: overview → where things are → commands → style → testing → commits → boundaries → pointers. It is kept under ~200 lines (the surveyed median was about 175) and points to `CONTRIBUTING.md`, `CONTEXT.md` and `docs/` rather than copying them. `CLAUDE.md` only imports it.

## Security

See [`SECURITY.md`](SECURITY.md).
