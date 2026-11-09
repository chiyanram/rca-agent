# Evaluation techniques for an LLM RCA agent: research note

**Question.** What does "eval" cover beyond an LLM judge? Specifically: how to score one RCA report, how to compare Agent versions, how to avoid fooling ourselves with small suites and prompt optimisers, which public RCA/AIOps benchmarks exist, and how agent evaluation differs from single-output evaluation.

Compiled 2026-11-09 from arXiv abstract/HTML pages, ACL Anthology, JMLR, author-hosted PDFs, official GitHub repos and official vendor docs. Numbers marked **(own calculation)** were computed for this note with a short NumPy/SciPy script from standard formulas; they are illustrations, not results from a source. "UNVERIFIED" marks anything not confirmed in a primary source during this session.

Decisions already taken in this project, which this note relates to but does not reopen: Grades come from fixed checks against hidden Answer keys; an LLM judge is advisory only, has its own config, comes from a different Model family, and is calibrated on about 20 human-graded reports; an Evaluation run is Suite × Agent version × repeats (3, or 5 for approval), gated on pass@1, with pass^k tracked; the promotion bar is no regression on Champion-passed Scenarios, at most a 5-point pass@1 drop, at most +25% cost, plus human sign-off; a post-MVP Optimisation run sees only pass/fail on a Held-out set (at least 10 of at least 30 Scenarios). Open question on the Gap review: should promotion also require a paired significance test? Section 3 gives the evidence; it does not decide.

## Summary table

| Topic | Key source(s) | What it says | Key numbers |
|---|---|---|---|
| Overlap metrics | Reiter 2018; Maynez et al. 2020; Kryściński et al. 2019 | BLEU/ROUGE-style overlap does not measure factual correctness | BLEU unsupported "outside of MT"; entailment beats ROUGE for faithfulness |
| LLM judge biases | Zheng et al. 2023; Panickssery et al. 2024 | Position, verbosity, self-enhancement bias; models prefer their own outputs | GPT-4 judge >80% agreement with humans on chat preference |
| Judge validation | Bavaresco et al. 2025; Thakur et al. 2025; Anthropic 2026 | Judges must be validated per task against humans; percent agreement is not enough | Reliability varies by dataset and property |
| pass@k / pass^k | Chen et al. 2021; Yao et al. 2024 (τ-bench) | pass@k = at least one of k succeeds; pass^k = all k succeed | gpt-4o τ-retail pass^1 61.2% → pass^8 <25% |
| Error bars | Miller 2024 (Anthropic) | Paired differences, clustered SEs, repeats, power analysis | ~969 questions to detect 3 pts; "at least 1,000 questions" |
| Power | Card et al. 2020 | Most NLP comparisons are underpowered | — |
| Paired tests | Dietterich 1998; Koehn 2004; Berg-Kirkpatrick et al. 2012; Dror et al. 2018 | McNemar for single-run classifiers; paired bootstrap common in NLP | McNemar "only test with acceptable type I error" when run once |
| Selection overfitting | Cawley & Talbot 2010; Dwork et al. 2015; Recht et al. 2019 | Choosing the best of many on a finite set overfits that set; reused holdouts overfit | — |
| Prompt optimisers | DSPy (Khattab 2023); MIPRO (Opsahl-Ong 2024); GEPA (2025) | Optimise prompts against a metric on train/validation data | GEPA: reports validation and test separately |
| RCA benchmarks | OpenRCA, RCAEval, AIOpsLab, ITBench, Cloud-OpsBench | Telemetry or live-environment RCA tasks on open microservice demos | Best results 11–78% depending on benchmark |
| Agent eval | Anthropic 2026; Kapoor et al. 2024; Google ADK docs; Cloud-OpsBench | Outcome vs transcript grading; cost as a first-class metric | GPT-5 right answer without evidence closure in ~30% of cases |

## 1. Scoring one output

### 1a. Deterministic / programmatic checks

**What they are.** Code that compares the report (or the environment state after the Trial) against a structured key: right component, right commit, right cause category, forbidden action did or did not happen. This is what OpenRCA, ITBench, AIOpsLab and τ-bench all do for their headline metric.

