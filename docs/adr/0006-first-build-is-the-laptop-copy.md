# The first build is the laptop copy

The first release (v1) is the Personal copy: anyone runs it on their own laptop with their own logins, sets up their own plugins from defaults, and every write waits for their approval. A shared team deployment (v2) is built only if the team and management agree after a v1 demo. The design had spent most of its effort on the shared deployment, while the real first use is one person investigating real production issues on a laptop. Three of that person's must-haves were switched off or deferred there: runbooks, recovery and telling the team.

So v1:
- opens draft PRs and creates the Confluence RCA page after approval;
- reads picked runbook pages through the person's own Atlassian MCP login;
- **prepares** recovery commands and email drafts for the person to run and send, never running or sending them itself.

v1 keeps the gates, the Action policy, the never-list, redaction, spend caps and a local event log. The shared deployment's machinery moves to v2:
- KMS, signed audit and shredding;
- roles and SSO;
- the GitLab broker;
- Attack runs;
- Recovery workflows the agent runs itself;
- sent Notifications.

The price: v1 can't show that the agent itself runs recovery, and some v2 parts will be designed again once a hosting platform is known.

Decided in [First build: laptop copy for my work estate](https://github.com/chiyanram/rca-agent/issues/58); the scope of each release is in [`docs/releases.md`](../releases.md).
