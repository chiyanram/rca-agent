# Running CLIs and MCP servers on injected, scoped, short-lived credentials

Research date: 2026-11-09. Primary sources only: official docs, GitHub READMEs and source. Anything marked **UNVERIFIED** was not confirmed in a primary source during this pass. No credentials or tenant URLs appear here; placeholders only.

## Summary table

| Tool (version checked) | Headless injected token? | Scoping | Read-only enforced server-side? | JSON output | Result bounding |
|---|---|---|---|---|---|
| `dtctl` v0.45.0 | Yes. Platform token through the config file (`token: ${VAR}` expansion) with `DTCTL_CONFIG` and `DTCTL_CONTEXT`. `DTCTL_TOKEN` is documented (partly UNVERIFIED in source). OAuth client credentials through `DTCTL_CLIENT_ID`/`DTCTL_CLIENT_SECRET`. | Per-scope (`storage:logs:read`, etc.), per-environment. Effective access is also capped by the token owner's (service user's) IAM permissions. | No. `--safety-level readonly` and profiles are client-side only. Only token scopes are enforced. | `-o json`, `--agent`/`-A` JSON envelope | `--max-result-records`, `--max-result-bytes`, `--default-scan-limit-gbytes`, `--fetch-timeout-seconds`, `query-limits` in config |
| Dynatrace MCP (local) v2.1.2 | Yes. `DT_PLATFORM_TOKEN`, or `OAUTH_CLIENT_ID`/`OAUTH_CLIENT_SECRET`, with `DT_ENVIRONMENT` (stdio env) | Same Dynatrace scopes | No read-only mode. Write tools (`send_email`, `send_slack_message`, `send_event`, `create_dynatrace_notebook`) are blocked only by missing scopes. | MCP tool results | `execute_dql` `recordLimit` (default 100), `recordSizeLimitMB` (default 1), `DT_GRAIL_QUERY_BUDGET_GB` (default 1000) |
| `gh` 2.102.0 | Yes. `GH_TOKEN`/`GITHUB_TOKEN` (or `GH_ENTERPRISE_TOKEN`) takes precedence over stored credentials. GitHub App installation token works. | Installation token: per-repository and per-permission at mint time | Yes, through token permissions. `gh` has no read-only mode. | `--json fields` + `--jq`/`--template`; `gh api` returns JSON | `--limit` on list commands (UNVERIFIED per command); `gh api` without `--paginate` returns one page |
| `glab` v1.128.0 | Yes. `GITLAB_TOKEN` > `GITLAB_ACCESS_TOKEN` > `OAUTH_TOKEN`, with `GITLAB_HOST` | Project/group access token: role + scopes (`read_api`, `read_repository`, ...) | Yes, through token scopes and role | `-F/--output json` on many commands; `glab api` | `--per-page`, `--page` |
| `az` 2.92.0 | Partly. `az login --identity`, `--service-principal` with secret or cert, or `--federated-token <JWT>`. There is no flag that takes a pre-minted ARM access token. | Azure RBAC at resource scope. A custom role can be narrowed to individual actions. | Yes (RBAC). But reading app settings needs `.../config/list/action`, which returns every secret on the site. | `-o json`, `--query` (JMESPath) | None generic (command-specific) |
| Atlassian Rovo MCP (remote) | Yes, if an org admin enables API-token auth: `Authorization: Basic base64(email:api_token)` or `Bearer <service-account API key>`. Default is OAuth 2.1 (interactive). | Scoped API tokens / service-account keys. Always limited by the user's or service account's permissions. | Yes (scopes + product permissions). `delete_jira`/`manage_jira` permission groups are off by default. | MCP | Not documented |
| `sooperset/mcp-atlassian` v0.24.1 | Yes. `JIRA_USERNAME`+`JIRA_API_TOKEN` (Cloud), `JIRA_PERSONAL_TOKEN` (Server/DC), `*_COMMAND` variants, OAuth BYOT `ATLASSIAN_OAUTH_ACCESS_TOKEN` | Through the token used. `JIRA_PROJECTS_FILTER` and `CONFLUENCE_SPACES_FILTER` are client-side. | `READ_ONLY_MODE` is client-side. A scoped read-only token is what enforces it on the server. | MCP | Not documented |
| `acli` | Partly. `acli jira auth login --site --email --token` (token read from stdin). Service-account scoped tokens currently fail (open issue CLOUD-12991). | Unscoped user API token only (today) | Not via the CLI | UNVERIFIED | UNVERIFIED |
| `mcp-grafana` v2.2.0 | Yes. `GRAFANA_SERVICE_ACCOUNT_TOKEN` or `GRAFANA_SERVICE_ACCOUNT_TOKEN_FILE` (re-read on every request). Per-request `X-Grafana-Service-Account-Token` over streamable-http. | Service-account role (Viewer/None + fine-grained RBAC in Enterprise/Cloud) | `--disable-write` is client-side. A Viewer-role service account enforces it on the server. | MCP | `--max-loki-log-limit` (default 100), Prometheus guardrails, `--loki-enforced-matchers`, SQL row limits |

