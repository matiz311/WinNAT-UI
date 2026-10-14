# WinNAT UI

**English** | [Italiano](README.md)

[![Download Windows ZIP](https://img.shields.io/badge/Download-Windows%20ZIP-blue?logo=windows)](https://github.com/matiz311/WinNAT-UI/releases/latest/download/WinNAT-UI-Windows.zip)
[![Latest release](https://img.shields.io/github/v/release/matiz311/WinNAT-UI)](https://github.com/matiz311/WinNAT-UI/releases/latest)
[![Windows build](https://github.com/matiz311/WinNAT-UI/actions/workflows/build.yml/badge.svg)](https://github.com/matiz311/WinNAT-UI/actions/workflows/build.yml)

**[Download WinNAT UI for Windows](https://github.com/matiz311/WinNAT-UI/releases/latest/download/WinNAT-UI-Windows.zip)**. Extract the entire ZIP, then run `WinNAT-UI.exe`. The current release is **unsigned**; SignPath Foundation signing has not yet been approved.

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

## Build and distribution
[GitHub Actions](.github/workflows/build.yml) builds the Windows application using PyInstaller in `--onedir --noupx` mode, checks binary metadata and invokes Microsoft Defender. The build must pass the required Defender check before an artifact or release is published. Checksums and a scan report accompany the build. The absence of reported threats does not prove that software is safe. The workflow can also be started via **Actions → Build Windows executable → Run workflow**.

The PowerShell backend uses readable `-Command` calls declared in [network.py](network.py), rather than `-EncodedCommand` or Base64. PyInstaller bundles a bootloader and is not an entirely plaintext executable.

## Networking limitations
This software does not provide a DHCP or DNS server, and does not test every connected device automatically. Set the connected device's IP within the LAN subnet, its default gateway to the PC's LAN address, and appropriate DNS servers. Do not configure competing ICS and WinNAT sharing on the same LAN. WAN identification is heuristic and must be confirmed.

Microsoft WinNAT supports a single internal prefix: multiple independent WinNAT definitions are not a supported multi-NAT design. The application does not automatically delete Hyper-V, VPN, ICS, or unrelated NAT configuration. For multiple networks, consider deliberate routing into a consolidated NAT prefix or a dedicated router.

## Managed setup removal
**Rimuovi setup gestito** (Remove managed setup) is available only when the wizard saved a setup record. It checks the managed `WinNAT-UI` rule and prefix before removal. It deletes the LAN address only if the wizard added it, and preserves other NAT rules and global forwarding settings. Local JSON snapshots are diagnostic backups, **not an automatic rollback**.

## Candidate configuration and commit
Creating or removing NAT rules and adding or removing a guided setup does **not** change Windows immediately. These actions are staged under **Modifiche pendenti** (Pending changes), where they can be discarded or committed after confirmation. State is refreshed before commit and a diagnostic snapshot is taken. This prototype supports one operation per commit and has no transactional rollback.

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
Early public release. Real-world Windows tests of forwarding, NAT, rollback behavior and interactions with Hyper-V/VPN/ICS remain necessary. Start with read-only diagnostics in a test environment.

## Version 1.3.0 interface
- **Dashboard** shows live configuration independently of NAT sessions.
- **NAT** shows active and pending rules in the same table, marking additions/removals.
- **Rete** stages guided setup and removal.
- **Modifiche** previews changes before commit; **Scarta** discards pending edits.
- **Sessioni** polls active NAT sessions separately every 60 seconds while selected, and offers a manual **Aggiorna** refresh.
- Async operations display an indeterminate progress bar. PowerShell runs without a separate console window.

For safety, the commit currently applies **one operation at a time**, although multiple changes can be staged. Windows operations do not offer transactional rollback.

## Version 1.4.0: existing configuration removal
- Independent adapter, IPv4, routing, forwarding and NAT inventory queries run concurrently; sessions remain separate.
- **Rete > Rimuovi esistente** stages removal of an existing NAT rule matching the selected subnet, including rules created outside this app.
- The LAN interface address is preserved unless optional exact-address removal is explicitly selected. ICS, DHCP, VPN and unrelated settings are not touched.
- Review **Modifiche**, then select **Commit**. Once the old NAT is removed, return to **Rete** to stage a clean setup.
- Local console access is strongly recommended: removing networking configurations can terminate a remote management session.

## Version 1.6.0 — Complete Windows 11 router/NAT setup

**Rete → Configura** implements the supplied Windows 11 NAT and IPv4 routing procedure. Select LAN, primary WAN, optional secondary WAN, LAN network, PC gateway, NAT name and interface metrics. Suggested defaults are Ethernet / USB-C / Wi-Fi, LAN `10.10.10.0/24`, PC gateway `10.10.10.1`, NAT `NAT-Firewall`, WAN metrics 10/50. All settings are editable.

- **Configura (Configure):** disables LAN DHCP, clears existing LAN IPv4 addresses and routes, assigns a static gateway without a LAN default route, sets `IPEnableRouter=1`, enables forwarding on selected LAN/WAN interfaces, sets WAN metrics and creates the NAT. WAN interfaces must already have connectivity and default routes. Existing WAN DHCP, DNS and IP settings are preserved.
- **Disabilita (Disable):** removes **every WinNAT object**, regardless of which tool created it; disables forwarding on selected interfaces and sets `IPEnableRouter=0`. LAN IPs and WAN metrics are preserved.
- **Ripristina (Reset):** additionally clears all IPv4 addresses and routes on the selected LAN, enables its DHCP client, and restores automatic interface metrics on selected WANs. This does not restore an earlier exact state or clear WAN configurations.
- **Candidate → Commit:** shows an operation-by-operation preview, requires confirmation, and rechecks the live settings before execution. A JSON diagnostic snapshot is stored, but it is **not an automatic rollback**.
- **Restart:** restart Windows after changing `IPEnableRouter` before full connectivity verification.

**Warning:** removing all WinNAT objects can disrupt Hyper-V, WSL2 and containers. LAN IP/route changes can terminate remote access. Operate from the local console, verify interface selections and review the plan before committing. Operations are not transactional; partial changes can remain after an error.

Automated planning tests: `test_network_guide.py`.

## Fix v1.7.0 — PersistentStore DHCP vs. static IPv4
Some Windows 11 network adapters can reject `New-NetIPAddress` with `Inconsistent parameters PolicyStore PersistentStore and Dhcp Enabled`, even after DHCP has been disabled using `Set-NetIPInterface`. The LAN static-IP operation now uses `netsh interface ipv4 set address source=static ... gateway=none store=persistent`, followed by explicit verification of the assigned IP and DHCP state. Resetting the LAN to DHCP uses `source=dhcp`.

The candidate/commit process is unchanged. After a failed commit, the GUI discards the potentially stale candidate and re-reads the actual Windows configuration: **inspect the live state before trying again**, as earlier steps may already have run.

Official Microsoft reference: https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/netsh-interface.

## Interface v1.7.1 — UX redesign
- Sidebar navigation (Ctrl+1…6) with a permanent *Administrator / Read-only* indicator.
- Overview with a single gateway verdict, WAN/WinNAT/Routing/ICS cards with text badges, interface and default-route tables; raw diagnostics under *Technical details*.
- Gateway page: live LAN → PC → WAN → Internet diagram, 3-step form with inline validation and a numbered preview of what Commit will do.
- Persistent change bar (Discard / Review / Apply); commit requires explicit acknowledgement of possible network interruption.
- Light/dark theme following Windows, high-DPI aware, non-blocking toasts. No new dependencies: Tkinter/ttk only (`ui_theme.py`).
