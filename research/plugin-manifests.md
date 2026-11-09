# Plugin manifests and trust models: prior art for the RCA agent plugin system

Date checked: 2026-11-09 (all URLs fetched that day unless marked).
Legend: **[V]** verified against the cited primary source today. **[M]** from memory or secondary sources, not verified today. Treat [M] items as leads, not facts.

## 1. Comparison table

| Aspect | Jenkins | Backstage | Grafana | MCP (Registry `server.json` / MCPB `manifest.json`) | HashiCorp (Terraform / Vault / go-plugin) | Airbyte / Steampipe |
|---|---|---|---|---|---|---|
| Manifest | `META-INF/MANIFEST.MF` in `.hpi`, generated from Maven POM (`Plugin-Dependencies`, `Jenkins-Version` [M]) | `package.json` with a `backstage` field (`role`, `pluginId`, `pluginPackages`, `peerModules`, `features`) plus `configSchema` | `plugin.json` (`type`, `id`, `info.version`, `includes`, `routes`, `backend`, `executable`, `dependencies`, `iam`) | `server.json` (name, version, packages, remotes). `manifest.json` (server, user_config, tools, compatibility) | Provider schema served over gRPC. `terraform-registry-manifest.json` (`protocol_versions`) | Airbyte: `spec` command output. Steampipe: Go `plugin.Plugin{TableMap,...}` |
| Capability declaration | Code-level `@Extension` points. No declarative capability list | Code-level: `createBackendPlugin`, extension points. Permissions declared in code | `type` plus `includes[]` plus backend handlers (query, resource, health, stream) | MCPB `tools[]` (name, description) with `tools_generated`. Runtime `tools/list` with annotations (hints) | Provider schema: resources and data sources per provider | Airbyte `discover` → `AirbyteCatalog`. Steampipe `TableMap` |
| Permission / risk model | Host RBAC (`checkPermission`, `Jenkins.ADMINISTER`). Plugin must enforce it itself | Permission framework: plugin defines permissions, integrator policy decides, plugin enforces | `includes[].role`, `routes[].reqRole`/`reqAction`, `iam.permissions` (action/scope) for the plugin's own service account | Tool annotations `readOnlyHint`/`destructiveHint`/`idempotentHint`/`openWorldHint`, which are **untrusted hints** | None per op. Terraform plan/apply is the human gate | None. Read-only by nature (sources) |
| Config + secrets | Credentials plugin: store **credential ID**, resolve at runtime. Domains + scopes. `Secret` type encrypted on disk | `configSchema` with `@visibility secret`. Values via `$env`/`$file`/`$include` | `jsonData` (clear) vs `secureJsonData` (encrypted, write-only from browser). Routes template `{{ .SecureJsonData.x }}` server-side | `isSecret` on env vars/headers (`server.json`). `sensitive: true` in `user_config`, substituted as `${user_config.x}` | Vault: secrets live in Vault. Terraform: provider config attributes can be `sensitive` [M] | `airbyte_secret: true` masks in UI/API |
| Access test | Form validation `doCheck*`/"Test Connection" pattern (a source of many CVEs) | None standard | `CheckHealth` ("Save & Test"), also exposed over HTTP API | None in manifest. MCP `ping`/initialize only [M] | `ConfigureProvider` errors at plan time [M] | `check(config)` → `SUCCEEDED`/`FAILED` + message |
| Versioning / compat | `Jenkins-Version` minimum core + `Plugin-Dependencies: a:1.13` [M for Jenkins-Version] | npm semver. Backstage release line | `info.version` semver. `dependencies.grafanaDependency` (node-semver range, required) | `version` semver. MCPB `compatibility.claude_desktop`/`platforms`/`runtimes` ranges | `protocol_versions`. Lock file pins version + hashes | Airbyte protocol version [M]. Steampipe SDK major in import path |
| Signing / integrity | Update-center metadata signed with a cert chained to a root bundled in Jenkins. Per-plugin artifacts are not individually signed by authors [M] | None beyond npm | Mandatory signing (MANIFEST.txt with SHA256 per file + signature). Levels: private/community/commercial | Registry verifies **namespace ownership** (GitHub OAuth, DNS/HTTP ed25519 proof), not code. MCPB optional PKCS#7 signature (self-signed allowed). `fileSha256` for mcpb packages | Terraform: GPG-signed SHA256SUMS, checked at `init`. Lock file TOFU. Vault: catalog SHA256 checked at register + exec | Airbyte: Docker images [M]. Steampipe: Hub/OCI [M] |
| Who may install | Overall/Administer ("Everything") | Whoever builds/deploys the backend (code change) | Server Admin (install). Org Admin (configure apps) | End user (desktop). Registry is a metadata catalog | Whoever writes config / Vault operator | Workspace admin [M] |
| Isolation | Same JVM, own ClassLoader per plugin (no security boundary) | Same Node process per backend [M]. Can split into several backends | Backend = separate process via go-plugin/gRPC. Frontend sandbox (optional) | Separate process (stdio) or remote (HTTP) | Separate process via go-plugin. Vault uses mTLS | Airbyte: container per connector [M]. Steampipe: gRPC plugin process |
| Notable failures | Many advisories: plaintext secrets, CSRF + missing permission check on "test connection" → credential capture/SSRF | Scaffolder sandbox escape (vm2) RCE [M] | CVE-2021-43798 path traversal via `/public/plugins/<id>/` (KEV-listed) | postmark-mcp (Sep 2025) malicious npm BCC exfil. CVE-2025-6514 mcp-remote RCE (CVSS 9.6) | (none researched) | (none researched) |