- OpenRCA's grader (`main/evaluate.py`) parses the predicted JSON into three fields: occurrence datetime, component and reason. The datetime matches if it is within 60 seconds. Component and reason must match exactly (case-sensitive). With several failures it tries every permutation and keeps the best; score = matched fields / total; "strict accuracy" counts only 1.0. Source: https://github.com/microsoft/OpenRCA (read from the raw `evaluate.py`).
- τ-bench judges success by comparing the database state at the end of the conversation with an annotated goal state. Source: Yao et al. 2024, arXiv:2406.12045.
- Anthropic's agent-eval guidance lists code-based graders as "fast, cheap, objective, reproducible" but "Brittle to valid variations that don't match expected patterns exactly" and "Lacking in nuance". Source: "Demystifying evals for AI agents", Anthropic Engineering, 9 Jan 2026, https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents.

**What this means for us.** OpenRCA shows the design cost of strict matching: exact component and reason strings. Our Answer keys need **canonical identifiers** (service name from the Service registry, commit SHA, file path, cause category from a fixed list) and the report schema must output them as fields, otherwise deterministic grading becomes brittle string matching. The brittleness Anthropic names is the reason our LLM judge exists at all: an advisory second opinion that flags "deterministically failed but plausibly right" Trials for a human to look at.

### 1b. Overlap and similarity metrics (BLEU, ROUGE, BERTScore, embedding cosine)

**Sources.**
- Reiter, E. (2018). "A Structured Review of the Validity of BLEU." *Computational Linguistics* 44(3). https://aclanthology.org/J18-3002/. Reviewed 284 correlations from 34 papers. Support for BLEU exists only for diagnostic evaluation of MT systems; no support "outside of MT", for evaluating individual texts, or for scientific hypothesis testing.
- Maynez, J., Narayan, S., Bohnet, B., McDonald, R. (2020). "On Faithfulness and Factuality in Abstractive Summarization." ACL 2020. arXiv:2005.00661. Found "substantial amounts of hallucinated content in all model generated summaries"; textual-entailment measures "better correlate with faithfulness than standard metrics" (ROUGE).
- Kryściński, W., McCann, B., Xiong, C., Socher, R. (2019). "Evaluating the Factual Consistency of Abstractive Text Summarization." arXiv:1910.12840. Existing metrics "do not account for whether summaries are factually consistent with source documents."
- Pagnoni, A., Balachandran, V., Tsvetkov, Y. (2021). "Understanding Factuality in Abstractive Summarization with FRANK." NAACL 2021. arXiv:2104.13346. Benchmarks factuality metrics against a typology of factual errors. Per-metric correlations for BERTScore/ROUGE not extracted in this session (UNVERIFIED which ranked where).
- Zhang, T. et al. (2020). "BERTScore: Evaluating Text Generation with BERT." ICLR 2020. arXiv:1904.09675. Token-level similarity between candidate and reference using contextual embeddings. It was validated on machine translation and image captioning (363 systems), not on factual or diagnostic text.
- Google ADK still ships `response_match_score` = "ROUGE-1 similarity to reference response" (default threshold 0.8) next to an LLM-judged `final_response_match_v2` that it recommends when meaning matters more than wording. Source: https://adk.dev/evaluate/.

**Why they mislead for RCA reports (reasoning from the sources above, not a measured result).** These metrics reward shared words or nearby embeddings. Two RCA reports can share almost every token and differ only in the service name, the commit, or a negation ("the timeout was *not* caused by the deploy"); that is exactly the part an RCA Answer key cares about. None of the sources validated these metrics on diagnostic or root-cause text. The factuality literature (Maynez, Kryściński, FRANK) exists precisely because overlap metrics missed factual errors in summaries.

**What this means for us.** Do not use BLEU/ROUGE/BERTScore/cosine as a Grade or as a promotion signal. At most, embedding similarity is useful for *retrieval-like housekeeping* (e.g. spotting near-duplicate Scenarios, or clustering failure reasons), not for correctness.

### 1c. LLM-as-judge: strengths, biases, calibration

