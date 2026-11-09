# rca-agent

[![Release](https://github.com/chiyanram/rca-agent/actions/workflows/release.yml/badge.svg)](https://github.com/chiyanram/rca-agent/actions/workflows/release.yml)
[![Latest release](https://img.shields.io/github/v/release/chiyanram/rca-agent?sort=semver)](https://github.com/chiyanram/rca-agent/releases)
[![Conventional Commits](https://img.shields.io/badge/Conventional%20Commits-1.0.0-yellow.svg)](https://www.conventionalcommits.org/)

An AI agent that finds the root cause of production incidents in Java services on Azure, and proposes a fix that a human approves.

> **Status: planning.** The repository holds the glossary, decisions and research for a build-ready spec. There is no application code yet. Progress lives on the [planning map](https://github.com/chiyanram/rca-agent/issues/1).

## What it does

An Operator picks an alert (or pastes one), and the agent runs an **Investigation**:

```mermaid
flowchart LR
    A[Alert<br/>Grafana · Dynatrace · ELK] --> B[Evidence<br/>logs · metrics · traces<br/>runtime events]
    B --> C[Changes<br/>commits · deployments]
    C --> D[Code<br/>across GitHub / GitLab repos]
    D --> E[RCA report]
    E --> G1{{RCA gate<br/>human decides}}
    G1 -->|fix| F[Fix proposal<br/>checked & compiled]
    F --> G2{{Fix gate<br/>human decides}}
    G2 --> P[Draft pull request]
    G1 -->|no fix| R[Recovery · Notify · Manual steps]
```

- **Every Investigation ends in an RCA report** with cited evidence: queries with links, code at the deployed commit.
- **Humans decide** at two mandatory gates. The agent never merges, deploys, restarts or rolls back; those stay Manual steps.
- **Backend-neutral**: per-signal Observability adapter (Grafana, Dynatrace, ELK), GitHub or GitLab, Gradle or Maven.
- **Provider-neutral**: runs on any capable model provider; nothing hard-depends on one AI vendor.
- **Graded, not guessed**: a Test bed of seeded faults with hidden answer keys measures every Agent version.

Target services: Java (Spring or Micronaut, Gradle or Maven) on Azure, including Azure Functions, built with GitHub Actions or GitLab CI.

## Design principles

- [12-factor agents](https://github.com/humanlayer/12-factor-agents): own the prompts, context and control flow; small focused agents; pause and resume.
- [AG-UI](https://docs.ag-ui.com/introduction) as the human-in-the-loop surface.
- An append-only event log is the source of truth and the audit trail.

## Planned stack

Python · Pydantic AI (one small agent per stage) · FastAPI · Postgres · AG-UI frontend · Docker Compose test bed.

## Repository layout

| Path | What |
|---|---|
| [`CONTEXT.md`](CONTEXT.md) | Glossary: one term, one meaning |
| [`AGENTS.md`](AGENTS.md) | Instructions for AI coding agents (`CLAUDE.md` imports it) |
| [`docs/agents/`](docs/agents/) | Issue-tracker workflow, triage labels, domain-doc rules |
| `docs/adr/` | Architecture decision records (created with the first one) |
| `research/*` branches | Research findings, one branch per ticket |
| `prototype/*` branches | Throwaway prototypes |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). In short: pick a ticket from the map, use the glossary's terms, write [Conventional Commits](https://www.conventionalcommits.org/). Releases and the [changelog](CHANGELOG.md) are generated from those commits.

Security issues: see [SECURITY.md](SECURITY.md).

## License

Proprietary. All rights reserved. See [LICENSE](LICENSE).
