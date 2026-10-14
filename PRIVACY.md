# Privacy Policy — WinNAT UI

Last updated: 14 October 2026

WinNAT UI is an open-source, locally operated Windows networking utility maintained by Matteo Cannizzo. This policy describes the application's current source-code behavior.

## Data processed locally
To display network configuration and diagnose WinNAT, the application queries local network adapter names and descriptions, IPv4 addresses, routes, gateways, NAT rules and sessions, forwarding status, and Windows Internet Connection Sharing (ICS) settings. This information can include private or public IP addresses and network topology details.

Before a configuration change, the application writes a diagnostic JSON snapshot to `%LOCALAPPDATA%\WinNAT-UI\backups\`. When using the guided setup, a local configuration-state file is stored at `%LOCALAPPDATA%\WinNAT-UI\managed-setup.json`. Users may also explicitly export diagnostic data to a chosen JSON file.

## Data transmission and third parties
The application does not implement telemetry, analytics, tracking, remote accounts, automatic updates, or transmission of diagnostic information to the maintainer. The application's purpose is to configure Windows networking and NAT, through which other devices may subsequently exchange traffic with Internet services chosen by those devices. Windows, endpoint security software, and third-party network services have their own behavior and privacy policies.

GitHub processes information when you visit the repository or download a release; refer to [GitHub's Privacy Statement](https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement).

## Retention and deletion
Local diagnostic files remain on the user's device until the user deletes them. The application currently does not automatically rotate or delete old backups. The application has no centralized user database.

To delete local application data, close WinNAT UI and remove `%LOCALAPPDATA%\WinNAT-UI\`, after retaining any backups you need. This **does not** undo operating-system network configuration. Use the application's guided removal before removing the application, if applicable.

## Security
The program may require administrator privileges to change Windows network configuration. Treat exported diagnostics as potentially sensitive, especially when they reveal network topology or active NAT sessions. The executable remains unsigned until an approved signing process is configured; antivirus scanning in CI is not a guarantee against malicious code.

## Contact
For privacy-related questions, report an issue at [WinNAT UI GitHub Issues](https://github.com/matiz311/WinNAT-UI/issues), without including private network addresses, credentials, or diagnostic files containing sensitive data.