**Sources.**
- Zheng, L. et al. (2023). "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena." NeurIPS 2023 Datasets & Benchmarks. arXiv:2306.05685. Names **position bias, verbosity bias, self-enhancement bias** and limited reasoning ability. Strong judges (GPT-4) reach "over 80% agreement" with human preferences, about the same as human–human agreement. That figure is for open-ended chat *preference*, not diagnostic correctness. The mitigations (e.g. swapping answer order) are in the paper body; not re-read here (UNVERIFIED detail).
- Panickssery, A., Bowman, S. R., Feng, S. (2024). "LLM Evaluators Recognize and Favor Their Own Generations." arXiv:2404.13076. Evaluators score their own outputs higher even when humans rate them equal; self-recognition ability correlates linearly with self-preference strength.
- Bavaresco, A. et al. (2025). "LLMs instead of Human Judges? A Large Scale Empirical Study across 20 NLP Evaluation Tasks." ACL 2025. arXiv:2406.18403. Eleven LLMs on 20 human-annotated datasets: reliability varies widely by model, dataset, evaluated property and annotator expertise; "LLMs should be carefully validated against human judgments before being used as evaluators."
- Thakur, A. S. et al. (2025). "Judging the Judges." GEM2 2025. arXiv:2406.12624. Only the largest judges approach human alignment and still trail inter-human agreement, with scores up to 5 points off; judges are lenient and sensitive to prompt length/complexity; **high percent agreement can hide very different scores**, so use chance-corrected alignment metrics.
- Shankar, S. et al. (2024). "Who Validates the Validators?" arXiv:2404.12272. "Criteria drift": people refine their grading criteria while grading outputs, so judge rubrics need iteration.
- Anthropic 2026 (above): model-based graders are flexible but non-deterministic and "Requires calibration with human graders"; give the judge an "Unknown" way out; use one isolated judge per dimension.

**Cohen's κ and sample size (own calculation).** κ corrects percent agreement for chance agreement. Bootstrapped 95% intervals for a binary pass/fail judge with a 50% pass base rate:

| Human-graded reports | Raw agreement | κ | 95% CI for κ |
|---|---|---|---|
| 20 | 85% | 0.70 | 0.35 – 1.00 |
| 20 | 90% | 0.80 | 0.49 – 1.00 |
| 50 | 85% | 0.68 | 0.44 – 0.87 |
| 50 | 90% | 0.80 | 0.60 – 0.96 |
| 100 | 90% | 0.80 | 0.68 – 0.90 |

The conventional Landis & Koch (1977) bands (0.61–0.80 "substantial", 0.81–1.00 "almost perfect") are commonly cited; the paper was not re-fetched this session (UNVERIFIED wording).

**What this means for us.**
- Our "different Model family" rule directly addresses the self-preference finding (Panickssery).
- About 20 human-graded reports is enough to catch a *bad* judge (κ near 0) but cannot distinguish "moderate" from "almost perfect": the 95% interval at n=20 spans roughly 0.35–1.0. That is fine while the judge is advisory only; it would not be enough to let the judge decide Grades. If the judge ever gains weight, 50–100 graded reports are what narrows κ to ±0.15.
- Report κ (or another chance-corrected statistic) and the confusion matrix, not percent agreement (Thakur). Track it per dimension (cause, location, cited facts), since reliability varies by property (Bavaresco).
- Recalibrate when the judge config changes, and expect our rubric to drift in the first rounds (Shankar).

## 2. Benchmarking versions

### 2a. Champion/challenger on a fixed suite

Comparing two Agent versions on the *same* Scenarios is a **paired** design. Miller (below) shows that analysing per-question paired differences cuts variance whenever the two systems' per-question scores are positively correlated (example: correlation 0.5 cuts the variance of the difference by about one third). Our Fork concept (same evidence, different Agent version) is the extreme form of pairing.

Anthropic 2026 distinguishes **capability evals** (should "start at a low pass rate") from **regression evals** (should "have a nearly 100% pass rate"), with capability tasks graduating into the regression suite. It also warns about **saturation**: when an agent passes all solvable tasks, real gains look like small score changes. It recommends "20-50 simple tasks drawn from real failures" as a starting suite, because early changes have large, easy-to-see effects.

