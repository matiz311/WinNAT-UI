# Draft implementation — Issue #44: release channel state and maintenance-aware update diagnostics

Status: **planning only**. No production code changed. Source: https://github.com/matiz311/WinNAT-UI/issues/44

## Confirmed context
The reporter checked updates while the old GitHub WinNAT-UI release structure was being replaced and the release versioning was rebuilt. No downloadable Windows builds were available then. The old report contains `HTTPError` but **does not contain its HTTP status**; a 404 is plausible, not retrospectively proven. The current `winnat_ui/updater.py` already interprets 404/403/429/5xx and `URLError`, and validates an official `WinNAT-UI-Windows.zip` asset and SHA-256 digest.

## Implementation steps
1. Classify `no_published_release` (HTTP 404), `release_without_required_asset` (successful metadata but no single ZIP), `invalid_release_metadata` (missing/invalid asset URL or digest), `rate_limited`, `server_unavailable`, and `network_failure`. Preserve the existing official URL allowlist and SHA-256 checks; never offer unverifiable binaries.
2. Make absent releases a clearly explained non-crash, non-NAT failure in manual checks; make automatic checks non-disruptive while retaining enough evidence for support. Show missing ZIP and absent stable release as different states.
3. Integrate a **versioned maintenance registry** from `docs` / `.github/maintenance` once policy PR #68 has been reviewed and integrated. Do not assume it exists on `main` yet. Read current status separately from historical events. Declare status `unknown` when inaccessible; make this lookup optional with timeout and a local last-known cache timestamp. No circular dependency on GitHub availability.
4. Correlate an updater error with maintenance only if UTC interval, affected component, and expected error signature match. Distinguish a **possible correlation** from **confirmed cause**, which requires evidence or maintainer confirmation. Support intentionally planned reconstruction of release assets and GitHub repository changes.
5. Instrument operations by phase: release lookup, asset enumeration, archive download, integrity validation, installation. Include real app version/build, UTC timestamp, endpoint host/path, HTTP status or exception type, and filtered traceback in reports.
6. Plan CI checks to validate the maintenance schema, confirm preregistration of disruptive release workflows and append successful/failed release events. Respect emergency retrospective exception described in policy; do not force registry availability at runtime.

## Acceptance tests
- Mock 404 no release; 200 release with no asset; duplicate ZIP; missing/bad digest; full valid release; 403/429, 5xx, DNS/timeout.
- Maintenance window overlaps error with matching component; window not overlapping; unrelated component; stale or inaccessible maintenance file; unknown timestamps; confirm no false positive `caused by maintenance`.
- Compiled Windows build tests; never weaken asset integrity or GitHub URL allowlist; app remains operational if release metadata or maintenance registry is missing.

## Dependencies and sequencing
- Policy PR #68: https://github.com/matiz311/WinNAT-UI/pull/68 — coordinate schema and pre-change recording before implementing runtime correlation.
- This branch is independent from #65 but taxonomy/UI helpers might overlap; reconcile through reviewed integration, not blind merge.
- Decide retention strategy and stable manifest endpoint with release maintainers. No invented retrospective dates for #44.
- Apply `AGENTS.md` merge/versioning gates, and do not publish a release as part of the draft.