## 2. Per-system detail

### 2.1 Jenkins
Sources:
- https://www.jenkins.io/doc/developer/plugin-development/dependencies-and-class-loading/ [V]
- https://www.jenkins.io/doc/developer/security/ [V]
- https://www.jenkins.io/doc/developer/security/secrets/ [V]
- https://github.com/jenkinsci/credentials-plugin/blob/master/docs/consumer.adoc [V]
- https://www.jenkins.io/doc/book/using/using-credentials/ [V]
- https://www.jenkins.io/doc/book/security/access-control/permissions/ [V]
- https://www.jenkins.io/doc/book/managing/plugins/ [V]
- https://www.jenkins.io/blog/2021/03/15/update-center-certificate-rotation/ (search snippet only)
- https://jenkins.io/blog/2017/01/10/security-warnings/ (search result only)
- Advisories: https://jenkins.io/security/issue/SECURITY-983, https://www.jenkins.io/security/advisory/2018-09-25/, https://www.jenkins.io/security/advisory/2019-07-11/ (via search snippets)

- **Manifest:** Maven POM dependencies become the `Plugin-Dependencies` manifest header, e.g. `Plugin-Dependencies: a:1.13,b:1.6` [V]. The `Jenkins-Version` (minimum core) header was not confirmed today [M].
- **Capabilities:** These are code-level `@Extension` implementations of `ExtensionPoint`s [M, well known]. There is no declarative list of operations or risk.
- **Permissions:** Host RBAC is built from Permission, Authentication, ACL and AccessControlled. Plugins must call `checkPermission` on sensitive operations, including `doCheck` form validation and `doAutoComplete`. The docs suggest `Jenkins.ADMINISTER` as the fallback [V]. Hiding UI elements is not a substitute for a check [V].
- **Credentials (key model to copy):**
  - Consumers persist only the credential ID (`IdCredentials.getId()`) and resolve it at runtime with `findCredentialById*` [V].
  - Listing uses domain requirements, e.g. `URIRequirementBuilder.fromUri(url)`, because "there could be duplicate IDs between domains" [V].
  - Listing does not access secrets and does not create usage records. Retrieval calls `CredentialsProvider.track(...)` for usage tracking [V].
  - Listing and validation are permission-gated (`ADMINISTER` with no item, `EXTENDED_READ`/`USE_ITEM` with an item) [V].
  - Scopes are Global and System. Credentials are encrypted with keys in `secrets/`, tied to the controller. The master key is unencrypted on disk, so this does not stop an attacker with file access [V].
  - Pipelines see only IDs [V].
