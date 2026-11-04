# rca-agent

Root-cause-analysis agent for Java services on Azure: reads alerts/logs (Grafana first), understands code across multiple GitHub repos, writes an RCA report, and — after human approval — opens a fix PR. Frontend over [AG-UI](https://docs.ag-ui.com/introduction); design follows [12-factor agents](https://github.com/humanlayer/12-factor-agents).

Currently in **planning**: see the issue labelled `wayfinder:map`. Vocabulary in [CONTEXT.md](CONTEXT.md).
