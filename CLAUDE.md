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

**Handoff:** Provide ChatGPT the PR URL, latest head SHA, summary of substantial changes, related PRs or potentially overlapping paths, verification evidence, and unresolved risks. ChatGPT must review and reconcile related changes, perform the merge, and verify the post-merge Windows build.

No generic instruction to "finish", "integrate", "ship", or "merge all changes" overrides this restriction.
