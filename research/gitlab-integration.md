# GitLab integration surface for the RCA agent

Researched 2026-11-06 against docs.gitlab.com (GitLab 19.x; the MCP server page cites 19.5 as GA). Covers gitlab.com and Self-Managed/Dedicated. It mirrors the decided GitHub design in `research/github-integration.md` and asks where GitLab maps and where it does not. Claims marked *(inference)* are not stated verbatim in the cited page.

## Answer in one paragraph

GitLab has **no GitHub App equivalent**: nothing like an installation that mints a 1-hour token narrowed per call to chosen repos and permissions. The nearest pattern is a **service account** (Free tier and up, no seat) acting as the minting identity. Per Investigation it calls `POST /projects/:id/access_tokens` to create a **project access token**: a bot user scoped to one project, with a role and scopes. Expiry is a **date only** (midnight UTC), so the agent must **revoke the token explicitly** when it is done. Read token = Reporter + `read_api` + `read_repository`. Write token = Developer + `api`, because `write_repository` "does not support API authentication". GitLab has **no `workflows`-style permission**: a Developer can change `.gitlab-ci.yml` on its own branch, and the MR pipeline runs as the bot. Contain that with protected CI variables, protected branches ("Allowed to merge: Maintainers", push: No one), and optionally an external CI config project or an Ultimate pipeline execution policy. Drafts are set by a **`Draft:` title prefix** (the create-MR call has no `draft` parameter), and drafts cannot merge. Read APIs map well, and deployed-SHA-at-time is *easier* than on GitHub. Code search beyond a single project needs Premium/Ultimate advanced search. The official GitLab MCP server (GA 19.5, Free) **rejects legacy project/group tokens**, so it cannot carry our down-scoped tokens. Keep a thin first-party REST adapter.

## 1. Identity and tokens

| Option | What it is | Fit for the agent |
|---|---|---|
| **Project access token** (PrAT) | Creates a bot user `project_{id}_bot_{rand}`, a member of **one project** with a chosen role (10 Guest to 50 Owner) and scopes. "Cannot access resources in other projects" [S1][S2]. On gitlab.com it needs **Premium/Ultimate**; on Self-Managed/Dedicated it works with any licence [S1] | **Closest to an installation token.** It can be minted per Investigation, per repo, per role |
| **Group access token** | Same idea, but the bot inherits into every project of the group [S3]. Premium/Ultimate on gitlab.com | Too broad for per-repo down-scoping |
| **Service account** | A non-human user (instance, group or project level). Free tier: 100 per top-level group or instance. Premium/Ultimate: unlimited. Uses no seat. Authenticates with a PAT; can be a member with a different role in each group or project [S4][S5] | **Minting identity**, and the fallback identity on gitlab.com Free (see §1.2) |
| **Fine-grained PAT** | GA in **19.2** (beta 18.10). Granular permissions (CRUD per resource) and `selected_memberships` per project or group, e.g. `{"permissions":["read_job"],"project_id":6}` [S6][S7]. Every request also needs the owner's own role to allow it [S6] | Promising for read tokens on gitlab.com Free. *Unverified:* whether service accounts can hold fine-grained PATs. Enforcement "does not apply to tokens for service accounts" [S6] |
| **OAuth application** | Authorization code (+PKCE) and device grant. **No client-credentials flow** [S8]. Access token 2 h, plus refresh token [S9]. Acts as the authorising user *(inference)* | Fits "act on behalf of the Operator" for reads. Wrong identity for the bot MR |
| **CI job token** | Valid "only while the job is running". Limited REST endpoints, no GraphQL [S10] | Not usable by an external agent |
| **OIDC / workload identity** | GitLab is an OIDC **issuer** for CI `id_tokens` to clouds [S11]. Accepting **external** OIDC tokens for GitLab's own API is not documented | **No equivalent** to "federate our runtime identity into GitLab". The minting credential stays a stored secret |

