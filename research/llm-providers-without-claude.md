# LLM providers and coding engines when Claude is unavailable

Research for ticket #25. Researched 2026-11-06. All prices are list prices in USD on that date, per 1M tokens unless stated. Model names, prices and products change often; re-check the linked pages before you rely on a number. **Unconfirmed** marks anything not verified against a primary source.

Context: our pipeline (Pre-fetch → Evidence → Change → Code-locator → RCA writer → RCA gate → Fix proposer → Fix gate → Open draft PR) owns stage order, gates, event log, context and tools. A small Pydantic AI agent runs each stage's inner loop. The model is set per stage in config. A coding engine may run *inside one stage* (the Fix proposer) but never owns the loop.

## TL;DR

- **Investigation stages (Evidence … RCA writer) need only a model API with good tool calling.** Pydantic AI 2.66.0 already reaches every serious option without Claude: OpenAI, Azure OpenAI / Foundry, Gemini (Gemini API or Google Cloud/Vertex), Bedrock (non-Claude models through Converse or the OpenAI-compatible "Mantle" route), self-hosted vLLM/Ollama/LiteLLM, and even GitHub Copilot as a model provider. No coding engine is needed for these stages.
- **The best fallback for Azure-hosted deployments is Azure OpenAI (Foundry)** with keyless Entra ID / Managed Identity and a **Data Zone** deployment for residency. Prices match OpenAI's at Global and are **+10% at Data Zone**. GPT-6.1 Sol costs $2.00 in / $10.00 out at Global, $2.20 / $11.00 at Data Zone.
- **Cost per Investigation** at 90% input / 10% output with no caching, using a frontier-tier model (GPT-6.1 Sol, Gemini 4 Argon, Gemini 3.1 Pro): **~$1.40 at 0.5M, ~$5.60 at 2M, ~$14 at 5M tokens**. Caching cuts this by roughly 30%. A mid tier (GPT-6.1 Terra, Gemini 3.8 Flash) costs about half or less. A small model (GPT-6 Luna, gpt-oss-120b) costs under $1 even at 5M. **One Fix round (~0.3M tokens) costs about $0.05–$1.60**, depending on tier.
- **GitHub Copilot changed shape in 2026.** It moved from premium requests to **usage-based "GitHub AI Credits"** (1 credit = $0.01, billed per token at per-model rates) on **2026-06-01**. Business costs $19/seat with 1,900 credits; Enterprise $39/seat with 3,900 credits. Credits are pooled per org, and overage is $0.01/credit. **GitHub Models was retired on 2026-07-30** and is no longer an option.
- **Copilot has a sanctioned headless path that fits our trust model.** A **GitHub App installation token with the org permission "Copilot Requests: read"** can make Copilot requests without a user (public preview). The organization pays, and its policies and budgets apply. This works for the Copilot SDK and CLI. The **cloud agent (assign an issue → PR) does *not* accept installation tokens**: it needs a user token. It owns its own loop, runs in GitHub's environment, and opens its own PR, so it can't be our Fix proposer without breaking our Fix gate. At most it could be an optional, non-MVP "hand-off" target.
- **Fix-proposer engine candidates without Claude Code: OpenCode (best fit) > Copilot CLI/SDK > Aider.**
  - OpenCode (MIT, v1.19.5, very active) has a headless server with an OpenAPI 3.1 spec, a JS SDK, `opencode run --format json`, and allow/ask/deny permission rules per tool and pattern. It supports Azure (including Entra via the Azure CLI), Bedrock, Vertex, any OpenAI-compatible endpoint, and an officially supported Copilot login.
  - Copilot CLI (1.0.106) has `-p`, `--output-format json`, allow/deny tool flags, and BYOK. It is GitHub-billed unless you bring your own key (BYOK).
  - Aider (Apache-2.0) has a good diff-edit core and ask/code/architect modes. But there has been no GitHub release since v0.86.0 (2025-08), its Python API is "not officially supported", and it has no tool-permission model or JSON event output.
- **Recommendation for #26:** the MVP needs **one provider path besides Claude**, chosen per deployment through per-stage model config. Our own Fix proposer (a Pydantic AI agent with our own edit/test tools) should be the default engine. Claude Agent SDK and OpenCode are optional pluggable engines behind the same stage contract.