## Cross-cutting conclusions

- Every tool can run headless without a person's interactive login. The exceptions are `acli` with service accounts (broken today) and Rovo MCP when the admin has not enabled API tokens.
- None of the "read-only" switches is a security boundary. That covers `dtctl --safety-level`, dtctl profiles, `READ_ONLY_MODE`, `--disable-write`, `ENABLED_TOOLS`, and MCP `readOnlyHint` annotations. The docs for dtctl and mcp-grafana say this outright, and the MCP spec says annotations are untrusted. Only the scopes, role or RBAC on the credential are enforced.
- Short lifetime varies a lot by system:

  | System | Credential lifetime |
  |---|---|
  | Dynatrace OAuth client-credentials | 300 s |
  | GitHub App installation token | 1 h |
  | Entra access token | 60–90 min |
  | Dynatrace platform token | Expiry set at creation |
  | Grafana service-account token | Optional expiry, none by default |
  | GitLab project access token | Minimum 1 day |
  | Atlassian API token | Minimum 1 day |

  In practice, a per-Investigation credential is only truly minted-on-demand and minutes-long for Dynatrace (OAuth client), GitHub (App) and Azure (MI/SP/federated). For GitLab, Atlassian and Grafana, the realistic pattern is a narrowly scoped, rotated token held in a vault and injected late. Minting per Investigation would need API-created tokens, which is possible for GitLab and Grafana.
- Isolation per process: `GH_CONFIG_DIR`, `GLAB_CONFIG_DIR`, `AZURE_CONFIG_DIR` and `DTCTL_CONFIG` all exist. Use a temporary directory per Investigation, and set `DTCTL_TOKEN_STORAGE=file` or use a config-file token so dtctl never touches a keyring.

---

## 1. dtctl (Dynatrace CLI)

Sources:
- https://github.com/Dynatrace/dtctl (README badges and raw docs now live under `Dynatrace/dtctl`; `dynatrace-oss/dtctl` is the published link). Latest release v0.45.0, 2026-10-21. Docs read from `main` on 2026-11-09.
- docs/CONFIGURATION.md, docs/TOKEN_SCOPES.md, docs/AGENT_MODE.md, docs/SERVE.md, docs/resources/dql-queries.md, cmd/session.go, cmd/plugin_dispatch.go
- Dynatrace docs (2026-11-09): https://docs.dynatrace.com/docs/manage/identity-access-management/access-tokens-and-oauth-clients/platform-tokens and .../oauth-clients

### Auth methods
- **Interactive OAuth:** `dtctl auth login --context X --environment URL` opens a browser and stores tokens in the OS keyring. Not suitable for the agent.
- **Non-interactive OAuth (client credentials):** set `DTCTL_CLIENT_ID` (`dt0s02.*`), `DTCTL_CLIENT_SECRET`, and `DTCTL_ACCOUNT_URN` (sent as the RFC 8707 resource indicator), then run `dtctl auth login --context ci --environment URL`. Notes from the docs:
  - Pass `--scopes` to narrow the token. Without it, the token carries every scope granted to the client, and dtctl prints a warning.
  - No refresh token is issued; re-run `auth login` to get a new one.
  - `--timeout` (default 5m) bounds the token request.
  - Missing credentials are a usage error. dtctl never silently falls back to the browser.
  - The docs prefer environment variables over the equivalent `--client-id` flags.
- **Platform token (`dt0s16.*`):**
  - Set up with `dtctl config set-context NAME --environment URL --token-ref REF [--safety-level readonly]` plus `dtctl config set-credentials REF --token ...`.
  - A config template can reference environment variables: `token: ${DT_API_TOKEN}`. The loader expands `$VAR`/`${VAR}` from the process environment.
  - Select the file with `DTCTL_CONFIG=path` (treated as explicit and trusted) and the context with `DTCTL_CONTEXT`.