**Scopes** [S12]:
- `read_api`: "read access to the API for the token's scope".
- `read_repository`: pull over Git.
- `write_repository`: pull and push over Git only, "Does not support API authentication".
- `api`: "complete read and write access to the API for the token's scope".
- `self_rotate`: rotate this token only (17.9+).

The effective power of a token is **role × scope**. Scopes don't narrow by resource type: `api` on a Developer token can do anything a Developer can.

**Expiry granularity.** `expires_at` is `YYYY-MM-DD`. Tokens expire at midnight UTC on that date. The default and maximum is 365 days (400 days behind a flag, admin-configurable from 17.6) [S1][S2]. No minimum is documented. The shortest practical lifetime is therefore until the next midnight UTC (up to ~48 h) *(inference)*. **Revoke** (`DELETE /projects/:id/access_tokens/:token_id`) at Investigation end, on cancel, and from a sweeper for orphans [S2]. When the last token of a bot expires or is revoked, the bot user is deleted after 30 days by default [S1].

### 1.1 Minting: the blocker to a faithful two-token pattern

- `POST /projects/:id/access_tokens` must be called **with a personal access token**: "You cannot authenticate with a project access token". The new token cannot exceed the caller's access level [S2].
- UI creation requires the caller to be **Maintainer or Owner** of the project [S1].
- So the minting service account is a **Maintainer on every Target-service project** with a long-lived `api` PAT (≤365 d, rotatable via `self_rotate`).
- A Maintainer can edit protected-branch settings, so the minting credential could disable the "never auto-merge" guard [S13][S14] *(inference: managing protected branches is a Maintainer action)*. A GitHub App private key can never exceed the App's declared permissions, which exclude `administration`.
- Mitigations:
  1. Hold the minting PAT only in a separate token-broker process, never in the agent runtime.
  2. Enforce branch protection at **group level** or via instance admin settings where possible.
  3. Audit and alert on protected-branch changes.
  4. On Premium/Ultimate, use **"Prevent editing approval rules"** (admin) for approval rules [S15].

### 1.2 Recommended token shapes

| Token | Shape | Notes |
|---|---|---|
| Read (per Investigation, per repo) | PrAT, role **Reporter** (20), scopes `read_api`, `read_repository`, expires tomorrow, revoked at end | Reporter can read environments and deployments. Guest can't on private projects [S13]. Pipelines and job logs are readable from Guest [S13]. Reporter "cannot push code" |
| Write (after Fix gate, one repo) | PrAT, role **Developer** (30), scope `api` (needed for branch, commit and MR via API) | Developer can create branches, push to non-protected branches, and open MRs [S13] |
| gitlab.com **Free** fallback | PrATs are unavailable. Use two **project-level service accounts** (Reporter, Developer) per repo, with PATs from `POST /projects/:id/service_accounts/:user_id/personal_access_tokens`, short `expires_at`, rotate or revoke per Investigation [S5] | Project service accounts need Maintainer/Owner to manage [S5] |

**Can the write token create a branch + MR without touching protected branches or CI?**
- **Protected branches: yes.** Set the default branch to "Allowed to push and merge: **No one**" and "Allowed to merge: **Maintainers**". Both are available on Free; adding named users or groups is Premium [S14]. Default branches are protected by default [S14].
- **CI config: no native control.** There is no `workflows` permission, and the permissions table has no CI-file row [S13]. A Developer can push a modified `.gitlab-ci.yml` to its fix branch, and that branch's pipeline runs as the bot *(inference)*. Mitigations:
  - Mark secrets **Protected**: "only available in pipelines that run on protected branches or protected tags" [S16].
  - **External CI config path** (`.gitlab-ci.yml@group/ci-project`), so editing the project's own file changes nothing [S17].
  - **Pipeline execution policy** with `override_project_ci` (**Ultimate**) [S18].
  - **CODEOWNERS** rule on `.gitlab-ci.yml` with required code-owner approval (**Premium**) [S19]. This gates the merge, not the pipeline run.
  - Push rule "prohibited file names" (**Premium**). It applies only to *new* files, so it does not block edits to an existing CI file [S20].
  - Agent-side: the Fix proposer refuses diffs touching `.gitlab-ci.yml` or `ci/` include files.