## 1. Model providers usable from Pydantic AI

Pydantic AI version checked: **2.66.0** (PyPI, 2026-11-04). Source: [models overview](https://pydantic.dev/docs/ai/models/overview/).

Supported prefixes relevant here: `openai:` (Responses API by default; `openai-chat:` is the legacy Chat Completions route), `azure:` / `azure-responses:`, `google:` (Gemini API), `google-cloud:` (Vertex), `bedrock:` (Converse) and `bedrock-mantle:` (OpenAI-compatible), `ollama:`, `vllm:`, `litellm:`, `openrouter:`, `github-copilot:`, plus `OpenAICompatibleProvider` for any other OpenAI-compatible endpoint. **`ModelFallback` / `FallbackModel`** tries a list of models in turn, by default on any `ModelAPIError`. This is useful when a provider is down, but it must be logged as an event so replay stays deterministic.

### 1a. Azure OpenAI / Microsoft Foundry

- **Models**: GPT-6.1 Sol/Terra, GPT-6 Astra/Sol/Luna, GPT-5.6 Sol/Terra/Luna and older GPT-5.x appear in the Azure Retail Prices API (eastus2, queried 2026-11-06). Foundry also sells Grok, DeepSeek, Kimi, Llama, Mistral, Phi and MAI models.
- **Pydantic AI**: `azure:<deployment>` (Chat Completions) or `azure-responses:<deployment>` (Responses). The endpoint is `https://<resource>.openai.azure.com/openai/v1/`. Prompt caching works on GPT-5.6+ (30-minute TTL). Azure's Responses API lacks some OpenAI features, such as native web search. ([Pydantic AI Azure docs](https://pydantic.dev/docs/ai/models/azure/))
- **Managed Identity / keyless auth**: supported and recommended by Microsoft. With the v1 endpoint you pass `get_bearer_token_provider(DefaultAzureCredential() | ManagedIdentityCredential(client_id=…), "https://ai.azure.com/.default")` as `api_key` to the `openai` client (needs `openai` ≥ 1.106.0). You also assign the **Cognitive Services OpenAI User** role to the managed identity. ([Microsoft Learn: managed identity](https://learn.microsoft.com/azure/foundry-classic/openai/how-to/managed-identity), [switching endpoints](https://learn.microsoft.com/azure/developer/ai/how-to/switching-endpoints#authentication))
  - The Pydantic AI Azure page documents only API keys. **Unconfirmed** whether `AzureProvider` accepts a token provider directly. Building the `openai` client with the token provider and passing it to the provider is the safe route.
- **Data residency** ([deployment types](https://learn.microsoft.com/azure/ai-foundry/openai/how-to/deployment-types#azure-ai-foundry-deployment-data-processing-locations), [data privacy](https://learn.microsoft.com/azure/foundry/responsible-ai/openai/data-privacy)):
  - *Global* deployments may process prompts in any geography.
  - *Data Zone* deployments process them only within the US or EU data zone.
  - *Regional (Standard)* deployments process them in-region, but not every model offers a regional SKU. For example, GPT-6.x in eastus2 lists only Global and Data Zone prices.
  - Data at rest stays in the resource's geography in every case.
  - Prompts and completions are not used to train models.
- **Tool calling quality**: GPT-5.x/6.x are strong tool callers; this is the same model family as OpenAI direct. One OpenCode doc note: Azure's stricter "DefaultV2" content filter can refuse requests, and switching the filter fixes it. Log-heavy RCA prompts could trigger filters (**unconfirmed** how often).
- **Pricing** ([Azure Retail Prices API](https://prices.azure.com/api/retail/prices), eastus2, Standard, short context ≤272K). Prices are input / cached input / output:

| Model | Global | Data Zone |
|---|---|---|
| GPT-6.1 Sol | 2.00 / 0.10 / 10.00 | 2.20 / 0.11 / 11.00 |
| GPT-6.1 Terra | 1.00 / 0.05 / 5.00 | 1.10 / 0.055 / 5.50 |
| GPT-6 Luna | 0.10 / 0.01 / 0.50 | 0.11 / 0.011 / 0.55 |
| GPT-6 Astra | 10.00 / 1.00 / 50.00 | 11.00 / 1.10 / 55.00 |

  Long context (>272K input) doubles the input price and adds about 50% to output.

### 1b. OpenAI direct

Prices are input / cached input / output ([pricing](https://developers.openai.com/api/docs/pricing)):

- GPT-6.1 Sol: 2.00 / 0.10 / 10.00
- GPT-6.1 Terra: 1.00 / 0.05 / 5.00
- GPT-6 Luna: 0.10 / 0.01 / 0.50
- GPT-6 Astra: 10 / 1 / 50
- GPT-5.3-Codex: 1.75 / 0.175 / 14.00
- gpt-5.4-mini: 0.75 / 0.075 / 4.50

API data is not used for training by default. Abuse-monitoring logs are kept up to 30 days. Zero data retention and modified abuse monitoring need approval. In-region *processing* is available only in the US, Europe and the UAE ([your data](https://developers.openai.com/api/docs/guides/your-data)). Auth is an API key only (no workload identity), which is weaker than Azure for our "workload identity first" rule.

### 1c. Gemini (Gemini API and Google Cloud / Vertex)

- **Pydantic AI**: `google:` (Gemini API) or `google-cloud:` (`GoogleCloudProvider(location=…)`). Auth is ADC, a service account, or an API key ([Pydantic AI Google docs](https://pydantic.dev/docs/ai/models/google/)). Workload identity federation works through ADC (standard Google auth; not stated on the Pydantic page).
- **Residency on Vertex**: the *global* endpoint has "no data residency guarantees". The `us` and `eu` multi-region and regional endpoints keep ML processing in that jurisdiction ([Vertex data residency](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/learn/data-residency)). Gemini 4 Argon is served only on `global`, `us` and `eu`, not on single regions.
- **Pricing**, Gemini API paid tier ([pricing](https://aistudio.google.com/docs/pricing)):
  - **Gemini 4 Argon**: 2.00 in / 10.00 out / 0.10 cached. This is a promo price "through November 30, 2026"; the later price is not shown, so it is **unconfirmed**.
  - **Gemini 3.1 Pro Preview**: 2.00 / 12.00 at ≤200K prompt, 4.00 / 18.00 above that.
  - **Gemini 3.8 Flash**: 0.75 / 3.75 until 2026-12-31, then **1.50 / 7.50** from 2027-01-01.
  - Paid-tier data is not used to improve products; free-tier Flash data is.
  - Vertex prices could not be read from the Vertex pricing page (**unconfirmed**, assumed close to the Gemini API).

### 1d. Amazon Bedrock (non-Claude)

- **Pydantic AI**: `bedrock:` (Converse API: Amazon Nova, Meta, Mistral, DeepSeek, Qwen, Cohere, some OpenAI models) and `bedrock-mantle:` (OpenAI-compatible: GPT-5.x/GPT-6 and gpt-oss). Auth is an AWS credential chain or a Bedrock API key ([Pydantic AI Bedrock docs](https://pydantic.dev/docs/ai/models/bedrock/)). IAM roles and workload identity work through boto3.
- **Prices**, us-east-1 on-demand, input / output ([AWS Price List API](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonBedrockFoundationModels/current/us-east-1/index.json), published 2026-10-12 / 2026-11-02):
  - Amazon Nova 2.0 Pro: 1.375 / 11.00 (1.25 / 10.00 cross-region global)
  - Nova 2.0 Lite: 0.33 / 2.75
  - Kimi K3: 3.30 / 16.50
  - Qwen3-Coder-480B: 0.45 / 1.80
  - DeepSeek v3.2: 0.62 / 1.85
  - gpt-oss-120b: 0.15 / 0.60
  - OpenAI GPT-5.x/6 on Bedrock: price not found in the price list (**unconfirmed**).
- **Fit**: good if a deployment is AWS-only. Open-weight models are cheap, but their tool-calling reliability on long agentic loops is below frontier models (**unconfirmed for our workload**; measure with the evaluation harness).

### 1e. Self-hosted OpenAI-compatible (vLLM, Ollama, LiteLLM)

- Pydantic AI has `vllm:`, `ollama:` and `litellm:` prefixes, or `OpenAICompatibleProvider`.
- **vLLM** (0.33.0, 2026-11-02) needs `--enable-auto-tool-choice --tool-call-parser <parser>` for tool calling. `required` and named tool choice use structured outputs, which guarantee "a validly-parsable function call - not a high-quality one". In `auto` mode, tools without `strict: true` may get malformed arguments ([vLLM tool calling](https://docs.vllm.ai/en/latest/features/tool_calling/)).
- **Cost** is GPU time, not tokens, so there is no per-Investigation list price. Data never leaves the network.
- **Fit**: the most restrictive environments. Expect weaker RCA quality, and gate on evaluation scores before you use it.

### 1f. GitHub Copilot as a model provider

- Pydantic AI `github-copilot:` uses a bearer token: a GitHub OAuth user token (`gho_`) or a Copilot API token. Fine-grained PATs got 401 in the authors' test, and classic PATs are unsupported. Only models that expose `/chat/completions` work: Claude, Gemini, Kimi and `gpt-5.4` "at the time of writing". Most GPT-5.6+/6.x and all Grok IDs are Responses-only and **unreachable** this way. The provider does not refresh tokens ([Pydantic AI Copilot docs](https://pydantic.dev/docs/ai/models/github-copilot/)).
- Billing is in AI credits at the same per-token rates as the vendor list prices (see §2c). Copilot also bills a **cache write** cost for newer OpenAI and Anthropic models.
- **Server-to-server**: GitHub documents an **installation access token of a GitHub App with the org permission `organization_copilot_requests: read`** for "services outside GitHub Actions" ([S2S tokens](https://docs.github.com/en/copilot/how-tos/copilot-sdk/auth/server-to-server-tokens), [manage app access](https://docs.github.com/en/copilot/how-tos/administer-copilot/manage-for-organization/manage-app-copilot-access); public preview). The org pays, only models allowed by org policy can be used, and there are no per-app budgets.
  - **Unconfirmed**: whether Pydantic AI's provider accepts an installation token (it documents only user and Copilot tokens).
- **Fit**: attractive where a Copilot Business/Enterprise contract exists and direct model APIs are not approved. It fits our GitHub App model: add one more permission to the read token's App, or use a separate App. The catch is a narrower model choice through Chat Completions.

## 2. GitHub Copilot

### 2a. Cloud agent ("assign an issue → PR")

Sources: [about Copilot on GitHub / cloud agent](https://docs.github.com/en/copilot/concepts/agents/cloud-agent/about-cloud-agent), [API](https://docs.github.com/en/copilot/how-tos/use-copilot-agents/cloud-agent/use-cloud-agent-via-the-api).

- **Starting it**: assign an issue to the `copilot-swe-agent` bot (REST/GraphQL, public preview), or `POST /agents/repos/{owner}/{repo}/tasks` with `prompt`, `base_ref`, `model` and `create_pull_request`. Task states are `queued`, `in_progress`, `completed`, `failed`, `idle`, `waiting_for_user`, `timed_out` and `cancelled`.
- **Auth**: **user-to-server tokens only** (PAT, OAuth, or GitHub App *user* token). **Installation tokens are not supported**, so the agent would always act as a person, not as our bot.
- **Environment**: GitHub Actions runner (59-minute hard limit, single repo, self-hosted runners allowed) or the new cloud sandbox (default since 2026-10-28; multi-repo within one org, no custom compute). One branch and one PR per task. Works only on GitHub-hosted repos. Rulesets can block it unless a bypass is configured.
- **Controls**: custom instructions, custom agents, MCP servers, hooks, firewall allowlists, content exclusions, and model choice. Session logs are kept 28 days (Actions) or for the life of the account (sandbox).
- **Billing**: tokens in AI credits, plus compute from the account's Actions/sandbox allowance.
- **Implication**: it owns its own inner loop and environment and opens the PR itself. That conflicts with our rules that the pipeline owns the loop, that the Fix gate comes *before* any PR, and that the write token is minted only after approval. **Not usable as the Fix proposer.** At most it is a later "hand off approved RCA to Copilot" option, which would sit outside the Investigation's trust boundary.

### 2b. Copilot CLI and SDK (headless)

- **CLI** `@github/copilot` 1.0.106 ([programmatic use](https://docs.github.com/en/copilot/how-tos/copilot-cli/automate-copilot-cli/run-cli-programmatically), [reference](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-programmatic-reference)). Useful flags:
  - `-p PROMPT`, `-s` (silent), `--output-format json` (JSONL events)
  - `--model`, `--no-ask-user`
  - Tool controls: `--available-tools`, `--allow-tool` / `--deny-tool` with filters such as `shell(git:*)` and `write(path)`, plus `--allow-url` / `--deny-url`
  - `--secret-env-vars` (redaction), `--share=PATH` (transcript export), `--assisted-approval` (model-based approval of eligible requests)
  - Auth through `COPILOT_GITHUB_TOKEN`, the Actions `GITHUB_TOKEN` with `copilot-requests: write`, or a GitHub App installation token.
- **SDK** (TypeScript, Python `github-copilot-sdk` 1.0.28, Go, .NET, Java, Rust) has sessions, hooks, a permission handler and observability ([SDK docs](https://docs.github.com/en/copilot/how-tos/copilot-sdk)). **BYOK** supports OpenAI, Azure OpenAI/Foundry, Anthropic, Ollama, Foundry Local, and any OpenAI-compatible endpoint (vLLM, LiteLLM), which bypasses Copilot auth and billing ([BYOK](https://docs.github.com/en/copilot/how-tos/copilot-sdk/auth/byok)).
- **Implication**: a viable pluggable **Fix-proposer engine**, run inside our stage in our worktree with our tool allowlist. Its output is parsed from JSONL. It is less portable than OpenCode (one vendor's agent runtime), but BYOK removes the dependency on Copilot billing.

### 2c. Licensing and quotas (usage-based billing since 2026-06-01)

Sources: [plans](https://docs.github.com/en/copilot/get-started/plans), [org billing](https://docs.github.com/en/copilot/concepts/billing-and-usage/organizations-and-enterprises/billing), [models and pricing](https://docs.github.com/en/copilot/reference/copilot-billing/models-and-pricing), [changelog 2026-04-27](https://github.blog/changelog/2026/04/27/github-copilot-is-moving-to-usage-based-billing/).

| Plan | Price | AI credits per month (1 credit = $0.01) |
|---|---|---|
| Pro / Pro+ / Max (individual) | $10 / $39 / $100 | 1,500 / 7,000 / 20,000 (base + flex) |
| **Business** | **$19 per seat** | **1,900 per user, pooled across the org** |
| **Enterprise** | **$39 per seat** | **3,900 per user, pooled** |
| Copilot access (Enterprise Cloud users / standalone) | $0 / $10 per user | none; metered from first use |

- **"Premium requests" no longer exist for monthly plans.** Usage is per-token at per-model rates, converted to credits. Examples (input / cached / cache write / output): GPT-6.1 Sol 2.00 / 0.10 / 2.50 / 10.00; GPT-6.1 Terra 1.00 / 0.05 / 1.25 / 5.00; Gemini 4 Argon 2.00 / 0.10 / – / 10.00; Gemini 3.8 Flash 0.75 / 0.075 / – / 3.75.
- **Overage**: $0.01 per credit once the pool is exhausted. Paid overage is **on by default** for Business and Enterprise; an admin must disable it or set budgets (user, cost-center, org or enterprise budgets in USD). Unused credits do not roll over, and the pool resets on the first of each month (UTC).
- **Rough math**: a 2M-token Investigation on GPT-6.1 Sol is about $5.60, or about 560 credits. So one Business seat's 1,900 credits cover about three such runs a month before overage, and pooled credits are shared across the org.

### 2d. GitHub Models

**Retired on 2026-07-30.** The playground, catalog, inference API and BYOK are gone ([notice](https://docs.github.com/en/github-models)). It is not an option for production or prototyping.

## 3. Aider

Sources: [chat modes](https://aider.chat/docs/usage/modes.html), [scripting](https://aider.chat/docs/scripting.html), [LLMs](https://aider.chat/docs/llms.html). Release info: PyPI `aider-chat` 0.86.2 (2026-02-12); latest GitHub release v0.86.0 (2025-08-09); repo last pushed 2026-05-22; Apache-2.0.

- **Modes**:
  - `ask` discusses the code and never edits.
  - `code` edits files.
  - `architect` has one model propose a change and an editor model turn it into file edits.
  - `help` answers questions about Aider itself.
- **Models**: almost any model through LiteLLM. Azure uses `azure/<deployment>` with `AZURE_API_KEY` (API key; Entra not documented, **unconfirmed**). GitHub Copilot works as an OpenAI-compatible base (`https://api.githubcopilot.com` plus an OAuth token). Ollama and OpenAI-compatible endpoints also work.
- **Headless use**: `aider --message/-m` or `--message-file` with `--yes`, `--no-auto-commits` and `--dry-run`. The Python `Coder.create(...).run()` API is "not officially supported or documented".
- **Gaps for us**:
  - no tool/permission model (it edits the files you add; shell commands need confirmation or `--yes`)
  - no structured JSON event stream
  - by default it auto-commits into the repo
  - no session resume beyond chat history files
  - release cadence has slowed
- **Fit**:
  - **Investigation**: poor. It is a pair-programmer, not a tool-using investigator; `ask` mode only reads files you hand it.
  - **Fix proposer**: possible as a "diff applier". Our stage picks the files, Aider (architect or code mode, `--no-auto-commits`) edits the worktree, and we take `git diff` as the Fix proposal. Its edit formats are well tested. Its weaknesses are auditability and maintenance. Rank it below OpenCode.

## 4. OpenCode

Sources: [repo](https://github.com/anomalyco/opencode) (MIT; latest release **v1.19.5, 2026-10-28**; about 225k stars; pushed daily), docs in the repo: [CLI](https://opencode.ai/docs/cli), [permissions](https://opencode.ai/docs/permissions), [providers](https://opencode.ai/docs/providers), [server](https://opencode.ai/docs/server), [SDK](https://opencode.ai/docs/sdk), [agents](https://opencode.ai/docs/agents); [Copilot changelog 2026-01-16](https://github.blog/changelog/2026-01-16-github-copilot-now-supports-opencode/).

- **Providers**: built on the Models.dev catalog with 75+ providers, including OpenAI, **Azure OpenAI** (API key, or **Entra ID through an Azure CLI session**; Managed Identity **unconfirmed**; deployment names must match model names or be mapped in config), Azure Cognitive Services, **Amazon Bedrock**, **Google Vertex**, Anthropic, Ollama, LM Studio, llama.cpp, OpenRouter, LiteLLM-style gateways, and **any OpenAI-compatible endpoint** through `@ai-sdk/openai-compatible` with a `baseURL`.
- **GitHub Copilot login**: device flow, officially supported by GitHub since 2026-01-16 for paid Pro, Pro+, Business and Enterprise ("no additional AI license needed"). Usage bills to Copilot AI credits. Some models need Pro+.
- **Headless use**:
  - `opencode run "<prompt>"` with `--model provider/model`, `--agent`, `--format json` (raw JSON events), `--continue` / `--session <id>` / `--fork`, `--auto` (auto-approve anything not explicitly denied), `--dir` and `--attach http://host:4096`.
  - `opencode serve` is a headless HTTP server with an **OpenAPI 3.1** spec and HTTP basic auth (`OPENCODE_SERVER_PASSWORD`). It has session create/fork/abort/revert, `POST /session/:id/message` (synchronous) or `prompt_async`, `GET /session/:id/diff`, permission responses (`POST /session/:id/permissions/:id`), and an SSE event stream.
  - A generated **JS/TS SDK** `@opencode-ai/sdk` (v2 adds structured output). **No official Python SDK** (**unconfirmed**); call the HTTP API from Python.
- **Permissions**: `permission` config with `allow` / `ask` / `deny` per tool (`edit`, `bash`, `webfetch`, `external_directory`, …). There are glob rules per command or path (last match wins), for example `bash: {"*": "deny", "./gradlew test*": "allow"}` or `edit: {"*": "deny", "src/**": "allow"}`. Explicit `deny` still applies under `--auto`. Built-in agents:
  - **Build**: all tools.
  - **Plan**: denies edits except plan files.
  - **Explore**: read-only subagent.
  - Custom agents can carry their own prompt and permissions.
- **Session resume**: sessions persist and can be continued by ID or forked. Over the server, a pending permission is a resumable event.
- **Maturity**: the 1.x line is fast-moving, with frequent releases. Config keys have changed before (`tools` was deprecated in v1.1.1), so pin a version.
- **Fit**:
  - **Investigation**: technically capable through Plan/Explore with read-only permissions. But using it would hand the inner loop, context and tool surface to a third-party runtime. That breaks our 12-factor rule for stages that must record cited Findings and use our Observability adapter tools. Not recommended for the investigation stages.
  - **Fix proposer**: **best non-Claude engine.** Run `opencode serve` per Investigation inside the worktree, pinned to the approved RCA. Use a custom "fix" agent with `edit` allowed only under the service's source paths, `bash` allowed only for build/test commands, and `webfetch` and git push denied. Stream events into our event log, take `GET /session/:id/diff` as the Fix proposal, and never let it open the PR (our Open-draft-PR stage does that after the Fix gate).

## 5. Comparison table

| Option | Kind | Auth / identity | Residency control | Headless / API | Tool & permission control | Licence / terms | Cost model | Investigation stages | Fix proposer |
|---|---|---|---|---|---|---|---|---|---|
| **Azure OpenAI / Foundry** (via Pydantic AI) | Model API | **Entra ID / Managed Identity** (keyless) or key | Global, **Data Zone (US/EU)**, Regional | Yes (OpenAI v1) | Ours (we own tools) | Azure terms; no training on prompts | Per token, same as OpenAI at Global, +10% at Data Zone | **Yes: preferred fallback** | Yes, with our own fix agent |
| OpenAI direct | Model API | API key only | Regional processing only US/EU/UAE (approval) | Yes | Ours | No training by default; 30-day abuse logs | Per token | Yes | Yes, with our own fix agent |
| Gemini API / Vertex | Model API | ADC / service account / WIF | Vertex `us` / `eu` / regional; global has no guarantee | Yes | Ours | Paid tier not used for training | Per token (Argon promo to 2026-11-30; Flash doubles 2027-01-01) | Yes | Yes, with our own fix agent |
| Bedrock (non-Claude) | Model API | IAM / API key | AWS region; cross-region global optional | Yes | Ours | AWS terms | Per token (Nova Pro 1.375 / 11; open-weight models cheaper) | Yes (evaluate quality) | Yes (evaluate) |
| Self-hosted vLLM / Ollama | Model API | Network-local | Full | Yes (OpenAI-compatible) | Ours | Model licence | GPU cost | Only if evaluations pass | Only if evaluations pass |
| Copilot as a model provider | Model API (Chat Completions) | User OAuth token or **App installation token (preview)** | GitHub-controlled | Yes | Ours | Copilot product terms; org policies apply | AI credits per token; seat pool | Yes (limited model set) | Yes, with our own fix agent |
| Copilot cloud agent | Hosted coding agent | **User token only** | GitHub | REST tasks API / issue assignment (preview) | Its own (instructions, MCP, firewall) | Copilot plan | Credits + compute minutes | No | **No**: owns its loop and opens the PR itself |
| Copilot CLI / SDK | Coding engine | Token / App installation token / BYOK | Per model provider | `-p`, JSONL, SDK sessions | `--allow-tool` / `--deny-tool` / `--available-tools`, URL rules | Copilot terms (or BYOK) | Credits or BYOK tokens | Not recommended (loop ownership) | **Yes (2nd choice)** |
| **OpenCode** | Coding engine (OSS) | Provider keys, Azure CLI Entra, Copilot device login | Per model provider | `run --format json`, **HTTP server (OpenAPI)**, JS SDK | **allow / ask / deny + glob rules**, read-only agents | **MIT** | Provider tokens or Copilot credits | Not recommended (loop ownership) | **Yes (best non-Claude engine)** |
| Aider | Coding engine (OSS) | Provider keys (LiteLLM) | Per model provider | `--message`, unofficial Python API | None (file list + confirmations) | Apache-2.0; slow releases | Provider tokens | No | Possible as a diff applier (3rd choice) |
| GitHub Models | Model API | – | – | **Retired 2026-07-30** | – | – | – | No | No |

## 6. Worked cost estimates

Assumptions:

- An Investigation is agentic and input-heavy: **90% input / 10% output**, with no prompt-cache hits (upper bound). The "50% cache" column assumes half the input tokens are cache reads; cache-write surcharges are ignored.
- A **Fix round = 0.3M tokens at 85% input / 15% output** (reads the suspect code, proposes a patch, one or two test-and-repair iterations).
- List prices are from §1. Copilot credits use the same per-token rates for these models, plus cache-write charges on newer OpenAI models.

| Model (route) | 0.5M | 2M | 5M | 5M, 50% cache | Fix round (0.3M) |
|---|---|---|---|---|---|
| GPT-6.1 Sol (OpenAI / Azure Global / Copilot) | $1.40 | $5.60 | $14.00 | $9.72 | $0.96 |
| GPT-6.1 Sol (Azure Data Zone) | $1.54 | $6.16 | $15.40 | $10.70 | $1.06 |
| GPT-6.1 Terra (OpenAI / Azure Global) | $0.70 | $2.80 | $7.00 | $4.86 | $0.48 |
| GPT-6 Luna (OpenAI / Azure Global) | $0.07 | $0.28 | $0.70 | $0.50 | $0.05 |
| GPT-5.3-Codex (OpenAI) | $1.49 | $5.95 | $14.88 | $11.33 | $1.08 |
| Gemini 4 Argon (promo price) | $1.40 | $5.60 | $14.00 | $9.72 | $0.96 |
| Gemini 3.1 Pro Preview | $1.50 | $6.00 | $15.00 | $10.95 | $1.05 |
| Gemini 3.8 Flash (2026 price) | $0.53 | $2.10 | $5.25 | $3.73 | $0.36 |
| Amazon Nova 2.0 Pro (Bedrock) | $1.17 | $4.67 | $11.69 | n/a | $0.85 |
| Kimi K3 (Bedrock) | $2.31 | $9.24 | $23.10 | $16.42 | $1.58 |
| Qwen3-Coder-480B (Bedrock) | $0.29 | $1.17 | $2.92 | n/a | $0.20 |
| gpt-oss-120b (Bedrock) | $0.10 | $0.39 | $0.97 | n/a | $0.07 |

Reading the table:

- Mixing tiers by stage is the main cost lever. Example: a small model for log/metric summarising in Evidence and Change, and a frontier model for the RCA writer and Fix proposer. A 2M-token run with about 70% of tokens on a small model costs roughly **$2** instead of $5.60.
- On Copilot Business, the pooled 1,900 credits per seat ($19) are used first. After that, overage is billed at the same per-token rates ($0.01/credit), so the per-run figures above hold.
- Copilot cloud agent and Actions-based runs also use compute minutes, which are not included above.

## 7. What this means for our stages

- **Pre-fetch**: no LLM, so it is unaffected.
- **Evidence / Change / Code-locator / RCA writer**: any model API above through Pydantic AI, chosen per stage in config. A coding engine is not needed and not wanted, because these stages must use only our tools and emit cited Findings. Requirements for the chosen model: reliable parallel tool calls, a large enough context (≥200K), and structured output for Findings. Prefer Azure OpenAI with Managed Identity and Data Zone where the deployment is on Azure. Keep `ModelFallback` optional and recorded as events.
- **Fix proposer**, in order of preference:
  1. **Our own Pydantic AI fix agent** (read/edit/apply-patch/run-build-and-tests tools in the per-Investigation worktree). It works with every provider and keeps the loop ours.
  2. A **pluggable engine** behind the same stage contract (input: approved RCA + worktree + allowlists; output: diff + test log + transcript events): Claude Agent SDK where allowed, **OpenCode** otherwise, Copilot CLI/SDK where a Copilot contract is the only approved route, and Aider only as a fallback diff applier.
  3. **Never** the Copilot cloud agent inside the Investigation.
- **Fix gate / Open draft PR**: unchanged. No engine gets the write token or opens PRs.

## Open points and unconfirmed items

- Whether Pydantic AI's `AzureProvider` takes an Entra token provider directly, or needs a pre-built `openai` client.
- Whether Pydantic AI's `github-copilot:` provider and the raw Copilot inference endpoint accept a GitHub App installation token (GitHub documents this for the SDK and CLI).
- Whether OpenCode's Azure provider supports Managed Identity (documented: API key and Azure CLI Entra) and whether it has an official Python SDK.
- Gemini 4 Argon's price after 2026-11-30; Vertex regional prices; prices for OpenAI models on Bedrock.
- Tool-calling quality of open-weight models (Bedrock or self-hosted) on our RCA tasks: needs the evaluation harness.
- Azure content-filter false positives on raw log text.
