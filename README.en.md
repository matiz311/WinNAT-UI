<img src="assets/winnat-ui-256.png" alt="" width="96" align="right">

# WinNAT UI

**English** | [Italiano](README.md)

[![Download Windows ZIP](https://img.shields.io/badge/Download-Windows%20ZIP-blue?logo=windows)](https://github.com/matiz311/WinNAT-UI/releases/latest/download/WinNAT-UI-Windows.zip)
[![Latest release](https://img.shields.io/github/v/release/matiz311/WinNAT-UI)](https://github.com/matiz311/WinNAT-UI/releases/latest)
[![Windows build](https://github.com/matiz311/WinNAT-UI/actions/workflows/build.yml/badge.svg)](https://github.com/matiz311/WinNAT-UI/actions/workflows/build.yml)

**[Download WinNAT UI for Windows](https://github.com/matiz311/WinNAT-UI/releases/latest/download/WinNAT-UI-Windows.zip)**. Extract the entire ZIP, then run `WinNAT-UI.exe`. The current published release is **v1.15.1** and **unsigned**; SignPath Foundation signing has not yet been approved.

**Upcoming release candidate:** v1.16.0 adds issue triage/search, failed-update reporting, and structured GitHub update channel diagnostics. The published release remains v1.15.1 until approved CI publication.

[Releases](https://github.com/matiz311/WinNAT-UI/releases) · [Privacy policy](PRIVACY.md) ([Italiano](PRIVACY.it.md)) · [Code signing policy](CODE_SIGNING_POLICY.md) ([Italiano](CODE_SIGNING_POLICY.it.md)) · [Changelog (IT)](CHANGELOG.md) · [MIT License](LICENSE)

WinNAT UI is a Windows 10/11 desktop application for diagnosing and managing **Windows NAT**, LAN/WAN adapters, IPv4 routing, and Internet Connection Sharing (ICS).

## Features
- Display network adapters, IPv4 addresses, gateways, forwarding settings and default routes.
- Inspect Windows NAT rules and sessions, SharedAccess service status, and ICS sharing settings.
- Infer the WAN from the default route, subject to manual verification; choose the LAN adapter.
- Add or remove WinNAT rules with conflict warnings.
- Guided Ethernet-to-Internet setup, default LAN `10.10.10.0/24` and PC address `10.10.10.1`.
- Remove the application-managed setup while preserving pre-existing LAN addresses.
- Export diagnostic JSON and save local snapshots before changes.
- Candidate configuration workflow: review and discard pending changes or **Apply (Commit)**. Currently one change per commit.

## Run
Download the ZIP from the [latest release](https://github.com/matiz311/WinNAT-UI/releases/latest), extract all files and run `WinNAT-UI.exe` as administrator.

To run the source directly:
```powershell
py -3 app.py
```
Requires Windows, PowerShell 5.1+, and administrator privileges for network changes.


## Repository layout
The repository keeps documentation at the top level and groups Python files by responsibility:

- `app.py` — application launcher, kept compatible with `py -3 app.py` and PyInstaller.
- `version.py` and `version_info.txt` — release version and Windows metadata used by the build process.
- `winnat_ui/` — application modules (networking, WinNAT, UI, updater and issue reporting).
- `tests/` — Python tests run in CI via `python -m unittest discover -s tests -t . -v`.
- `tools/` — diagnostic and maintenance scripts; `assets/` — icons and resources.
- `services/` — external services; `.github/workflows/` — GitHub Actions pipelines.

Markdown documents, `LICENSE` and `bug-service.json` stay in the repository root to keep project information and the client's remote service URL stable.

## Build and distribution
[GitHub Actions](.github/workflows/build.yml) builds the Windows application using PyInstaller in `--onedir --noupx` mode, checks binary metadata and invokes Microsoft Defender. The build must pass the required Defender check before an artifact or release is published. Checksums and a scan report accompany the build. The absence of reported threats does not prove that software is safe. The workflow can also be started via **Actions → Build Windows executable → Run workflow**.

The PowerShell backend uses readable `-Command` calls declared in [winnat_ui/network.py](winnat_ui/network.py), rather than `-EncodedCommand` or Base64. PyInstaller bundles a bootloader and is not an entirely plaintext executable.

## Networking limitations
This software does not provide a DHCP or DNS server, and does not test every connected device automatically. Set the connected device's IP within the LAN subnet, its default gateway to the PC's LAN address, and appropriate DNS servers. Do not configure competing ICS and WinNAT sharing on the same LAN. WAN identification is heuristic and must be confirmed.

Microsoft WinNAT supports a single internal prefix: multiple independent WinNAT definitions are not a supported multi-NAT design. The application does not automatically delete Hyper-V, VPN, ICS, or unrelated NAT configuration. For multiple networks, consider deliberate routing into a consolidated NAT prefix or a dedicated router.

## Managed setup removal
**Rimuovi setup gestito** (Remove managed setup) is available only when the wizard saved a setup record. It checks the managed `WinNAT-UI` rule and prefix before removal. It deletes the LAN address only if the wizard added it, and preserves other NAT rules and global forwarding settings. Local JSON snapshots are diagnostic backups, **not an automatic rollback**.

## Candidate configuration and commit
Creating or removing NAT rules and adding or removing a guided setup does **not** change Windows immediately. These actions are staged under **Modifiche pendenti** (Pending changes), where they can be discarded or committed after confirmation. One candidate operation is applied per commit.

For **Configure gateway**, the candidate is a **desired state**. Immediately before Commit the application re-reads Windows, computes the delta, and writes only what is still missing. Retrying after a partial failure therefore skips IP, forwarding, metric, and NAT settings that already match. A second inventory verifies convergence after the writes. Destructive **Disable/Reset** operations retain strict preview fingerprint checks and stop when relevant state changed externally.

Local `candidate-commit`, `pre-commit`, `post-commit`, and when needed `post-rollback` checkpoints are stored under `%LOCALAPPDATA%\WinNAT-UI\commit-states`. Rollback is compensating and best-effort; Windows network configuration is not an atomic transaction.

## Windows Defender
A previous unsigned development build was reported as `Trojan:Win32/Bearfoos.B!ml`. It has not been conclusively established whether the detection was a false positive. Do not bypass Defender or restore quarantined files without independent verification. Preserve detection details, review the source and build, and submit the sample to Microsoft when appropriate. New builds use `--onedir --noupx` and require a Defender scan before publication.

## Product identity and signing
The executable declares WinNAT UI and Matteo Cannizzo in its Windows version resources. **Metadata does not establish a verified publisher.** Only a verifiable Authenticode signature from a trusted signing process can provide verified signing identity. The current binary remains unsigned; the public repository is preparing an application for SignPath Foundation, which has not approved or issued a certificate.

If accepted, release pages will include the attribution: “Free code signing provided by SignPath.io, certificate by SignPath Foundation”.

[Code signing policy](CODE_SIGNING_POLICY.md) · [SignPath Foundation terms](https://signpath.org/terms.html)

## Uninstall
Close the application, use guided removal first if it created your NAT setup, and remove the extracted program directory. See the [privacy policy](PRIVACY.md) for optional removal of locally stored diagnostic files.

## Microsoft references
- [Setting up a NAT network](https://learn.microsoft.com/en-us/windows-server/virtualization/hyper-v/setup-nat-network)
- [New-NetNat](https://learn.microsoft.com/en-us/powershell/module/netnat/new-netnat)
- [Get-NetNat](https://learn.microsoft.com/en-us/powershell/module/netnat/get-netnat)

## Maturity
**Published version: v1.14.0 (16 October 2026).** Windows CI builds and automated tests have passed; real-world tests of forwarding, NAT, the updater, rollback and Hyper-V/VPN/ICS interactions are still required. Begin with read-only diagnostics in a test environment.

## Feature history — published releases

The current **v1.14.0** includes the features introduced in the releases below. On 16 October 2026, the preceding 28 releases were republished with consistent version numbers, rebuilt binaries and verified Git tags. The numbers below refer only to **currently published** [GitHub Releases](https://github.com/matiz311/WinNAT-UI/releases). See the [changelog](CHANGELOG.md) and [Italian release notes](RELEASE_NOTES.it.md) for release-specific detail.

- **v1.2.0–v1.4.0:** initial distribution, network inventory, dashboard, pending changes, Commit and guided NAT configuration removal.
- **v1.5.0–v1.5.2:** full Windows gateway setup, DHCP/PersistentStore and static LAN IPv4 fixes.
- **v1.6.0–v1.6.4:** redesigned navigation, light/dark themes and improved PowerShell diagnostics.
- **v1.7.0–v1.9.0:** read-only compatibility diagnostics, compensating rollback, dynamic WANs and LAN subnet discovery.
- **v1.10.0–v1.11.2:** checksum-verified updater, issue reporting and issue-gateway integration.
- **v1.12.0–v1.12.5:** diff-based idempotent Commit, checkpoints and safer NAT/LAN subnet management.
- **v1.13.0 and v1.13.0.1:** subnet aggregation in advanced gateway setup and a HOTFIX isolating the simple Add NAT operation.
- **v1.14.0:** deployment and validation of anonymous issue reporting and improved updater diagnostics.

**Operational note:** Windows network changes are not atomic transactions. Always review the pending configuration and retain local access. The automatic updater still needs validation on a real Windows installation.
