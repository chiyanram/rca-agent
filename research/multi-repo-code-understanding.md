# Multi-repo code understanding for Java/Gradle Spring & Micronaut services

Research for issue #5 (map #1). Sources checked 2026-11-04. Versions and limits are as of that date.

## Question

How can the agent go from Incident evidence (stack traces, service names, endpoints, recent deploys) to the relevant code across many GitHub repos (one per Target service, Java/Gradle, Spring or Micronaut)? What are the trade-offs in latency, cost, freshness and accuracy?

## Answer in brief

Use a layered approach. Deterministic lookups come first and an agentic loop finishes the job:

1. **A service→repo registry is the backbone.** No search technique reliably answers "which repo is `orders-api`?" or "which repo owns `com.acme.orders`?". A small, declarative registry does. For each service it lists the repo, the telemetry service name, package prefixes, base URLs, and the Gradle module layout.
2. **Pin to the deployed commit, not the default branch.** Stack-trace line numbers only mean something at the exact SHA that is running. The Spring Boot `info` endpoint shows `git.commit.id` when `git.properties` is on the classpath, and GitHub Actions deployments record the SHA.
3. **Read code through local partial clones and agentic grep/read.** Fetch each repo at the deployed SHA into a cached mirror, then let Claude use ripgrep, glob and file reads. This is what Claude Code does today, and it is the freshest and most accurate option for stack-trace-driven RCA.
4. **Resolve evidence deterministically before the LLM runs.**
   - Map each stack frame to a fully qualified class name (FQCN), then a repo via package prefix, then a file path and line.
   - Map each endpoint to the controller method that serves it, using a cheap tree-sitter index of annotations (no Gradle build needed).
   - Map outbound clients (Feign, Spring HTTP interfaces, Micronaut `@Client`) to the target service through their config keys. This gives a cross-service call graph.
5. **Defer jdtls (Java LSP) to the Fix proposal phase.** It gives precise references, call hierarchy and compile diagnostics. The cost is a full Gradle import per repo (Java 25 runtime, minutes, GBs, private-dependency credentials).
6. **Use GitHub code search API only as a fallback** for discovery across the org. It indexes the default branch only, allows 10 requests/min, uses legacy syntax (no regex), and documents no freshness guarantee.
7. **Skip embeddings and Sourcegraph for the MVP.** Revisit embeddings for symptom-only incidents with no stack trace. Revisit Zoekt or Sourcebot (OSS) if the repo count grows beyond what local mirrors handle.

## 1. GitHub code search API

- **Endpoint:** `GET /search/code` "requires you to authenticate and limits you to 10 requests per minute". It returns up to 100 results per page and "up to 1,000 results for each search". [GitHub REST: Search][gh-search]
- **Only the default branch is indexed:** "Only the *default branch* is considered."
  - Only files smaller than 384 KB are searchable.
  - Only repos with fewer than 500,000 files are searchable.
  - Repos need activity or search appearances in the last year.
  - Archived repos are excluded.
  - Sources: [GitHub: Searching code (legacy)][gh-legacy], [GitHub REST: Search][gh-search]
- **The REST API uses the legacy search syntax.** The "Searching code (legacy)" page says that syntax is the one you "should only need to use for the REST API endpoint". The newer GitHub code search, with regex and symbol search, is documented for the web UI ([About GitHub code search][gh-new]). That page does not say the newer engine is available via REST.
- **Freshness:** Neither page gives an indexing-latency guarantee. The `sort=indexed` option exists, but `sort` and `order` are "closing down". [gh-search]
- **Fetching files:** The Contents API returns full JSON for files of 1 MB or less, raw-only for 1 to 100 MB, and nothing above 100 MB. Directories return at most 1,000 entries; for larger trees, use the Git Trees API. [GitHub REST: Contents][gh-contents]
- **Overall REST budget:** 5,000 requests/hour per user or app installation (up to 15,000 on Enterprise Cloud). Secondary limits apply: 100 concurrent requests and 900 points/min. [GitHub REST: rate limits][gh-rate]

