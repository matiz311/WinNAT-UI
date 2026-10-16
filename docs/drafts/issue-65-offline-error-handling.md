# Draft implementation — Issue #65: offline and DNS-aware issue synchronization

Status: **planning only**. No production code changed. Source: https://github.com/matiz311/WinNAT-UI/issues/65

## Confirmed context
The reporter deliberately disconnected the PC from the Internet. The reported WinNAT-UI 1.15.0 failure occurred during **Stato bug**: `app.py refresh_issue_tracker → issue_tracker.synchronize → public_issues → _read_json → urllib.request.urlopen`. Root exception: `socket.gaierror [Errno 11001] getaddrinfo failed` wrapped in `URLError`. This means name resolution failed; the stack trace alone does not prove general Internet disconnection. The disconnect is confirmed by the user independently.

## Implementation steps
1. In `winnat_ui/issue_tracker.py`, centralize external-request exception classification: DNS/name-resolution failure, timeout, generic connection/URL error, TLS/proxy failure, HTTP 403/429/404/5xx, malformed response. Preserve the original exception for filtered diagnostics. Keep network checks bounded by timeouts.
2. Define an explicit result/status model for remote issue synchronization, including `synced`, `offline_or_unreachable`, `dns_failure`, `http_failure`, and `unknown`. Do not translate all DNS errors into a definitive claim that the machine is offline.
3. In `app.py refresh_issue_tracker`, retain the local history and previously known issue status when synchronization fails; do not show a successful refresh or infer that no fix exists. Show a clear, recoverable UI message and **Riprova** action. Optionally show last successful sync time and stale indicator.
4. Optional bounded post-failure diagnostics: consult Windows connectivity indication, local interface/default route state, DNS resolution for the actual GitHub host, and HTTPS access to the same authorized service. Treat each signal as suggestive, not definitive; no mandatory third-party probes or ICMP-only Internet tests.
5. Make offline checks non-blocking, prevent recursive bug-report creation from expected connectivity outages, and allow manual reporting once connectivity returns. No changes to WinNAT, routes, interface DHCP/static settings, or DNS as a side-effect.
6. Align error categories and user messages with the updater without tightly coupling the modules. Avoid exposing tokens/secrets in logs and GitHub issue bodies.

## Acceptance tests
- Mock `socket.gaierror(11001)`, `URLError`, timeout, TLS/proxy issues, HTTP 403/429/5xx, bad JSON and success.
- Manual scenarios: deliberately disconnect Internet; Wi-Fi connected but captive/offline; broken DNS with a working link; GitHub HTTPS failure with working DNS; restoration and successful retry.
- Verify app remains responsive, stored history untouched, remote status flagged unverified, no duplicate automatic reports, and fix availability never falsely asserted.
- Test compiled EXE on Windows, then CI tests and actual release verification before assigning `fixed-in/v...`.

## Open design decisions
- Whether to use Windows NLM/NCSI as an optional signal and how to avoid unreliable connectivity assertions.
- UI placement for last-sync time and actionable retry.
- Shared exception taxonomy with updater and compatibility with existing `synchronize()` return contract.

## Coordination
Keep this branch scoped to issue #65; do not modify the updater/release-maintenance feature without an explicit integration design. Follow `AGENTS.md` integration gate, versioning policy and main-branch ownership rules. No merge or release authorized by this draft.
