# GitHub integration surface for the RCA agent

Ticket: chiyanram/rca-agent#7 · Researched 2026-11-04 · Sources: docs.github.com (fetched 2026-11-04) and `github/github-mcp-server` README/docs at **v2.1.0 (released 2026-11-03)**. REST API versions current at time of writing: `2026-03-10` and `2022-11-28` (the default when `X-GitHub-Api-Version` is omitted; supported until 2028-03-10) [S10].

## Answer in one paragraph

Use a **GitHub App** (one per org that owns Target-service repos), not a PAT. Mint **installation access tokens per Investigation, down-scoped by `repositories` and `permissions`**: a read-only token for evidence gathering, and a separate `contents:write` + `pull_requests:write` token only after the HITL gate approves a Fix proposal. Do **not** grant `workflows` or `administration`, and protect default branches with a ruleset that requires review and doesn't list the App as a bypass actor, so "never auto-merge" holds even if the agent misbehaves. Use REST for nearly everything: Actions runs and logs, deployments, and branch/commit/PR creation are all REST. Webhooks (`deployment_status`, `workflow_run`) are worth subscribing to for enrichment, but they are not delivered reliably. The official GitHub MCP server (v2.1.0) covers code, commits, PRs, Actions and branch/PR creation. It supports GitHub App auth (stdio only), toolset/tool allow-lists and `--exclude-tools`. However, `--read-only` **cannot** be combined with PR creation, and it has **no deployments tools**. So either run it with an explicit `--tools` allow-list (no `--read-only`), or put a thin first-party REST client behind our own tool boundary. The credential is still the real security boundary.

## 1. GitHub App vs fine-grained PAT

| Concern | GitHub App (installation token) | Fine-grained PAT |
|---|---|---|
| Lifetime | Installation token expires after **1 hour** [S3]. The JWT used to mint it lasts **≤10 min** [S4] | Default 30 days, configurable 1–366 days or no expiry, subject to org max-lifetime policy [S5] |
| Multi-repo / multi-org | Installed per org or user. The installer picks repos [S2]. One App can be installed on many orgs (one installation token per org) | **Single resource owner per token**: "Each token is limited to access resources owned by a single user or organization". Cannot "access multiple organizations at once" [S5] |
| Per-call scoping | Token request can narrow to up to **500 `repositories`/`repository_ids`** and a **subset of `permissions`**. It can never exceed the installation's grant [S3] | Fixed at creation |
| Identity on PRs/commits | Acts as `<app-slug>[bot]`, independent of any human: "not dependent on a user", survives the installer leaving the org, and doesn't consume a seat [S2]. Commits created via the REST Git/Contents API with the installation token (no custom author/committer) are **signed and shown as Verified** [S11] | Acts **as the human owner**, with that person's access [S5]. Automation breaks if the user loses access [S2] |
| Checks API | Supported (`checks:read`) [S6] | **Not supported**: fine-grained PATs cannot "Call the Checks API" (listed limitation) [S5] |
| Org governance | Org owner approves the installation and its permission set | Org can require approval. The token reads only public resources until approved [S5] |
| Webhooks | Built-in centralized App webhook across all installed repos [S2] | None. You'd configure per-repo/org webhooks separately |
| Rate limit | See section 4. Scales with repos/users, and 15k/h on Enterprise Cloud [S1] | 5,000/h shared with everything else that user does [S1] |
| GitHub's own guidance | Recommended for long-lived integrations | "API testing or short-lived scripts" [S2] |

