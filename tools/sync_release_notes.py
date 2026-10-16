"""Synchronize published GitHub Release bodies without changing tags or assets.

Dry run by default; use --apply after manual review of the proposed changes.
Changelog is the source of version-specific facts. Open issues are linked
to the live issue tracker (not assigned to historical versions).
"""
import json
import pathlib
import re
import subprocess
import sys

import release

REPO_URL = "https://github.com/matiz311/WinNAT-UI"
ROOT = pathlib.Path(__file__).resolve().parent.parent
MARKER = "<!-- WINNAT_RELEASE_NOTES_END -->"


def gh(*args, data=None):
    out = subprocess.run(["gh", "api", *args], input=data, capture_output=True,
                         text=True, encoding="utf-8")
    if out.returncode:
        raise SystemExit(out.stderr)
    return out.stdout


def kind(version):
    """Release type derived from the canonical functional version."""
    match = release.SEMVER.fullmatch(version)
    if not match:
        raise ValueError("Versione invalida: " + version)
    major, minor, patch, hotfix = [int(x or 0) for x in match.groups()]
    if hotfix:
        return "HOTFIX"
    if patch:
        return "PATCH"
    if minor:
        return "MINOR"
    return "MAJOR"



def preserved_footer(body):
    text = (body or "").replace("\r\n", "\n")
    if MARKER in text:
        return text.split(MARKER, 1)[1].strip()
    # Preserve the known, existing release-security footer if any.
    for anchor in ("**UNSIGNED DEVELOPMENT BUILD**", "**BUILD NON FIRMATA**"):
        pos = text.find(anchor)
        if pos != -1:
            return text[pos:].strip()
    return ""


def new_body(version, old_body):
    changes = release.notes(version)
    classification = kind(version)
    footer = preserved_footer(old_body)
    parts = [
        "## WinNAT-UI v" + version,
        "**Classificazione:** " + classification,
        "### Modifiche della versione",
        changes,
        "### Open Issues",
        "Problemi ancora aperti: " + REPO_URL + "/issues?q=is%3Aissue+is%3Aopen",
        "### Documentazione",
        "- Note per tutte le versioni: " + REPO_URL + "/blob/main/RELEASE_NOTES.it.md",
        "- Regole del versioning e catalogo pubblicato: " + REPO_URL + "/blob/main/VERSIONING_POLICY.md",
        "- Changelog tecnico: " + REPO_URL + "/blob/main/CHANGELOG.md",
        MARKER,
    ]
    if footer:
        parts.append(footer)
    return "\n\n".join(parts).rstrip() + "\n"


def main(apply):
    entries = json.loads(gh("--paginate", "repos/{owner}/{repo}/releases?per_page=100"))
    count = 0
    for item in entries:
        tag = item.get("tag_name", "")
        if not re.fullmatch(r"v?\d+\.\d+\.\d+(?:\.\d+)?", tag):
            print("SALTATA " + tag + ": tag non SemVer")
            continue
        version = tag.removeprefix("v")
        try:
            body = new_body(version, item.get("body"))
        except SystemExit:
            print("SALTATA " + tag + ": changelog assente")
            continue
        if body.strip() == (item.get("body") or "").replace("\r\n", "\n").strip():
            print("INVARIATA " + tag)
            continue
        print(("AGGIORNATA " if apply else "DA AGGIORNARE ") + tag
              + " [" + kind(version) + "]")
        count += 1
        if apply:
            gh("-X", "PATCH", "repos/{owner}/{repo}/releases/" + str(item["id"]),
               "--input", "-", data=json.dumps({"body": body}, ensure_ascii=False))
    print("Release " + ("aggiornate: " if apply else "da aggiornare: ") + str(count))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main("--apply" in sys.argv)
