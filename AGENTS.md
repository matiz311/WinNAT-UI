# AI collaboration and merge policy — WinNAT-UI

This file governs AI contributions to this repository. It applies to **Claude**, **ChatGPT**, and any other AI agent using GitHub, a CLI, automation, or an API.

## Ownership and permissions

- **Only ChatGPT, acting for the repository owner, is authorized to decide and perform a merge** into `main` (or another protected integration branch).
- **Claude must never merge**, enable auto-merge, approve its own work as a substitute for the integration decision, push directly to `main`, fast-forward or reset `main`, cherry-pick directly into `main`, or trigger an alternate merge mechanism. This prohibition applies even if permissions or tooling would technically allow it.
- Claude may analyze, develop on isolated branches, commit changes, run tests, open/update pull requests, and document integration risks. It must hand over the PR and evidence to ChatGPT; **opening a PR is not permission to merge it**.
- No agent should bypass this policy by switching credentials, tokens, forks, GitHub Actions, or direct Git operations. If the merge owner is unavailable, leave the PR open.

## Deterministic merge queue: origin, importance, chronology

ChatGPT must inspect **all pending merge requests**, including ChatGPT-authored and Claude-authored work, and record a queue before choosing the next integration. **Sorting order is strict and lexicographic:**

1. **Contributor origin:** ChatGPT's changes **first**, Claude's changes **second**. Determine the actual author/origin of the work rather than assuming the PR opener is the code author.
4. **Importance within each origin group:** Critical (security, data loss, regressions/blocking failures) → High (major functionality or dependencies) → Normal → Low (cosmetic/docs). Explain the priority based on impact, not age or personal preference.
5. **Chronology within the same origin and importance:** oldest original PR/request creation time first (FIFO); later pushes or edits do not reset the original date. Record that timestamp so the order is auditable.

If two PRs overlap, are mutually dependent, or cannot safely be merged in this order, **do not force an unsafe merge**: create a coherent integration candidate, defer a blocked PR, and document the reason/order adjustment. A priority exception requires an explicit documented decision from the project owner; Claude cannot use one to self-merge. Recompute the queue after every merge or meaningful PR update.

## Mandatory versioning review on every merge request

ChatGPT owns versioning decisions for **every** PR, even docs-only changes or contributions proposing no version bump. For each candidate:

- Compare `version.py`, `version_info.txt`, the latest published GitHub release/tag, `CHANGELOG.md`, `RELEASE_NOTES.it.md`, and applicable README/updater metadata; check whether any concurrent PR proposes the same or an incompatible version.
- Classify the actual integrated change as **MAJOR / MINOR / PATCH / HOTFIX / BUILD-only (no product-version bump)** following `VERSIONING_POLICY.md`. Document the chosen classification, rationale, and whether a version change is required **now**. Ordinary merges must not accidentally publish or bump the released version.
- For PRs combined into one integration, decide the version **once for the final combined change**, not independently for each contributor or in the order of their original branch bumps. Reconcile duplicate/conflicting version numbers and changelog entries before merge.
- Ensure release numbers, Windows EXE metadata, tags, artifacts and updater remain consistent, with no reuse of already published versions. Preserve existing approval gates for releases, especially MAJOR/MINOR.

## ChatGPT's mandatory integration gate

Before merging **any** pull request, ChatGPT must:

1. **Inventory ongoing work.** Inspect the current `main` head, all relevant open PRs/branches, their latest commits, changed files, and pending changes. Distinguish closed/merged work from work still awaiting integration.
2. **Prioritize the merge queue.** Group ChatGPT-origin work before Claude-origin work; within each group order by importance descending and then by the original request/PR creation date ascending. Record any blocked dependency or explicit owner-approved exception.
3. **Validate versioning for every PR.** Check version/release compatibility, competing version changes in other PRs, and the correct MAJOR/MINOR/PATCH/HOTFIX/BUILD-only decision for the final integration.
4. **Review material changes.** Read the actual diffs and validate architecture, behavior, error handling, security, data/configuration changes, versioning, upgrade compatibility, rollback, and test coverage. A green CI status or GitHub `mergeable` flag alone is never sufficient.
5. **Check overlap semantically and textually.** Compare changed files, modules, feature ownership, execution paths, and dependent behaviors against other open PRs and recently merged changes. Detect contradictory designs even when Git reports no merge conflict.
6. **Integrate related work together when needed.** Resolve overlapping PRs into a consistent integration branch or coordinated PR set; explicitly decide what to keep, rework, defer, or reject. Do not blindly combine mutually exclusive implementations. Test the **combined final tree**, not just each PR independently.
7. **Verify the exact candidate.** Recheck the final head SHA and base branch; ensure the Windows GitHub Actions `Build Windows executable` workflow passes on the integration candidate. It includes Python syntax/unit tests, Node gateway validation, a PowerShell diagnostic smoke test, PyInstaller packaging, EXE metadata checks, and Microsoft Defender scanning. If required checks are missing, failing, or still in progress, do not merge. For changes requiring real Windows networking or updater verification, document what CI cannot establish and obtain the relevant validation before declaring full functional acceptance.
8. **Merge under ChatGPT authority only.** Record the integration decision and evidence in the PR. Use the expected PR head SHA to prevent merging a changed candidate. Never enable automatic merges as a substitute for this review.
9. **Build after merge.** Confirm the `main` workflow builds the actual merged commit successfully; check the artifact, tests, EXE metadata, Defender result, and workflow conclusion. A pre-merge green check does not replace this post-merge build. If it fails, investigate and fix via a new reviewed PR or revert where appropriate; do not claim completion.
10. **Keep releases separate.** An integration/build is not permission to publish a release. Respect `VERSIONING_POLICY.md` and the existing release approval gate; avoid unrequested changes to `version.py`, `version_info.txt`, tags, or GitHub Releases.

## Project-specific architectural caution

WinNAT and network configuration paths are high impact. Check changes to `app.py`, `winnat_ui/nat_backend.py`, `winnat_ui/network*.py`, rollback, and related tests together. Never assume that allowing multiple independently configured WinNAT objects is equivalent to the project's current documented single-WinNAT architecture. An alternative design requires an explicit architectural decision and relevant host-level validation before integration.

## PR hand-off requirements

Every agent PR should identify:
- what behavior changes and why;
- changed modules, compatibility/rollback implications, and tests added;
- overlaps or dependencies with open/merged PRs and the proposed resolution;
- tests/build run, with results and precise limitations;
- the original work's author (ChatGPT or Claude), original request/PR date, proposed importance, and known dependencies;
- the proposed version classification or explicit BUILD-only/no-version-bump decision, for ChatGPT to validate.

**Claude: STOP after preparing and handing off the PR. ChatGPT owns the integration review, any merge, and the post-merge build verification.**