## 2. Draft MRs and "never auto-merge"

- `POST /projects/:id/merge_requests` requires `source_branch`, `target_branch` and `title`. **There is no `draft` parameter** [S21]. Mark the MR draft with a title prefix `Draft:` (also `[Draft]`, `(Draft)`) or the `/draft` quick action. "Merge requests marked as **Draft** cannot merge until you remove the **Draft** flag". Available on Free [S22].
- Commit the patch atomically: `POST /projects/:id/repository/commits` with `branch` + `start_branch` + `actions[]` (create/update/delete/move/chmod) [S23]. This creates the branch in the same call.
- Stop the bot from merging:
  - Protected branch "Allowed to merge: Maintainers" (Free) with the bot as Developer [S14].
  - Required approvals via approval rules (**Premium/Ultimate**) [S15]. Authors don't count as approvers by default [S15].
  - The adapter exposes no `merge`/`accept` op, and never passes `auto_merge` / `merge_when_pipeline_succeeds` [S21].
- Tier summary: Free gives drafts plus "Maintainers only" merge, which is enough for never-auto-merge. Premium adds required approvals, code owners and push rules.

## 3. Read API equivalents (REST v4)

| Need | GitLab endpoint | Notes |
|---|---|---|
| Commits in window | `GET /projects/:id/repository/commits?ref_name&since&until&path` [S23] | No `x-total` headers |
| Single commit / diff | `GET …/repository/commits/:sha`, `…/:sha/diff` [S23] | |
| Commit to MR | `GET …/repository/commits/:sha/merge_requests` [S23] | Same as GitHub `commits/{sha}/pulls` |
| Commit statuses | `GET …/repository/commits/:sha/statuses` [S23] | No separate "checks" concept |
| Compare | `GET /projects/:id/repository/compare?from&to&straight` [S24] | `compare_timeout`, `collapsed`/`too_large` flag truncated diffs |
| MR, commits, diffs | `GET …/merge_requests/:iid`, `…/commits`, `…/diffs` (`/changes` deprecated) [S21] | `diff_refs` gives base/head SHAs |
| Pipelines | `GET /projects/:id/pipelines?ref&sha&status&updated_after` [S25] | |
| Jobs / job log | `GET …/pipelines/:pid/jobs`, `GET …/jobs/:job_id/trace` [S26] | No range or size option on trace. Fetch failed jobs only and tail client-side |
| Environments | `GET /projects/:id/environments/:env_id` returns `last_deployment.sha` [S27] | |
| Deployed SHA at time T | `GET /projects/:id/deployments?environment=E&status=success&order_by=finished_at&sort=desc&finished_before=T`, first item [S28] | `finished_*` filters require `order_by=finished_at` or `status=success`. The response includes `sha`, `ref` and the deploying job and pipeline. Only exists if deploy jobs declare `environment:` *(inference, as on GitHub)* |
| File read | `GET …/repository/files/:path?ref`, `/raw`, `/blame` [S29] | Blame limited to 400/min per user and project |
| Tree / archive | `GET …/repository/tree?recursive`, `…/archive?sha&path` (5/min on gitlab.com) [S24] | |
| Code search | `GET /projects/:id/search?scope=blobs&search=…&ref=` [S30] | Global and **group** `blobs` need **Premium/Ultimate + advanced or exact code search** [S30]. The project-level page states no tier *(likely basic search on Free, unverified)*. Supports `path:` and `extension:` filters. 100/min on gitlab.com [S31] |
| Partial clone | `git clone --filter=blob:none` (Git ≥ 2.22) over HTTPS with the PrAT as password and any non-blank username [S32][S1] | Same mirror design as GitHub |