- **`DTCTL_TOKEN`:** AGENT_MODE.md shows `export DTCTL_CONFIG=...; export DTCTL_CONTEXT=prod; export DTCTL_TOKEN=dt0s16...`. The file carries a header note "SME to verify against the current binary". In source, `DTCTL_TOKEN` and `DT_API_TOKEN` appear in credential scrub lists (session and plugin env), but I did not find where they are read directly. **UNVERIFIED** whether `DTCTL_TOKEN` is read without a `${DTCTL_TOKEN}` reference in config. The safe pattern is a per-Investigation temporary config with `token: ${SOME_VAR}`, plus `DTCTL_CONFIG` and `DTCTL_CONTEXT`. There is no `DTCTL_ENVIRONMENT`; the URL comes from the context.
- **Storage:** OS keyring by default. `DTCTL_TOKEN_STORAGE=file` keeps OAuth tokens in owner-only (0600), unencrypted files. Use it headless.
- **`dtctl serve http`** (development tier): each request brings its own environment URL and token. Host config, keyring and credential env vars are never read. The server has no authentication of its own. It is not a stable contract.

### Scopes
TOKEN_SCOPES.md gives the `readonly` scope bundle (logs, events, metrics, spans, entities, buckets, etc.). The per-resource table maps `bucket` to `storage:buckets:read`. `dtctl commands [filter] --required-scopes` prints the minimal scope union for a set of commands.

For DQL queries:
- The Dynatrace MCP README states `storage:buckets:read` plus the table scope, e.g. `storage:logs:read`.
- The Dynatrace OAuth docs example also includes `app-engine:apps:run`.
- Minimal set for log queries: `storage:logs:read`, `storage:buckets:read`. **UNVERIFIED** whether `app-engine:apps:run` is needed for plain DQL through dtctl.

### Token lifetime and permission model
- Client-credentials access token: `expires_in: 300` (Dynatrace OAuth docs example).
- Authorization-code token: 600 s.
- Platform tokens:
  - Expiry is chosen at creation and can be set to "never".
  - A token can be restricted to selected environments.
  - It works "within the bounds of the assigned user permissions".
  - It can be created for a service user. This needs the `iam:service-users:use` permission.
  - Limit of 50 tokens per user and 100 per service user.
- Recommended setup: an OAuth client with a service-user subject and narrow scopes, minting a 5-minute token per Investigation.

### Safety mode
- `--safety-level readonly | readwrite-mine | readwrite-all | dangerously-unrestricted`.
- The docs say: "Safety levels are client-side only. For actual security, configure your API tokens with minimum required scopes."
- Ownership checks (`readwrite-mine`) are also client-side.
- Profiles (`DTCTL_PROFILE`) limit which commands exist. They are also client-side ("A determined caller can unset DTCTL_PROFILE").

### Output and bounding
- `-o json|yaml|csv`. `--agent`/`-A` gives a JSON envelope `{ok, result, context}`.
- Query flags:

  | Flag | Purpose |
  |---|---|
  | `--max-result-records` | Cap returned records (server default about 1000) |
  | `--max-result-bytes` | Cap result size in bytes |
  | `--default-scan-limit-gbytes` | Cap data scanned; beyond it the result is PARTIAL |
  | `--fetch-timeout-seconds` | Time limit for fetching |
  | `--enforce-query-consumption-limit` | Enforce the tenant consumption limit |
  | `--default-sampling-ratio` | Sampled, approximate results |
  | `--timeout` | Default 5m |

- `query-limits:` in config (global and per-context) sets `scan-limit-gbytes`, `max-result-records`, `max-result-bytes` and `sampling-ratio`. These can only tighten. `--no-query-limits` lifts them per invocation.
- Large results can "spill" to disk. `DTCTL_SPILL=never` turns this off; consider it so data stays inside the redaction pipeline.

## 2. Dynatrace MCP server (local, `@dynatrace-oss/dynatrace-mcp-server`)

Sources: https://github.com/dynatrace-oss/dynatrace-mcp README and src/index.ts (main, last push 2026-08-26). Release v2.1.2, 2026-07-20. Checked 2026-11-09.