**Verdict:** a GitHub App, for these reasons: bot identity on fix PRs, short-lived down-scopable tokens (fits 12-factor "own your context" and the security ticket #14), multi-org support, Checks API access, and centralized webhooks. A fine-grained PAT is acceptable **only for the local Test bed** while bootstrapping, scoped to one test org.

Operational notes:
- The App's **private key** can mint tokens for everything the installation grants. Keep it in a secret store (Azure Key Vault), never in the repo [S9].
- Set the JWT `iat` 60 s in the past to tolerate clock drift [S4].
- "Installation" ≈ org. Resolve `installation_id` once per org via `GET /repos/{owner}/{repo}/installation`. Cache tokens for under 1 h.

## 2. Minimum permissions per operation

All rows are repository permissions on the App, taken from the "Permissions required for GitHub Apps" reference [S6]. `Metadata: read` is mandatory for every App and covers `GET /repos/{owner}/{repo}` etc.

| Agent operation | Endpoint(s) | Permission |
|---|---|---|
| Read code / tree | `GET /repos/{o}/{r}/contents/{path}`, `GET /git/trees` | Contents: **read** |
| List commits, get commit, compare two SHAs (for "what changed since the last good deploy") | `GET /commits`, `GET /commits/{ref}`, `GET /compare/{base...head}` | Contents: **read** |
| PRs associated with a suspect commit | `GET /commits/{sha}/pulls` | Pull requests: **read** |
| Read PRs / review comments | `GET /pulls…` | Pull requests: **read** |
| List workflow runs, jobs, download job logs | `GET /actions/runs`, `GET /actions/jobs/{id}/logs` | Actions: **read** |
| List deployments + statuses (which SHA is in which Azure environment) | `GET /deployments`, `GET /deployments/{id}/statuses` | Deployments: **read** |
| Check runs / combined status for a SHA | `GET /commits/{ref}/check-runs`, `GET /commits/{ref}/status` | Checks: **read**, Commit statuses: **read** |
| **(post-HITL)** Create branch | `POST /git/refs` | Contents: **write** |
| **(post-HITL)** Commit patch | `POST /git/blobs`, `/git/trees`, `/git/commits` + `PATCH /git/refs/{ref}` (multi-file, atomic) or `PUT /contents/{path}` (single file) | Contents: **write** |
| **(post-HITL)** Open (draft) PR, request reviewers | `POST /pulls` with `"draft": true`, `POST /pulls/{n}/requested_reviewers` | Pull requests: **write** |

**Do not grant:**
- **Workflows: write.** This is the extra permission needed when a ref/contents write touches `.github/workflows/*` [S6]. Leaving it off means a fix PR physically cannot alter CI/CD.
- **Administration.** Not needed for anything the agent does.
- **Actions: write.** The agent never re-runs or triggers workflows.
- **Deployments: write.**

**Never auto-merge.** `contents:write` is technically enough to push to unprotected branches and to merge. Enforce the rule in three layers:
1. A branch ruleset or protection on the default branch that requires PR + approving review, with the App **not** on the bypass list.
2. Open PRs as **draft**. "Draft pull requests cannot be merged" until marked ready [S12].
3. The agent's tool surface has no merge tool (MCP: `--exclude-tools merge_pull_request`, see section 6).

Draft-PR availability on private repos depends on the GitHub plan. Verify on the target orgs' plans (not confirmed in the fetched docs).

**Two-token pattern.** The App holds the union of the permissions above. Each Investigation mints:
- *investigation token*: `repositories=[repos in scope]`, `permissions={contents:read, pull_requests:read, actions:read, deployments:read, checks:read, statuses:read, metadata:read}`.
- *fix token*, only after the Fix-proposal HITL gate: `repositories=[the one repo]`, `permissions={contents:write, pull_requests:write, metadata:read}`.

This is native to the installation-token API [S3] and gives per-step least privilege plus clear audit.

## 3. REST vs GraphQL

- **Use REST as the default.** Actions (runs, jobs, **logs**), branch creation (`git/refs`), Git database commits, and the contents API are REST surfaces in the GitHub App permissions reference [S6]. Deployments, check runs and commit→PR lookup are all available in REST.
- **GraphQL is optional, for batched reads.** For example, fetching a PR plus its commits, files and reviews in one round trip. It has separate budgets: installations get 5,000 points/h scaling to a max of 12,500, or 10,000 on Enterprise Cloud; connections need `first`/`last` ≤100; a call can request at most 500k nodes; there is a 10 s timeout [S7].
- Pin `X-GitHub-Api-Version` explicitly (`2022-11-28` today, or `2026-03-10` after reviewing its breaking changes) [S10].

## 4. Rate limits (primary + secondary) [S1][S7]

| Credential | REST primary | GraphQL primary |
|---|---|---|
| PAT (classic or fine-grained) | 5,000 req/h per user (shared with the user's other tokens/apps) | 5,000 pts/h |
| App installation token (non-EC) | 5,000/h base, **+50/h per repo over 20 and per org user over 20, max 12,500/h** | same scaling, max 12,500 |
| App installation on GitHub Enterprise Cloud org | **15,000/h** | 10,000 pts/h |
| `GITHUB_TOKEN` (inside Actions) | 1,000/h per repo (15,000 on EC) | — |

Secondary limits apply to all credentials:
- ≤100 concurrent requests (REST+GraphQL combined).
- ≤900 points/min for REST, where GET = 1 point and POST/PATCH/PUT/DELETE = 5.
- ≤2,000 points/min for GraphQL.
- Content creation ~80/min and 500/h.

Implication: one Investigation reads perhaps tens to low hundreds of objects (commits in a window, a few runs plus logs, deployments), so limits are not a concern at RCA volumes. **Job logs are the heavy item.** Fetch only failed jobs, tail them, and cache by run ID. Honour `Retry-After` / `x-ratelimit-reset`.

## 5. Webhooks that could trigger or enrich Investigations [S8]

| Event | App permission | Use for the RCA agent |
|---|---|---|
| `deployment_status` | Deployments: read | **Primary enrichment.** Build a "which SHA went to which environment, when" timeline, the #1 RCA correlator for "alert fired shortly after a deploy". No event fires for `inactive` states. Actions jobs that reference an `environment:` **create deployment objects and statuses automatically** (unless the job sets `deployment: false`) [S13]. So Azure deploys from Actions are visible here with no workflow changes, *provided the deploy job uses `environment:`*. |
| `deployment` | Deployments: read | Deployment created (payload links `workflow_run`) |
| `workflow_run` | Actions: read | Actions `requested`/`in_progress`/`completed`. A failed deploy pipeline can be its own Incident source, or context for one |
| `workflow_job` | Actions: read | Per-job granularity. Usually not needed |
| `push`, `pull_request` (`closed`+merged) | Contents / Pull requests: read | Maintain a recent-changes index per repo (optional) |
| `check_suite`/`check_run` | Checks: read | CI signal per SHA (optional) |

Caveats:
- **GitHub does not automatically retry failed deliveries.** You must list and redeliver through the App webhook deliveries API [S14].
- Payloads over 25 MB are dropped [S8].

Recommendation: webhooks are an **optimization, not a dependency**. At Investigation start, always query `GET /deployments?environment=…` and `GET /actions/runs?created=…` for the alert's time window (pull model, 12-factor stateless). Optionally ingest `deployment_status` into a small timeline cache to make that faster, and in future to auto-open Investigations on failed deploys. Incidents themselves come from the Observability adapter (Alertmanager), not GitHub.

## 6. Official GitHub MCP server (`github/github-mcp-server` v2.1.0, 2026-11-03) [S9]

**Toolsets.** These were listed in the README at v2.1.0:
- Defaults: `context`, `repos`, `issues`, `pull_requests`, `users`.
- Also available: `actions`, `code_quality`, `code_security`, `copilot`, `copilot_issue_intents`, `dependabot`, `discussions`, `gists`, `git`, `governance`, `labels`, `notifications`, `orgs`, `projects`, `secret_protection`, `security_advisories`, `stargazers`.
- The remote server adds `copilot_spaces` and `github_support_docs_search`.

**Relevant tools.**
- `repos`:
  - Reads: `get_file_contents`, `get_repository_tree`, `list_commits`, `get_commit`, `search_code`, `list_branches`, `list_tags`, releases.
  - Writes: `create_branch`, `push_files`, `create_or_update_file`, `delete_file`, `fork_repository`, `create_repository`, `delete_repository`.
- `pull_requests`: `pull_request_read` (incl. `get_commits`), `list_pull_requests`, `create_pull_request`, `update_pull_request`, `update_pull_request_branch`, `merge_pull_request`.
- `actions`: `actions_list` (incl. `list_workflow_runs`, `list_workflow_jobs`), `actions_get` (run, job, usage, logs URL), `get_job_logs` (`failed_only`, `tail_lines`), `actions_run_trigger` (write: run/rerun/cancel).
- **No deployments / deployment-status tools exist** in any toolset at v2.1.0. That remains a gap for our #1 correlator.

**Restriction controls** (composable; local flag / env var, remote HTTP header):
- `--toolsets` / `GITHUB_TOOLSETS`, `--tools` / `GITHUB_TOOLS` (additive allow-list). An unknown name fails startup.
- `--exclude-tools` / `GITHUB_EXCLUDE_TOOLS` / `X-MCP-Exclude-Tools`. Takes precedence over toolsets and tools.
- `--read-only` / `GITHUB_READ_ONLY` / `X-MCP-Readonly`. **Takes precedence over everything**: "write tools are skipped if `--read-only` is set, even if explicitly requested via `--tools`". Therefore **read-only + `create_pull_request` is impossible in one server instance.**
- `--lockdown-mode`: filters public-repo content by authors without push access. It is a prompt-injection *mitigation*, "**not** an authorization boundary". Private repos are unaffected.
- Scope filtering hides tools only for **classic PATs**. With fine-grained PATs and App tokens all configured tools are shown and the API enforces permissions.

**Auth.** PAT, OAuth (interactive), or **GitHub App installation** (`--app-id`, `--app-installation-id`, `--app-private-key-path`; auto-refreshes the token). App auth is **stdio only, not the `http` command**. The server uses one installation, so it cannot per-call down-scope or switch org.

**How to get "read-only plus PR creation":**
- Option A, two MCP instances:
  1. Instance 1: `--read-only --toolsets repos,pull_requests,actions` with the read token.
  2. Instance 2, attached only after the HITL gate: `--tools create_branch,push_files,create_pull_request` (no read-only) with the fix token. Add `--exclude-tools merge_pull_request,delete_file,delete_repository,create_repository,fork_repository,actions_run_trigger` as belt-and-braces.
- Option B, one instance with an explicit allow-list: `--tools get_file_contents,get_repository_tree,list_commits,get_commit,search_code,pull_request_read,list_pull_requests,actions_list,actions_get,get_job_logs,create_branch,push_files,create_pull_request`. Gate the three write tools in the agent loop behind the HITL approval.

**Recommendation.** Do not make the MCP server the integration boundary. Reasons:
1. No deployments tools.
2. It can't use the two-token, per-Investigation down-scoped pattern with App auth (single long-lived installation, stdio only).
3. Tool outputs are generic, and we want compact, RCA-shaped evidence (12-factor: own your tools/context).

Build a small **first-party GitHub adapter** (REST via Octokit/PyGithub or similar) exposing ~10 RCA-shaped tools:
- `recent_deployments(env, window)`
- `diff_between(sha_a, sha_b)`
- `failed_job_log_tail(run)`
- `commits_touching(path, window)`
- `prs_for_commit`
- `read_file@sha`
- `open_draft_fix_pr(...)` (only callable with a fix token)

Optionally keep the MCP server (Option A, instance 1, read-only) for exploratory code reading while prototyping.

## 7. Impacts on other tickets

- **#14 Security & trust boundaries:**
  - Adopt the GitHub App + two-token pattern, with no `workflows`/`administration`/`actions:write`.
  - Add a branch ruleset to the default branch (App not a bypass actor).
  - Keep the App private key in Key Vault.
  - MCP lockdown mode is not a boundary. Job logs and PR/commit text are prompt-injection vectors.
- **#9 HITL gates:** the Fix-proposal gate is where the fix token is minted. Approval = permission escalation.
- **#11 / #5 code reading across repos:** use the contents/trees/compare APIs at a pinned SHA (the deployed SHA from `deployment_status`), or a shallow clone using the installation token (`x-access-token:<token>`). Rate limits favour cloning for large reads.
- **#12 Fix proposal checks:** the fix PR is draft and cannot touch `.github/workflows`. CI on the PR branch runs normally and is readable via `checks:read`.
- **#13 Test bed:** deploy jobs in the sample services must use `environment:` so deployment objects exist. Create a test org + App installation (a fine-grained PAT is OK only for bootstrap).
- **#4 / #8 runtime:** the GitHub adapter is in-process tools, not a dependency on MCP. Both Python and TS have mature REST clients.

## Sources

- [S1] REST rate limits: https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api
- [S2] Deciding when to build a GitHub App: https://docs.github.com/en/apps/creating-github-apps/about-creating-github-apps/deciding-when-to-build-a-github-app
- [S3] Generating an installation access token: https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-an-installation-access-token-for-a-github-app
- [S4] Generating a JWT for a GitHub App: https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-a-json-web-token-jwt-for-a-github-app
- [S5] Managing personal access tokens (fine-grained limitations): https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens
- [S6] Permissions required for GitHub Apps: https://docs.github.com/en/rest/authentication/permissions-required-for-github-apps
- [S7] GraphQL rate and query limits: https://docs.github.com/en/graphql/overview/rate-limits-and-query-limits-for-the-graphql-api
- [S8] Webhook events and payloads: https://docs.github.com/en/webhooks/webhook-events-and-payloads
- [S9] github/github-mcp-server v2.1.0: README, docs/server-configuration.md, docs/github-app-auth.md, docs/scope-filtering.md: https://github.com/github/github-mcp-server
- [S10] REST API versions: https://docs.github.com/en/rest/about-the-rest-api/api-versions
- [S11] About commit signature verification (bot signatures): https://docs.github.com/en/authentication/managing-commit-signature-verification/about-commit-signature-verification
- [S12] About pull requests (drafts): https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/about-pull-requests
- [S13] Control deployments (environment → deployment objects): https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/control-deployments
- [S14] Handling failed webhook deliveries: https://docs.github.com/en/webhooks/using-webhooks/handling-failed-webhook-deliveries
