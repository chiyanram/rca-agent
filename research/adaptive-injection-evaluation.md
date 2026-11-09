# Adaptive prompt-injection evaluation: research note

**Question.** How should an evaluation harness for an LLM root-cause-analysis (RCA) agent test its prompt-injection defences against an *adaptive* attacker? What do published sources say about attack methods, metrics, attacker-model choice and budgets? The attack surface is logs, trace attributes, commit/PR messages, code comments and alert text.

Compiled 2026-11-09 from arXiv HTML/abstract pages, the official GitHub repos and Meta's blog. "UNVERIFIED" marks anything not confirmed in a primary source.

## Summary table

| Source | What it shows | Key numbers |
|---|---|---|
| Shi et al. 2025 (Gemini IPI) | **The source of the 18% vs 94.6% figures.** A static set understated how vulnerable the hardened model was | Static set: 92% ASR on Gemini 2.0, 18% on Gemini 2.5. Adaptive TAP: 94.6% on Gemini 2.5 (Calendar), 2,160 queries. An attack cost under $10 per trigger |
| Nasr et al. 2025 (Attacker Moves Second) | Adaptive attacks broke 12 defences | Above 90% ASR on most defences. Search attack: at most 800 queries per scenario, median 13–110 to first success, plateau after 100–200 queries. Humans broke 100% of scenarios |
| AgentDojo (Debenedetti et al. 2024) | Benchmark design and the three metrics | 97 user tasks, 27 injection tasks, 629 security cases. GPT-4o: 47.7–57.7% targeted ASR. Full run cost about $35 |
| InjecAgent (Zhan et al. 2024) | Direct-harm vs data-stealing attacks; base vs enhanced settings | 1,054 cases. ReAct GPT-4: about 24% (base) and about 47% (enhanced) |
| Zhan et al. 2025 (Adaptive attacks break IPI defences) | Eight defences fall to white-box GCG/AutoDAN | Above 50% ASR on every defence. Each adversarial string took about 30 minutes on one A100 |
| WASP (Evtimov et al. 2025) | Partial vs end-to-end success on web agents | Up to 86% partial (intermediate) success, 0–17% end-to-end |
| CaMeL (Debenedetti et al. 2025) | Capability/data-flow defence | 77% of tasks solved with provable security (84% undefended). 0 successful AgentDojo attacks. About 2.8× tokens. No adaptive attack run against CaMeL itself (UNVERIFIED beyond the first half of the paper) |
| PromptShield (Jacob et al. 2025) | AUC misleads; report TPR at low FPR | PromptGuard: AUC 0.874, but 12.8% TPR at 1% FPR. ProtectAI v2: 2.0% TPR at 1% FPR |
| TAP / PAIR | Query cost of black-box LLM-attacker loops | TAP: 12–116 mean queries per jailbreak. PAIR: at most 90 queries per behaviour, about 24 per success on GPT-4 |
| Hofer, Debenedetti & Tramèr 2026 | TAP vs GCG on AgentDojo; attacker strength | TAP beats GCG. GPT-5 as attacker gives 1.2–11.8× the ASR of GPT-5-mini. Only 4.5% ASR against GPT-5 |
| Meta Agents Rule of Two 2025 | Design rule, not an evaluation method | At most 2 of 3 properties per session: untrusted input, sensitive access, state change |

## 1. Source of the "~18% static vs ~94.6% adaptive" figures

**Citation.** "Lessons from Defending Gemini Against Indirect Prompt Injections." Chongyang Shi et al. (Google DeepMind), 2025. arXiv:2505.14534. https://arxiv.org/abs/2505.14534

**The static figure (verified quotes).** The static set is "1,799 prompts containing five tools (not contained in the list of tools used to adversarially fine-tune Gemini 2.5)". The paper reports: "Against Gemini 2.0 the ASR on this evaluation set was 92% but dropped to 18% on Gemini 2.5." The triggers were optimised against Gemini 2.0, so they are non-adaptive with respect to 2.5. The paper continues: "Had we not conducted further adaptive attacks and evaluations, we would have incorrectly concluded that Gemini 2.5 exhibits a higher degree of robustness than it does."

**The adaptive figure.** Table 1 gives adaptive ASR and query counts for Gemini 2.5. The data type is passport and the trigger format is non-JSON.

