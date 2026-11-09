# Jira Cloud: linking to and creating issues from an agent

Researched 2026-11-09 for issue #46. Public Atlassian docs only. Primary source for the REST
facts is the Jira Cloud platform REST v3 OpenAPI spec
(<https://dac-static.atlassian.com/cloud/jira/platform/swagger-v3.v3.json>, spec version
`1001.0.0-SNAPSHOT`), which is what the reference pages at
<https://developer.atlassian.com/cloud/jira/platform/rest/v3/> are generated from.

Confidence key: **High** = stated verbatim in Atlassian docs/spec. **Medium** = Atlassian docs
imply it, or it comes from an older/legacy Atlassian page. **Low** = community or third-party
source only, or not found; needs testing on a real site.

## Questions

1. Create issue (`POST /rest/api/3/issue`): permissions, required fields, per-project required fields.
2. Issue links vs remote links: permissions; `globalId` idempotency; remote link without Edit issues?
3. Comments: permission; possible without Edit issues?
4. Per-project service account permissions; are API token / OAuth scopes project-limited?
5. Atlassian service accounts: Jira REST via `api.atlassian.com/ex/jira/{cloudId}`, token lifetime, limits.
6. Rovo / Atlassian Remote MCP server: Jira tools, read-only via groups, API token auth needs admin?
7. JQL for duplicate detection: remote link, label, custom field; native remote-link function?
8. Content safety: ADF only? mention notifications? create-issue notifications?

## Findings

### 1. Create issue

- **Permissions:** "*Browse projects* and *Create issues* project permissions for the project in
  which the issue or subtask is created." OAuth: classic `write:jira-work`; granular (beta)
  `write:issue:jira`, `write:comment:jira`, `write:comment.property:jira`, `write:attachment:jira`,
  `read:issue:jira`. **High.** Source: spec / <https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issues/#api-rest-api-3-issue-post>
- **Required fields:** the spec does not hard-code a list. It says the settable fields "are determined
  using Get create issue metadata ... These are the same fields that appear on the issue's create
  screen." In practice `project`, `issuetype` and `summary` are always needed; 400 is returned if the
  request "is missing required fields" or "contains fields that cannot be set for the issue type".
  **High** (that metadata decides); **Medium** (the minimal trio, from the spec example and common usage).
- **Per project / issue type extras:** yes. Field configuration and create screens are per project and
  issue type, and `GET /rest/api/3/issue/createmeta/{projectIdOrKey}/issuetypes/{issueTypeId}` returns
  the field metadata (including `required`) for that pair. It needs *Create issues* permission and
  `read:jira-work` (granular `read:issue-meta:jira`, `read:field-configuration:jira`). The older
  all-in-one `GET /rest/api/3/issue/createmeta` is **deprecated** (changelog CHANGE-1304). A 422 is
  returned when "a configuration problem prevents the creation of the issue". **High.**
  Source: <https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issues/#api-rest-api-3-issue-createmeta-projectidorkey-issuetypes-issuetypeid-get>
- **Reporter:** the reporter defaults to the caller. Setting a different `reporter` needs the
  *Modify reporter* project permission ("Edit reporters" in team-managed projects). **Medium.**
  Source: <https://support.atlassian.com/jira/kb/you-dont-have-permission-to-modify-the-reporter-in-this-project-in-jira/>
- `description`, `environment` and multi-line custom fields take ADF; single-line text fields take a
  plain string. **High.**

### 2. Issue links vs remote links

| | Issue link `POST /rest/api/3/issueLink` | Remote link `POST /rest/api/3/issue/{key}/remotelink` |
|---|---|---|
| Links | Jira issue to Jira issue | Jira issue to an external URL / object |
| Project permission | *Browse projects* on all projects involved, plus *Link issues* on the project of the outward ("from") issue | *Browse projects* and *Link issues* on the issue's project |
| Edit issues needed? | No | No |
| Other | Issue-level security view rights; comment-visibility role/group if a restricted comment is added | Issue-level security view rights |
| Classic scope | `write:jira-work` | `write:jira-work` |
| Granular scopes (beta) | `write:issue-link:jira`, `write:issue:jira`, `write:comment:jira` | `write:issue.remote-link:jira`, `write:issue:jira`, `read:issue.remote-link:jira` |
| Site prerequisite | Issue linking enabled | Issue linking enabled ("requires issue linking to be active") |
| Idempotent? | Partly: a duplicate link request returns "created" but does not create a second link; **an included comment is still added each time** | Yes: "If a `globalId` is provided and a remote issue link with that global ID is found it is updated. Any fields without values in the request are set to null. Otherwise, the remote issue link is created." |