## 4. Operator authorisation

- `GET /projects/:id/members/all/:user_id` returns the member **including inherited and invited-group memberships**. When a user has several memberships, "only their membership with the highest `access_level` is returned", which "represents the effective permission of the user" [S33].
- Roles: 10 Guest, 15 Planner, 20 Reporter, 25 Security Manager, 30 Developer, 40 Maintainer, 50 Owner [S33][S34].
- Rules:
  - At start: the Operator needs ≥ Reporter, or ≥ Guest on public projects.
  - At the Fix gate: the approver needs ≥ Developer, the role that can push branches and create MRs [S13].
- Gaps: the endpoint does not reflect instance admins, and visibility of invited private groups depends on the caller [S33]. The caller (the read token) needs ≥ Reporter to see members *(inference)*. The nearest GitHub equivalent is `GET /collaborators/{user}/permission`.

## 5. Issues and work items (read linked, post a note)

- REST is still current for issues:
  - `GET /projects/:id/issues/:iid`, `…/closed_by`, `…/related_merge_requests` [S35].
  - Post a note: `POST /projects/:id/issues/:iid/notes` or `…/merge_requests/:iid/notes` (`body`, optional `internal`) [S36].
  - Notes are Guest+ [S13]. Note creation is limited to 60/min on gitlab.com [S31].
- **Epics are Premium/Ultimate** [S37]. The Epics REST API is deprecated (17.0) and slated for removal in API v5. Use the **work items GraphQL API** (`namespace(fullPath){ workItem(iid) }`, `workItemUpdate`) from 18.1 [S36][S38].
- For the agent: read the issues linked to a suspect MR via REST, and treat epics as optional context behind a tier check.

## 6. Rate limits

**gitlab.com, currently in effect** [S31]:
- Authenticated API: **2,000/min per user**.
- Git HTTPS: 10,000/min per user.
- All traffic: 2,000/min per IP.
- Search API: 100/min.
- Raw endpoint: 300/min per project, commit or path.
- Repository files API: 500/min per IP and path.
- Notes: 60/min.
- Project member list: 200/min.
- Headers: `RateLimit-Limit`, `RateLimit-Remaining`, `RateLimit-ResetTime`, `Retry-After`, and a 429 when exceeded.

**gitlab.com, proposed per-plan limits** ("not in effect yet", planned Jan 2027) [S31]:
- Per user: Free 5,000/h (100/min burst), Premium 15,000/h, Ultimate 25,000/h.
- Per top-level group: Free 400/min burst.
- The Free burst of 100/min is the one to design for: one Investigation should stay well under it, so batch and cache.

**Self-Managed** [S39]:
- Authenticated and unauthenticated API limits are **disabled by default**.
- When enabled, the defaults are 7,200/h per user and 3,600/h per IP.
- Endpoint-specific limits such as blame (400/min) still apply [S29].

Since every PrAT is its own bot user, per-user limits apply **per token** *(inference)*, which is generous for RCA volumes.

## 7. GitLab MCP server (official, built in)

- Status: **GA in 19.5**, on Free/Premium/Ultimate since 19.2. Served over HTTP at `/api/v4/mcp`, or stdio via `mcp-remote` [S40].
- **Auth: OAuth (`mcp` scope) or fine-grained PAT with MCP Execute permission only. Legacy personal, project and group tokens are rejected with 403** [S40].
- Toolsets: `meta`, `core`, `merge_requests`, `work_items`, `repository`, `ci`, `duo_agent_platform` (default); `wikis`, `code_security`, `orbit` (opt-in) [S40].
- Restriction: the `X-Gitlab-Enabled-Mcp-Server-Toolsets` and `X-Gitlab-Enabled-Mcp-Server-Tools` headers act as an allow-list. There is **no read-only flag**. "Listing a tool doesn't grant access", and the API still enforces permissions [S40].
- Tools [S41]:
  - Reads: `list_commits`, `get_commit`, `get_repository_file`, `list_repository_tree`, `get_merge_request(_diffs/_commits)`, `list_pipelines`, `get_pipeline`, `get_job` (with log), `search`, `semantic_search`, `get_work_item`.
  - Writes: `add_branch`, `add_commit`, `save_merge_request`, `save_note`, **`accept_merge_request`**, `manage_pipeline`, `save_project`.
  - **No compare and no deployments/environments tools.**
