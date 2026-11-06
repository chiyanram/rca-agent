# CONTEXT

Glossary for the RCA agent. One term, one meaning.

## Terms

- **Incident** — a triggering alert plus the context attached to it (service, time window, labels). The unit of work that starts an Investigation. Always opened by an Operator, who picks the alert; an alert never starts an Investigation on its own. A repeat of the same alert while its Investigation is open updates that Investigation instead of starting another.
- **Operator** — a signed-in person who starts Investigations and makes Gate decisions. The agent acts with its own identity but only on behalf of an Operator, and never does what that Operator is not allowed to do.
- **Investigation** — one run of the agent on one Incident: gathering evidence, forming hypotheses, and producing an RCA report. Ends with an RCA report unless a human cancels or abandons it.
- **Stage** — one step of an Investigation with a single job (Pre-fetch, Evidence, Change, Code-locator, RCA writer, Fix proposer, Open draft PR). Stages run in a fixed order set by the pipeline, never chosen by the agent. A stage that runs out of budget hands on an incomplete result with its gaps named, rather than failing the Investigation.
- **Pre-fetch** — the first Stage: it gathers the evidence almost every Investigation needs (alert details, error log patterns, key metrics, recent changes) without asking the model.
- **Finding** — a claim made during an Investigation together with its citations: an observability query with its time range and link, or a code location at a specific commit. Stages hand Findings forward; the RCA report may only rest on Findings already recorded.
- **RCA report** — the output every Investigation must produce: root-cause hypothesis, supporting evidence, and suspect code locations across repos.
- **Fix proposal** — an optional patch plus draft pull request that follows an approved RCA report. Never produced without passing a HITL gate.
- **HITL gate** — a mandatory point in an Investigation where the agent stops and a human decides before work continues. There are two: the **RCA gate** (after the RCA report) and the **Fix gate** (after the Fix proposal, before the draft PR). A gate never approves itself; it waits.
- **Gate decision** — what a human chooses at a HITL gate (e.g. approve, revise with feedback, reject, abandon), recorded with who and when.
- **Human question** — a question the agent asks a human on its own initiative. It pauses the Investigation like a HITL gate but is optional, not mandatory.
- **Action** — anything done during an Investigation, by the agent or by a human: a query, a code read, a question, a command, opening a pull request. Every Action is recorded in the Investigation.
- **Action policy** — the rule that gives every Action a risk class (read, sensitive-read, write, critical) and decides whether it runs straight away or only after human approval. Write Actions need approval; critical Actions need approval and are not available yet.
- **Target service** — a system the agent investigates (Java/Gradle, Spring or Micronaut, deployed on Azure, built by GitHub Actions). Each lives in its own GitHub repo.
- **Service registry** — the Operator-maintained list that says, for each Target service or shared library, which repo holds its code, which packages and client names belong to it, and any notes the Operator wants the agent to know. Kept in setup; the agent reads code only from repos it lists.
- **Deployed commit** — the commit actually running for a service in an environment at a given time. Code locations in Findings point at it; when it cannot be determined, the location says so.
- **Seeded fault** — a deliberately injectable defect in a Target service of the test bed, used to give Investigations a known, repeatable root cause.
- **Test bed** — the local environment of sample Target services and observability stack used to exercise and grade the agent.
- **Observability adapter** — the boundary through which the agent reads alerts, logs, metrics, and traces from one backend (Grafana stack first; Dynatrace, Azure App Insights later).