All **High** (verbatim spec). Sources:
<https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issue-links/#api-rest-api-3-issuelink-post>,
<https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issue-remote-links/#api-rest-api-3-issue-issueidorkey-remotelink-post>

- Reading back: `GET /rest/api/3/issue/{key}/remotelink?globalId=...` returns the one record with that
  global ID (needs only *Browse projects*, `read:jira-work`; reserved URL characters in the global ID
  must be escaped). **High.**
- So a remote link **can** be added without *Edit issues*; *Link issues* is the gate. **High.**
- Caveat: update-by-`globalId` overwrites, nulling omitted fields, so a re-post must send the full
  object. **High.**

### 3. Comments

- `POST /rest/api/3/issue/{key}/comment` needs *Browse projects* and *Add comments* (plus issue-level
  security view rights). *Edit issues* is not listed, so a comment can be added without it. Body is
  ADF. Optional `visibility` restricts to a role or group. 413 when the per-issue comment limit is
  hit. Classic scope `write:jira-work`; granular `write:comment:jira` (+ several read scopes).
  **High.** Source: <https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issue-comments/#api-rest-api-3-issue-issueidorkey-comment-post>
- For contrast, edit issue (`PUT /rest/api/3/issue/{key}`) needs *Browse projects* and *Edit issues*. **High.**

### 4. Per-project permissions vs token scopes

- **Per-project Jira permissions: yes.** Project permissions come from the permission scheme attached
  to each project; schemes grant to users, groups and project roles, and a scheme may be shared by
  several projects (so changing a shared scheme affects all of them). The service-account token page
  says service accounts "need appropriate project roles" and "follow the same permission and scope
  rules as user accounts". So a service account can be put in a role only in chosen projects.
  **Medium-High.** Sources: <https://support.atlassian.com/jira-cloud-administration/docs/manage-project-permissions/>,
  <https://support.atlassian.com/user-management/docs/manage-api-tokens-for-service-accounts/>
- **Scopes are not project-limited.** Scopes (classic or granular) are per app/product, site-wide; no
  Atlassian doc describes a project-restricted scope. "Jira permissions also control access to data
  and aren't overridden by scopes" — scopes are a ceiling, project permissions decide what actually
  succeeds. **High** that scopes are capped by permissions; **Medium-High** that there is no project
  restriction (absence of evidence on the official scopes page).
  Source: <https://developer.atlassian.com/cloud/jira/platform/scopes-for-oauth-2-3LO-and-forge-apps/>
- Classic vs granular: classic = `read:jira-work`, `write:jira-work`, `read:jira-user`,
  `manage:jira-project`, `manage:jira-configuration`, `manage:jira-webhook`. Atlassian says to prefer
  classic and use granular "only when you can't use classic scopes". `write:jira-work` covers create,
  edit, comment **and delete issue**, so classic write is broad. Granular write scopes for these
  endpoints are marked **Beta** in the spec. **High.**
- Scoped tokens cannot be changed after creation; a new token is required for new scopes. **High.**
- A request with a scoped token can trigger Forge apps that act with their own permissions, not the
  token's scopes. **High.** Source: <https://support.atlassian.com/atlassian-account/docs/manage-api-tokens-for-your-atlassian-account/>

### 5. Atlassian service accounts

- Created by **organization admins** in admin.atlassian.com (Directory > Service accounts); not
  person-bound; cannot be provisioned from an IdP; "cannot be used for interactive login to the
  Atlassian Cloud UI". **High.** Source: <https://support.atlassian.com/user-management/docs/understand-service-accounts/>