- Verdict: same as GitHub, do not make it the boundary. It can't use per-Investigation project access tokens. It lacks compare and deployments, our main correlators. Writes are only excludable by allow-list. Possible later use: as an Operator-delegated OAuth read path, allow-listed to read tools.

## 8. Where GitLab differs from the GitHub design

| GitHub decision | GitLab equivalent | Gap / action |
|---|---|---|
| GitHub App, installation token 1 h | Service account (minter) + per-project access token | **No App.** Minter needs a Maintainer PAT, which is more powerful than an App key (§1.1). Isolate it in a token broker |
| Down-scope per call (repos + permissions) | One PrAT per project, role × scope | One token per repo, not one per Investigation. Mint lazily per repo touched |
| Expiry 1 h | Date-granular (midnight UTC) | **Explicit revoke is mandatory**, plus an orphan sweeper |
| Read perms (contents, PRs, actions, deployments, checks, statuses) | Reporter + `read_api` + `read_repository` | Maps |
| Write: contents:write + pull_requests:write | Developer + `api` | `api` is broad: it can also create issues, run pipelines and delete unprotected branches. Constrain in the adapter |
| No `workflows` permission | **None exists** | CI-file edits are possible on the fix branch. Use protected variables, external CI path, PEP (Ultimate) or CODEOWNERS (Premium), and agent-side diff refusal |
| No `administration` | Role ≤ Developer on bot tokens | Maps for bot tokens. **Not** for the minter |
| Ruleset, no bot bypass | Protected branch: push No one, merge Maintainers (Free) | Maps. Approval rules need Premium |
| Draft PR via `draft: true` | `Draft:` title prefix | Adapter must prefix the title and verify `draft: true` in the response |
| Bot identity `app[bot]` | `project_{id}_bot_{rand}`, new user per token | Noisy MR author name. On Free, use a named service account instead |
| Checks + statuses | Commit statuses + pipelines/jobs | Map "checks" to the pipeline status for the SHA |
| `list_workflow_runs` / job logs | Pipelines/jobs, `/trace` | Maps. No server-side tail |
| Deployments + statuses | Deployments with `status`, `finished_before` filters | **Better**: deployed SHA at time T is one query |
| Code search fallback | Project blob search; group search needs Premium + advanced search | Fall back to the local partial mirror + ripgrep |
| Partial mirrors with read token | Same (`blob:none`, token as password) | Maps |
| Operator check `collaborators/permission` | `members/all/:user_id` effective `access_level` | Maps (highest role wins) |
| Official MCP: optional | Rejects project/group tokens | Not usable with our token model |
| Self-hosting | Self-Managed: PrATs on any licence; rate limits off by default | Self-Managed is *easier* than gitlab.com Free |

### Adapter interface spanning both

Use provider-neutral names. **Change request** = PR or MR. **Pipeline run** = workflow run or pipeline. **CI job** = job. **Repo** = GitHub repo or GitLab project (`owner/name` or `group/sub/project` path, stored as an opaque `RepoRef`).