- **Access test:** The "Test Connection" button is implemented as `doCheck*`/`doTest*` web methods [M on naming]. These are the root of a large CVE class (see below).
- **Signing and trust:** Update-center JSON is signed. Jenkins bundles a root cert, and a custom CA goes in `JENKINS_HOME/update-center-rootCAs`. The check can be disabled with `hudson.model.DownloadService.signatureCheck` (from search snippets, not fetched). Security warnings, with an ID, affected-version pattern and advisory URL, are published in update-center metadata and shown in the plugin manager (from search snippets, not fetched).
- **Who installs:** Overall/Administer, whose summary is "Everything". Admins can "Install and upload plugins that can run arbitrary code". If an untrusted user gets Administer, the instance "should be considered fully compromised" [V].
- **Isolation:** Each plugin has its own ClassLoader inside the same JVM. This separates names, not security [V/M: the same-JVM point is implied by the docs].
- **Lessons from advisories:**
  - Recurring pattern 1: CSRF plus missing permission check on form-validation or "test connection" endpoints. Attackers make Jenkins connect to an attacker URL using attacker-chosen credential IDs and so capture stored credentials (SSRF). Examples: SECURITY-983 / CVE-2019-10305 XL Deploy; Docker plugin CVE-2019-10340/10341; GitLab, Jira and HipChat plugins.
  - Recurring pattern 2: secrets stored in plaintext in job or config XML, visible with Extended Read.
  - Many advisories ship with no fix ("plugin abandoned").

### 2.2 Backstage
Sources:
- https://backstage.io/docs/tooling/package-metadata/ [V]
- https://backstage.io/docs/conf/defining/ [V]
- https://backstage.io/docs/conf/writing/ [V]
- https://backstage.io/docs/backend-system/architecture/plugins/ [V]
- https://backstage.io/docs/permissions/overview/ [V]
- https://backstage.io/docs/permissions/concepts/ [V]
- https://backstage.io/docs/permissions/writing-a-policy/ [V]

- **Manifest:** The `package.json` `backstage` field is "required for all Backstage packages" [V]. It contains:
  - `role`: `frontend-plugin`, `backend-plugin` or `backend-plugin-module`
  - `pluginId`, `pluginPackages`, `pluginPackage` (for modules), `peerModules`
  - `features`: export path → feature type, generated at prepack
- **Config schema:** A top-level `configSchema` (inline JSON schema or a path to `.json`/`.d.ts`). All package schemas are merged at validation, and `backstage-cli config:check` runs the check [V].
  - Visibility: `@visibility frontend | backend (default) | secret`. A `secret` value is backend-only and "may be excluded from logs". Declaring the same value `frontend` in one schema and `secret` in another is a merge error [V].
  - Values come from `$env`, `$file` and `$include` (with a `#key.path` fragment). They are loaded at startup only, not reloaded. The docs advise against hard-coding secrets and point to stores like Vault [V].
  - Secrets are references only by convention, through `$env`/`$file`.
- **Backend plugin:** `createBackendPlugin({pluginId, register(env){ env.registerInit({deps, init}) }})`, installed with `backend.add(...)` [V].
  - The docs describe plugins as independent "microservices" that "must never communicate with each other directly through code", and a deployment can be split into multiple backends [V].
  - Same-process co-hosting in one backend is my reading and was not stated on the page [M].
- **Permission framework:** Plugin authors declare permissions (a unique name plus optional attributes). Integrators write a policy (user, permission) → allow, deny or conditional. "Policies are responsible for decisions and plugins … for enforcing them." Conditional decisions are delegated back to the plugin, which can turn them into DB queries. By default, "endpoints are not protected" [V].
  - `attributes.action` ∈ create/read/update/delete was not confirmed today [M].
  - This shape maps directly onto a per-operation risk class.
- **Signing / trust / who installs:** None. Plugins are npm dependencies compiled into the deployer's app, so trust equals the supply chain of whoever builds the image.
- **Incidents:** Scaffolder template sandbox escape via vm2 → RCE (Oxeye, ~2022) [M, not verified today].