**What this means for us.** "No regression on Champion-passed Scenarios" is in effect a regression eval; the rest of the suite is a capability eval. Keeping them as named subsets lets each have the right expectation.

### 2b. pass@k vs pass^k

- **pass@k**: probability at least one of k samples succeeds. Introduced for code generation with an unbiased estimator by Chen, M. et al. (2021), "Evaluating Large Language Models Trained on Code", arXiv:2107.03374 (Codex solved 28.8% of HumanEval with one sample, 70.2% with 100 samples per problem).
- **pass^k**: probability *all* k i.i.d. trials succeed, estimated per task as C(c, k)/C(n, k) and averaged. pass^k never increases with k; pass^1 = pass@1. gpt-4o on τ-retail: pass^1 61.2%, pass^8 below 25%; τ-airline pass^1 35.2%. Source: Yao, S., Shinn, N., Razavi, P., Narasimhan, K. (2024), "τ-bench", arXiv:2406.12045 (formula from the HTML version).
- Anthropic 2026: use pass@k when one success is enough, pass^k when consistency matters (a 75% per-trial rate gives about 42% pass^3).

**What this means for us.** An RCA agent's Operator sees one Investigation, not the best of k, so pass@k > 1 is not a meaningful product metric for us; pass@1 (gate) and pass^k (consistency) are the right pair, which matches the decision. Use the unbiased estimator from n repeats rather than "did all of exactly k runs pass" when n > k.

### 2c. Repeats and variance

**Source.** Miller, E. (2024). "Adding Error Bars to Evals: A Statistical Approach to Language Model Evaluations." arXiv:2411.00640. Recommendations, paraphrased:
1. Report the standard error of the mean with every score.
2. Use **clustered standard errors** when questions come in related groups; in the paper's Table 4, the clustered SE for DROP was about 3× the naive SE.
3. Reduce variance by **resampling each question K times** (example: K=2 cuts variance by 1/3, K=4 by 1/2; the ceiling in that example is 2/3) and don't lower temperature to fake stability.
4. Compare models with **paired differences** per question, and report the difference, its SE and the score correlation.
5. Run a **power analysis**: n = (z_{α/2} + z_β)² (ω² + σ²_A/K_A + σ²_B/K_B) / δ². Worked example: about 969 independent questions to detect δ = 3 points at 80% power; "new evals should contain at least 1,000 questions." A second example: with n = 198 and correlation 0.5, going from K = 1 to K = 10 lowers the minimum detectable effect from 13.2% to 7.5%.

ITBench runs each SRE scenario 10 times per model and still sees a scenario diagnosed in 6 of 10 runs and another in 1 of 10 (see §4).

**What this means for us.**
- Repeats reduce *within-Scenario* noise (σ²/K) but not *between-Scenario* variance (ω²). With 30 Scenarios, more repeats help only up to a ceiling; more Scenarios is the main lever.
- Trials of the same Scenario are a cluster, not independent samples: 30 Scenarios × 5 repeats is not n = 150. Any CI or test should resample Scenarios, not Trials.

## 3. Evaluation method

### 3a. Train / held-out splits, leakage and optimiser overfitting

**Sources.**
- Cawley, G. C., Talbot, N. L. C. (2010). "On Over-fitting in Model Selection and Subsequent Selection Bias in Performance Evaluation." *JMLR* 11:2079–2107. A high-variance selection criterion lets the *selection process itself* overfit, by amounts "comparable" to real differences between algorithms; applies to any method optimising a criterion over a finite sample.
- Dwork, C., Feldman, V., Hardt, M., Pitassi, T., Reingold, O., Roth, A. (2015). "Generalization in Adaptive Data Analysis and Holdout Reuse." arXiv:1506.02629. "Reusing a holdout set adaptively multiple times can easily lead to overfitting to the holdout set itself"; proposes a reusable-holdout mechanism (published as Thresholdout; the name is not on the abstract page, UNVERIFIED there) that answers through a noisy, thresholded interface.
- Recht, B., Roelofs, R., Schmidt, L., Shankar, V. (2019). "Do ImageNet Classifiers Generalize to ImageNet?" arXiv:1902.10811. New test sets cost 3–15% (CIFAR-10) and 11–14% (ImageNet) accuracy, but the authors attribute the drop to harder images, "not caused by adaptivity"; ranking gains carried over. A counterweight: heavy reuse did not destroy *rankings* in that setting.
- Kapoor, S., Stroebl, B., Siegel, Z. S., Nadgir, N., Narayanan, A. (2024). "AI Agents That Matter." arXiv:2407.01502. Many agent benchmarks lack adequate holdouts, enabling shortcuts and overfitting.

