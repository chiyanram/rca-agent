# Our own pipeline, with one small Pydantic AI agent per Stage

An Investigation runs as a fixed sequence of Stages (Pre-fetch → Evidence → Change → Code-locator → RCA writer → RCA gate → Fix proposer → Fix gate → Open draft PR) that our Python code owns: stage order, gates, the event log, context rendering and tools. Inside each Stage a small Pydantic AI agent runs the inner tool loop with its own step budget. We chose this over a single autonomous agent or a framework-owned graph because 12-factor agents' hardest requirement (factor 8: a durable pause between choosing an Action and running it, surviving restarts) and owning prompts and context (factors 2, 3) are where frameworks push back; keeping the pipeline ours keeps every gate deterministic.

Decided in [Which agent runtime and language do we build on?](https://github.com/chiyanram/rca-agent/issues/8) and [What are the pipeline stages, their contracts, and the project setup?](https://github.com/chiyanram/rca-agent/issues/16).

## Considered options

- **LangGraph**: capable, but its checkpoint state becomes a second source of truth beside our event log.
- **Custom loop only**: purest 12-factor, but re-implements tool calling, validation and AG-UI plumbing Pydantic AI already gives us.
- **Claude Agent SDK as the whole agent**: ties the design to one vendor ([ADR-0005](0005-provider-neutral-models.md)); allowed only as a pluggable engine inside a Stage.
