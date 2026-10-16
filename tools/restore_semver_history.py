"""Emergency restore of verified pre-migration public tags and GitHub Releases.

Uses GitHub REST Git References instead of git push (the Actions Git transport
cannot rewrite historical workflow-bearing refs with its current permissions).
"""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

REPO = "matiz311/WinNAT-UI"
NAME = "WinNAT-UI-Windows.zip"


def gh(*args, check=True):
    p = subprocess.run(["gh", *args], capture_output=True, text=True, encoding="utf-8")
    if check and p.returncode:
        raise RuntimeError("GitHub operation failed: " + " ".join(args[:5]) + " " + p.stderr[-600:])
    return p


def asset_hash(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def main(work):
    manifest = json.loads((work / "migration_manifest.json").read_text(encoding="utf-8"))
    entries = manifest["original_releases"]
    if len(entries) != 28:
        raise ValueError("Expected exactly 28 preserved original releases")
    for item in entries:
        path = work / "originals" / item["old"] / NAME
        if not path.exists() or asset_hash(path) != item["original_sha256"]:
            raise ValueError("Backup missing/corrupt: " + item["old"])
    for i, item in enumerate(entries):
        tag, sha = item["old"], item["ref_sha"]
        print("Restoring " + tag + " (" + str(i+1) + "/28)", flush=True)
        note_file = work / "originals" / tag / "original-notes.md"
        note_file.write_text(item["release_body"], encoding="utf-8")
        get = gh("api", f"repos/{REPO}/git/ref/tags/{tag}", check=False)
        released_while_creating_tag = False
        if get.returncode:
            ref_result = gh("api", "-X", "POST", f"repos/{REPO}/git/refs",
                            "-f", "ref=refs/tags/" + tag, "-f", "sha=" + sha,
                            check=False)
            if ref_result.returncode:
                print("REST Git ref rejected; attempting atomic GitHub Release+tag creation", flush=True)
                gh("release", "create", tag,
                   str(work / "originals" / tag / NAME),
                   "--target", sha, "--repo", REPO,
                   "--title", "WinNAT UI " + tag,
                   "--notes-file", str(note_file),
                   "--latest" if i == len(entries)-1 else "--latest=false")
                released_while_creating_tag = True
        else:
            existing = json.loads(get.stdout)["object"]["sha"]
            if existing != sha:
                raise ValueError("Tag points at an unexpected commit: " + tag)
        if not released_while_creating_tag:
            exists = gh("release", "view", tag, "--repo", REPO, check=False).returncode == 0
            if not exists:
                gh("release", "create", tag, str(work / "originals" / tag / NAME),
                   "--verify-tag", "--repo", REPO, "--title", "WinNAT UI " + tag,
                   "--notes-file", str(note_file),
                   "--latest" if i == len(entries)-1 else "--latest=false")
    result = json.loads(gh("api", f"repos/{REPO}/releases?per_page=100").stdout)
    found = {x["tag_name"] for x in result}
    expected = {x["old"] for x in entries}
    if found != expected:
        raise ValueError("Restore incomplete: missing " + ", ".join(sorted(expected - found)))
    print("RESTORED: 28 original releases and matching tags", flush=True)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