- **Credentials:** (a) scoped API token, 1–365 days, default 1 year, Basic (service-account email +
  token) or Bearer; (b) OAuth 2.0 client credentials (2LO) via `https://auth.atlassian.com/oauth/token`,
  access token valid 60 minutes (`expires_in: 3600`). Both must call the gateway
  `https://api.atlassian.com/ex/jira/{cloudId}/rest/api/3/...` (Cloud ID, not Org ID), not the site
  URL. Token revocation takes up to 10 minutes. Secrets are not recoverable after creation. **High.**
  Sources: <https://support.atlassian.com/user-management/docs/manage-api-tokens-for-service-accounts/>,
  <https://support.atlassian.com/user-management/docs/create-oauth-2-0-credential-for-service-accounts/>
- **Licence/seat:** service accounts with Jira access "do not count towards your user limit". 5 free
  per org; up to 250 with Atlassian Guard Standard, 1,000 with Enterprise. Not available on Government
  Cloud. **High.**
- **Reporter:** issues created by the service account show it as reporter (it is the caller). No
  service-account-specific reporter restriction found; setting someone else as reporter needs
  *Modify reporter*. **Medium.**
- Unscoped (classic) personal API tokens can still hit the site URL with Basic auth; scoped ones
  cannot. **High.**

### 6. Rovo / Atlassian Remote MCP server

Source for all of this: <https://support.atlassian.com/atlassian-rovo-mcp-server/docs/supported-tools/>
(tool list says it applies to **Atlassian MCP v2** only). **High** unless noted.

- **Tool groups and scopes:** `read_jira` (`read:jira:agent-interface`), `write_jira`
  (`write:jira:agent-interface`), `search_jira` (`search:jira:agent-interface`), `delete_jira` and
  `manage_jira` (both disabled by default, need admin enablement).
- **Relevant tools:**
  - read: `getJiraIssue`, `listJiraIssueRemoteIssueLinks`, `listJiraIssueLinkTypes`,
    `getJiraIssueTypeMetaWithFields`, `listJiraProjectIssueTypesMetadata`, `listJiraIssueComments`, `lookupJiraAccountId`
  - write: `createJiraIssue`, `editJiraIssue`, `transitionJiraIssue`, `addOrEditJiraIssueComment`,
    `createJiraIssueLink`, `createJiraIssueRemoteIssueLink`, `watchJiraIssue`
  - search: `searchJiraIssuesUsingJql`
- Older names seen elsewhere (`addCommentToJiraIssue`, `getJiraIssueRemoteIssueLinks`) are v1 names;
  v2 renamed them as above. **Medium** (v1 names come from third-party connector listings).
- By default only "Primary" tools are exposed directly; the rest are reached through
  `discover` / `executeRead` / `executeWrite` / `executeDestructive`; `?tools=all` lists all.
- **Read-only:** org admins grant or revoke access per permission group and each tool inherits its
  group's access, so withholding `write_jira` makes Jira read/search-only. Whether this can be set per
  client/agent rather than org-wide was not found. **High** for group control; **Low** for per-client.
- **Auth:** OAuth 2.1 and API token. API token auth is off by default and must be enabled by an
  **org admin** (Rovo MCP server settings > Authentication). Personal token = Basic (email:token);
  service-account key = Bearer. **Medium** (from search results summarising Atlassian guides and
  community threads; the per-header behaviour is community-reported).
- The MCP server still acts as the authenticated user, so Jira project permissions still apply. **Medium.**

### 7. JQL for duplicate detection

- **Remote links:** no native JQL field or function. Atlassian's suggestion JRACLOUD-27498 "JQL search
  for issues that link to a remote URL" is **Closed — Won't Do** (2015). **High.**
  Source: <https://jira.atlassian.com/browse/JRACLOUD-27498>
- Remote-link JQL functions exist only in Marketplace apps (e.g. Appfire JQL Search Extensions
  `remoteLinkUrl`; JQL Booster Pack `remoteLinkedIssuesOf()`; ScriptRunner's `linkedIssuesOfRemote()`
  is a Data Center function and community answers say it is not on Cloud). The name
  `issuesWithRemoteLinksByGlobalId` was **not found** in any source. **Low-Medium.**
  Sources: <https://appfire.atlassian.net/wiki/spaces/JQLSEARCH/pages/604209213/Web+links>,
  <https://community.atlassian.com/forums/Jira-questions/How-exactly-to-extract-global-id-for-function/qaq-p/2860602>