**Prompt optimisers.**
- DSPy (Khattab, O. et al. 2023, arXiv:2310.03714): compiles LM pipelines to maximise a chosen metric.
- MIPRO (Opsahl-Ong, K. et al., EMNLP 2024, arXiv:2406.11695): optimises instructions and demonstrations with "a stochastic mini-batch evaluation function"; up to 13% gains on five of seven programs.
- GEPA (2025, arXiv:2507.19457; first author Agrawal per common citation, UNVERIFIED): reflects in natural language on trajectories and evaluator **feedback text** (μ_f returns "feedback_text" alongside the score); splits training data into a feedback set and a Pareto validation set and keeps candidates on the per-instance Pareto front; uses a "standard train/validation/test split" where "Optimizers have full access to the train split, including text and labels"; reports validation and test separately and a lower generalisation gap than prior optimisers. Up to 35× fewer rollouts than GRPO, >10% over MIPROv2.

**Winner's curse (own calculation).** Choose the best of m candidates on an n-Scenario set when all candidates are truly identical at 60% pass rate. Expected *observed* score of the winner:

| n Scenarios | m = 5 | m = 20 | m = 50 |
|---|---|---|---|
| 20 | 72.5% (+12.5) | 79.7% (+19.7) | 83.4% (+23.4) |
| 30 | 70.4% (+10.4) | 76.2% (+16.2) | 79.3% (+19.3) |
| 50 | 68.0% (+8.0) | 72.7% (+12.7) | 75.2% (+15.2) |

This assumes independent candidates, so it overstates the effect for correlated prompt variants; the direction is the point. The winner's training score is biased upward and has to be re-measured on data that took no part in selection.

**What this means for us.**
- Our decisions already match the literature's main defences: the optimiser sees pass/fail only, never per-Scenario held-out detail (a coarse interface in the spirit of Dwork's reusable holdout), and it never sees Answer keys. GEPA's design is the contrast: it is built to consume *labels and feedback text* on its training split. If we adopt GEPA-style optimisers, the feedback text must come only from training Scenarios, and anything derived from an Answer key is leakage.
- Every held-out query still leaks about one bit. A fixed per-catalog-version Held-out set queried by many Optimisation runs will slowly overfit (Dwork); counting and capping held-out queries per catalog version, and rotating in new Scenarios when the catalog version changes, are the levers.
- With 10 held-out Scenarios, a 95% CI on pass@1 is roughly ±25–30 points (see 3b). The held-out check can catch gross overfitting; it cannot confirm a small gain.

### 3b. Statistical significance for small suites

**Paired tests for pass/fail per Scenario.**
- **McNemar's test** uses only discordant Scenarios (Champion passed / Challenger failed, and the reverse). Dietterich, T. G. (1998), "Approximate Statistical Tests for Comparing Supervised Classification Learning Algorithms," *Neural Computation* 10(7) (author PDF, https://web.engr.oregonstate.edu/~tgd/publications/dietterich-approximate-statistical-tests-nc1998.pdf): McNemar's test "is shown to have low Type I error"; "For algorithms that can be executed only once, McNemar's test is the only test with acceptable Type I error." With few discordant pairs use the exact binomial version.
- **Paired bootstrap**: resample Scenarios with replacement, recompute the difference, read off a CI. Koehn, P. (2004), "Statistical Significance Tests for Machine Translation Evaluation," EMNLP 2004, https://aclanthology.org/W04-3250/ (popularised paired bootstrap for MT; method details not re-read this session, UNVERIFIED). Berg-Kirkpatrick, T., Burkett, D., Klein, D. (2012), "An Empirical Investigation of Statistical Significance in NLP," EMNLP-CoNLL: significance depends on gain size, test-set size and system similarity, and "rule of thumb" gain thresholds hold only "with heavy caveats".
- Dror, R. et al. (2018), "The Hitchhiker's Guide to Testing Statistical Significance in NLP," ACL 2018: significance testing in ACL/TACL 2017 papers was "often ignored or misused"; gives a protocol for choosing a test.
- Card, D. et al. (2020), "With Little Power Comes Great Responsibility," EMNLP 2020, arXiv:2010.06595: underpowered comparisons are common (e.g. typical MT test sets of about 2,000 sentences have about 75% power to detect 1 BLEU).

