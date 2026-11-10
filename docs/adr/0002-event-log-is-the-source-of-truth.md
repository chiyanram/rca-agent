# The append-only event log is the source of truth and the audit trail

Every Investigation is an append-only Postgres event log (event id, sequence, attempt number, versioned payloads); its status, the AG-UI screen, resume after a crash, replay, Forks for evaluation and the Audit trail are all views of that log. We chose this over separate state tables plus an audit table because 12-factor agents asks to unify execution and business state, and a second copy would drift from the first. The cost: every reader works from a fold of events, and a schema change needs versioned events, not a migration.

Decided in [How is Investigation state held, paused and resumed?](https://github.com/chiyanram/rca-agent/issues/10) and [Audit log: retention, encryption at rest, tamper-evidence and export](https://github.com/chiyanram/rca-agent/issues/19).

## Consequences

- Grants are INSERT/SELECT only; a per-Investigation hash chain makes tampering detectable (v2).
- Bulky payloads are encrypted per Investigation and crypto-shredded 90 days after Close; the who-did-what skeleton stays 2 years (v2).

## v1 note

**v1 (laptop copy):** the same append-only log, held locally in the Personal copy's Postgres. It is a plain history: no hash chain, no app encryption (Guided setup records the person's disk-encryption answer), and a plain delete of a closed Investigation's content after 90 days or on **Delete now**, keeping the who-did-what record. The hash chain, signed checkpoints, KMS encryption and shredding are v2 ([`docs/releases.md`](../releases.md), [ADR-0006](0006-first-build-is-the-laptop-copy.md)).