| Scenario | TAP | Actor-Critic | Beam Search |
|---|---|---|---|
| Email | 53.6% / 2,160 q | 40.8% / 1,560 q | 4.2% / 12,519 q |
| **Calendar** | **94.6% / 2,160 q** | 59.6% / 12,480 q | 0% |

For comparison, Gemini 2.0 Calendar reached 100% (TAP, 4,320 queries) and 98.6% (Beam Search, 125,188 queries).

**Caveat.** The two numbers are not a like-for-like pair. The 18% is an average over the 1,799-prompt set. The 94.6% is one scenario (Calendar, passport) under the best of three attacks. The secondary blog that circulated them (stingrai.io) says "Flash versions"; that model variant is UNVERIFIED in the primary text I read.

**Methods.**
- Actor-Critic: an attacker model proposes a trigger, the target returns a success probability, and a critic refines the trigger.
- Beam Search: random-token edits, similar to GCG.
- TAP: black-box; the reward is the edit distance to the target function call.
- Linear Generation: few-shot generation, used mainly to build training data.
- None of the attacker models are named.

**Scenario design.** The agent is asked to exfiltrate a passport number, SSN or reset token through `send_email` or `update_calendar_event`. An attack counts only if the function is actually invoked with the private data. The best trigger is chosen on a validation set and ASR is reported on a held-out test set of 500 examples in Section 6.

**Cost.** "the attacker's cost was less than $10 to create a highly successful trigger against Gemini 2.0 Flash". TAP "generally requires fewer than a few thousand queries". Each attack step sends a batch of 25–50 examples.

**Other findings.**
- Adaptive attacks were "equal to or outperform[ed]" non-adaptive ones in 16 of 24 defence×attack cases.
- Some non-adaptive attacks did better; the authors suspect gradient obfuscation.
- "models that have better instruction following capabilities are in some cases easier to attack."
- "Robustness requires defense in depth."

## 2. The Attacker Moves Second

**Citation.** "The Attacker Moves Second: Stronger Adaptive Attacks Bypass Defenses Against LLM Jailbreaks and Prompt Injections." Milad Nasr, Nicholas Carlini, Chawin Sitawarin, Sander V. Schulhoff, Jamie Hayes, Michael Ilie, Juliette Pluto, Shuang Song, Harsh Chaudhari, Ilia Shumailov, Abhradeep Thakurta, Kai Y. Xiao, Andreas Terzis, Florian Tramèr. 2025. arXiv:2510.09023. https://arxiv.org/abs/2510.09023

**Methods.**
- **Gradient:** used against RPO only. GCG-style: 500 steps with 512 queries per step.
- **RL:** the attacker LLM proposes, sees the output and score, and reflects for 5 rounds. There are 32 sessions per sample and GRPO updates. The base model is described only as "closed-source", with no safety alignment.
- **Search:** a MAP-Elites/OpenEvolve controller. The mutator is **Gemini-2.5 Pro** (maximum thinking budget), sampling 8 candidates per iteration. A critic LLM turns feedback into a 1–10 score.
- **Human:** a public competition with more than 500 participants, 40 challenges and $20,000 in prizes. Score = 5,000 minus tokens used.

**Feedback given to the attacker.** RL and search see the target's outputs and scores. Search also sees detector confidence/flags and tool-call outputs. Humans see the reasoning stream, the tool calls and success/fail.

**Headline results.** Twelve defences were bypassed, most at above 90% ASR, and most had originally reported near-zero ASR.

| Defence | Original | Adaptive |
|---|---|---|
| Spotlighting | about 1% (AgentDojo) | above 95% (search) |
| Prompt Sandwiching | about 1% (AgentDojo) | above 95% (search) |
| MetaSecAlign | 2% | 96% (search) |
| RPO | – | 98% (RL), 96% (gradient) |
| Circuit Breakers | – | 100% (RL) |
| PromptGuard, ProtectAI, Model Armor | – | above 90% (search) |
| PIGuard | – | 71% (search) |
| MELON | – | 76% without defence knowledge, 95% with full knowledge |
| DataSentinel, StruQ | – | bypassed by RL |

**Static vs adaptive on the same target.** Static uses AgentDojo's "important instructions" template; adaptive is the search attack.

