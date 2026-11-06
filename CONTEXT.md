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
- **Fix proposal** — an optional change that follows an approved RCA report: patches to one or more repos (each opened as its own draft pull request once approved), with a rationale, Check results and Impact reach. It may also say that no safe code fix exists. Never produced without passing a HITL gate. "Pull request" means a GitHub pull request or a GitLab merge request.
- **Fix engine** — the pluggable coder that writes a Fix proposal's patches. It only proposes; it never decides whether its own work is good.
- **Check** — a verification the agent's own code runs on a Fix proposal (it applies, it changed something real, it stays within limits, it compiles, its tests and regression test behave). Only Check results count; what the Fix engine claims about its work never does. Some Checks block approval, the rest inform the human.
- **Impact reach** — what a Fix proposal's change can affect: the changed code, everything that calls it, the entry points behind it and the services that call those. Worked out by the agent's own code, not by the model.
- **Fix review** — a model's critique of a Fix proposal before the Fix gate, in a bounded number of rounds. Advisory only: a review point counts only when it points at real code.
- **HITL gate** — a mandatory point in an Investigation where the agent stops and a human decides before work continues. There are two: the **RCA gate** (after the RCA report) and the **Fix gate** (after the Fix proposal, before the draft PR). A gate never approves itself; it waits.
- **Gate decision** — what a human chooses at a HITL gate (e.g. approve, revise with feedback, reject, abandon), recorded with who and when.
- **Human question** — a question the agent asks a human on its own initiative. It pauses the Investigation like a HITL gate but is optional, not mandatory.
- **Action** — anything done during an Investigation, by the agent or by a human: a query, a code read, a question, a command, opening a pull request. Every Action is recorded in the Investigation.
- **Action policy** — the rule that gives every Action a risk class (read, sensitive-read, write, critical) and decides whether it runs straight away or only after human approval. Write Actions need approval. Critical Actions need their own approval, and the only one the agent carries out is running a Recovery workflow; anything else that touches production is a Manual step.
- **Recovery workflow** — a team's own automated recovery procedure (for example, retrying failed messages) that a person has confirmed, during setup, as one the agent may run for a given service. The agent may run it only after its own approval, and the agent's own code chooses every value it is given. A workflow nobody confirmed can never be run.
- **Manual step** — a recovery or configuration action the agent proposes but a human performs, by whatever means they choose (for example, a rollback, a restart, or changing a setting outside any repo). The agent never claims it happened; the Operator records whether it was done.
- **Notification** — a message the agent sends about an Investigation, only to people or groups confirmed for that service, in the agent's own fixed format, after an Operator approves the exact text.
- **Target service** — a system the agent investigates (Java built with Gradle or Maven, Spring or Micronaut, deployed on Azure, built by GitHub Actions or GitLab CI). Each lives in its own repo on GitHub or GitLab.
- **Service registry** — the Operator-maintained list that says, for each Target service or shared library, which repo holds its code, which packages and client names belong to it, and any notes the Operator wants the agent to know. Kept in setup; the agent reads code only from repos it lists.
- **Deployed commit** — the commit actually running for a service in an environment at a given time. Code locations in Findings point at it; when it cannot be determined, the location says so.
- **Seeded fault** — a deliberately injectable defect in a Target service of the test bed, used to give Investigations a known, repeatable root cause.
- **Test bed** — the local environment of sample Target services and observability stack used to exercise and grade the agent.
- **Observability adapter** — the boundary through which the agent reads alerts, logs, metrics, and traces. Each kind of signal can come from a different backend (for example alerts and traces from Dynatrace, logs from ELK); the agent sees the same shape whichever backend answers.
- **Log digest** — the app's own summary of a log window: raw lines grouped into recurring patterns, each with counts and the code it points to. Built the same way whatever backend holds the logs.
- **Source-control adapter** — the boundary through which the agent reads code, change history and deployments and opens draft pull requests, whichever hosting service holds the repo (GitHub or GitLab).
- **Build adapter** — the boundary through which a Fix proposal is compiled and tested in isolation, whichever build tool the repo uses (Gradle or Maven). It never sees credentials; when private dependencies can't be fetched, it checks what it can and says the build was partial.
