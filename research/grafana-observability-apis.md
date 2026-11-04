# Grafana stack APIs for an RCA agent (+ Dynatrace / App Insights glance)

Ticket: #6 · Map: #1 · Researched 2026-11-04 against "latest" upstream docs.

## TL;DR

- **Alert in:** Alertmanager `webhook_config` POSTs a stable JSON payload (`"version": "4"`): group fields plus `alerts[]` with `labels`, `annotations`, `startsAt`, `generatorURL`, `fingerprint`. Grafana-managed alerts use the same shape plus Grafana-only fields (`orgId`, `values`, `dashboardURL`, `panelURL`, `silenceURL`, `imageURL`), with its own `"version": "1"`. Accepting both is easy because the core fields match.
- **Evidence out:** Loki (`/loki/api/v1/query_range`, LogQL), Prometheus (`/api/v1/query_range`, PromQL), and Tempo (`/api/search` with TraceQL, `/api/traces/<id>`) are plain HTTP GET APIs with JSON responses. Each also has label/tag discovery endpoints, which an agent needs so it doesn't guess label names.
- **Official Grafana MCP server exists:** `grafana/mcp-grafana` v2.2.0 (2026-11-02). It covers Prometheus, Loki, Tempo, alerting, dashboards and more, routes through Grafana's datasource proxy, and authenticates with a service-account token. It is a strong candidate to back the Grafana adapter (or to use as-is in prototypes). The trade-off is that the test bed needs a Grafana instance in front of the backends.
- **Test bed shortcut:** `grafana/docker-otel-lgtm` v0.39.0 bundles an OTel Collector, Prometheus, Loki, Tempo, Pyroscope and Grafana in one dev image, with OTLP on 4317/4318. It has **no Alertmanager**, so either add an Alertmanager container or use Grafana-managed alerting with a webhook contact point.
- **Java path:** the OTel Java agent (v2.33.1) exports traces, metrics and logs over OTLP `http/protobuf` to `:4318` with no code changes. Logback is auto-captured and trace context is injected into the MDC. The Micrometer bridge is off by default. Loki ingests OTLP natively at `/otlp` (Loki 3.x).
- **Later backends:** Dynatrace exposes Problems v2, metrics v2 and logs (the classic logs v2 search is deprecated by end of 2027 in favour of Grail/DQL), plus an official remote MCP server. Azure exposes the Logs Query API (KQL, `api.loganalytics.azure.com`), common-alert-schema webhooks, and Azure MCP Server 2.0 (GA) with Monitor tools.

## Versions checked (GitHub latest releases, 2026-11-04)

| Component | Latest | Released |
|---|---|---|
| Prometheus | v3.15.1 | 2026-10-21 |
| Alertmanager | v0.34.2 | 2026-10-29 |
| Loki | v3.7.9 | 2026-10-20 |
| Tempo | v3.1.1 | 2026-10-21 |
| Grafana | v13.3.0 | 2026-10-27 |
| grafana/mcp-grafana | v2.2.0 | 2026-11-02 |
| grafana/alloy | v1.21.3 | 2026-10-28 |
| grafana/docker-otel-lgtm | v0.39.0 | 2026-10-30 |
| OTel Java instrumentation (agent) | v2.33.1 | 2026-10-26 |
| dynatrace-oss/dynatrace-mcp | v2.1.2 (final, deprecated) | 2026-07-20 |

Source: `gh api repos/<owner>/<repo>/releases/latest`.

---

## 1. Alertmanager webhook payload

Source: https://prometheus.io/docs/alerting/latest/configuration/ (`<webhook_config>`)

Alertmanager POSTs JSON to the configured `url`:

```json
{
  "version": "4",
  "groupKey": "<string>",          // identifies the alert group; use for dedup
  "truncatedAlerts": 0,            // alerts dropped due to max_alerts
  "status": "firing|resolved",
  "receiver": "<string>",
  "groupLabels": {}, "commonLabels": {}, "commonAnnotations": {},
  "externalURL": "<string>",       // backlink to Alertmanager
  "notification_reason": "<string>",
  "alerts": [{
    "status": "firing|resolved",
    "labels": {}, "annotations": {},
    "startsAt": "<rfc3339>", "endsAt": "<rfc3339>",
    "generatorURL": "<string>",    // e.g. Prometheus graph URL holding the expr
    "fingerprint": "<string>"
  }]
}
```

