# GitHub maintenance registry

The repository stores two distinct JSON documents:

- `maintenance-history.json`: versioned audit history. Write planned disruptive work **before** changing services; do not backfill invented timestamps. Event fields: `id`, `type` (`routine`, `extraordinary`, `structural`), `status` (`planned`, `in_progress`, `completed`, `cancelled`), `started_at` and `ended_at` (UTC ISO 8601 or null if unknown), `components`, `description`, `expected_errors`, `related_issues`, `evidence`. Include rollback and linked workflow/commit data when available. Corrections must have attributable commits.
- `maintenance-status.json`: current per-service state. `status` is `operational`, `maintenance`, `degraded`, `unavailable`, or `unknown`. `unknown` means no trustworthy observation yet; never represent a missing update or missing file as `operational`. `updated_at` is null until a real observation is published.

Any client fetching the status file must treat it as **advisory**. Use short network timeouts, explicitly identify stale observations, and remain functional if it cannot be retrieved. A maintenance status cannot bypass official-asset URL checks or SHA-256 verification and cannot alone prove causality.

## Manual operating procedure

1. Before planned disruptive work, commit the planned event in history with a unique `MAINT-YYYYMMDD-NNN` identifier, precise UTC start when known, affected components, impact and rollback.
2. Set the affected services to `maintenance` in status, referencing the same event ID, with the actual UTC publication timestamp.
3. Perform the change, then validate GitHub release metadata and that the release ZIP has an official URL and verifiable SHA-256.
4. Record the conclusion, actual time, workflow/commit references, encountered errors and verification evidence in history. Restore operational status **only after verification**.
5. For emergencies where advance registration was impossible, document the exception and the earliest reliable timestamps. No guessed retrospective hours.

Example historical event (the migration related to #44): its actual start/end UTC and original HTTP status are **not documented**. Preserve null times and describe 404 only as a compatible, unproven error. Do not fabricate a live maintenance state for this historical incident.

**Limitation:** this schema and operating procedure do not themselves enforce workflows or deploy any status endpoint. CI validation and automatic lifecycle recording require separate changes.