- **Auth:**
  - `DT_ENVIRONMENT` is required.
  - `DT_PLATFORM_TOKEN` is optional.
  - `OAUTH_CLIENT_ID`/`OAUTH_CLIENT_SECRET` is the alternative, intended for service users and backend-to-backend use.
  - With only `DT_ENVIRONMENT` set, the server opens a browser (authorization code flow) and stores tokens in the keychain. `DT_MCP_TOKEN_STORAGE=file` is for headless use.
  - `DT_SSO_URL` overrides SSO discovery.
- **Scopes:** README list, e.g. `app-engine:apps:run` ("needed for almost all tools"), `storage:buckets:read` and `storage:<table>:read` for `execute_dql`, `document:documents:read`. Write tools need write scopes: `storage:events:write`, `email:emails:send`, `document:documents:write`, Slack app-settings.
- **Read-only:** there is no read-only flag or tool allow-list in the server.
  - Tools carry `readOnlyHint`/`destructiveHint` annotations. Odd detail: `execute_dql` is marked `readOnlyHint: false`.
  - Write tools exist: `send_slack_message`, `send_email`, `send_event`, `create_dynatrace_notebook`, `create_document`. Blocking them requires withholding scopes and/or filtering tools in our MCP client.
- **Bounding:** `execute_dql` params `recordLimit` (default 100) and `recordSizeLimitMB` (default 1) map to `maxResultRecords`/`maxResultBytes`. `DT_GRAIL_QUERY_BUDGET_GB` (default 1000) is a per-session scan budget with a warning at 80%.
- **Transport:** stdio by default. `--http` mode with `MCP_BEARER_TOKEN` for caller auth (a static bearer, not per-request Dynatrace credentials).
- **Telemetry is on by default.** Disable it with `DT_MCP_DISABLE_TELEMETRY=true`.
- The README now recommends `dtctl` for local use and the hosted "Dynatrace Remote MCP Server" for agent-to-agent use. The remote server's auth model was not researched (**UNVERIFIED**).

## 3. gh (GitHub CLI)

Sources: `gh help environment`, `gh help formatting`, `gh api --help` from local gh 2.102.0 (2026-09-30). GitHub docs, "Generating an installation access token for a GitHub App" (checked 2026-11-09).

- **Token injection:**
  - `GH_TOKEN`, `GITHUB_TOKEN` (in order of precedence) for github.com and `*.ghe.com`. Setting one "avoids being prompted to authenticate and takes precedence over previously stored credentials".
  - `GH_ENTERPRISE_TOKEN`/`GITHUB_ENTERPRISE_TOKEN` for GHES, with `GH_HOST`.
  - `GH_PROMPT_DISABLED` turns off prompts.
  - `GH_CONFIG_DIR` isolates config per process.
  - Set `GH_TELEMETRY=false` or `DO_NOT_TRACK=1`, plus `GH_NO_UPDATE_NOTIFIER`.
- **GitHub App installation token:**
  - Mint with `POST /app/installations/{id}/access_tokens`.
  - The optional `repositories`/`repository_ids` body (up to 500 repos) and `permissions` body narrow the token below the installation's grant.
  - It expires after 1 hour.
  - Pass it as `GH_TOKEN`. The GitHub Actions docs use the same pattern.
  - User-centric commands (e.g. some `gh auth` output) may not work with an installation token (**UNVERIFIED** in detail).
- **Read-only:** enforced only by the token's permissions (e.g. `contents: read`, `issues: read`). gh has no read-only mode.
  - Caution: `gh api` switches from GET to POST as soon as parameters are added with `-f`/`-F`. Force `--method GET` in our wrapper, and rely on a read-only token anyway.
- **Output:** `--json <fields>` plus `--jq` or `--template` (no external jq needed). `gh api` returns JSON and supports `--jq`, `--paginate`, `--slurp` and `--cache`.
- Fine-grained PAT max lifetime and org policies were not re-verified this pass (**UNVERIFIED**).

## 4. glab (GitLab CLI)

Sources: https://gitlab.com/gitlab-org/cli README (v1.128.0, 2026-11-03), https://docs.gitlab.com/cli/authentication/, https://docs.gitlab.com/cli/configuration/, https://docs.gitlab.com/user/project/settings/project_access_tokens/ (checked 2026-11-09).

