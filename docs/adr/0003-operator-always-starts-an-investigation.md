# An Operator always starts an Investigation; alerts never do

No alert, webhook or schedule starts an Investigation on its own: a signed-in Operator picks the alert from a list or pastes it. 12-factor agents suggests triggering from anywhere, and an earlier decision had an Alertmanager webhook start runs; we reversed that because the agent acts only on behalf of an Operator (every Action is authorized against that person, and access to the service's repos is checked when they start), which an alert-started run cannot satisfy; it also removes the inbound webhook and its secret from the attack surface. Alert-triggered Investigations are out of scope for this effort. A repeat of the same alert updates the open Investigation instead of starting another.

Decided in [Security and trust boundaries: credentials, data sent to the LLM, prompt injection from logs](https://github.com/chiyanram/rca-agent/issues/14) (superseding the webhook start in [How is Investigation state held, paused and resumed?](https://github.com/chiyanram/rca-agent/issues/10)); pasting refined in [How does an Operator start an Investigation from a pasted alert email or message?](https://github.com/chiyanram/rca-agent/issues/31).

## v1 note

**v1 (laptop copy):** the one local user holds every role, so they are the Operator; there is no sign-in. They pick a live alert or Dynatrace problem, or paste alert text, an email or an id ([`docs/releases.md`](../releases.md), [ADR-0006](0006-first-build-is-the-laptop-copy.md)).
