"""Rewrite the notes of every published GitHub release from CHANGELOG.md.

Runs in GitHub Actions (workflow "Sync release notes", manual). Tags and
assets are never touched: only the text at the top of each release body is
replaced; the existing footer (signing, privacy, Defender notes) is kept.

  python tools/sync_release_notes.py            -> dry run, prints changes
  python tools/sync_release_notes.py --apply    -> updates releases (needs GH_TOKEN)
"""
import json
import subprocess
import sys

import release

REPO_URL = "https://github.com/matiz311/WinNAT-UI"


def gh(*args, data=None):
    out = subprocess.run(["gh", "api", *args], input=data, capture_output=True, text=True, encoding="utf-8")
    if out.returncode:
        raise SystemExit(out.stderr)
    return out.stdout


def new_body(version, body):
    body = (body or "").replace("\r\n", "\n")
    if "\n---\n" in body and body.startswith("## Novit"):
        footer = body.split("\n---\n", 1)[1]
    else:
        footer = body.partition("\n\n")[2]
    notes = release.notes(version).replace("### ", "#### ")
    return ("## Novità in " + version + "\n\n" + notes + "\n\nChangelog completo: " + REPO_URL +
            "/blob/main/CHANGELOG.md\n\n---\n" + footer.strip() + "\n")


def main(apply):
    releases = json.loads(gh("--paginate", "repos/{owner}/{repo}/releases?per_page=100"))
    for r in releases:
        version = r["tag_name"].lstrip("v")
        try:
            body = new_body(version, r["body"])
        except SystemExit:
            print("SALTATA " + r["tag_name"] + ": nessuna sezione nel CHANGELOG")
            continue
        if body.strip() == (r["body"] or "").replace("\r\n", "\n").strip():
            print("invariata " + r["tag_name"])
            continue
        print(("AGGIORNATA " if apply else "da aggiornare ") + r["tag_name"])
        if apply:
            gh("-X", "PATCH", "repos/{owner}/{repo}/releases/%d" % r["id"], "--input", "-",
               data=json.dumps({"body": body}))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main("--apply" in sys.argv)