- **Token precedence:** `GITLAB_TOKEN` > `GITLAB_ACCESS_TOKEN` > `OAUTH_TOKEN`. The env var wins over a stored token.
  - Env tokens go only to "trusted hosts": `GITLAB_HOST` (or the config host, default gitlab.com), the `GITLAB_REPO` host, or hosts in the config file.
  - CI job token via `GLAB_ENABLE_CI_AUTOLOGIN=true` inside GitLab CI.
  - `glab auth login --stdin` stores the token in the keyring or config. Avoid this; use the env var.
- **Config isolation:** `GLAB_CONFIG_DIR`.
- **Project access tokens:**
  - Each one creates a bot user with a chosen role (e.g. Reporter) and scopes (e.g. `read_api`, `read_repository`).
  - Expiry is a date and the token expires at midnight UTC. The default and maximum is 365 days, or 400 days behind a feature flag in 17.6+. Admins can change the maximum.
  - Minimum granularity is 1 day, so "per-Investigation" means a daily token or API-created tokens that are revoked after use.
- **Output:** `-F/--output json` on many commands (e.g. `glab mr list`), plus `glab api`. Paging with `-P/--per-page` (default 30) and `-p/--page`.

## 5. az (Azure CLI)

Sources: Microsoft Learn: `az login` and `az rest` reference (azure-cli latest = 2.92.0, 2026-11-03), "Tips for using the Azure CLI successfully", "Access tokens in the Microsoft identity platform", "Azure permissions for Web and Mobile", "Azure built-in roles for Web and Mobile" (checked 2026-11-09).

- **Login methods:**
  - `az login --identity` (system MI), `--identity --client-id | --object-id | --resource-id` (user-assigned MI).
  - `az login --service-principal -u APP_ID -p SECRET | --certificate PEM --tenant T`.
  - `az login --service-principal -u APP_ID --federated-token <OIDC JWT> --tenant T` (workload identity federation). Here the injected short-lived artifact is the federated assertion.
  - `--allow-no-subscriptions` and `--skip-subscription-discovery` are also available.
  - All of these are headless.
- **Pre-minted access token:** `az login` has no flag that accepts an ARM access token. `az rest` only attaches its own token "if Authorization header is not set", and `--skip-authorization-header` exists. So `az rest --headers Authorization="Bearer ..."` can carry a pre-minted token. **UNVERIFIED** whether `az rest` runs without any prior `az login` in that case. It is simpler for our own HTTP adapter (Python SDK / `azure-identity`) to call ARM directly with the minted token.
- **Isolation:** `AZURE_CONFIG_DIR` per process/script. Microsoft recommends this for concurrent runs to avoid MSAL cache conflicts. Use a temporary directory per Investigation and delete it afterwards.
- **Lifetime:** Entra access tokens default to a random 60–90 minutes. CAE-capable clients can get 20–28 h. Configurable token lifetime is not supported for managed identity service principals.
- **Output:** `-o json` (also `tsv`, `yaml`, `none`), with `--query` (JMESPath).
- **Least privilege for reading app settings:**
  - `Microsoft.Web/sites/config/list/Action` is described as "List Web App's security sensitive settings, such as publishing credentials, app settings and connection strings". This is what `az webapp/functionapp config appsettings list` needs (POST `.../config/appsettings/list`). Reader is not enough.
  - The action is all-or-nothing per site: it returns every secret value, so output must be redacted before storage.
  - **Website Contributor** includes `Microsoft.Web/sites/*` (create, manage, restart, publish, write config). It is far too broad.
  - Recommended: a custom role with `Microsoft.Web/sites/read` + `Microsoft.Web/sites/config/list/Action` (+ `Microsoft.Web/sites/config/Read`), assigned at the scope of the single site.
  - The permissions list also shows `microsoft.web/sites/config/web/appsettings/read` ("Get Web App Single App setting"). **UNVERIFIED** which REST endpoint and az command use it, and whether it returns a single value without the list action. Worth testing, because it would allow reading one setting instead of all of them.

## 6. Atlassian

### 6a. Atlassian Rovo MCP server (official, remote)
Sources:
- https://developer.atlassian.com/cloud/rovo-mcp/guides/authentication-and-authorization/ (last updated 2026-09-02)
- https://support.atlassian.com/security-and-access-policies/docs/control-atlassian-rovo-mcp-server-settings/ (undated)
- https://support.atlassian.com/atlassian-account/docs/manage-api-tokens-for-your-atlassian-account/ (undated)

Checked 2026-11-09.

