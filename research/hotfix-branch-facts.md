# Hotfix branches on GitHub and GitLab: creation, protection, cherry-pick, draft PRs

Researched 2026-11-09 for [How are production hotfixes made: upstream first, then a hotfix branch from the deployed tag?](https://github.com/chiyanram/rca-agent/issues/33). Items stated as inference are not verbatim in the cited docs; the GitHub ruleset inference is flagged for a live check on [Gap review](https://github.com/chiyanram/rca-agent/issues/24), the GitLab ones on [Verify GitLab token facts on a live instance](https://github.com/chiyanram/rca-agent/issues/37).

**1. GitHub: creating a branch from a tag's commit**
- **Yes, the app can create it.** `POST /repos/{o}/{r}/git/refs` with `ref=refs/heads/hotfix/v1.4.2` and `sha=<the tag's peeled commit>` needs Contents: write. If the ref touches workflow files, it also needs Workflows: write; the endpoint appears under both permission tables. https://docs.github.com/en/rest/authentication/permissions-required-for-github-apps , https://docs.github.com/en/rest/git/refs
- **Rulesets:** "Restrict creations" means "only users with bypass permissions can create branches or tags whose name matches the pattern." The bypass list can include GitHub Apps (and, in org repos, roles and teams), so the bot has to be on it. "Require a pull request before merging" covers changes to the target branch. The docs do not say it blocks creating the branch; creation is controlled by "Restrict creations". https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets
- **Classic branch protection:** this can block creation only through "Restrict who can push", which "Optionally... appl[ies] the same restrictions to the creation of branches that match the rule." Push or create permission can be granted to "installed GitHub Apps with write access". Admins always bypass unless "Do not allow bypassing" is set. https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches
- **For the design:** a `hotfix/**` ruleset that only requires PRs should not block creating the branch (an inference from the docs, not stated outright). If the ruleset includes Restrict creations, the app must be on the bypass list.

**2. GitHub: cherry-pick and draft PRs**
- **Cherry-pick:** I found no cherry-pick endpoint in the REST docs I checked. As far as I know there isn't one in REST or GraphQL either. So the bot either runs local `git cherry-pick` and pushes, or builds the commit itself with the Git Data API (trees, commits, refs).
- **Draft PR to a non-default base:** `POST /pulls` accepts `base` = "an existing branch on the current repository", so any branch works, plus `draft: true`. https://docs.github.com/en/rest/pulls/pulls
- **Limits:**
  - Private repos get drafts only on Team or Enterprise Cloud; Free and Pro get them on public repos only.
  - The base branch must already exist in the same repository.
  - The creator needs write access to the head branch.

**3. GitLab: can a Developer create a branch matching a protected pattern**
- **UI and API (`POST /projects/:id/repository/branches`):** governed by **Allowed to merge**, which "Controls who can merge changes through merge requests and create new protected branches through the UI and API." With "Maintainers" selected there, a Developer token cannot create `hotfix/*` this way. The prerequisite also says "You must have the Developer, Maintainer, or Owner role."
- **git push:** governed by "Allowed to push and merge". The docs say protected branches can be created from the command line only "if direct push is allowed". With "No one" selected, the bot cannot push-create the branch either.
- **When MRs are required for everyone,** a new protected branch can only start from "existing protected branches and commits that are already in protected branches."
- Source: https://docs.gitlab.com/user/project/repository/branches/protected/ (#push-and-merge-permissions, #create-protected-branches)
- **For the design:** either set Allowed to merge to Developers, or mint the token with the Maintainer role.

**4. GitLab: cherry-pick API**
- `POST /projects/:id/repository/commits/:sha/cherry_pick` "Cherry-picks a commit to a given branch." It takes `branch` (required), optional `message`, and `dry_run` ("If `true`, does not commit any changes"). It commits directly onto `branch`. https://docs.gitlab.com/api/commits/
- **Permissions:** the API page gives no permission statement. The UI page says you need a role "that allows you to edit merge requests and add code to the repository." https://docs.gitlab.com/user/project/merge_requests/cherry_pick_changes/
- I infer that it needs push rights on the target branch. So the bot should create an unprotected head branch first, cherry-pick onto it, then open the MR.

**5. GitLab: draft MRs and protected tags**
- **Draft MR to a non-default branch:** the MR API's `target_branch` can be any branch, and a "Draft:" title prefix (or `draft`) marks it as a draft. This is my understanding; I did not fetch the MR API page.
- **Protected tags** control only creating, updating and deleting the tag itself. Branches can still be created from it ("Users can still create branches, but not tags, with the protected names"). Watch for a branch and a tag with the same name: "A tag and a branch with identical names can contain different commits." https://docs.gitlab.com/user/project/protected_tags/

**6. Upstream-first practice**
- trunkbaseddevelopment.com: "reproduce the bug on the trunk, fix it there with a test… then cherry-pick that to the release branch." It also says "You should not fix bugs on the release branch in the expectation of cherry-picking them back to the trunk." Some teams "release from a tag on the trunk" and "wait for a bug that needs fixing… before creating a branch from the release tag." https://trunkbaseddevelopment.com/branch-for-release/
- GitLab's current cherry-pick docs list "Backport bug fixes from the default branch to previous release branches" as a use case. I could not verify the old GitLab Flow page's "upstream first" wording from the fetched archive.