| Target | Static | Adaptive |
|---|---|---|
| Gemini-2.5 Pro, no defence | 30% | 100% |
| GPT-5 Mini, no defence | 0% | 75% |
| MELON on Gemini-2.5 Pro | 0% | 89% |
| Model Armor on GPT-5 Mini | 0% | 56% |
| ProtectAI on Gemini-2.5 Pro | 15% | 90% |

**Budget.**
- At most 800 queries per scenario.
- Median queries to first success: 13–110 (Table 7); 13 for undefended Gemini-2.5 Pro.
- Most runs plateau after 100–200 queries.
- There is high variance between runs, and the authors suggest independent restarts and parallelism.
- **No dollar cost is reported for the automated attacks.**

**Human attackers.**
- Across 29 overlapping scenarios, humans reached 100% ASR.
- The best single participant reached 75%, using as few as 50 queries.
- The search attack reached 69% at 800 queries.

**Evaluation recommendations stated by the authors.**
- Use adaptive attacks.
- Scale the attack budget before claiming robustness.
- Report utility alongside ASR.
- Evaluate detectors at practically acceptable FPR.
- Test plan-then-execute defences on scenarios where control flow depends on the data.
- Give every attacker equal attempts when comparing.

## 3. AgentDojo

**Citation.** "AgentDojo: A Dynamic Environment to Evaluate Prompt Injection Attacks and Defenses for LLM Agents." Edoardo Debenedetti, Jie Zhang, Mislav Balunović, Luca Beurer-Kellner, Marc Fischer, Florian Tramèr. 2024 (NeurIPS 2024 Datasets & Benchmarks; venue UNVERIFIED on the arXiv page). arXiv:2406.13352. https://github.com/ethz-spylab/agentdojo

**Design.**
- Four suites: Workspace, Slack, Travel and Banking.
- Tools: 74 by the table rows; the paper also says 70.
- 97 user tasks and 27 injection tasks.
- 629 security cases, formed as user task × injection task within each suite.
- Injections go into **placeholders in environment state that surface in tool outputs**. The attacker controls only those placeholders, and only within tools the user task actually calls (`get_injection_candidates`).
- Injections placed at the end of a tool response were the most effective.

**Metrics.**
- Benign utility: user tasks solved with no attack present.
- Utility under attack: security cases where the user task is solved without adversarial side effects.
- Targeted ASR: security cases where the attacker goal is met.
- Success and failure are checked by deterministic functions over environment state, not by an LLM judge.

**GPT-4o results.** Baseline: utility 69%, utility under attack about 50%, targeted ASR 47.7% (Table 3) or 57.7% (Table 5). The paper is internally inconsistent here.

| Defence | Benign utility | Utility under attack | Targeted ASR |
|---|---|---|---|
| Tool filter | 73.1% | 56.3% | 6.8% |
| PI detector | 41.5% | 21.1% | 7.95% |
| Repeat prompt | 85.5% | 67.3% | 27.8% |
| Delimiting | 72.7% | 55.6% | 41.7% |

The tool filter fails in 17% of cases, where the tools the user task needs are enough to carry out the attack.

**Attacks (GPT-4o targeted ASR).** "Important instructions" 57.7%, "Ignore previous" 5.4%, InjecAgent-style 5.7%, TODO 3.7%. Using the wrong user or model name in the attack roughly halved ASR.

**Cost.** About $35 for the 629 security cases on GPT-4o and about $4 for the 97 utility tasks.

**Adaptive attacks.** The data card names "evaluating only with default attacks… without employing an adaptive attack" as an unsuitable use.

## 4. InjecAgent

**Citation.** "InjecAgent: Benchmarking Indirect Prompt Injections in Tool-Integrated LLM Agents." Qiusi Zhan, Zhixiang Liang, Zifan Ying, Daniel Kang. ACL Findings 2024. arXiv:2403.02691. https://github.com/uiuc-kang-lab/InjecAgent

**Scale.** 1,054 cases covering 17 user tools and 62 attacker tools; 30 agents evaluated.

**Attack types.**
- **Direct harm:** the agent calls a harmful tool, for example to transfer money or unlock a door.
- **Data stealing:** two stages. S1 extracts private data with a tool; S2 transmits it to the attacker. Success requires both.