**Fit for RCA:**

| Factor | Assessment |
|---|---|
| Latency | Fine |
| Cost | Free |
| Freshness | Bad: default branch only, unknown index lag |
| Accuracy | Bad for line numbers. The deployed SHA can differ from `main`, especially for the "recent deploy broke it" case |
| Throughput | 10 req/min is a hard ceiling for an agent loop |

Good for "which repo in the org mentions `PaymentGatewayClient`?" when the registry has no answer.

The GitHub MCP server (`github/github-mcp-server`, v2.1.0 released 2026-11-03) wraps these same APIs and inherits the same limits.

## 2. Local clones + agentic grep/read (Claude Code style)

- **Claude Code's own approach:** Boris Cherny (Claude Code's creator) has said that early versions used RAG with a local vector DB, and that "agentic search generally works better". Reasons given were freshness, simplicity, and the security liability of an index.
  - This is reported second-hand from a Latent Space podcast appearance (see [summary][cherny]). The claim was not rigorously benchmarked ("vibes").
- **The Grep tool is ripgrep:** Claude Code's Grep tool "is built on ripgrep and uses ripgrep's regex syntax". [Claude Code tools reference][cc-tools]
- **Cheap clones:** Partial clone (`git clone --filter=blob:none`) skips blobs at clone time and "demand fetches" them later. `checkout` bulk-prefetches the blobs it needs, but one-at-a-time faulting "tends to be slow". [git partial-clone docs][git-partial]
  - Practical pattern: keep a bare/partial mirror per repo on the agent host.
  - For each Investigation: `git fetch origin <deployed-sha>`, then `git worktree add` at that SHA.
  - Cost: seconds for typical service repos once the mirror exists.

**Fit for RCA:**