### 2.3 Grafana
Sources:
- https://grafana.com/developers/plugin-tools/reference/plugin-json [V]
- https://grafana.com/developers/plugin-tools/publish-a-plugin/sign-a-plugin [V]
- https://grafana.com/docs/grafana/latest/administration/plugin-management/plugin-sign/ [V]
- https://grafana.com/docs/grafana/latest/administration/plugin-management/ [V]
- https://grafana.com/developers/plugin-tools/key-concepts/backend-plugins/ [V]
- https://grafana.com/developers/plugin-tools/how-to-guides/data-source-plugins/add-authentication-for-data-source-plugins [V]
- https://pkg.go.dev/github.com/grafana/grafana-plugin-sdk-go/backend [partial]
- CVE-2021-43798 via tenable/wiz (search only)

- **`plugin.json` fields:**
  - `type`: app / datasource / panel / renderer
  - `id`
  - `info.version`: semver, plus `info.updated` and `info.build`
  - `state`: alpha / beta / stable / deprecated
  - `includes[]`: type dashboard/page/panel/datasource, with `role` and `action`
  - `routes[]`: `path`, `method`, `url`, `reqRole`, `reqAction`, `headers`, `body`, `tokenAuth`, `jwtTokenAuth`, `urlParams`
  - `backend` (bool), `executable` (binary looked up as `<exe>_<os>_<arch>`)
  - `dependencies.grafanaDependency`: **required**, node-semver range. `grafanaVersion` is deprecated.
  - `dependencies.plugins[]`
  - `iam.permissions[]`: `{action, scope}` (Grafana ≥10.3, behind a feature toggle). Grafana issues the plugin its own service-account token via env `GF_PLUGIN_APP_CLIENT_SECRET` [V]
- **Secrets:** `jsonData` is cleartext ("do not use … with sensitive data"). `secureJsonData` is encrypted server-side on save and never readable by the browser again; `secureJsonFields` only says whether a secret is set [V].
  - The data-source proxy injects secrets server-side via route templates `{{ .SecureJsonData.apiKey }}` / `{{ .JsonData.x }}` [V].
  - Backends read `DecryptedSecureJSONData` from instance settings [V].
  - **Pattern:** the manifest declares *where* a secret is used (header/url template). The host injects it, and the plugin frontend never sees it.
- **Health:** The health-check capability is called on "Save & Test" and is also exposed over the HTTP API for external polling [V].
  - Go SDK: `CheckHealth(ctx, *CheckHealthRequest) (*CheckHealthResult, error)` [V].
  - Status values `HealthStatusOk/Error/Unknown` and the Message/JSONDetails fields were not confirmed today [M].
- **Backend isolation:** Backends run as a "separate process", launched as a subprocess over gRPC (HashiCorp go-plugin). The plugin "can't crash your Grafana process" and only gets the interfaces passed to it [V].
  - Instances are cached per configuration until the config changes [V].
  - A frontend sandbox exists as an extra layer [V, details not read].
- **Signing:**
  - Grafana verifies every plugin's signature at startup. Statuses are Core / Invalid / Modified / Unsigned / Signed. Unsigned plugins are not loaded (error logged) [V].
  - `allow_loading_unsigned_plugins` (a list of plugin IDs [M on format]) overrides this, with a warning logged. It is unsupported in Grafana Cloud. Dev mode allows all [V].
  - `MANIFEST.txt` holds a signed message with plugin ID, version, signature type, key ID and SHA256 of every file, verified against a public key built into Grafana [V].
  - Levels:
    - **Private**: your own instances, bound to `rootUrls`, signed without review.
    - **Community**: OSS deps, catalog, reviewed.
    - **Commercial**: closed or commercial deps, catalog, reviewed.
    - Grafana signs its own plugins.
  - The signing token must belong to the account matching the plugin ID prefix [V].
- **Who installs:** Server Admin or Org Admin can use the catalog. For apps, Server Admin installs/updates/uninstalls and Org Admin configures, so install and configure are split [V].
- **Incident:** CVE-2021-43798, unauthenticated path traversal via `/public/plugins/<plugin-id>/../..`. Affects 8.0.0-beta1–8.3.0 and is on the CISA KEV list (secondary sources). The lesson is that the host's generic per-plugin routes are attack surface even for benign plugins.

