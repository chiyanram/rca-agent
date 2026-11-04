# CONTEXT

Glossary for the RCA agent. One term, one meaning.

## Terms

- **Incident** — a triggering alert plus the context attached to it (service, time window, labels). The unit of work that starts an Investigation.
- **Investigation** — one run of the agent on one Incident: gathering evidence, forming hypotheses, and producing an RCA report.
- **RCA report** — the output every Investigation must produce: root-cause hypothesis, supporting evidence, and suspect code locations across repos.
- **Fix proposal** — an optional patch plus draft pull request that follows an approved RCA report. Never produced without passing a HITL gate.
- **HITL gate** — a point in an Investigation where the agent stops and a human approves, rejects, or edits before work continues.
- **Target service** — a system the agent investigates (Java/Gradle, Spring or Micronaut, deployed on Azure, built by GitHub Actions). Each lives in its own GitHub repo.
- **Seeded fault** — a deliberately injectable defect in a Target service of the test bed, used to give Investigations a known, repeatable root cause.
- **Test bed** — the local environment of sample Target services and observability stack used to exercise and grade the agent.
- **Observability adapter** — the boundary through which the agent reads alerts, logs, metrics, and traces from one backend (Grafana stack first; Dynatrace, Azure App Insights later).