**How many Scenarios to detect a 5-point pass@1 change? (own calculation)** Paired McNemar, 80% power. Normal-approximation sample size (Connor 1987, *Biometrics*; formula standard, paper not re-fetched, UNVERIFIED citation detail): n = [z_{α/2}√p_d + z_β√(p_d − δ²)]² / δ², where p_d is the share of Scenarios that are discordant.

| Share of Scenarios that flip between versions (p_d) | Two-sided α=0.05 | One-sided α=0.05 |
|---|---|---|
| 0.05 (every flip is in one direction) | 155 | 122 |
| 0.10 | 312 | 246 |
| 0.15 | 469 | 369 |
| 0.20 | 626 | 493 |

Simulated exact-McNemar power for a true 5-point drop with p_d = 0.10: 30 Scenarios ≈ 1%, 50 ≈ 7%, 100 ≈ 25%, 200 ≈ 54%, 300 ≈ 75%.

Minimum detectable difference at 80% power: about 16–22 points with 30 Scenarios, 12–17 with 50, 9–12 with 100 (p_d from 0.10 to 0.20).

95% Wilson CI for a single pass@1 of 70%: 30 Scenarios → 52–83%; 50 → 56–81%; 100 → 60–78%; 300 → 65–75%.

Per-Scenario averaging over repeats (Miller's K) shrinks the within-Scenario part of the variance and so lowers p_d's noise component somewhat, but these orders of magnitude stand: **a 5-point change is not statistically detectable with tens of Scenarios**; Miller's "at least 1,000 questions" for 3 points is consistent.

**The rule-based bar has its own false-alarm rate (own calculation).** Two *identical* Agent versions, each Scenario judged "passed" by majority over r repeats. Probability that one given Scenario is Champion-passed but Challenger-failed purely by noise, and the chance that at least one of 30 such Scenarios shows a "regression":

| Per-trial pass rate | r = 3: per Scenario / any of 30 | r = 5: per Scenario / any of 30 |
|---|---|---|
| 0.95 | 0.7% / 19% | 0.1% / 3% |
| 0.90 | 2.7% / 56% | 0.8% / 23% |
| 0.80 | 9.3% / 95% | 5.5% / 81% |
| 0.70 | 16.9% / ~100% | 13.6% / 99% |

**Evidence for the open question (not a decision).**
- *For adding a paired test:* it is the standard method for comparing two systems on the same items (Dietterich, Dror, Miller); it measures what the 5-point rule is trying to measure; reporting the paired difference and its CI costs nothing extra; it guards against declaring a Challenger *better* on noise, which matters most for Optimisation-run Challengers selected as best-of-m (winner's curse).
- *Against making it a gate at our sizes:* with 30–50 Scenarios a paired test has almost no power to detect a 5-point drop (1–7%). A "must not be significantly worse" gate would pass nearly every Challenger, giving false comfort; a "must be significantly better" gate would block nearly every real but small improvement. Hundreds of Scenarios would be needed for either to bite at 5 points.
- *About the existing rule-based bar:* "no regression on Champion-passed Scenarios" is already a paired, per-Scenario check, but with flaky Scenarios (per-trial pass rate ≤ 0.8) it will flag noise most of the time unless "Champion-passed" means something stable (e.g. passed in all repeats, or re-run the flagged Scenarios). The 5-point pass@1 threshold is well inside the noise band of a 30–50 Scenario suite (CI width ±13–16 points), so on its own it acts as a coarse tripwire, not a measurement.
- *Middle options seen in the sources:* report the paired difference with a Scenario-level bootstrap CI and McNemar p-value as information beside the rule-based bar (Miller rec. 4); use a test only for the "is the Challenger actually better" claim of optimiser-proposed Challengers; run a power analysis before choosing thresholds (Miller rec. 5, Card).

## 4. Public RCA / AIOps benchmarks

| Benchmark | What it measures | Data / environment | Metrics | Headline result |
|---|---|---|---|---|
| **OpenRCA** (Xu et al., ICLR 2025) | Given a natural-language query, find root-cause time, component and reason from offline telemetry | 335 failures, >68 GB of logs/metrics/traces from three enterprise systems (Telecom, Bank, Market) | Deterministic field match (time ±60 s, exact component/reason); strict and partial accuracy | Claude 3.5 Sonnet + RCA-agent 11.34% strict, 17.31% partial |
| **RCAEval** (Pham et al. 2024/25) | Service- and indicator-level RCA from telemetry | 735 cases, 3 datasets (RE1 metrics only; RE2 metrics+logs+traces; RE3 code-level faults), 11 fault types, on Online Boutique, Sock Shop, Train Ticket | AC@k, Avg@k (ranking) | 15 reproducible baselines (mostly non-LLM) |
| **AIOpsLab** (Chen et al. 2025, Microsoft) | Live agent–environment interaction across detection, localisation, RCA, mitigation | Deploys DeathStarBench HotelReservation and SocialNetwork on Kubernetes, injects faults, generates load; 48 problems from 10 fault scenarios incl. one no-fault | Accuracy, time-to-detect/mitigate, steps, tokens (cost) | Best overall 59.32% (Flash); mitigation hardest |
| **ITBench** (Jha et al. 2025, IBM) | SRE, CISO and FinOps automation; SRE part = diagnosis + mitigation | 94 scenarios (42 SRE) on the OpenTelemetry Astronomy Shop on Kubernetes; Grafana, Loki, Jaeger, Prometheus; 10 runs per scenario | pass@1, NTAM topology-aware fault-localisation score, MTTD, MTTR | GPT-4o SRE diagnosis 13.81%, mitigation 11.43%; 36% easy → 5% hard |
| **Cloud-OpsBench** (Wang et al. 2026, arXiv:2603.00468) | RCA correctness *and* investigation quality | 754 runtime-verified cases, 57 fault types, OnlineBoutique and TrainTicket; snapshots replayed through diagnostic interfaces | Joint RCA Accuracy, evidence closure over diagnostic evidence graphs | JRA up to 0.78 / 0.68; GPT-5 right without evidence closure in 33.1% / 29.4% of cases |

Sources: OpenRCA repo and site (https://github.com/microsoft/OpenRCA, https://microsoft.github.io/OpenRCA; ICLR 2025 proceedings PDF, numbers confirmed via the project site/leaderboard, MIT licence). RCAEval arXiv:2412.17015 (HTML). AIOpsLab arXiv:2501.06706 (HTML; the paper mentions both four and six evaluated agents). ITBench arXiv:2502.05352 (HTML). Cloud-OpsBench arXiv:2603.00468 (abstract; v3 Nov 2026).

Related analyses on OpenRCA, useful as methodology rather than as benchmarks:
- Kim, T. et al. (2026), "Why Do AI Agents Systematically Fail at Cloud Root Cause Analysis?", arXiv:2602.09937: 1,675 runs over five LLMs; 12 pitfall types; "hallucinated data interpretation and incomplete exploration" are common across all models; prompt engineering alone did not fix them.
- Gopal, A., Krishnan, A. (2026), "How Far Can Root Cause Analysis Go on Real-World Telemetry Data?", arXiv:2607.13548: rules mined on one OpenRCA cloudbed and tested on a **held-out cloudbed**, with multiple-testing correction; "all results are specific to OpenRCA."
- Not checked in a primary source (UNVERIFIED, named only): ORCA-Bench (Traversal blog), "Between Promise and Pain" (APSys '25).

**Fit for Java services on Azure Functions with Dynatrace.** None of them matches: all use open-source microservice demos on Kubernetes (or offline telemetry from undisclosed enterprise systems), with Prometheus/Jaeger/Loki-style or raw-file observability, not Dynatrace, and none covers serverless/function-app runtime events (cold starts, function timeouts, host restarts). Train Ticket (RCAEval, Cloud-OpsBench) is the most Java-relevant system; RCAEval only says its three systems span Java, Go, Python and C# without a per-system breakdown (Train Ticket being mostly Java Spring Boot is UNVERIFIED in the sources read). So: **reference only**, as expected. What is worth borrowing:
- OpenRCA's three-field structured answer and deterministic grader, and its strict-vs-partial split.
- AIOpsLab's explicit **no-fault** problem (only GPT-4 recognised it), matching our Scenarios with no known answer.
- ITBench's 10 repeats per scenario and its easy/medium/hard tiers; its reported run-to-run swings (6/10 vs 1/10) support our repeats.
- Cloud-OpsBench's evidence-closure idea for the "facts the report must cite" part of our Answer keys.
- A one-off run of our agent against OpenRCA through an adapter could be a sanity check of general RCA skill, but needs an observability adapter for files; its scores would not predict performance on our Target services.

## 5. Agent-specific evaluation

### 5a. Outcome vs trajectory (process) evaluation

- Anthropic 2026: the outcome is "the final state in the environment at the end of the trial", the transcript is the full record; it is "often better to grade what the agent produced, not the path it took", so valid but unexpected paths are not penalised.
- Google ADK offers both: `tool_trajectory_avg_score` ("Exact match of tool call trajectory", default threshold 1.0, i.e. 100% match) and rubric-based tool-use evaluation, beside final-response metrics. Source: https://adk.dev/evaluate/. (Exact/in-order/any-order match modes were not on this page; UNVERIFIED.)
- Cloud-OpsBench shows why outcome alone is not enough for RCA: GPT-5 named the right root cause *without* closing the evidence chain in about 30% of cases; "final-answer accuracy alone cannot establish whether an agent has traced the failure and collected the evidence needed."
- Kim et al. 2026 analyse process-level failures (incomplete exploration, hallucinated data interpretation) that outcome scores hide.

**What this means for us.** Grade outcome first (the Answer key), but treat **process checks as hard constraints rather than path matching**: forbidden actions, reads outside scope, and "the facts the report must cite" (evidence actually retrieved in the trajectory, not just asserted). That gives the benefit of process evaluation without the brittleness of exact-trajectory matching. Exact tool-trajectory matching (ADK-style) suits narrow regression tests of a single Stage, not whole Investigations.

### 5b. Cost and latency as metrics

- Kapoor et al. 2024: accuracy-only leaderboards produce "needlessly complex and costly" agents; evaluate cost and accuracy jointly (Pareto view).
- AIOpsLab and ITBench both report time (time-to-detect/mitigate, MTTD/MTTR), steps and tokens next to accuracy.
- Anthropic 2026: "latency, token usage, cost per task, and error rates can be tracked on a static bank of tasks" at no extra cost once evals exist.

**What this means for us.** The ≤+25% cost bar is consistent with this literature. Cost per Trial is itself noisy (variable number of tool calls), so the same paired, Scenario-level comparison applies: compare per-Scenario cost ratios, not totals. Latency and step count are worth recording per Trial even without a gate, since step blow-ups are a known failure mode (AIOpsLab: wasted repeated actions, context overload).

## Unknowns

- Per-metric correlations (BERTScore, ROUGE) with factuality in FRANK were not extracted.
- Zheng et al.'s specific bias mitigations and per-setting agreement numbers were not re-read beyond the abstract.
- Koehn 2004, Connor 1987 and Landis & Koch 1977 were cited from standard knowledge; their text was not fetched this session.
- No source measured overlap metrics or LLM judges on root-cause reports specifically.
- No public benchmark covers Azure Functions, Dynatrace, or serverless runtime events.
- The own-calculation tables assume binary per-Scenario outcomes and independent Scenarios; real Scenarios that share a Seeded fault or service are clustered (Miller rec. 2), which widens every interval above.
