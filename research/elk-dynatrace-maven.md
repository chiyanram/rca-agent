# ELK and Dynatrace as Observability backends, plus sandboxed Maven builds

Researched 2026-11-06 against current upstream docs. This follows `research/grafana-observability-apis.md` (Grafana stack first).
Items marked **(unverified)** come from source code, community posts or inference rather than a reference page. Check them before relying on them.

## TL;DR

- **ELK logs:** ES|QL (`POST /_query`, `POST /_query/async`) is the best fit for an agent. It is one text query with `GROK`/`DISSECT` for parsing raw lines at query time, `STATS ... BY CATEGORIZE(message)` for digests, and a `filter` body field that bounds `@timestamp`. Use Query DSL `_search` as a fallback on older clusters (< 8.11).
- **ELK alerts:** Kibana has **no supported public API that lists active alert instances**; the GitHub issue asking for one is still open. Read the alerts-as-data indices (`.alerts-*`, `kibana.alert.status: active`) with the same read-only ES key, or fall back to listing rules (`GET /api/alerting/rules/_find`).
- **Dynatrace:** a single DQL endpoint (`/platform/storage/query/v1/query:execute` + `query:poll`) covers logs, spans, metrics and problems (`fetch dt.davis.problems`). Queries are billed by GiB scanned, so every query must carry a timeframe and a scan limit. Problems API v2 (`/api/v2/problems`, classic token) still works for listing open problems.
- **Trace IDs:** Dynatrace log enrichment writes `dt.trace_id` (or `trace_id` on Grail) as 32-hex W3C trace IDs when W3C Trace Context is on. These are the same IDs ECS `trace.id` and OTel/Tempo use, so cross-backend correlation is a string-normalisation problem (case, dashes) rather than a mapping problem.
- **One adapter interface is viable** if it is split by signal: the configuration routes `alerts`, `logs`, `metrics` and `traces` each to a backend, and a per-source **log field map** says which field or parse rule yields level, logger, trace id and service. Add two ops: `listAlerts` and `logPatterns` (digest).
- **Maven sandbox:** keep credentials **outside** the sandbox. A repository-manager proxy (Nexus/Artifactory/etc.) or a pre-warmed `~/.m2` holds the private-feed creds, and the sandbox `settings.xml` has a single credential-less `<mirror mirrorOf="*">`, or the build runs with `-o`. Use ECJ `-proceedOnError` (not `javac`) for the partial-compile fallback.

---

## A. Elasticsearch / Kibana

