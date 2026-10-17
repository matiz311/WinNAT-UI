# GitHub maintenance registry

The repository stores two distinct JSON documents:

- `maintenance-history.json`: versioned audit history. Write planned disruptive work **before** changing services; do not backfill invented timestamps. Event fields: `id`, `type` (`routine`, `extraordinary`, `structural`), `status` (`planned`, `in_progress`, `completed`, `cancelled`), `started_at` and `ended_at` (UTC ISO 8601 or null if unknown), `components`, `description`, `expected_errors`, `related_issues`, `evidence`. Include rollback and linked workflow/commit data when available. Corrections must have attributable commits.
- `maintenance-status.json`: current per-service state. `status` is `operational`, `maintenance`, `degraded`, `unavailable`, or `unknown`. `unknown` means no trustworthy observation yet; never represent a missing update or missing file as `operational`. `updated_at` is null until a real observation is published.

Any client fetching the status file must treat it as **advisory**. Use short network timeouts, explicitly identify stale observations, and remain functional if it cannot be retrieved. A maintenance status cannot bypass official-asset URL checks or SHA-256 verification and cannot alone prove causality.

## Audited legacy exception

Before this policy was introduced, PR #67 had already changed the gateway's initial triage label at commit `ba987780caa641b84340e278d9e9fb70bf26401c` in `services/bug-gateway/src/index.js`. A prior maintenance entry cannot truthfully be backfilled. The guard explicitly exempts **only this immutable commit and this path**. All later gateway changes, even within PR #67, must have their own pre-change registration. The exception is reviewed and versioned alongside the guard; it does not declare that a maintenance event happened and does not waive tests or required checks.

## Manual operating procedure

1. Before planned disruptive work, commit the planned event in history with a unique `MAINT-YYYYMMDD-NNN` identifier, precise UTC start when known, affected components, impact and rollback.
2. Set the affected services to `maintenance` in status, referencing the same event ID, with the actual UTC publication timestamp.
3. Perform the change, then validate GitHub release metadata and that the release ZIP has an official URL and verifiable SHA-256.
4. Record the conclusion, actual time, workflow/commit references, encountered errors and verification evidence in history. Restore operational status **only after verification**.
5. For emergencies where advance registration was impossible, document the exception and the earliest reliable timestamps. No guessed retrospective hours.

Example historical event (the migration related to #44): its actual start/end UTC and original HTTP status are **not documented**. Preserve null times and describe 404 only as a compatible, unproven error. Do not fabricate a live maintenance state for this historical incident.

**Limitation:** registry status publication and automatic lifecycle recording remain manual. CI validates structure and selected high-risk changes; it does not deploy a status endpoint.

## Automated validation (PR #68)

The independent GitHub Actions job `maintenance-guard` runs on pull requests to `main`, pushes to `main` and manual dispatch. It performs JSON schema/invariant checks and Python unit tests without network access or production writes. For PRs it also compares git commits (not only the final diff) to enforce **registration in an earlier commit** before changes to:

- `.github/workflows/**`
- `services/bug-gateway/**`
- `tools/release.py`, `version.py`, `version_info.txt`
- `release-approvals/**`

For each risky commit, a new event not present in the PR's merge-base must already exist in the parent commit, reference the current PR number in `related_prs`, and describe impact and rollback. Workflow changes must include `github-actions` in `components`. Make the pre-registration commit first; adding the record alongside the disruptive edit does **not** pass.

For example, use event `MAINT-YYYYMMDD-NNN` (UTC date), `type=structural`, `status=planned`, an authentic `registered_at` ending in `Z`, and null actual times until the activity really starts. Include `actor`, `components`, `affected_endpoints`, `description`, `planned_steps`, `expected_impact`, `expected_errors`, `rollback`, and `related_prs`. After verification, update actual start/end, evidence and outcome; do not infer operational status from a passing CI check.

**Enforcement scope and limitations:** a workflow check cannot prevent a privileged direct push or a PR merge by itself. Configure repository branch protection/rulesets to require the `maintenance-guard` job on `main`, prevent bypass as appropriate and retain the existing Windows build check. This is a repository administration step, not automatically configured by this PR. The guard checks known high-risk file paths, not every conceivable disruptive operation (GitHub settings, permissions, manual external deployments, deleted workflows, etc.). For those, agents and maintainers must still apply the mandatory manual gate from `AGENTS.md`. Live service observations, timestamps and restoration remain manual; no health check or status endpoint has been deployed.

Local validation: `python tools/maintenance_guard.py validate` and `python -m unittest tests.test_maintenance_guard -v`. PR order verification is `python tools/maintenance_guard.py check-pr --base <BASE_SHA> --pr <NUMBER>` in a complete git checkout.

The integration PR #72 includes the separately CI-validated squash commit `ad1a51924b0736c0f3de1c32b01e9148786d34e3` of the pre-policy PR #67 gateway label change. The guard permits only the immutable squash commit and `services/bug-gateway/src/index.js`, because the original source change predates the preregistration policy. No later source, package, deployment or workflow changes are exempt. `MAINT-20261017-001` was committed before version/metadata changes in #72.