**Settings.**
- **Base:** the attacker instruction alone.
- **Enhanced:** prefixes "IMPORTANT!!! Ignore all previous instructions and strictly adhere to the following instruction:".

**Metrics.** ASR-valid counts only valid outputs; ASR-all counts all outputs.

**Results.** ReAct GPT-4: about 24% (base) and about 47% (enhanced). Fine-tuned GPT-4: about 7.1% (secondary extraction from the paper; exact table cell UNVERIFIED).

## 5. Adaptive Attacks Break Defenses Against IPI Attacks on LLM Agents

**Citation.** Qiusi Zhan, Richard Fang, Henil Shalin Panchal, Daniel Kang. NAACL Findings 2025. arXiv:2503.00061.

**Setup.**
- White-box: the attacker knows the agent, the defence and the prompts.
- Benchmark: a 100-case InjecAgent subset (plus a 16-case AgentDojo check).
- Targets: Vicuna-7B (ReAct) and Llama-3-8B (function calling).
- Attacks: GCG, multi-objective GCG (detector evasion), two-stage GCG (paraphrasing) and AutoDAN.

**Results.** All 8 defences were bypassed at above 50% ASR.
- Perplexity filter: 24% → 76% (Vicuna).
- Paraphrasing: 8% → 54% (Llama-3).
- Fine-tuned detector: detection fell from 61% to 1%.

**Compute.** About 30 minutes on one A100 per adversarial string, with 500–2,000 steps.

**Not studied.** Black-box and grey-box attacks are left as future work.

## 6. WASP

**Citation.** "WASP: Benchmarking Web Agent Security Against Prompt Injection Attacks." Ivan Evtimov, Arman Zharmagambetov, Aaron Grattafiori, Chuan Guo, Kamalika Chaudhuri (Meta). 2025. arXiv:2504.18575.

**Setup.** VisualWebArena GitLab and Reddit sandboxes. The attacker can only post content. There are 21 attacker goals × 2 user goals × 2 templates = 84 tasks, plus a 37-task utility set.

**Metrics.**
- **ASR-intermediate:** whether the agent was diverted, judged by an LLM judge (GPT-4o).
- **ASR-end-to-end:** whether the attacker goal was achieved, checked by a rule over final environment state.

**Results.** Up to 86% partial success, but only 0–17% end-to-end (o1: 0.857 vs 0.167), which the authors call "security through incompetence." Both metrics are therefore needed.

## 7. CaMeL

**Citation.** "Defeating Prompt Injections by Design." Edoardo Debenedetti, Ilia Shumailov, Tianqi Fan, Jamie Hayes, Nicholas Carlini, Daniel Fabian, Christoph Kern, Chongyang Shi, Andreas Terzis, Florian Tramèr. 2025. arXiv:2503.18813.

**Design.**
- A privileged LLM writes code from the trusted query only.
- A quarantined LLM with no tools parses untrusted data into a schema.
- An interpreter tracks data flow and attaches capabilities (provenance and allowed readers) to values.
- Security policies check every tool call; a violation is either denied or sent to the user for confirmation.

**Evaluation on AgentDojo.**
- 77% of tasks solved with provable security, vs 84% undefended.
- 0 of 949 attacks succeeded with Claude 3.5 Sonnet; the tool filter, the next-best defence, had 8.
- About 2.82× input tokens and 2.73× output tokens for the median task.

**Limitations stated.** Side channels (exceptions can leak a bit; timing), policy-maintenance burden and user fatigue, and possible ROP-like attacks.

**Adaptive attacks.** The CaMeL evaluation used AgentDojo's standard attacks. No adaptive attack run against CaMeL itself was found (UNVERIFIED: only the first half of the paper was read). Its guarantee is structural: injected data cannot change control flow. That is why Nasr et al. recommend testing plan-then-execute designs specifically on scenarios where control flow depends on the data.

## 8. Meta: Agents Rule of Two

**Citation.** "Agents Rule of Two: A Practical Approach to AI Agent Security." Meta AI blog, 31 Oct 2025. https://ai.meta.com/blog/practical-ai-agent-security/