### 2.4 MCP (Registry, MCPB, tool annotations)
Sources:
- https://modelcontextprotocol.io/specification/2025-06-18/server/tools [V]
- https://modelcontextprotocol.io/specification/2025-06-18/schema (ToolAnnotations) [V]
- https://raw.githubusercontent.com/modelcontextprotocol/mcpb/main/MANIFEST.md [V]
- https://raw.githubusercontent.com/modelcontextprotocol/mcpb/main/CLI.md [V]
- https://raw.githubusercontent.com/modelcontextprotocol/registry/main/docs/reference/server-json/generic-server-json.md [V]
- https://raw.githubusercontent.com/modelcontextprotocol/registry/main/docs/modelcontextprotocol-io/authentication.mdx [V]
- Incidents via search: Snyk / Qualys / DarkReading on postmark-mcp; JFrog on CVE-2025-6514 (secondary)

- **`server.json` (registry):**
  - `$schema`: versioned, e.g. `.../schemas/2025-12-11/server.schema.json`
  - `name`: namespaced, e.g. `io.github.user/x`
  - `version`
  - `packages[]`: `registryType` (npm/pypi/nuget/cargo/oci/mcpb), `identifier`, `version`, `transport` (stdio / streamable-http+url), `environmentVariables[]` with `isRequired`, `isSecret`, `default`, `choices`
  - `remotes[]`: `type`, `url`, `headers[]` with the same flags
  - `repository`
  - mcpb packages carry `fileSha256` [V]
- **Registry trust:** The registry verifies *namespace ownership* only:
  - `io.github.*` via GitHub OAuth device flow. Org namespaces need an org admin/owner.
  - Domains via an ed25519 public key in a DNS TXT record (`v=MCPv1; k=ed25519; p=...`) or `/.well-known/mcp-registry-auth` over HTTPS with no redirects.
  - The docs do not say the registry hosts, scans or signs code [V]. It is a metadata catalog, and package integrity is left to npm/PyPI/OCI.
- **MCPB `manifest.json`:**
  - `manifest_version` ("0.3"), `name`, `version` (semver)
  - `server{type: node|python|binary|uv, entry_point, mcp_config{command,args,env,platform_overrides}}`
  - `user_config{key: {type: string|number|boolean|directory|file, title, description, sensitive, required, default}}`
    - `sensitive: true` masks input and "stores it securely"
    - Values are substituted into `mcp_config` as `${user_config.key}`, so secrets reach the server as env vars or args
  - `tools[]` (`name`, `description`) and `tools_generated` (bool: more tools appear at runtime). Same pair for `prompts`.
  - `compatibility{claude_desktop: ">=0.10.0", platforms: [darwin|win32|linux], runtimes: {node|python: range}}`
  - `privacy_policies[]` (required if the extension connects to external services processing user data) [V]
- **MCPB signing:** `mcpb sign` produces a detached PKCS#7 SignedData appended to the ZIP between `MCPB_SIG_V1`/`MCPB_SIG_END`. X.509 certs should carry Code Signing EKU. Self-signed is allowed (dev) and `verify` only *warns* when self-signed. Verify reports validity, subject/issuer, dates and fingerprint [V].
  - Whether the host (Claude Desktop) enforces signatures or blocklists was not checked [unverified].
- **Tool annotations:** `readOnlyHint` (default false), `destructiveHint` (default **true**, meaningful only if not read-only), `idempotentHint` (default false), `openWorldHint` (default **true**). The schema says: "all properties in ToolAnnotations are **hints** … not guaranteed to provide a faithful description … Clients should never make tool use decisions based on ToolAnnotations received from untrusted servers." The tools page says clients "MUST consider tool annotations to be untrusted unless they come from trusted servers" [V].
  - Defaults are fail-safe: an unannotated tool counts as non-read-only, destructive and open-world.
- **Spec guidance:** There SHOULD be a human in the loop able to deny invocations. Clients SHOULD confirm sensitive operations, show inputs before calling, validate results before passing them to the LLM, time out calls and audit-log. Servers MUST validate inputs, enforce access control, rate-limit and sanitize outputs [V].
  - `tools/list_changed` lets a server change its tool set at runtime [V]. So a declared manifest tool list and runtime reality can diverge.