**Query APIs**
- **ES|QL** `POST /_query` (GA 8.11). Body: `query`, `filter` (Query DSL pre-filter), `params` (`?` placeholders, so no string injection), `columnar`, `time_zone` (9.4+). Needs index privilege `read`. Response: `columns` + `values`, `is_partial`. [ref](https://www.elastic.co/docs/api/doc/elasticsearch/operation/operation-esql-query)
- **Async ES|QL** `POST /_query/async`. `wait_for_completion_timeout` defaults to 1s, `keep_alive` to 5 days, and `keep_on_completion` to false. The response returns an `id` to poll. [ref](https://www.elastic.co/docs/api/doc/elasticsearch/operation/operation-esql-async-query)
- **Limits:** 1,000 rows by default and 10,000 max regardless of `LIMIT`, but `STATS`/`WHERE` run over all data. Text fields act like case-sensitive keywords unless you use `MATCH`/`QSTR`/`KQL()`. Referencing an unmapped field is an error by default. The same field must have the same type across all indices. [ref](https://www.elastic.co/docs/reference/query-languages/esql/limitations)
- **Query DSL** `_search` and **async search** (`_async_search`) remain the fallback, and they are what `categorize_text` needs. [ref](https://www.elastic.co/docs/api/doc/elasticsearch/operation/operation-async-search-submit)

**Time-bounded queries over data streams.** Always send `filter: {range: {"@timestamp": {gte, lt}}}` with the ES|QL body (or a `WHERE @timestamp >= ... AND < ...` clause). The adapter should inject this from the op's time window, so a pass-through query never runs unbounded. `FROM logs-*` targets data streams by pattern.

**Field discovery (`listLabelValues` equivalent)**
- `POST /<pattern>/_field_caps?fields=*` with `index_filter: {range: {"@timestamp": {gte: ...}}}` restricts results to backing indices that can hold the window (best effort). Needs `read` + `view_index_metadata`. [ref](https://www.elastic.co/docs/api/doc/elasticsearch/operation/operation-field-caps)
- Values for a field: `FROM logs-* | WHERE @timestamp > ... | STATS c = COUNT(*) BY service.name | SORT c DESC | LIMIT 50`. On DSL, use a `terms` agg instead.

**Deterministic digests**
- **ES|QL `CATEGORIZE`**: `STATS count = COUNT(*) BY CATEGORIZE(message)`. Preview in 9.0 and GA from 9.1/Serverless. It **requires a Platinum license**. Options are `analyzer`, `output_format` (`regex`|`tokens`) and `similarity_threshold` (default 70). It must be the first grouping. Pair it with `SAMPLE` for one raw line per category. [ref](https://www.elastic.co/docs/reference/query-languages/esql/functions-operators/grouping-functions/categorize)
- **`categorize_text` aggregation** (DSL) returns `key`, `regex` and `max_matching_length` per bucket, and `categorization_filters` strip ids before grouping. It is memory-heavy, so the docs advise async search and nesting it under a `sampler`. [ref](https://www.elastic.co/docs/reference/aggregations/search-aggregations-bucket-categorize-text-aggregation)
- Kibana **Log pattern analysis** (AIOps) is the UI over the same algorithm and is useful for deep links. [ref](https://www.elastic.co/docs/explore-analyze/machine-learning/machine-learning-in-kibana/xpack-ml-aiops)
- **Implication:** server-side categorisation is licence-gated and algorithm-versioned (8.3 changed it). The agent's own digest (normalise → template → group), run over the fetched error lines, stays the **portable, reproducible** path. Use the backend's categoriser as an optional accelerator.

**Parsing raw lines at query time** (when only `@timestamp` + `message` are reliable)
- ES|QL `DISSECT message "%{ts} %{level} [%{thread}] %{logger} - %{msg}"` is delimiter-based and cheap. `GROK message "%{LOGLEVEL:level} ..."` is regex-based; typed captures look like `%{NUMBER:n:int}`, and a failed match gives `null`. [grok](https://www.elastic.co/docs/reference/query-languages/esql/commands/grok) · [dissect](https://www.elastic.co/docs/reference/query-languages/esql/commands/dissect)
- DSL: `runtime_mappings` in the search request (Painless with `grok`/`dissect` helpers) defines search-time fields with no reindex. [ref](https://www.elastic.co/docs/manage-data/data-store/mapping/runtime-fields)
- Parsed fields are not indexed, so filter on the indexed field first (`WHERE MATCH(message, "ERROR")`) and parse afterwards.

**ECS conventions and gaps.** The expected fields are `log.level`, `log.logger`, `service.name`, `trace.id` (32 hex), `span.id` and `transaction.id`. [tracing](https://www.elastic.co/docs/reference/ecs/ecs-tracing) · [log](https://www.elastic.co/docs/reference/ecs/ecs-log). When they are missing, treat the field mapping as config (section C): per data stream, either a field name or a `DISSECT`/`GROK` rule applied to `message`. Also allow a trace-id regex, e.g. `\[!dt dt\.trace_id=([0-9a-fA-F]{32})` for Dynatrace-enriched lines. Never let the model guess field names; call `field_caps` first.

**Alerts (`listAlerts`)**
- Public Kibana alerting API covers **rules**, not alert instances: `GET /api/alerting/rules/_find`, `GET /api/alerting/rule/{id}`, plus mute/snooze per alert. [group](https://www.elastic.co/docs/api/doc/kibana/group/endpoint-alerting) The request for a supported "list alerts" API is still open ([elastic/kibana#152345](https://github.com/elastic/kibana/issues/152345)).
- **Alerts-as-data:** search alias `.alerts-{context}.{dataset}-{space}` (or `.alerts-*`) with `term kibana.alert.status: active`, using `kibana.alert.rule.uuid` and `@timestamp`. Do not change these mappings. [ref](https://www.elastic.co/docs/explore-analyze/alerting/alerts/query-alerts) Security detections have their own `POST /api/detection_engine/signals/search`.
- Kibana **alerting v2** (preview) writes to a different stream (`.rule-events` / `.alerts-events-*`; `episode.status`). Its naming is still moving between doc builds, so treat it as a second shape to support later **(unverified)**.
- **Watcher** (`GET _watcher/_query/watches`) is the older, ES-native mechanism. It has no "firing alert" state beyond watch history (`.watcher-history-*`), so it is low priority.

**Deep links.** Discover's locator (`DISCOVER_APP_LOCATOR`) takes `timeRange`, `query` (KQL or `{esql: "..."}`), `filters` and `dataViewId`, and serialises them to `/app/discover#/?_g=(time:(from:'…',to:'…'))&_a=(…)` in rison. [source](https://github.com/elastic/kibana/blob/main/src/platform/plugins/shared/discover/common/app_locator.ts) The exact `_a` shape is internal and changes across versions, so build links with absolute ISO times and test each target version **(unverified)**.

**Auth**
- API key: `POST /_security/api_key` with `role_descriptors: {rca: {indices: [{names: ["logs-*", ".alerts-*", "traces-apm*"], privileges: ["read", "view_index_metadata"]}]}}` and an `expiration`. The effective rights are the intersection with the owner's rights. Send it as `Authorization: ApiKey <encoded>`. [ref](https://www.elastic.co/docs/api/doc/elasticsearch/operation/operation-security-create-api-key)
- JWT realm: `access_token` type (8.7+) suits OAuth client-credentials. Send `Authorization: Bearer <jwt>` + `ES-Client-Authentication: SharedSecret <s>`. [ref](https://www.elastic.co/docs/deploy-manage/users-roles/cluster-or-deployment-auth/jwt) OIDC realm is for interactive Kibana SSO, not the agent.

**APM traces.** Elastic APM / EDOT data lands in `traces-apm*` data streams (ECS `trace.id`, `transaction.*`, `span.*`). [ref](https://www.elastic.co/docs/solutions/observability/apm/data-streams) A trace is fetched with `FROM traces-apm* | WHERE trace.id == ?`, so `getTrace` is a query, not a dedicated endpoint.

**MCP.** The standalone `elastic/mcp-server-elasticsearch` is deprecated (security fixes only) ([#219](https://github.com/elastic/mcp-server-elasticsearch/issues/219)). Its successor is the **Agent Builder MCP endpoint** at `{KIBANA}/api/agent_builder/mcp` (GA 9.3, preview 9.2), authenticated by API key (Stack) or OAuth 2.1 (Serverless only). Read-only behaviour comes from the key's privileges plus `feature_agentBuilder.read`, not from a tool allowlist. [ref](https://www.elastic.co/docs/explore-analyze/ai-features/agent-builder/mcp-server) This is useful for prototypes. The adapter should still call ES directly, because it needs to control time windows and digests.

## B. Dynatrace

**DQL query API** (Grail): `https://{env}.apps.dynatrace.com/platform/storage/query/v1/` with `query:execute` (POST), `query:poll` (GET `?request-token=`), `query:cancel`, `query:verify` and `query:autocomplete`. [ref](https://docs.dynatrace.com/docs/dynatrace-api/platform-api/platform-storage-query-v1) · [execute](https://docs.dynatrace.com/docs/dynatrace-api/platform-api/platform-storage-query-v1/query-execute-post)
- Body: `query`, `defaultTimeframeStart`/`End` (both required, or they are ignored; a timeframe in the query wins), `defaultScanLimitGbytes`, `maxResultRecords`, `maxResultBytes`, `fetchTimeoutSeconds`, `requestTimeoutMilliseconds`, `enforceQueryConsumptionLimit` and `timezone` (UTC).
- Returns 200 with the result if it finishes within the request timeout, otherwise 202 + `requestToken`. `state` ∈ NOT_STARTED/RUNNING/SUCCEEDED/RESULT_GONE/CANCELLED/FAILED. `result.metadata.grail.scannedBytes` and `notifications` come back with the result. 429 is possible, but no numeric rate limit is documented.
- **Auth:** `Authorization: Bearer <platform token or OAuth token>`. Scopes: `storage:logs:read`, `storage:spans:read`, `storage:metrics:read`, `storage:events:read`, `storage:entities:read` and `storage:buckets:read` (bucket read is needed alongside data reads). **Platform tokens** are long-lived, user- or service-user-bound and capped by that user's permissions, and can expire or be environment-restricted. [ref](https://docs.dynatrace.com/docs/manage/identity-access-management/access-tokens-and-oauth-clients/platform-tokens) OAuth clients (client-credentials) suit a server. Bucket-level conditions can narrow `storage:logs:read`.

**Signals in DQL**
- Logs: `fetch logs, from: …, to: … | filter loglevel == "ERROR"`. Fields include `content`, `loglevel`, `status`, `log.source`, `trace_id` (32 hex) and `span_id` (16 hex). [semantic dictionary](https://docs.dynatrace.com/docs/semantic-dictionary/model/log) Use `parse content, "<DPL pattern>"` when fields are missing.
- Patterns: the Logs app's **Patterns (preview)** mode groups similar lines and emits DPL that can be reused in `parse`. It has no DQL command of its own, so digests stay agent-side. [ref](https://docs.dynatrace.com/docs/analyze-explore-automate/logs/lma-logs-app/patterns)
- Spans: `fetch spans | filter trace.id == toUid("<hex>")` **(the `toUid` form is from a community answer; verify)**. `request.is_root_span` marks entry spans. [ref](https://docs.dynatrace.com/docs/observe/application-observability/distributed-tracing/advanced-tracing-analytics) The Distributed Tracing app caps scans at 50 GB / 1,000 spans. [limits](https://docs.dynatrace.com/docs/analyze-explore-automate/distributed-tracing/limits)
- Metrics: `timeseries avg(<metric.key>), by: {dt.entity.service}, from: …`.

**Problems → alerts**
- Classic: `GET https://{env}.live.dynatrace.com/api/v2/problems?problemSelector=status("open")&from=now-2h` uses a classic token with scope `problems.read`. The default window is 2h, paging uses `nextPageKey`, and v1 has been deprecated since 1.243. [ref](https://docs.dynatrace.com/docs/dynatrace-api/environment-api/problems-v2/problems/get-problems-list)
- Grail: `fetch dt.davis.problems, from: now()-24h | filter event.status == "ACTIVE" and not dt.davis.is_duplicate == "true"`. These are update **events**, so take the latest record per `event.id` (sort by timestamp, then dedup) before filtering. `display_id` is the human `P-…` id. [ref](https://docs.dynatrace.com/docs/dynatrace-intelligence/use-cases/dynatrace-intelligence-dql-examples)
- Prefer Grail (one token type, one API). Keep v2 as a fallback for environments without Grail problems.

**Trace IDs.** OneAgent propagates W3C `traceparent`/`tracestate` (plus proprietary `x-dynatrace`), and the trace ID shown in Dynatrace is the W3C trace-id. [ref](https://docs.dynatrace.com/docs/observe/application-observability/distributed-traces/context-propagation) Log enrichment injects `dt.trace_id`, `dt.span_id` and `dt.entity.process_group_instance`: via MDC (`%X{dt.trace_id}`) for Logback/Log4j, or as an inline `[!dt dt.trace_id=…,dt.span_id=…]` prefix for unstructured lines. Enrichment works even when the logs ship to another backend, e.g. ELK. [ref](https://docs.dynatrace.com/docs/observe-and-explore/logs/lma-log-enrichment) Values may be upper- or lower-case hex, so normalise to lower-case 32-hex before cross-backend lookup.

**Deep links.** The AppShell **intents** mechanism generates links via `getIntentLink` (`@dynatrace-sdk/navigation`). Known intents include `dynatrace.notebooks/view-query` (payload `dt.query`) and `dynatrace.distributedtracing/view-trace`; the URL form is `{env}/ui/intent/<app>/<intent>#<url-encoded JSON>` **(seen in MCP-server source, not reference docs)**. [ref](https://developer.dynatrace.com/develop/guides/navigation/intents/about-intents/)

**Cost and limits.** Query consumption = GiB of uncompressed data scanned × the rate-card price, visible in `dt.system.events` (`BILLING_USAGE_EVENT`). [ref](https://docs.dynatrace.com/docs/license/capabilities/events/dps-events-query) `fetch` defaults to a 500 GB scan limit, and the Logs app defaults to 1,000 records. The adapter should always set a timeframe, `defaultScanLimitGbytes` (e.g. 10–50), `maxResultRecords` and `enforceQueryConsumptionLimit: true`, and record `scannedBytes` on the Finding.

**MCP.** Dynatrace hosts a remote MCP server at `https://{env}.apps.dynatrace.com/platform-reserved/mcp-gateway/v0.1/servers/dynatrace-mcp/mcp`. It needs `mcp-gateway:servers:invoke` + `:read` plus `storage:*:read`, takes a platform token (recommended) or a confidential OAuth client, and its tools are DQL generate/run, problems, entities and forecasting. [ref](https://docs.dynatrace.com/docs/dynatrace-intelligence/dynatrace-mcp) The local `dynatrace-oss/dynatrace-mcp` is deprecated in its favour, and its local-only tools included Slack/email sending. **No documented read-only mode exists**, so read-only rests entirely on token scopes. Issue a token with read scopes only, and none of `automation:*`, `document:*:write` or `davis-copilot:*` unless needed.

## C. One adapter across Grafana, ELK and Dynatrace

**Per-signal routing.** Config, not code, picks the backend per signal:

```yaml
observability:
  alerts:  { backend: dynatrace }          # or alertmanager | grafana | kibana
  logs:    { backend: elk, source: app-logs }
  metrics: { backend: prometheus }
  traces:  { backend: dynatrace }          # or tempo | elastic-apm
  backends:
    elk:        { url: …, auth: apikey-ref }
    dynatrace:  { url: …, auth: platform-token-ref, scanLimitGb: 20 }
    prometheus: { url: … }
  logSources:
    app-logs:
      target: "logs-app-*"                 # data stream / bucket / LogQL selector
      fields:                              # field name OR parse rule per role
        level:   { parse: dissect, pattern: "%{ts} %{level} [%{thread}] %{logger} - %{msg}", from: message }
        logger:  { parse: same }
        traceId: { regex: "dt\\.trace_id=([0-9a-fA-F]{32})", from: message, normalise: lowerhex }
        service: { field: data_stream.dataset }
        message: { field: message }
```

The adapter compiles `fields` into the backend's native form: ES|QL `DISSECT`/`GROK`, DQL `parse`, or LogQL `| pattern`/`| regexp`. The agent therefore always sees canonical `level`, `logger`, `traceId`, `service` and `message` columns. Raw native queries still pass through, with the canonical projection appended.

**Op changes**
- `listAlerts(window, filter?)`: new, since alert listing is the Investigation entry point. Back it with Alertmanager `/api/v2/alerts`, Kibana `.alerts-*` search, or Dynatrace `dt.davis.problems` / Problems v2. `parseAlert` then normalises the result to the same Alert shape.
- `logPatterns(query, window, limit)`: new. It returns `{template, count, firstSeen, lastSeen, sampleLine, sampleTraceIds, loggers}`. The default implementation is agent-side (fetch error lines, then template them deterministically), so results are reproducible and backend-neutral. An optional backend accelerator can use `CATEGORIZE` or the Loki/Dynatrace pattern features.
- `listLabelValues` → generalise to `listFields(signal, window)` + `listFieldValues(field, window)`. ELK needs field discovery (`_field_caps`) before values.
- `getTrace(traceId, window)` must accept a trace id from *any* source. Normalise to lower-case 32-hex. If the trace backend has no hit, return "not found in <backend>" as a Finding, not an error.
- `deepLink` is per backend, and may legitimately return none (Dynatrace intents and Kibana `_a` are version-fragile).
- Every result carries `{backend, nativeQuery, window, cost?: scannedBytes}` so Findings stay citable.

**Cross-backend correlation.** Error line in ELK → `traceId` via the field map → `getTrace` on the traces backend (Dynatrace/Tempo/APM) → span service and endpoint → `queryMetrics` on Prometheus for that service. The shared key is the W3C trace-id. Correlation fails only when enrichment is off, so `logPatterns` should report the fraction of lines with a traceId.

## D. Maven (and Gradle) builds in an isolated sandbox

**Versions (2026-11):** Maven 3.10.0 (2026-10-01) is the latest GA. Maven 4.0.0 is still at rc-7, and it adds a project-local `.mvn/settings.xml`. Gradle is at 9.8.2. `maven-dependency-plugin` is at 3.11.0, and the Surefire docs cover 3.6.1. (Source: `gh api repos/<o>/<r>/releases`, plugin sites.)

**Private feeds without exposing secrets to built code.** Build code (tests, plugins, annotation processors, `exec`) runs with the build's environment and filesystem. So any credential *inside* the sandbox (`settings.xml`, `${env.X}` interpolation [ref](https://maven.apache.org/settings.html), `MVNW_PASSWORD`) is readable by the code under test. Options, best first:
1. **Resolving proxy outside the sandbox.** A repository manager or a small caching proxy holds the upstream credentials: Azure Artifacts PAT with Packaging-read ([ref](https://learn.microsoft.com/azure/devops/artifacts/maven/project-setup-maven)), GitHub Packages token with `read:packages` ([ref](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-apache-maven-registry)), GitLab `Private-Token`/`Deploy-Token`/`Job-Token` header via `<httpHeaders>` ([ref](https://docs.gitlab.com/user/packages/maven_repository/)), or Nexus/Artifactory users. The sandbox `settings.xml` has one `<mirror><mirrorOf>*</mirrorOf><url>http://proxy.internal/…</url></mirror>` with no `<server>`. Egress is limited to the proxy, and the proxy is read-only and scoped per Target repo. [mirror](https://maven.apache.org/guides/mini/guide-mirror-settings.html)
2. **Pre-warmed local repo + offline.** Resolve outside the sandbox (with creds), mount `~/.m2/repository` read-only (or copy it), then run `mvn -o`. `dependency:go-offline` resolves "all project dependencies, including plugins and reports". Known gaps: providers and plugins resolved dynamically at execution time (e.g. surefire's JUnit provider), extensions, and reactor modules (`excludeReactor=true` by default) are missed. Warm up by running the real goals once outside the sandbox (e.g. `mvn -B verify`), not only `go-offline`. [go-offline](https://maven.apache.org/plugins/maven-dependency-plugin/go-offline-mojo.html)
3. Short-lived token inside the sandbox: only acceptable when the token is read-only, minutes-lived and feed-scoped. It is still exfiltratable.

**Maven Wrapper.** `./mvnw` downloads the `distributionUrl` from `.mvn/wrapper/maven-wrapper.properties` (default type `only-script`, needs curl/wget). It honours `MVNW_REPOURL` and the `settings.xml` mirror, and `distributionSha256Sum` verifies the download. [ref](https://maven.apache.org/tools/wrapper/) In the sandbox, pre-cache `~/.m2/wrapper/dists` or point `MVNW_REPOURL` at the proxy. Prefer the wrapper's pinned version over the image's `mvn`.

**Narrow builds**
- Multi-module: `mvn -pl <module> -am` builds the module plus what it depends on. `-amd` also builds dependents, which is the set to re-test after a change. [ref](https://maven.apache.org/guides/mini/guide-multiple-modules.html)
- Tests: `-Dtest=FooTest,Bar*#method` (method selection needs JUnit 4.x/TestNG per the docs; JUnit 5 via the platform provider also works in practice **(unverified)**). Add `-Dsurefire.failIfNoSpecifiedTests=false` so modules without matches don't fail. [ref](https://maven.apache.org/surefire/maven-surefire-plugin/examples/single-test.html)
- Map changed `src/main/.../Foo.java` → candidate tests by naming (`FooTest`, `FooIT`) plus reverse references (grep or the code index). Fall back to the module's whole suite.

**Partial-compile fallback (private deps unresolvable)**
- Build a classpath from whatever resolved: `dependency:build-classpath` fails as a whole if any artifact is missing, so walk the POM's declared coordinates and keep the jars present in the local repo.
- `javac` stops before code generation once errors are reported, and missing types show up as `cannot find symbol`. That is fine as a **diagnostic**: keep only errors located in changed lines/files, and ignore those that trace to missing packages.
- Eclipse ECJ `-proceedOnError` keeps compiling and writes class files with problem methods. This makes it the better "did my change type-check against what is available" tool. [ref](https://help.eclipse.org/latest/topic/org.eclipse.jdt.doc.user/tasks/task-using_batch_compiler.htm)
- jdtls (v1.63.0) imports through m2e. Missing artifacts surface as pom and unresolved-type diagnostics, but the rest of the project still gets diagnostics. Set `java.import.maven.offline.enabled: true` so it never tries to fetch. [vscode-java settings](https://github.com/redhat-developer/vscode-java/blob/main/package.json)
- A partial compile must be labelled as such in the Fix proposal ("compiled against N/M deps; tests not run").

**Gradle parity**
- Repo override: an init script (`-I` or `GRADLE_USER_HOME/init.d/*.init.gradle(.kts)`) can strip non-approved repositories and add the proxy for all projects. Use `settingsEvaluated { pluginManagement/dependencyResolutionManagement }` for settings-level repos. [ref](https://docs.gradle.org/current/userguide/init_scripts.html)
- `--offline` uses the dependency cache only. `-m/--dry-run` lists the tasks that would run without executing them. `:module:test --tests 'com.x.FooTest'` filters tests. `-p`/task paths scope modules. [ref](https://docs.gradle.org/current/userguide/command_line_interface.html)
- Builds are code (`build.gradle(.kts)` executes at configuration time), so the "no secrets in sandbox" rule matters even more than for Maven.

**Detecting build tool and Java version**
- Tool: `mvnw`/`pom.xml` → Maven. `gradlew`/`settings.gradle(.kts)`/`build.gradle(.kts)` → Gradle. Prefer the wrapper. Both present → ask the Service registry/config.
- Java: Maven `maven.compiler.release` / `<release>` / `maven.compiler.source|target` / `java.version` (Spring Boot parent) / `jdk.version` (Micronaut parent) **(property names per parent POMs; verify per project)**, plus `.mvn/jvm.config` and `toolchains.xml`. [toolchains](https://maven.apache.org/guides/mini/guide-using-toolchains.html) Gradle: `java { toolchain { languageVersion = JavaLanguageVersion.of(N) } }` or `sourceCompatibility`. [ref](https://docs.gradle.org/current/userguide/toolchains.html) Repo hints: `.java-version`, `.sdkmanrc`, `.tool-versions`, and the CI workflow `java-version`. Resolve via the effective model (`mvn -o help:evaluate -Dexpression=maven.compiler.release -q -DforceStdout`) when the parent POM is available.

## Open questions

- Is the Kibana alerts-as-data schema stable enough to depend on, or should ELK `listAlerts` wait for alerting v2 GA?
- Licence: is `CATEGORIZE` (Platinum) available in target clusters? This doesn't block anything, because agent-side digest is the default.
- Dynatrace: confirm the `toUid()` trace filter and the intent URL format against a live tenant. Pick a per-Investigation scan budget.