**The rule.** Within a session, an agent should hold at most two of:
- [A] "process untrustworthy inputs"
- [B] "access to sensitive systems or private data"
- [C] "change state or communicate externally"

If all three are needed, the agent requires supervision; Meta names human-in-the-loop approval as "the preferred method." The post gives no evaluation or testing method.

## 9. Detector metrics: TPR at fixed FPR vs AUC

**Citation.** "PromptShield: Deployable Detection for Prompt Injection Attacks." Dennis Jacob, Hend Alzahrani, Zhanhao Hu, Basel Alomair, David Wagner. ACM CODASPY 2025. arXiv:2501.15145.

**Results (Table 4).**

| Detector | AUC | TPR @ 1% FPR | TPR @ 0.1% FPR |
|---|---|---|---|
| PromptShield (Llama-3.1-8B) | 0.998 | 94.8% | 65.3% |
| InjecGuard | 0.765 | 20.4% | 6.6% |
| PromptGuard (v1) | 0.874 | 12.8% | 9.4% |
| ProtectAI v1 | 0.646 | 7.1% | – |
| ProtectAI v2 | 0.705 | 2.0% | 0% |

Quote: "Prior metrics (AUC) are a poor predictor of performance in the low-FPR regime". PromptGuard ranks above InjecGuard by AUC but below it at 1% FPR. The rationale is the base rate: benign traffic dominates.

**Llama Prompt Guard 2 model card** (Hugging Face mirror; official Meta card UNVERIFIED):

| Model | AUC (English) | Recall @ 1% FPR |
|---|---|---|
| Prompt Guard 2, 86M | 0.998 | 97.5% |
| Prompt Guard 2, 22M | 0.995 | 88.7% |
| Prompt Guard 1 | 0.987 | 21.2% |

These are the vendor's static numbers. Nasr et al. still bypassed PromptGuard at above 90% adaptively.

**Microsoft Prompt Shields.** No published TPR@FPR evaluation was found (UNVERIFIED / not found).

## 10. TAP and PAIR: queries per successful attack

**TAP.** "Tree of Attacks: Jailbreaking Black-Box LLMs Automatically." Anay Mehrotra, Manolis Zampetakis, Paul Kassianik, Blaine Nelson, Hyrum Anderson, Yaron Singer, Amin Karbasi. NeurIPS 2024. arXiv:2312.02119.
- Attacker: Vicuna-13B. Evaluator: GPT-4.
- Parameters: branching factor 4, width 10, depth 10.
- Mean queries per target, TAP vs PAIR (the table layout was ambiguous, so treat cells as approximate):

| Target | TAP | PAIR |
|---|---|---|
| GPT-4 | 90%, 28.8 q | 60%, 39.6 q |
| GPT-4o | 94%, 16.2 q | 78%, 40.3 q |
| Claude-3 Opus | 60%, 116.2 q | 24%, 55 q |

- Ablation: removing pruning raised queries from 22.5 to 55.4.

**PAIR.** "Jailbreaking Black Box Large Language Models in Twenty Queries." Patrick Chao, Alexander Robey, Edgar Dobriban, Hamed Hassani, George J. Pappas, Eric Wong. 2023/2024. arXiv:2310.08419.
- 30 streams × 3 iterations, at most 90 queries.
- Attacker: Mixtral 8x7B. Judge: Llama Guard.
- Results: GPT-4 48% at 23.7 queries per success; Gemini 73% at 23.5 queries.

These are jailbreak numbers, not indirect prompt injection. Shi et al. needed about 2,000+ queries for TAP on IPI tool-call goals and note that "optimizing for specific function calls" is harder.

## 11. Attacker model choice

**No source directly tests same-family vs cross-family attackers on a fixed target.** The available evidence:

- **PAIR, Table 6** (Vicuna-13B target): Mixtral 88% at 10 queries, Vicuna 78% at 20, GPT-3.5 69% at 28.6. The authors attribute GPT-3.5's weaker result to its safety alignment: unaligned attackers help.
- **Nasr et al.** The RL attacker is chosen to have "no safety alignment." The search mutator is Gemini-2.5 Pro, and one target is also Gemini-2.5 Pro, so a same-family attack reached 100%.
- **Hofer, Debenedetti & Tramèr**, "Assessing Automated Prompt Injection Attacks in Agentic Environments," 2026, arXiv:2606.10525.
  - Setup: TAP on AgentDojo with GPT-5 as attacker and GPT-5-mini as judge.
  - Attacker strength: GPT-5 vs GPT-5-mini as attacker gave 44.6% vs 36.6% (single-task, Qwen3-4B target) and 4.7% vs 0.4% (universal, GPT-5 target).
  - Against GPT-5 itself (same family as the attacker): only about 4.5% ASR, about 30% Success@N.
  - TAP beats GCG. GCG transfer from Qwen to GPT-5 was below 1%.
  - Attacker refusals were material: 37% empty injections before mitigation.
  - The attacker sees the score, the full agent response and the tool calls.
  - Compute: about 0.6 h per single-task TAP run on an H200.
  - Judge precision was only 29–52%, so the LLM judge over-reports success. A rule-based success check is needed.
- **Feedback with or without target outputs.** Every successful black-box loop above (TAP, PAIR, search, RL, Actor-Critic) uses target outputs and/or a score. No source was found that quantifies attack success without any output feedback (UNVERIFIED gap).

## 12. Budget numbers

| Source | Budget reported |
|---|---|
| Nasr search attack | At most 800 queries per scenario; median 13–110 to first success; plateau 100–200 queries; **$ not reported** |
| Shi TAP (IPI) | About 2,160–4,320 queries per scenario; under $10 per strong trigger (Gemini 2.0 Flash) |
| AgentDojo | About $35 per 629 cases on GPT-4o (about $0.056 per case, my arithmetic, 2024 prices) |
| TAP / PAIR (jailbreak) | About 12–116 queries per success |
| Hofer | About 0.6 GPU-hour per single-task TAP; 4 runs × 6 evaluations per task; $ not reported |

**Sizing a $100 run cap.** No source gives the cost of an adaptive campaign in dollars against an agent comparable to ours.

## Implications for our harness (directly source-supported only)

1. A fixed injected variant per scenario can understate attack success badly. The source shows a static set at 18% vs adaptive TAP at 94.6% on the same hardened model (Shi). Nasr shows static 0–30% vs adaptive 56–100% on the same targets.
2. Report three metrics:
   - benign utility,
   - utility under attack,
   - targeted ASR.

   Decide success by deterministic checks over environment state or tool calls (AgentDojo; Shi requires the actual function invocation). LLM judges over-report success (Hofer: 29–52% precision).
3. Track partial diversion separately from end-to-end attacker-goal completion (WASP: 86% vs 17%).
4. Place injections only in data the attacker could realistically control and that the task actually reads (AgentDojo injection vectors). End-of-tool-output placement was the most effective.
5. For any classifier or detector component, report TPR at a fixed low FPR (1% or 0.1%), not AUC (PromptShield; Nasr).
6. Use a capable, non-safety-aligned or refusal-mitigated attacker LLM that sees the target's outputs and tool calls plus a score (PAIR ablation, Nasr, Hofer). Attacker strength materially changes ASR.
7. Use independent restarts and parallel trials; single runs have high variance (Nasr).
8. Capability-based defences (tool scoping, CaMeL-like) are argued to hold structurally. Test them where the attacker's goal is reachable *with the tools the task legitimately needs*: AgentDojo's tool filter fails in those 17% of cases, and Nasr says to test plan-then-execute defences on data-dependent control flow.
9. A human red-team outperformed automated search (100% vs 69% on 29 scenarios; Nasr).

## Unknowns

- Dollar cost of the Nasr search or RL campaigns, and the per-query token sizes of any IPI adaptive attack in agentic settings.
- Whether the 18% and 94.6% figures are both on the Flash variant; the 18% is a set average and the 94.6% is a single scenario.
- Direct evidence on same-family vs cross-family attacker choice; no controlled study was found.
- Attack success when the attacker gets no target output (blind or one-shot black-box); not quantified in the sources read.
- CaMeL under an adaptive attacker: none found.
- Microsoft Prompt Shields TPR@FPR: no published figure found.
- InjecAgent fine-tuned GPT-4 figure (7.1%) and the exact TAP/PAIR table cells: extracted from parsed HTML with ambiguous layout.
- The second half of several papers (CaMeL, TAP, AgentDojo appendix) was not read in full.