- **Isolation:** stdio servers are separate local processes with the user's privileges. Remote servers sit across HTTP.
- **Incidents (secondary sources):**
  - postmark-mcp (npm, Sep 2025): an impostor package (not published by Postmark) added a hidden BCC to an attacker address in v1.0.16 after earlier clean versions. It was the first malicious MCP server in the wild, and a rug pull via an unpinned update.
  - CVE-2025-6514: mcp-remote 0.0.5–0.1.15, a malicious remote server gets OS command execution on the client, CVSS 9.6, fixed in 0.1.16 per JFrog.

### 2.5 HashiCorp (Terraform providers, Vault plugins, go-plugin)
Sources:
- https://raw.githubusercontent.com/hashicorp/go-plugin/main/README.md [V]
- https://developer.hashicorp.com/terraform/registry/providers/publishing [V]
- https://developer.hashicorp.com/terraform/language/files/dependency-lock [V]
- https://developer.hashicorp.com/vault/docs/plugins/plugin-architecture [V]

- **go-plugin:** Plugins are subprocesses talking net/rpc or gRPC. A panic in a plugin doesn't crash the host. A basic protocol version can be bumped to invalidate old plugins. Plugins "can be verified with an expected checksum" and RPC can use TLS [V].
  - The handshake magic cookie being "not a security measure" is a README statement I recall but did not see in today's fetch [M].
- **Terraform:**
  - Every release must be GPG-signed. `SHA256SUMS` covers each zip plus the manifest, `SHA256SUMS.sig` is a binary GPG signature, and "Terraform will verify this during `terraform init`" [V].
  - `terraform-registry-manifest.json` declares `metadata.protocol_versions` (`["5.0"]` SDKv2, `["6.0"]` Framework) [V].
  - `.terraform.lock.hcl` pins `version` and multi-platform `hashes` (`h1:` content hash preferred, `zh:` legacy zip hash) and errors on mismatch. It is trust on first use: you verify once, then later runs must match. `-upgrade` reselects [V].
  - Tiers (official/partner/community) and their keys were not covered on the page [M].
  - Capabilities are declared by the provider schema (resources and data sources) [M, well known].
- **Vault:**
  - Plugins are registered in a catalog with a SHA256. The artifact is checked at registration *and again at each execution*.
  - The plugin directory cannot be a symlink.
  - Vault↔plugin traffic uses mutual TLS (AutoMTLS for HashiCorp-managed plugins). Vault passes a response-wrapping JWT at launch.
  - Only the catalog entry replicates; every node needs the binary [V].
  - Registration is an operator (sudo) action [M].

### 2.6 Airbyte / Steampipe
Sources:
- https://docs.airbyte.com/platform/understanding-airbyte/airbyte-protocol [V]
- https://docs.airbyte.com/platform/connector-development/connector-specification-reference [V]
- https://steampipe.io/docs/develop/writing-plugins [V]

- **Airbyte protocol:** Four commands:
  - `spec`: no input → `ConnectorSpecification` whose `connectionSpecification` is a JSON Schema used to validate config
  - `check(config)`: → `AirbyteConnectionStatus{status: SUCCEEDED|FAILED, message}`. If check succeeds, "all subsequent methods in the sync" are expected to succeed. A FAILED check is treated as a *user/config error*.
  - `discover(config)`: → `AirbyteCatalog` (streams with JSON schema)
  - `read(config, configured_catalog, state)`
  - Output goes to STDOUT (or a Unix socket) and logs to STDERR [V].
  - `"airbyte_secret": true` obfuscates a field in UI and API. `airbyte_hidden` and `multiline` also exist [V].
  - Connectors run as Docker images (linked page not read) [M].
  - This is the cleanest model for **spec → check → discover** as install-time steps: validate config, test access, then learn what is actually reachable with these creds.