Implications for the agent:
- **Incident key:** use `groupKey` (or per-alert `fingerprint`) to dedupe, because one Incident can arrive many times through repeat_interval and resolved notifications.
- **Service:** labels such as `service`, `job`, `namespace` and `severity` carry the Target service identity, but only if the alert rules are written to include them. The test bed's alert rules should always set a `service` label that matches OTel `service.name` (in Loki and Prometheus this shows up as `service_name`).
- **Time window:** take `startsAt` (minus a lookback) to now.
- **Query:** `generatorURL` holds the PromQL expression (URL-encoded `g0.expr`), which is useful evidence.
- **Pull alternative:** Alertmanager's API v2 `GET /api/v2/alerts` lists active alerts (OpenAPI spec in the Alertmanager repo).

## 2. Grafana alerting webhook

Source: https://grafana.com/docs/grafana/latest/alerting/configure-notifications/manage-contact-points/integrations/webhook-notifier/

Same core as Alertmanager (`receiver`, `status`, `alerts[]`, `groupLabels`, `commonLabels`, `commonAnnotations`, `externalURL`, `groupKey`, `truncatedAlerts`), with `"version": "1"` plus:
- top level: `orgId`, `state` (`alerting|ok`), `title`, `message`
- per alert: `values` (the values that triggered the alert), `silenceURL`, `dashboardURL`, `panelURL`, `imageURL`, `fingerprint`. Unresolved alerts have `endsAt` = `0001-01-01T00:00:00Z`.

**Conclusion:** one webhook parser covers both. Key on `alerts[].labels`, `startsAt` and `fingerprint`, and treat the Grafana extras as optional enrichment.

## 3. Loki: HTTP API and LogQL

Source: https://grafana.com/docs/loki/latest/reference/loki-http-api/

| Endpoint | Use | Key params |
|---|---|---|
| `GET /loki/api/v1/query_range` | logs or metric-over-logs for a window | `query`, `start`, `end`/`since`, `limit` (default 100), `step`, `direction` (default backward) |
| `GET /loki/api/v1/query` | instant **metric** queries only (log queries give 400) | `query`, `time`, `limit` |
| `GET /loki/api/v1/labels`, `/label/<name>/values` | discover labels (default last 6h) | `start`, `end`, `query` |
| `GET/POST /loki/api/v1/series` | streams that match selectors | `match[]` |
| `GET /loki/api/v1/index/volume[_range]` | log volume per label | `query`, `start`, `end`, `aggregateBy` |
| `GET /loki/api/v1/patterns` | clustered log patterns (requires `pattern_ingester`) | `query`, `start`, `end`, `step` |
| `GET/POST /loki/api/v1/detected_fields` | fields parsed from lines/structured metadata | `query`, `line_limit`, `limit` |

- **Timestamps:** integer = ns epoch, float = seconds, RFC3339 also accepted; durations look like `5m`.
- **Response:** `{status, data:{resultType, result, stats}}`.
  - `streams`: `[{stream:{labels}, values:[[ns_string, line], ...]}]`
  - `matrix`/`vector`: Prometheus-style.

LogQL examples useful for RCA:
- `{service_name="orders"} |= "ERROR"`, or `| json | level="ERROR"`
- `{service_name="orders"} | trace_id="<id>"`: correlate to Tempo. The OTel trace ID lands in structured metadata when shipped via OTLP.
- `sum by (service_name) (count_over_time({service_name=~".+"} |= "Exception" [5m]))`: error-rate-over-logs.
- `patterns` and `detected_fields` are cheap summaries an agent can read before pulling raw lines. They are worth exposing to save context tokens.

## 4. Prometheus: HTTP API and PromQL

Source: https://prometheus.io/docs/prometheus/latest/querying/api/ (OpenAPI at `/api/v1/openapi.yaml`)