- **Native options:**
  - `labels = "x"` / `labels in (...)` — exact match on a label. **High** (standard JQL).
  - Custom fields: select/number/user fields support `=`; free-text fields support only `~`
    (tokenised "contains", not exact). **Medium** (JQL fields page did not render; standard behaviour).
  - Issue entity properties: `issue.property[key].path = value` works **only if the property is
    indexed by a Connect (`jiraEntityProperties`) or Forge (`jira:entityProperty`) app**; a property
    set by a plain REST client is not searchable. **High.**
    Source: <https://developer.atlassian.com/cloud/jira/platform/jira-entity-properties/>
  - Known-candidate check: once you have issue keys, `GET .../remotelink?globalId=` confirms a link
    exactly. **High.**
- Search freshness: `/rest/api/3/search/jql` says "Recent updates might not be immediately visible";
  the `reconcileIssues` parameter gives read-after-write consistency for named issues. **High.**
  Source: <https://developer.atlassian.com/cloud/jira/platform/search-and-reconcile/>

### 8. Content safety and notifications

- **ADF:** rich-text fields and comments in v3 are ADF JSON (a `doc` of defined node/mark types).
  There is no HTML node; only the documented nodes/marks are accepted (link via the `link` mark).
  `expand=renderedBody` returns Jira's own HTML rendering, not caller-supplied HTML. **High** for the
  ADF model; **Medium** that raw HTML cannot be injected (absence of any HTML node).
  Source: <https://developer.atlassian.com/cloud/jira/platform/apis/document/structure/>
- **Mentions:** an ADF `mention` node takes an `id` (Atlassian account ID) and `text`. Plain `@name`
  text is not a mention. Users get an email by default when "someone mentions them" (user can turn it
  off; only if they can browse the project / issue security level). Whether a mention created through
  REST always fires that email is **not stated** in Atlassian docs — community reports say yes.
  **Medium/Low.** Sources: <https://developer.atlassian.com/cloud/jira/platform/apis/document/nodes/mention/>,
  <https://support.atlassian.com/jira-cloud-administration/docs/configure-notification-schemes/>
- **Create notifications:** each project's notification scheme maps the "Work item created" event to
  recipients (assignee, reporter, current user, watchers, roles, etc.). By default Jira does not notify
  users of their own changes. Create issue has **no** `notifyUsers` parameter; edit issue has one, but
  disabling it needs *Administer Jira* or *Administer projects*. **High.**
- `POST /rest/api/3/issue/{key}/notify` exists to send an explicit notification. **High** (spec).

## Implications for the design

- Linking only (remote link + optional comment) needs *Browse*, *Link issues*, *Add comments* — no
  *Edit issues* and no *Create issues*. Creating adds *Create issues* and per-project field knowledge.
- Remote links keyed by a stable `globalId` give native idempotency on a known issue, but re-posts must
  send the full object. Issue-link + comment is not idempotent for the comment.
- Least privilege must come from Jira project permissions (roles in chosen projects); token/OAuth
  scopes are site-wide and classic `write:jira-work` includes delete.
- Required fields differ per project/issue type; a create path must read createmeta per pair or be
  configured per project, and must handle 400/422.
- Duplicate detection cannot query remote links in native JQL; options are labels, an indexed property
  (needs an app), a select/number custom field, or keeping our own issue-key mapping.
- Service accounts avoid seats and person-bound tokens but need an org admin to create, and tokens
  expire (≤1 year; OAuth 60 min).
- Rovo MCP can be held read-only by not granting `write_jira`, but that is an org-level admin switch
  and API-token use needs admin enablement; the design should not depend on it (provider-agnostic).
- Mentions and create events notify people; agent-written content should avoid `mention` nodes unless
  intended, and expect watchers/reporter emails per the project's scheme.