- **Auth:**
  - OAuth 2.1 (interactive consent) is the default.
  - API token auth must be enabled by an org admin (Atlassian Administration > Rovo/Connectors > MCP server > Authentication). It uses `Authorization: Basic base64(email:api_token)` (personal token) or `Authorization: Bearer <api_key>` (service-account API key).
  - Atlassian recommends API tokens for non-interactive/machine use.
  - Jira Service Management tools are API-token only. Code search and Teams tools are OAuth only.
- **Acts as the user:** "every action respects the authenticated user's existing access controls and permissions". With a service-account key, it acts as the service account.
- **Scopes:** Tokens and keys "honor configured scopes". The auth page names no specific scope list (**UNVERIFIED** mapping of tool to scope).
  - API tokens can be created with scopes; scopes are required for service-account tokens.
  - Expiry is 1–365 days (default 1 year).
  - Scoped tokens call `api.atlassian.com/ex/{jira|confluence}/{cloudId}`.
- **Admin controls:**
  - API-token toggle.
  - Allowed AI domains (Atlassian-supported plus custom).
  - Org IP allowlists apply to MCP for both OAuth and token auth.
  - The `delete_jira`/`manage_jira` permission groups are off by default.
  - The docs advise monitoring audit logs (a separate "Monitor ... activity" page was not read).
- Per-tool allow-listing on the server side was not documented. Do it in our client.

### 6b. sooperset/mcp-atlassian (community)
Sources: https://github.com/sooperset/mcp-atlassian (v0.24.1, 2026-11-08) and https://mcp-atlassian.soomiles.com/llms-full.txt (checked 2026-11-09).

- **Auth through env (stdio):**
  - Cloud: `JIRA_URL`, `JIRA_USERNAME` + `JIRA_API_TOKEN`, `CONFLUENCE_*` equivalents.
  - Server/DC: `JIRA_PERSONAL_TOKEN`/`CONFLUENCE_PERSONAL_TOKEN`.
  - `*_TOKEN_COMMAND` variants fetch the secret from a command (timeout `CREDENTIAL_COMMAND_TIMEOUT`, default 30 s). A plain token var takes precedence.
  - OAuth 2.0 (3LO) with `ATLASSIAN_OAUTH_*`, or BYOT `ATLASSIAN_OAUTH_CLOUD_ID` + `ATLASSIAN_OAUTH_ACCESS_TOKEN`. With BYOT, refresh is the caller's job, which fits a short-lived injected token.
  - mTLS is also supported.
  - In multi-user HTTP mode, each request carries `Authorization: Bearer <token>` + `X-Atlassian-Cloud-Id`, or a PAT with `X-Atlassian-*-Url`.
- **Restrictions (all client-side in the server process):**
  - `READ_ONLY_MODE=true` "disables all write operations".
  - `ENABLED_TOOLS` (or `--enabled-tools`) and `TOOLSETS` intersect.
  - `JIRA_PROJECTS_FILTER`, `CONFLUENCE_SPACES_FILTER`.
  - Server-side enforcement comes only from a read-only scoped token or a low-permission account.
- The docs mention API/scoped tokens on Confluence Cloud v1 endpoints. Full scoped-token support status is **UNVERIFIED**.

### 6c. acli (Atlassian CLI)
Sources: https://developer.atlassian.com/cloud/acli/reference/commands/jira-auth-login/ (last updated 2024-10-03) and https://jira.atlassian.com/browse/CLOUD-12991 (created 2026-07-28, updated 2026-10-23, status "Gathering Interest").

- `acli jira auth login --web` uses OAuth through a browser. `acli jira auth login --site S --email E --token` reads an API token from stdin, and the page says this means tokens "without scopes".
- Known gap: authenticating with a service-account email and a scoped API token fails with "Authentication failed". The workaround is a normal user with an unscoped token. This conflicts with least privilege, so avoid acli for now.
- **UNVERIFIED:** credential storage location, env-var token injection, config-dir isolation, JSON output flags.

## 7. Grafana mcp-grafana

Sources: https://github.com/grafana/mcp-grafana README (v2.2.0, 2026-11-02) and https://grafana.com/docs/grafana/latest/administration/service-accounts/ (checked 2026-11-09).

