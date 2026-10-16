# Mandatory instructions for Claude — WinNAT-UI

Read and follow [AGENTS.md](AGENTS.md) before changing this repository. The following instructions are explicit and take precedence over any general desire to finish the task automatically.

**CLAUDE IS NOT AUTHORIZED TO MERGE PULL REQUESTS. ONLY CHATGPT MAY DECIDE AND PERFORM MERGES.**

- Do not call `gh pr merge`, GitHub's merge API, merge/auto-merge buttons, or any equivalent command.
- Do not enable auto-merge or arrange a bot/workflow to merge for you.
- Do not push, fast-forward, force-update, or cherry-pick commits directly into `main` as a substitute for a merge.
- Do not use a different identity, credential, token, or tool to get around these restrictions.
- You may implement changes on a feature branch (when authorized), run tests, create/update PRs, review diffs, and report findings. **Leave the PR open for ChatGPT.**
- In the PR, describe major behavior/architecture changes, dependencies, overlaps with other ongoing work, tests performed, and build results. Highlight competing implementations rather than silently choosing one.
- Do not bump product versions, publish releases, or trigger release approval without explicit authorization.

## Priority and version handoff

- ChatGPT merges **ChatGPT-origin changes first**, then **Claude-origin changes**, prioritizing importance (Critical → High → Normal → Low) and, within equal priority, the oldest original request/PR first. Claude must not merge, reorder the queue unilaterally, or manipulate timestamps to jump ahead.
- In every PR, state the true contributor origin, original request/PR creation date, assessed importance and dependencies/overlaps, and a proposed MAJOR/MINOR/PATCH/HOTFIX/BUILD-only version classification.
- ChatGPT **must** check versioning for every PR and reconcile collisions between proposed versions/changelogs before deciding a merge. Claude does not independently approve versions or initiate publication; no change of `version.py`/`version_info.txt` unless specifically authorized.
- Where the queue conflicts with dependencies, Claude must highlight the issue and leave the merge/integration choice to ChatGPT.

**Handoff:** Provide ChatGPT the PR URL, latest head SHA, summary of substantial changes, related PRs or potentially overlapping paths, verification evidence, and unresolved risks. ChatGPT must review and reconcile related changes, perform the merge, and verify the post-merge Windows build.

No generic instruction to "finish", "integrate", "ship", or "merge all changes" overrides this restriction.