| Endpoint | Use |
|---|---|
| `GET/POST /api/v1/query` | instant query (`query`, `time`, `timeout`, `limit`) |
| `GET/POST /api/v1/query_range` | range query (`query`, `start`, `end`, `step`) |
| `/api/v1/series`, `/api/v1/labels`, `/api/v1/label/<n>/values` | discovery (`match[]`, `start`, `end`, `limit`) |
| `/api/v1/metadata` | metric type/help/unit |
| `/api/v1/alerts`, `/api/v1/rules` | firing alerts and rule definitions (shows the alert's expression) |
| `/api/v1/targets` | scrape health (is the service even up?) |

- **Envelope:** `{status:"success"|"error", data, errorType?, error?, warnings?, infos?}`.
- **`resultType`:** `vector|matrix|scalar|string`. Sample values are strings (because of NaN/Inf).
- **Errors:** 400 (bad params), 422 (query execution failed), 503 (timeout).
- **Typical RCA queries** (Spring/Micronaut with OTel or Micrometer metric names):
  - error ratio: `sum(rate(http_server_request_duration_seconds_count{service_name="orders",http_response_status_code=~"5.."}[5m])) / sum(rate(...[5m]))`
  - p99: `histogram_quantile(0.99, sum by (le) (rate(http_server_request_duration_seconds_bucket{...}[5m])))`
  - JVM: `jvm_memory_used_bytes`, `jvm_gc_duration_seconds`, `jvm_thread_count`

  Exact metric names depend on the instrumentation path (OTel semconv vs Micrometer naming). Pin them once the test bed exists.

## 5. Tempo: search and trace-by-id

Source: https://grafana.com/docs/tempo/latest/api_docs/

| Endpoint | Use |
|---|---|
| `GET /api/traces/<traceid>` | full trace (optional `start`/`end` epoch s to narrow blocks) |
| `GET /api/v2/traces/<traceid>` | adds `q` (TraceQL span filter), span pruning (experimental) and hierarchy controls. `Accept: application/vnd.grafana.llm` returns a **simplified LLM-oriented JSON** (marked unstable) |
| `GET /api/search` | `q` (TraceQL), `tags`, `minDuration`/`maxDuration`, `start`/`end`, `limit` (default 20), `spss` (default 3) |
| `GET /api/v2/search/tags`, `/api/v2/search/tag/<tag>/values` | attribute discovery, by scope |
| `GET /api/metrics/query_range`, `/api/metrics/query` | TraceQL metrics (e.g. `{...} \| rate()`) |

- Trace responses are OTLP JSON by default, or protobuf with `Accept: application/protobuf`.
- Without `start`/`end`, search covers only recent data.
- **TraceQL examples:**
  - `{ resource.service.name = "orders" && status = error }`
  - `{ span.http.response.status_code >= 500 } | select(span.db.statement)`
  - `{ duration > 2s }`

**Agent note:** traces are large. Prefer search, then fetch one trace, then (in the adapter) summarise to the error span chain plus exception events (`exception.type`, `exception.stacktrace`). Stack frames from those events are the bridge to "suspect code locations" in the RCA report.

## 6. Official Grafana MCP server (`grafana/mcp-grafana`)

Source: https://github.com/grafana/mcp-grafana (README, v2.2.0 2026-11-02)

- Go binary or Docker image. Transports: `stdio` (default), `sse`, `streamable-http` (`/mcp`, default `localhost:8000`).
- Config: `GRAFANA_URL` and `GRAFANA_SERVICE_ACCOUNT_TOKEN`. Per-request headers (`X-Grafana-Service-Account-Token`, `X-Grafana-Org-Id`, `X-Grafana-URL`) work over streamable-http only.
- `--disable-write` drops the write tools, and `--disable-<category>` turns off a category. Needs Grafana ≥ 9.0.
- Queries go **through Grafana datasources**: the agent addresses a datasource UID, not Loki/Prometheus/Tempo URLs directly.

Tools relevant to RCA (enabled by default unless noted):

| Category | Tools |
|---|---|
| Prometheus | `query_prometheus`, `query_prometheus_histogram`, `list_prometheus_metric_names`, `list_prometheus_metric_metadata`, `list_prometheus_label_names`, `list_prometheus_label_values` |
| Loki | `query_loki_logs`, `query_loki_stats`, `query_loki_patterns`, `list_loki_label_names`, `list_loki_label_values`, `analyze_loki_labels` |
| Tempo | `search_tempo_traces`, `get_tempo_trace`, `diff_tempo_traces`, `query_tempo_metrics`, `list_tempo_attribute_names`, `list_tempo_attribute_values`, `get_tempo_traceql_docs` |
| Alerting | `alerting_rules_read`, `alerting_silences_read`, `alerting_manage_routing` (+ write variants). Covers Grafana-managed rules and external Alertmanagers |
| Datasources | `list_datasources`, `get_datasource`, `check_datasources_health` |
| Dashboards/Nav | `search_dashboards`, `get_dashboard_summary`, `get_dashboard_panel_queries`, `generate_deeplink`, `get_panel_image` |
| Other | `get_annotations` (deploy markers!), Pyroscope (`query_pyroscope`), Incident/OnCall, `get_assertions` (Asserts), `grafana_api_request` (raw escape hatch) |
| Opt-in | `run_panel_query`, `get_query_examples`, SQL, CloudWatch, Elasticsearch, etc. |

**Assessment:**
- It covers all three signals plus alert-rule lookup and deeplinks (good for citing evidence in the RCA report).
- **Option A:** the Grafana adapter wraps mcp-grafana (agent → adapter → MCP).
- **Option B:** call the raw APIs directly (agent → adapter → Loki/Prom/Tempo HTTP).
- A gives free maintenance and LLM-tuned tools but adds a Grafana dependency and ~70 tools of surface area. Filter it with `--disable-*` and `--disable-write`.
- B keeps the adapter thin and backend-native. Either way the adapter boundary hides the choice. Decide in the adapter design or prototype ticket.

## 7. Java instrumentation path for the test bed

Sources:
- https://opentelemetry.io/docs/zero-code/java/agent/configuration/
- https://opentelemetry.io/docs/languages/sdk-configuration/otlp-exporter/
- https://github.com/open-telemetry/opentelemetry-java-instrumentation/blob/main/docs/supported-libraries.md
- https://grafana.com/docs/loki/latest/send-data/otel/
- https://github.com/grafana/docker-otel-lgtm

**Recommended (lowest effort, the same for Spring and Micronaut):** OTel Java agent (`-javaagent:opentelemetry-javaagent.jar`, v2.x).
- Agent 2.0+ defaults to the `http/protobuf` OTLP protocol. The default endpoint is `http://localhost:4318` (`/v1/traces`, `/v1/metrics`, `/v1/logs`).
- Exporters default to `otlp` for all three signals. Set `OTEL_SERVICE_NAME` per service.
- **Logback:** auto-instrumented (1.0+). The appender instrumentation ships log records over OTLP, and the MDC instrumentation injects `trace_id`/`span_id`. Logs, traces and metrics share `service.name`, which is what makes cross-signal correlation work.
- **Micrometer:** the bridge instrumentation exists but is **disabled by default**. Either enable it, or rely on the agent's own HTTP/JVM metrics in OTel semconv.
- The OTel Collector routes the data:
  - traces → Tempo (OTLP)
  - metrics → Prometheus (OTLP receiver `--web.enable-otlp-receiver`, or remote-write)
  - logs → Loki native OTLP at `http://<loki>/otlp` (structured metadata is on by default in Loki ≥ 3.0)
- In Loki, `service.name` becomes the index label `service_name` (dots become underscores). Large `exception.stacktrace` attributes can exceed the 64KB structured-metadata limit and get a 400. Move them into the body or drop them in the collector.

**Alternatives:**
- Micrometer `micrometer-registry-prometheus` with `/actuator/prometheus` (Spring) or `/prometheus` (Micronaut), scraped by Prometheus. This is classic and well understood, but metric names then differ from the OTel semconv names.
- Loki logback appender (loki4j) or Promtail/Alloy tailing files. These add more moving parts than OTLP.

**Compose option:**
- `grafana/docker-otel-lgtm` (dev/test only) bundles the Collector, Prometheus, Loki, Tempo, Pyroscope and Grafana (:3000, OTLP :4317/:4318) in one image, and ships a Java example.
- It has **no Alertmanager**. Use Grafana-managed alert rules with a webhook contact point pointing at the agent, or add a `prom/alertmanager` container plus Prometheus rules.
- The alternative is separate containers (prometheus, alertmanager, loki, tempo, grafana, otel-collector or alloy), which gives more control and closer parity with production.

---

## 8. Glance: Dynatrace API v2

Sources:
- https://docs.dynatrace.com/docs/dynatrace-api/environment-api/problems-v2/problems/get-problems-list
- https://docs.dynatrace.com/docs/dynatrace-api/environment-api/log-monitoring-v2/get-search-logs
- https://docs.dynatrace.com/docs/dynatrace-intelligence/dynatrace-intelligence-integrations/dynatrace-mcp
- https://github.com/dynatrace-oss/dynatrace-mcp

- **Problems (the "alert" equivalent):** `GET /api/v2/problems` (scope `problems.read`).
  - Filters: `problemSelector`, `entitySelector`, `from`/`to` (default 2h; accepts `now-2h`), `fields=evidenceDetails,impactAnalysis,recentComments`.
  - Returns `problemId`, `displayId`, `title`, `severityLevel`, `impactLevel`, `status`, `affectedEntities`, `rootCauseEntity`, and with `fields`, `evidenceDetails`.
  - Dynatrace has already done some RCA (Davis), so the adapter should surface `rootCauseEntity` and `evidenceDetails` as pre-computed evidence.
  - Pushed problems arrive via the custom-webhook problem notification integration.
- **Metrics:** `GET /api/v2/metrics/query` (`metricSelector`, `entitySelector`, `resolution`, `from`/`to`; scope `metrics.read`).
- **Logs:** classic `GET /api/v2/logs/search` (`query`, `from`, `to`, `limit` ≤ 1000) is **deprecated, removal by end of 2027**. New environments use Grail and DQL.
- **Traces:** via Grail/DQL (`fetch spans`) on the platform.
- **MCP:**
  - **Official remote MCP server** on the Dynatrace Platform: `https://{env}.apps.dynatrace.com/platform-reserved/mcp-gateway/v0.1/servers/dynatrace-mcp/mcp`, bearer platform token, scopes `mcp-gateway:servers:invoke|read` plus `storage:*:read`. Capabilities: DQL generate/explain/run, problems, vulnerabilities, K8s events, timeseries forecasting, entity lookup.
  - There is also a Claude Code plugin `dynatrace@claude-plugins-official`.
  - The older open-source `dynatrace-oss/dynatrace-mcp` (tools: `list_problems`, `execute_dql`, `find_entity_by_name`, `list_exceptions`, …) is **deprecated**: v2.1.2 is the final release, and it was never officially supported.
  - Both require the 3rd-gen Platform (`apps.dynatrace.com`), not classic `live.dynatrace.com`.

## 9. Glance: Azure Monitor / Application Insights

Sources:
- https://learn.microsoft.com/en-us/azure/azure-monitor/logs/api/overview (updated 2026-09)
- https://learn.microsoft.com/en-us/azure/azure-monitor/alerts/alerts-common-schema
- https://github.com/microsoft/mcp (Azure.Mcp.Server README)

- **Query:**
  - `POST https://api.loganalytics.azure.com/v1/workspaces/{workspaceId}/query`, body `{"query": "<KQL>", "timespan": "PT1H"}`, Entra ID bearer token (client-credentials for a service).
  - Response: `{tables:[{name, columns:[{name,type}], rows:[[...]]}]}`.
  - Workspace-based App Insights data lives in tables such as `AppRequests`, `AppDependencies`, `AppExceptions` and `AppTraces`, correlated by `OperationId` (the trace ID).
  - Classic `api.applicationinsights.io` links still appear in alert payloads. Treat them as legacy.
- **Alerts:** action-group webhook with the **common alert schema** (`schemaId: azureMonitorCommonAlertSchema`).
  - `data.essentials`: `alertId`, `alertRule`, `severity` Sev0–4, `signalType`, `monitorCondition` Fired/Resolved, `alertTargetIDs`, `configurationItems`, `firedDateTime`.
  - `data.alertContext` (varies by type): log alerts carry `searchQuery`, window times and `linkToSearchResultsAPI`. Results are not embedded for Log Alerts V2, so re-query.
  - `customProperties`.
  - Payloads are capped at 256 KB.
- **Metrics:** Azure Monitor metrics REST API (per resource), or Azure Monitor managed Prometheus (PromQL), which would let the Prometheus code path be reused.
- **MCP:** **Azure MCP Server 2.0 is GA** (`microsoft/mcp`, install via `npx @azure/mcp`, `dotnet tool`, Docker). Its Azure Monitor tools cover Log Analytics workspace/table queries, metrics and health models, plus App Lens diagnostics. Trace queries need a private-preview Trace Store.

---

## 10. Proposed minimal Observability adapter operation set

Design goals:
- Backend-neutral nouns.
- Time-bounded everything.
- Native query strings as an escape hatch: LLMs already know PromQL, LogQL, TraceQL, KQL and DQL, so the adapter shouldn't invent a query language.
- Small, summarised results to save context.

```text
# Ingest
parseAlert(rawPayload, sourceHint?) -> Incident
    # Alertmanager v4 / Grafana v1 / Dynatrace problem / Azure common schema
    # Incident = {id(dedupe key), status, title, service, labels, annotations,
    #             startsAt, endsAt?, links[], backendRefs{ruleExpr?, rootCauseEntity?...}}
listActiveAlerts(window, filter?) -> Incident[]      # pull mode / reconciliation

# Discovery (so the agent never guesses names)
describeBackend() -> {signals:[logs|metrics|traces], queryLanguages:{logs:"LogQL", metrics:"PromQL", traces:"TraceQL"}}
listServices(window) -> string[]
listLabels(signal, window, selector?) -> string[]
listLabelValues(signal, label, window, selector?) -> string[]

# Evidence
queryMetrics(query, window, step?) -> Series[]               # PromQL | KQL | metricSelector
queryLogs(query, window, limit, direction?) -> LogLine[]      # LogQL | KQL | DQL
summarizeLogs(selector, window) -> {patterns[], volume, topFields}   # Loki patterns/detected_fields; optional
searchTraces(query, window, limit) -> TraceSummary[]         # TraceQL | KQL | DQL
getTrace(traceId, window?) -> TraceDigest                    # error-span chain + exception events + stack frames

# Context / citation
getAlertRule(ruleRef) -> {expr, for, labels}                 # Prometheus /rules, Grafana alerting
getChangeEvents(service, window) -> Event[]                  # Grafana annotations / Dynatrace events / Azure activity log; optional
deepLink(signal, query, window) -> url                       # for the RCA report evidence
```

**Minimum for v1 (Grafana):** `parseAlert`, `listLabelValues`, `queryMetrics`, `queryLogs`, `searchTraces`, `getTrace`, `deepLink`. The rest are nice-to-have.

Every operation takes an explicit `window` derived from the Incident (`startsAt - lookback`, `endsAt|now`).

## Open questions / follow-ups

- **Raw APIs vs mcp-grafana behind the adapter:** decide with a prototype. Measure tool count, token cost, and whether the Grafana dependency is acceptable.
- **Single LGTM image vs separate containers in Compose:** the single image has no Alertmanager. The question is whether to use Grafana-managed alerting (webhook contact point) or add Alertmanager.
- **Metric naming convention for Seeded fault alert rules:** OTel semconv (agent) vs Micrometer. Pick one so rules and agent prompts are stable.
- **Required label contract:** every alert rule must carry `service` (= `service.name`) so `parseAlert` can fill `Incident.service`.
