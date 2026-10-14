# Code signing policy

## Status
Code signing through SignPath Foundation is **not yet approved or enabled**. The executable is currently unsigned. This policy describes the intended release process, not an existing certificate.

## Project
- Repository: https://github.com/matiz311/WinNAT-UI
- License: MIT
- Committer/maintainer: [matiz311](https://github.com/matiz311)
- Reviewer (current project maintainer): [matiz311](https://github.com/matiz311)
- Release approval: [matiz311](https://github.com/matiz311)

## Release controls
- Signed releases, if approved, must originate from the canonical public repository and a reviewed GitHub Actions workflow.
- Release approval is explicitly required and must use the signing service's protected workflow.
- A successful build and Defender scan are prerequisites; they do not guarantee the software is malware-free.
- No user credentials, certificate private keys or signing tokens are embedded in the source or output.
- All contributors must use multi-factor authentication for repository and signing-service access.

## Privacy
This program does not transfer information to other networked systems unless specifically requested by the user or administrator operating it. It queries local Windows networking state and writes local JSON snapshots. When configured, Windows networking itself forwards traffic to destinations requested by the connected devices. No telemetry is implemented by this application.

## Future SignPath attribution
If and only if accepted into the Foundation program, the release page will display the required text:
"Free code signing provided by SignPath.io, certificate by SignPath Foundation"

See https://signpath.org/terms.html and https://signpath.org/apply.html.
