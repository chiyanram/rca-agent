# AGENTS.md conventions in well-known open-source repos

Researched 2026-11-09 while setting up this repo's agent instruction files (during the session for [Does the Test bed get a Kubernetes profile…](https://github.com/chiyanram/rca-agent/issues/32)). Shapes the layout of `AGENTS.md` and the note in `CONTRIBUTING.md`. Third-party files were read, not copied.

**AGENTS.md conventions in well-known repos (checked 2026-11-09)**

I fetched every file below with `gh api` or raw.githubusercontent from the default branch. I read the headings of all of them, grepped them for commit, check and security rules, and read uv's and transformers' files in full.

**Sample**
- Root files: apache/airflow, vercel/next.js, temporalio/sdk-python, pydantic/pydantic-ai, astral-sh/uv, astral-sh/ruff, langchain-ai/langchain, huggingface/transformers.
- microsoft/vscode: its root `AGENTS.md` is 5 lines and only points to `.github/copilot-instructions.md` (173 lines), so I analysed that file instead.
- openai/codex: there is **no root AGENTS.md** on main right now. There are only 3 nested ones (`codex-rs/tui/src/bottom_pane/`, `codex-rs/code-mode-host/`, `codex-rs/exec-server/.../sandbox_integrity/`). Codex had a root file earlier; I did not check when it was removed.
- huggingface/transformers: root `AGENTS.md` and `CLAUDE.md` are symlinks to `.ai/AGENTS.md`.
- Not used: microsoft/TypeScript has no AGENTS.md.

**Specs and docs**
- https://agents.md
  - Calls the file "a README for agents": plain Markdown, no required fields.
  - Suggested sections: project overview, build and test commands, code style, testing, security; optionally commit/PR guidelines and deployment.
  - In monorepos, use nested files; the closest one to the edited file wins, and the user's chat prompt overrides all.
  - If the file lists test or lint commands, agents will try to run them and fix failures before finishing.
  - No length limit. Now stewarded by the Agentic AI Foundation under the Linux Foundation.
- https://code.claude.com/docs/en/memory
  - "target under 200 lines per CLAUDE.md file"; specific, concise instructions are followed more reliably.
  - `@path` imports, recursive up to **4 hops**.
  - Rules that only matter for some files go in `.claude/rules/*.md` with `paths:` frontmatter; multi-step procedures go in skills.
  - Claude Code reads `AGENTS.md` natively when there is no CLAUDE.md. If both exist, it reads only CLAUDE.md, unless CLAUDE.md contains `@AGENTS.md`.
  - The docs say CLAUDE.md is context, not enforced; to actually block an action, use hooks.
- https://docs.github.com/en/copilot/how-tos/configure-custom-instructions/add-repository-instructions
  - Supports `.github/copilot-instructions.md`, plus `.github/instructions/*.instructions.md` with `applyTo` globs (and `excludeAgent`).
  - Supports `AGENTS.md` anywhere in the repo (nearest wins), or one root `CLAUDE.md`/`GEMINI.md`.
  - The only length guidance is "no longer than 2 pages", and that is in the prompt Copilot uses to generate the file. The page does not say which Copilot surfaces read AGENTS.md.

**1. Common sections (out of 9 analysed files; my counts from headings, so approximate)**
- Setup/build/test commands: **8/9**. uv instead says "Read CONTRIBUTING.md".
- Commit/PR conventions: **7/9**.
- Code style / coding guidelines: **~7/9**.
- Testing rules: **~7/9**.
- Repo layout / "where things are": **6/9**.
- Project overview / intro: **~6/9**, usually 1–3 sentences.
- Security / boundaries / secrets: **~5/9** (airflow, next.js, langchain, vscode "Public Content", uv).
- Pointers to further docs: **most**. airflow has a "References" section, langchain "Additional resources".

The usual order is overview → layout → commands (setup, build, test, lint) → style → testing → PR/commit → boundaries/security → references. airflow is closest to this textbook shape: Environment Setup, Commands, Repository Structure, Architecture Boundaries, Security Model, Coding Standards, Testing Standards, Commits and PRs, Boundaries, References.

**2. Length and tone**
- Root line counts: transformers 40, uv 49, temporal 137, pydantic-ai 176, vscode (copilot file) 173, ruff 241, airflow 254, langchain 390, next.js 538.
- **Median about 175 lines**; the short ones are 40–50 lines.
- Tone is imperative bullets plus fenced command blocks. uv is all bullets starting with ALWAYS / NEVER / PREFER / AVOID / DO NOT.
- pydantic-ai is more explanatory prose ("Philosophy").

**3. Notable patterns**
- **Nested files per subdirectory:**
  - airflow: about 16 (providers/, ui/, dev/, execution_api/ …).
  - next.js: about 10 (packages/next, turbopack, test, crates).
  - pydantic-ai: about 20, each with a CLAUDE.md twin.
  - codex: 3 nested only.
- **One source for all tools:**
  - ruff `CLAUDE.md` is just `@AGENTS.md`.
  - transformers uses symlinks.
  - vscode AGENTS.md points to copilot-instructions.md.
- **Pointing to docs instead of copying them in:** uv → CONTRIBUTING.md; airflow → contributing-docs/*.rst; transformers → modular guide; next.js → named skills (`$pr-status-triage`).
- **Never / always boundaries:**
  - airflow has a "Boundaries / Never" list (never commit secrets; never run pytest on the host, use `breeze`).
  - next.js has "Secrets and Env Safety".
  - uv: "NEVER assume clippy warnings … are pre-existing".
- **Checks the agent must run before finishing:**
  - ruff: run `uv run --only-dev --locked prek` at the end of every task.
  - transformers: `make style` / `make fix-repo` before a PR.
  - airflow: `prek run --from-ref <branch>`.
  - next.js: run what the pre-commit hook runs before committing.
  - temporal: format and lint before submitting.
- **Commit conventions:**
  - **Conventional Commits only in langchain** (scope required, enforced by `pr_lint.yml`).
  - temporal: short, imperative commit messages.
  - pydantic-ai: PR titles are plain imperative sentences with no `fix:` prefix.
- **No AI co-author trailers:** airflow ("Never list an agent as a commit co-author") and pydantic-ai ("no Co-Authored-By trailer referencing Claude").
- **Rules about agent-written PRs:**
  - transformers: first-time contributors must not submit agent-written PRs.
  - uv and ruff: don't leak the agent conversation into comments or PR text.

**4. Companion files (10 repos; tree regex check, so possible false negatives)**
- LICENSE: **10/10**.
- CONTRIBUTING: **9/10**. langchain has none in the tree; its contributor guide is presumably on its docs site, which I did not verify.
- Dependabot/Renovate: **9/10**.
- Issue templates: **9/10**.
- CODEOWNERS: **8/10**.
- PR template: **7/10**.
- SECURITY.md: **6/10**.
- Pre-commit / husky / prek: **about 6/10**.
- .editorconfig: **6/10**.
- Root CLAUDE.md: **4/10**.
- CODE_OF_CONDUCT: **3/10**.
- **ADRs: effectively 1/10** (airflow); the next.js and langchain regex matches were false positives.

So LICENSE, CONTRIBUTING, issue templates, dependability bots and CODEOWNERS are near-universal; ADRs are rare.

**Uncertainty:** the files change often (several mention recent skills and tools), so counts are a snapshot as of today. Section counts are my reading of headings, not exact. "Pre-commit" may undercount repos that run hooks a different way (for example uv).