| Factor | Assessment |
|---|---|
| Freshness | Best: exact deployed SHA, plus `git log`/`git diff` between the previous and current deploy SHA. This is the most valuable RCA signal for "recent deploy" incidents |
| Accuracy | High, because Claude reads real code |
| Latency | Several tool turns per question |
| Cost | Token cost grows with how much the agent reads |
| Mitigation | Deterministic pre-resolution (sections 5 and 6) hands Claude file:line starting points, so it reads less |
| Ops | Disk plus a GitHub credential with `contents:read` (see #7) |

## 3. Symbol navigation: tree-sitter vs jdtls

### tree-sitter-java

- Latest tag `v0.23.5`. The repo ships `queries/tags.scm` for symbol tagging and `highlights.scm` (checked via GitHub API).
- Parses source only. No build, no classpath, milliseconds per file.
- Good enough to extract:
  - class, method and annotation declarations with their line ranges
  - annotation arguments (`@GetMapping("/orders/{id}")`, `@Client("inventory")`)
  - Java package declarations
- Cannot resolve types across files or libraries (for example, which `save()` is called). For the RCA lookups, this rarely matters.

### Eclipse JDT LS (jdtls)

- Latest tag `v1.63.0`. Needs a Java 25 runtime at minimum to run. It can compile projects targeting Java 1.8 to 25.
- Gradle support comes via Buildship.
- Features include references and implementations, call and type hierarchy, as-you-type diagnostics, and source resolution for jars.
- Source: [eclipse.jdt.ls README][jdtls]

### Claude Code's LSP integration

- Anthropic publishes `jdtls-lsp` (and `kotlin-lsp`) in its official plugin marketplace. [Code intelligence plugins][cc-lsp]
- The `LSP` tool can:
  - jump to a definition
  - find references
  - get type information at a position
  - list symbols in a file
  - search workspace symbols
  - find implementations
  - trace call hierarchies
- It also pushes diagnostics after edits. [Claude Code tools reference: LSP tool behavior][cc-tools]
- Caveats:
  - Plugin language servers don't start in Claude Code cloud sessions.
  - Memory grows while the server indexes the project.
- If we build on the Claude Agent SDK (see #8), we can reuse the plugin config (`lspServers`: `command`, `extensionToLanguage`, `startupTimeout`, `requestTimeout` defaulting to 60 s). [Plugin manifest reference][cc-plugins]

**Fit for RCA:**

| Factor | Assessment |
|---|---|
| Accuracy | jdtls is the most accurate (semantic resolution, Spring/Micronaut generated code via annotation processing) |
| Latency and cost | Worst: a full Gradle import per repo per SHA (minutes, GBs of RAM) |
| Dependencies | Needs credentials for private artifact repositories (Azure Artifacts, GitHub Packages) |
| Robustness | Breaks when the build breaks |

Use for Fix proposals, where we need to compile and run tests anyway (#12). Not needed to locate code for an RCA report.

## 4. Embeddings / semantic indexes

- Anthropic "does not offer its own embedding model" and points to Voyage AI.
  - `voyage-code-4` (blog dated 2026-08-13) is "optimized for code retrieval and agentic coding applications".
  - Context is 32,000 tokens, with 1024 default dimensions (256/512/2048 available).
  - `voyage-code-3` is the previous generation.
  - Rerankers: `rerank-3` and `rerank-3-lite`.
  - Source: [Claude docs: Embeddings][embed]
- An index has to be built and kept fresh per repo. Matching the deployed SHA means one index per deployed version, or accepting skew.
- **Fit for RCA:** Our evidence is mostly exact identifiers: FQCNs, method names, URL paths, exception types, log message templates. Exact search beats semantic search on those.
  - Embeddings help with fuzzy symptoms ("checkout is slow") when no trace is available.
  - Costs: index ops, embedding cost, staleness, and an extra copy of source code to secure.
  - Recommendation: defer, and revisit if evaluation (#13) shows misses on symptom-only Incidents.

## 5. Code-graph / code-search platforms

- **Sourcegraph:**
  - The pricing page lists a single Enterprise plan "starting at $16K" (minimum annual contract), with self-hosted or single-tenant deployment and a "Full MCP Server, API, and CLI access". [Sourcegraph pricing][sg-price]
  - The old public monorepo snapshot (`sourcegraph/sourcegraph-public-snapshot`) is archived.
  - Overkill for an MVP with a handful of repos.
- **Zoekt** (`sourcegraph/zoekt`, Apache-2.0, actively pushed 2026-11): a trigram-indexed code search engine, fast regex and substring search across many repos. It can index a chosen branch.
- **Sourcebot** (`sourcebot-dev/sourcebot`, MIT, ~4k stars, active): self-hosted, Zoekt-based multi-repo search with a UI.
- **SCIP / scip-java** (`sourcegraph/scip-java`, Apache-2.0, v0.13.2 on 2026-10-22): emits precise cross-repo code-navigation indexes from a Java build. Same build cost as jdtls, but offline and storable per SHA.
- **Fit:** Worth adopting only when the repo count makes local mirrors plus ripgrep slow (roughly dozens or more of large repos), or for discovery across the whole org. Zoekt would replace GitHub code search for discovery and has no 10 req/min limit.

## 6. Mapping evidence to code

### 6.1 Stack-trace frames to repo and file

A JVM frame looks like `at com.acme.orders.service.OrderService.place(OrderService.java:142)`.

- **FQCN to repo:** use the longest-prefix match on `packagePrefixes` in the registry.
  - Library frames (`org.springframework.`, `io.micronaut.`, `reactor.`, `java.`) are skipped or tagged as framework.
  - Shared internal libraries need their own registry entry, marked `kind: library`.
- **FQCN to path:** use the Java convention `src/main/java/<package as dirs>/<OuterClass>.java`.
  - Inner and lambda classes (`Foo$Bar`, `Foo$$Lambda`) map to the outer class.
  - For multi-module Gradle builds, glob `**/src/main/{java,kotlin}/<path>`.
  - Fall back to the tree-sitter package index for non-standard layouts.
- **Line numbers:** valid only at the deployed SHA. How to get the SHA:
  - Spring Boot `info` endpoint: auto-configured `GitProperties` when `git.properties` is on the classpath. It exposes `git.commit.id` by default. [Spring Boot actuator endpoints][sb-actuator]
  - Gradle generates `git.properties` with the `com.gorylenko.gradle-git-properties` plugin (latest v4.0.1, 2026-06-01).
  - Micronaut's management `info` endpoint has an equivalent git source.
  - Alternatively, take it from GitHub Actions deployment records (#7), or from the OTel resource attribute `service.version` / image tag if CI stamps the SHA (#6).
- **"Caused by" chains** often cross service boundaries only through HTTP error bodies or trace context. Use traces (#6) to hop services, then repeat the frame mapping per service.

### 6.2 Inbound endpoints to controller method

Extract an endpoint index per repo per SHA with tree-sitter.

- **Spring MVC/WebFlux:**
  - class-level `@RequestMapping(path)`
  - method-level `@GetMapping`, `@PostMapping`, `@PutMapping`, `@DeleteMapping`, `@PatchMapping`, `@RequestMapping(method=..)`
  - plus `server.servlet.context-path` / `spring.webflux.base-path` from `application*.yml|properties`
- **Micronaut:**
  - `@Controller("/hello")` on the class
  - `@Get`, `@Post` etc. on methods ("All the method annotations default to `/`")
  - plus `micronaut.server.context-path`
  - Source: [Micronaut HTTP 5.1.x][mn-http]
- **Matching:** normalize path templates (`{id}`, regex vars) and match the HTTP route attribute seen in the evidence: `http.route` / `url.path` on server spans or logs.
- **Pitfalls:**
  - functional routes (`RouterFunction`, Micronaut `RouteBuilder`), which need a grep fallback
  - gateway path rewriting (Azure API Management / App Gateway)
  - constants used in annotations (`@GetMapping(Paths.ORDERS)`), which need resolution of constants within the repo

### 6.3 Outbound HTTP clients to target service

Extract the client declarations and resolve each to a service through config.

- **Spring HTTP Service clients** (Spring Framework 7.0.x, Boot 4.1.x):
  - interfaces with `@HttpExchange` / `@GetExchange` etc.
  - grouped via `@ImportHttpServices(group = "echo", ...)`
  - base URL from `spring.http.serviceclient.<group>.base-url`
  - Sources: [Spring Framework REST clients][spring-rest], [Spring Boot: Calling REST services][sb-rest]
  - Spring Cloud OpenFeign 5.0.x now calls itself "feature-complete" and suggests "migrating over to Spring HTTP Service Clients", so expect both styles in existing services.
- **OpenFeign:**
  - `@FeignClient(name = "...", url = "...")`, where `name` is required.
  - The URL resolves in this order: annotation `url`, then `spring.cloud.openfeign.client.config.<name>.url`, then a load-balanced lookup by `name` (= `serviceId`). [Spring Cloud OpenFeign][feign]
- **Micronaut declarative client:**
  - `@Client("id")` (`value` and `id` are aliases), resolved via `micronaut.http.services.<id>.url|urls` or service discovery.
  - When service config is used, other annotation attributes except the id are ignored.
  - Sources: [Micronaut configuration reference 5.1.x][mn-config], [`@Client` javadoc][mn-client]
- **Imperative calls** (`RestClient`/`WebClient`/`RestTemplate` with literal or `@Value` URLs) need a grep fallback on base-URL properties.
- **Resolution:** client → base URL host or service id → registry `baseUrls` / `aliases` → target repo. Then match the client method's path against that repo's endpoint index. This yields cross-repo edges of the form "caller method → callee controller method". Env-specific URLs come from `application-<profile>.yml` or Azure App Settings / Key Vault references, which the registry should hold per environment.
- **Distributed traces are the runtime truth** for which edges were actually hit during the Incident. The static graph explains them and finds code. Combine both (#6).

## 7. Service→repo registry

There is no reliable way to infer this, so declare it. Options:

- **Central YAML in the agent's config repo.** Simplest for the MVP and reviewable in PRs.
- **`catalog-info.yaml` per repo (Backstage format).** It carries `github.com/project-slug: <owner>/<repo>` and `backstage.io/source-location`. [Backstage well-known annotations][backstage] This lets teams own their entry and leaves a path to a real Backstage later. The agent can discover these files via the GitHub API or code search.

Suggested fields per service:

```yaml
- service: orders-api               # canonical name, used in Incidents
  aliases: [orders, orders-svc]     # OTel service.name, App Insights cloud_RoleName, k8s/App Service names
  repo: acme/orders-api
  kind: service                     # or library
  framework: spring-boot            # or micronaut
  packagePrefixes: [com.acme.orders]
  modules: [app, client]            # Gradle subprojects, optional
  baseUrls:                         # per env, for outbound-client resolution
    prod: https://orders.internal.acme.net
  deployedShaSource: actuator-info  # or gh-deployments | otel-resource | image-tag
  owners: [team-checkout]
```

The tree-sitter endpoint and client indexes can **propose** registry updates, for example an unknown `@Client("inventory")`. Humans approve them.

## Trade-off summary

| Approach | Latency | Cost | Freshness | Accuracy for RCA | Role |
|---|---|---|---|---|---|
| Registry | instant | ~0 | as maintained | exact | **backbone** |
| Deterministic frame/endpoint/client resolution (tree-sitter + config) | ms to s | ~0 | exact SHA | high | **pre-step** |
| Local partial clones + agentic grep/read | s per turn, several turns | tokens | exact SHA, plus deploy diff | high | **core loop** |
| GitHub code search API | ~1 s, 10/min cap | free | default branch, lag unknown | medium; wrong SHA | fallback discovery |
| jdtls / LSP | minutes to import | CPU/RAM, build creds | exact SHA | highest | Fix proposals |
| SCIP index | build time per SHA | storage + CI | per indexed SHA | highest | later, at scale |
| Zoekt / Sourcebot | ms | self-host | per indexed branch | high (lexical) | later, at scale |
| Sourcegraph Enterprise | ms | $16K+/yr | per indexed branch | high | probably not |
| Embeddings (voyage-code-4) | ms query, index build | API + vector store | stale unless reindexed | low on identifiers, good on fuzzy | deferred |

## Implications for other tickets

- **#11 (grilling: how the agent finds code):** start from the recommendation above. Open decisions:
  - registry format (central YAML vs `catalog-info.yaml`)
  - source of the deployed SHA
  - mirror location and cleanup
  - whether tree-sitter indexing runs per Investigation or in CI
- **#12 (Fix proposal gate):** jdtls / Gradle build in a sandbox is the natural place for compile, test and diagnostics. Budget the import time and private-repo credentials.
- **#7 (GitHub integration):** needs `contents:read` for clones and `deployments`/Actions read for deploy SHAs and compare. GitHub code search needs an authenticated token and is capped at 10 req/min.
- **#6 (observability):** confirm the stack-trace format in Loki / App Insights, the `http.route` attribute, and whether `service.version` or the commit SHA is on the OTel resource.
- **#13 (test bed):** sample services should include `gradle-git-properties`, the actuator/management `info` endpoint, at least one Feign or HTTP-interface client, and one Micronaut `@Client`, so mapping across repos is exercised.
- **#14 (security):** local mirrors hold source code on the agent host. Code snippets go to Claude. Embeddings would add another copy.

## Sources

[gh-search]: https://docs.github.com/en/rest/search/search
[gh-legacy]: https://docs.github.com/en/search-github/searching-on-github/searching-code
[gh-new]: https://docs.github.com/en/search-github/github-code-search/about-github-code-search
[gh-contents]: https://docs.github.com/en/rest/repos/contents
[gh-rate]: https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api
[cherny]: https://officechai.com/ai/claude-researcher-explains-how-agentic-search-performed-better-than-rag-for-code-generation/
[cc-tools]: https://code.claude.com/docs/en/tools-reference
[cc-lsp]: https://code.claude.com/docs/en/plugins/code-intelligence
[cc-plugins]: https://code.claude.com/docs/en/plugins-reference
[git-partial]: https://git-scm.com/docs/partial-clone
[jdtls]: https://github.com/eclipse-jdtls/eclipse.jdt.ls
[embed]: https://platform.claude.com/docs/en/build-with-claude/embeddings
[sg-price]: https://sourcegraph.com/pricing
[sb-actuator]: https://docs.spring.io/spring-boot/reference/actuator/endpoints.html
[mn-http]: https://docs.micronaut.io/5.1.x/http/
[mn-config]: https://docs.micronaut.io/5.1.x/configuration-reference/
[mn-client]: https://docs.micronaut.io/latest/api/io/micronaut/http/client/annotation/Client.html
[spring-rest]: https://docs.spring.io/spring-framework/reference/integration/rest-clients.html
[sb-rest]: https://docs.spring.io/spring-boot/reference/io/rest-client.html
[feign]: https://docs.spring.io/spring-cloud-openfeign/reference/spring-cloud-openfeign.html
[backstage]: https://backstage.io/docs/features/software-catalog/well-known-annotations

- GitHub REST Search: https://docs.github.com/en/rest/search/search
- GitHub Searching code (legacy): https://docs.github.com/en/search-github/searching-on-github/searching-code
- About GitHub code search: https://docs.github.com/en/search-github/github-code-search/about-github-code-search
- GitHub REST Contents: https://docs.github.com/en/rest/repos/contents
- GitHub REST rate limits: https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api
- Claude Code tools reference (Grep, LSP): https://code.claude.com/docs/en/tools-reference
- Claude Code code intelligence plugins: https://code.claude.com/docs/en/plugins/code-intelligence
- Claude Code plugin manifest (`lspServers`): https://code.claude.com/docs/en/plugins-reference
- Cherny on agentic search vs RAG (secondary): https://officechai.com/ai/claude-researcher-explains-how-agentic-search-performed-better-than-rag-for-code-generation/
- git partial clone: https://git-scm.com/docs/partial-clone
- Eclipse JDT LS: https://github.com/eclipse-jdtls/eclipse.jdt.ls
- tree-sitter-java: https://github.com/tree-sitter/tree-sitter-java
- Claude docs, Embeddings (Voyage): https://platform.claude.com/docs/en/build-with-claude/embeddings
- Sourcegraph pricing: https://sourcegraph.com/pricing
- Zoekt: https://github.com/sourcegraph/zoekt
- Sourcebot: https://github.com/sourcebot-dev/sourcebot
- scip-java: https://github.com/sourcegraph/scip-java
- GitHub MCP server: https://github.com/github/github-mcp-server
- Spring Boot actuator endpoints (info/git): https://docs.spring.io/spring-boot/reference/actuator/endpoints.html
- gradle-git-properties: https://github.com/n0mer/gradle-git-properties
- Spring Framework REST clients (HTTP interfaces): https://docs.spring.io/spring-framework/reference/integration/rest-clients.html
- Spring Boot Calling REST services: https://docs.spring.io/spring-boot/reference/io/rest-client.html
- Spring Cloud OpenFeign: https://docs.spring.io/spring-cloud-openfeign/reference/spring-cloud-openfeign.html
- Micronaut HTTP 5.1.x: https://docs.micronaut.io/5.1.x/http/
- Micronaut configuration reference 5.1.x: https://docs.micronaut.io/5.1.x/configuration-reference/
- Micronaut `@Client` javadoc: https://docs.micronaut.io/latest/api/io/micronaut/http/client/annotation/Client.html
- Backstage well-known annotations: https://backstage.io/docs/features/software-catalog/well-known-annotations
