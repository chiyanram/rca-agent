# CONTEXT

Glossary for the RCA agent. One term, one meaning.

## Terms

- **Incident** — a triggering alert plus the context attached to it (service, time window, labels). The unit of work that starts an Investigation.
- **Investigation** — one run of the agent on one Incident: gathering evidence, forming hypotheses, and producing an RCA report. Ends with an RCA report unless a human cancels or abandons it.
- **RCA report** — the output every Investigation must produce: root-cause hypothesis, supporting evidence, and suspect code locations across repos.
- **Fix proposal** — an optional patch plus draft pull request that follows an approved RCA report. Never produced without passing a HITL gate.
- **HITL gate** — a mandatory point in an Investigation where the agent stops and a human decides before work continues. There are two: the **RCA gate** (after the RCA report) and the **Fix gate** (after the Fix proposal, before the draft PR). A gate never approves itself; it waits.
- **Gate decision** — what a human chooses at a HITL gate (e.g. approve, revise with feedback, reject, abandon), recorded with who and when.
- **Human question** — a question the agent asks a human on its own initiative. It pauses the Investigation like a HITL gate but is optional, not mandatory.
- **Action** — anything done during an Investigation, by the agent or by a human: a query, a code read, a question, a command, opening a pull request. Every Action is recorded in the Investigation.
- **Action policy** — the rule that gives every Action a risk class (read, sensitive-read, write, critical) and decides whether it runs straight away or only after human approval. Write Actions need approval; critical Actions need approval and are not available yet.
- **Target service** — a system the agent investigates (Java/Gradle, Spring or Micronaut, deployed on Azure, built by GitHub Actions). Each lives in its own GitHub repo.
- **Seeded fault** — a deliberately injectable defect in a Target service of the test bed, used to give Investigations a known, repeatable root cause.
- **Test bed** — the local environment of sample Target services and observability stack used to exercise and grade the agent.
- **Observability adapter** — the boundary through which the agent reads alerts, logs, metrics, and traces from one backend (Grafana stack first; Dynatrace, Azure App Insights later).