- **Steampipe:** A plugin is Go code returning `*plugin.Plugin{Name, TableMap, DefaultTransform, SchemaMode static|dynamic, ConnectionConfigSchema}` and served over gRPC with `plugin.Serve` [V].
  - Connections live in HCL `.spc` files (`connection "x" { plugin = "..." }`), and service mode needs a restart to load new ones [V].
  - `SchemaMode: dynamic` means the capability set depends on the connection [V].
  - Hub/OCI distribution was not covered [M].

## 3. Patterns worth copying / traps

**Copy:**
1. **Store a credential reference, not the secret** (Jenkins credential IDs, Backstage `$env`/`$file`, Grafana `secureJsonData`).
   - The manifest declares credential *kind* and *where it is injected*.
   - The host resolves the reference at call time and logs usage (Jenkins `track()`).
   - Scope the reference to a target URL or domain (Jenkins domains) so a credential can't be replayed to another host.
2. **Host-side secret injection** (Grafana routes `{{ .SecureJsonData.x }}`). Where possible the host's HTTP adapter adds auth headers, so plugin code never holds the raw secret.
3. **spec → check → discover** (Airbyte), and **CheckHealth** exposed both on "Save & Test" and via API for monitoring (Grafana). Make the access test a first-class manifest operation with a typed OK/FAILED + message result, and classify a failed check as a config error.
4. **Plugin declares permissions; the host policy decides; enforcement happens at a choke point** (Backstage). For us, the manifest declares operation → risk class. The *host* (not the plugin) gates write/critical ops, because Backstage and Jenkins both show that leaving enforcement to plugin code fails.
5. **Fail-safe defaults** (MCP annotations default to destructive + open-world). An operation with no declared risk class should be treated as `critical`.
6. **Compatibility as a required semver range** against the host API version (Grafana `grafanaDependency` is required; MCPB `compatibility`; Terraform `protocol_versions`).
7. **Integrity:** a per-file SHA256 manifest signed by a trusted key (Grafana MANIFEST.txt), a lock file pinning version + hash (Terraform), and a re-check of the hash at every execution, not just install (Vault).
8. **Trust tiers:** first-party, reviewed third-party, and private/unsigned. Unsigned plugins are refused unless an admin explicitly allow-lists that plugin ID, with a logged warning (Grafana).
9. **Split install from configure** (Grafana: Server Admin installs, Org Admin configures). Keep both separate from *using* an operation.
10. **Out-of-process plugins** (Grafana/go-plugin/Vault/MCP stdio) give crash isolation and a narrow interface. Add mTLS or a per-launch token (Vault) if the channel is a socket.
11. **Central security-warnings feed** with affected-version patterns, surfaced in the admin UI (Jenkins update-center `warnings`).

**Traps:**
1. **Trusting self-declared risk.** The MCP spec explicitly says annotations from untrusted servers must not drive decisions. A third-party plugin's own "read-only" label is a claim, not a control. Verify it via review/signing tier, or enforce it with least-privilege credentials (read-only tokens).
2. **"Test connection" endpoints as SSRF and credential-exfil primitives** (dozens of Jenkins CVEs). The access test must use only the stored config and its bound target, require admin permission, and be CSRF-protected.
3. **Plaintext secrets in plugin config** (Jenkins). Never let plugins persist their own config blobs containing secrets.
4. **Same-process "isolation"** (Jenkins ClassLoaders, Backstage backends) is not a security boundary. Installing a plugin equals arbitrary code execution, so plugin install should be Jenkins-Administer-level.
5. **Runtime capability drift.** MCP `tools_generated`/`list_changed` and Steampipe dynamic schema let the runtime set differ from the manifest. Pin to the declared set and reject or flag undeclared operations.
6. **Unpinned updates / rug pulls / impostor packages** (postmark-mcp). Registry namespace verification proves who published, not that the code is safe. Pin versions + hashes and require re-approval on update.
7. **Self-signed signatures that only warn** (MCPB). A signature without a trust anchor policy is just a checksum.
8. **Host-generic plugin routes as attack surface** (Grafana CVE-2021-43798). Static or proxy routes the host exposes per plugin need their own hardening.
9. **Allow-by-default authorization** (Backstage: "endpoints are not protected" by default).