```text
interface ForgeAdapter                      # one impl per forge; tokens injected per call
  # Credentials (token broker side, not exposed to the model)
  mintReadCredential(repo, investigationId) -> Credential     # GH: installation token; GL: PrAT Reporter
  mintWriteCredential(repo, investigationId, approval) -> Credential   # GH: contents+PR write; GL: PrAT Developer+api
  revoke(credential)                                          # GL: mandatory; GH: best-effort
  operatorAccess(repo, operatorIdentity) -> none|read|write|maintain   # normalised role

  # Change stage (read)
  listDeployments(repo, environment, before?, after?, status?) -> Deployment{sha, ref, env, finishedAt, runRef}
  resolveDeployedCommit(repo, environment, at) -> sha | unknown
  listCommits(repo, ref, since, until, path?) -> Commit[]
  compareCommits(repo, base, head) -> {commits, files, truncated}
  listPipelineRuns(repo, sha? ref? window?) -> PipelineRun[]
  getFailedJobLogTail(run, lines) -> JobLog[]
  getChangeRequest(repo, id) / changeRequestsForCommit(repo, sha)
  linkedIssues(changeRequest) -> IssueRef[]

  # Code
  readFile(repo, path, sha) / searchCode(repo, query, sha?) -> may return UNSUPPORTED (tier)
  cloneUrl(repo, credential)                                  # for partial mirror

  # Fix (write, only with write credential, after Fix gate)
  openDraftChangeRequest(repo, baseBranch, branchName, files[], title, body) -> ChangeRequestRef
  # never: merge, approve, mark-ready, trigger pipeline, edit CI files (adapter rejects CI paths)
  postNote(issueOrChangeRequest, body)
```

Design rules:
1. Capabilities are discovered per repo (tier, search availability) and returned as `UNSUPPORTED`, not as errors.
2. The adapter, not the model, enforces the CI-path deny-list and the "draft only" invariant (GitLab: title prefix + post-check).
3. Credentials never enter the model context.

## Sources (docs.gitlab.com, fetched 2026-11-06)

- S1 /user/project/settings/project_access_tokens/
- S2 /api/project_access_tokens/
- S3 /user/group/settings/group_access_tokens/
- S4 /user/profile/service_accounts/
- S5 /api/service_accounts/
- S6 /auth/tokens/fine_grained_access_tokens/
- S7 /api/personal_access_tokens/
- S8 /api/oauth2/
- S9 /integration/oauth_provider/
- S10 /ci/jobs/ci_job_token/
- S11 /ci/secrets/id_token_authentication/
- S12 /security/tokens/access_token_scopes/
- S13 /user/permissions/
- S14 /user/project/repository/branches/protected/
- S15 /user/project/merge_requests/approvals/rules/
- S16 /ci/variables/
- S17 /ci/pipelines/settings/
- S18 /user/application_security/policies/pipeline_execution_policies/
- S19 /user/project/codeowners/
- S20 /user/project/repository/push_rules/
- S21 /api/merge_requests/
- S22 /user/project/merge_requests/drafts/
- S23 /api/commits/
- S24 /api/repositories/
- S25 /api/pipelines/
- S26 /api/jobs/
- S27 /api/environments/
- S28 /api/deployments/
- S29 /api/repository_files/
- S30 /api/search/
- S31 /user/gitlab_com/rate_limits/
- S32 /topics/git/clone/
- S33 /api/project_members/
- S34 /api/members/
- S35 /api/issues/
- S36 /api/notes/
- S37 /user/group/epics/
- S38 /api/graphql/epic_work_items_api_migration_guide/
- S39 /administration/settings/user_and_ip_rate_limits/
- S40 /user/model_context_protocol/mcp_server/
- S41 /user/model_context_protocol/mcp_server_tools/

Open questions to verify against a live instance:
1. The minimum `expires_at` for a PrAT (is today rejected?).
2. Whether project-level `scope=blobs` works on Free (basic search).
3. Whether service accounts can hold fine-grained PATs scoped to selected projects.
4. Whether a Developer-role bot's MR pipeline receives any non-protected secrets in the target projects.