- **Auth:**
  - `GRAFANA_URL` + `GRAFANA_SERVICE_ACCOUNT_TOKEN`, or `GRAFANA_SERVICE_ACCOUNT_TOKEN_FILE`. The file "is read fresh on every request, so rotated tokens are picked up automatically".
  - `GRAFANA_API_KEY` is deprecated.
  - Over streamable-http, per-request `X-Grafana-Service-Account-Token`/`X-Grafana-Org-Id` (and `X-Grafana-URL` with `--allow-grafana-url-override`). This does not work over SSE.
  - Caller auth to the MCP server: `--server-auth-token`/`MCP_GRAFANA_SERVER_TOKEN`.
- **Token lifetime:** no expiry by default. An expiry can be set at creation, and admins can cap it with `token_expiration_day_limit`. Grafana recommends "a few hours or less". Tokens can be created via the API.
- **Scoping:** service-account basic role (Viewer, or `None` since 10.2) plus fine-grained RBAC (Enterprise/Cloud). The README lists the RBAC actions and scopes each tool needs.
- **Read-only:**
  - `--disable-write` removes create/update tools. `--enable-write-tools=...` adds exceptions back.
  - `--enabled-tools` (category allow-list; `admin` and others are off by default), `--disable-<category>`, `--disable-query`.
  - All of these are client-side. A Viewer-role service account enforces it on the server.
- **Bounding:**
  - `--max-loki-log-limit` (default 100).
  - `--loki-enforced-matchers` (label matchers ANDed into every Loki query; requires `--disable-api`).
  - `--prometheus-guardrail-mode off|shadow|enforce` with a max-points cap.
  - SQL tools have automatic limit enforcement.
  - `--grafana-timeout` (default 10s).

## 8. MCP in general

Sources: https://github.com/modelcontextprotocol/modelcontextprotocol, `docs/specification/2026-07-28/basic/authorization/index.mdx` and `security-considerations.mdx`, and `server/tools.mdx` (latest dated spec 2026-07-28, checked 2026-11-09).

- Authorization is optional.
  - HTTP transports SHOULD use the OAuth 2.1-based flow (MCP server = resource server, Protected Resource Metadata, PKCE).
  - **STDIO servers SHOULD NOT follow the OAuth spec and should "retrieve credentials from the environment".** This is the hook for late, per-process injection of a scoped token.
- Clients MUST use RFC 8707 `resource` indicators with the server's canonical URI. Servers MUST validate the audience.
- **Token passthrough is forbidden:**
  - Clients MUST NOT send tokens not issued by the MCP server's authorization server.
  - Servers "MUST NOT accept or transit any other tokens".
  - For upstream APIs, the server acts as its own OAuth client and MUST NOT pass through the client's token.
- Tokens MUST NOT go in URL query strings. `client_credentials` clients are recognised (step-up guidance distinguishes them).
- Tool `annotations` (`readOnlyHint`, `destructiveHint`) "MUST" be treated as untrusted unless the server is trusted. They are not an enforcement mechanism.
- **Per-tool allow-listing in clients:** the spec defines none. Our Python service is the MCP client, so it controls which tools from `tools/list` are exposed to the LLM. Implement the allow-list, audit and redaction there. Server-side filters (`ENABLED_TOOLS`, `--enabled-tools`) are defence in depth. (Third-party client features such as per-tool permission rules exist in some clients but were not researched here.)

## Recommended injection pattern (derived from the sources above)

1. Per Investigation: mint or fetch the narrowest credential, as close to use as possible.
   - Dynatrace: OAuth client credentials with `--scopes storage:logs:read storage:buckets:read`, 5-minute token.
   - GitHub: App installation token restricted to the repositories and permissions needed, 1 h.
   - Azure: MI/SP/federated login against a custom role with `config/list/action` on one site.
   - GitLab / Grafana / Atlassian: a scoped, rotated read-only token from the vault.
2. Spawn the CLI or stdio MCP server with a clean environment that holds only that credential, plus a per-Investigation config directory (`GH_CONFIG_DIR`, `GLAB_CONFIG_DIR`, `AZURE_CONFIG_DIR`, `DTCTL_CONFIG` + `DTCTL_TOKEN_STORAGE=file`). Turn telemetry off where possible (`GH_TELEMETRY=false`, `DT_MCP_DISABLE_TELEMETRY=true`).
3. Apply client-side switches too (`--safety-level readonly`, `READ_ONLY_MODE`, `--disable-write`, tool allow-list), but treat them as defence in depth only.
4. Force JSON output and result bounds. Audit every call and redact before storage. Delete the config directory and revoke the token at the end.
