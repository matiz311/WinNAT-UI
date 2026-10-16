"""Read-only preflight for historical WinNAT-UI SemVer migration.

Usage: python tools/migrate_release_history.py --inventory migration-inventory.json
Requires gh auth and permission to view releases/tags. NEVER changes Git refs.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess

REPO = "matiz311/WinNAT-UI"
TAG_PATTERN = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)(?:\.(\d+))?$")
ROW = re.compile(r"^\| `(v[0-9.]+)` \| `(v[0-9.]+)` \| (MINOR|PATCH|HOTFIX|MAJOR) \|$", re.M)


def request(path):
    p = subprocess.run(["gh", "api", "--paginate", path], text=True, capture_output=True)
    if p.returncode:
        raise RuntimeError("GitHub API failure: " + p.stderr.strip())
    # GitHub cli --paginate may concatenate multiple JSON arrays.
    text = p.stdout.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        items = []
        while text:
            value, offset = decoder.raw_decode(text)
            items.extend(value if isinstance(value, list) else [value])
            text = text[offset:].lstrip()
        return items


def parse_plan(text):
    matches = ROW.findall(text)
    if not matches:
        raise ValueError("No migration records found")
    old, new = [a for a, _, _ in matches], [b for _, b, _ in matches]
    if len(set(old)) != len(old) or len(set(new)) != len(new):
        raise ValueError("Duplicate old or new release version")
    tuples = [version_tuple(n) for n in new]
    if tuples != sorted(tuples) or len(set(tuples)) != len(tuples):
        raise ValueError("Target versions must be unique and chronological")
    return matches


def version_tuple(value):
    match = TAG_PATTERN.fullmatch(value)
    if not match:
        raise ValueError("Invalid version: " + value)
    return tuple(int(v or 0) for v in match.groups())


def audit(plan, releases, tags):
    by_tag = {r["tag_name"]: r for r in releases}
    known_tags = {r["name"]: r for r in tags}
    if len(by_tag) != len(releases) or len(known_tags) != len(tags):
        raise ValueError("Duplicate tag/release in GitHub inventory")
    if not releases or not tags:
        raise ValueError("GitHub returned an empty release or tag inventory")
    source_tags = {old for old, _, _ in plan}
    issues = []
    report = []
    for old, new, kind in plan:
        release = by_tag.get(old)
        if not release:
            issues.append("Historical release not found: " + old)
        if old not in known_tags:
            issues.append("Historical tag not found: " + old)
        if new in known_tags and new not in source_tags and new != old:
            issues.append("Target tag already exists: " + new)
        assets = [] if not release else [
            {"name": a.get("name"), "id": a.get("id"), "size": a.get("size"),
             "digest": a.get("digest"), "url": a.get("url")}
            for a in release.get("assets", [])
        ]
        windows = [a for a in assets if a["name"] == "WinNAT-UI-Windows.zip"]
        if release and len(windows) != 1:
            issues.append("Expected exactly one Windows ZIP for: " + old)
        for asset in windows:
            digest = asset.get("digest") or ""
            if not re.fullmatch(r"sha256:[0-9a-fA-F]{64}", digest):
                issues.append("SHA256 digest missing/invalid for: " + old)
            if not isinstance(asset.get("size"), int) or asset["size"] <= 0:
                issues.append("ZIP size missing/invalid for: " + old)
        if old in known_tags and not (known_tags[old].get("commit") or {}).get("sha"):
            issues.append("Source tag commit SHA missing: " + old)
        report.append({
            "old": old, "new": new, "kind": kind, "release_id": release.get("id") if release else None,
            "release_target": release.get("target_commitish") if release else None,
            "source_tag_sha": (known_tags[old].get("commit") or {}).get("sha") if old in known_tags else None,
            "published_at": release.get("published_at") if release else None,
            "release_body": release.get("body") if release else None,
            "assets": assets,
        })
    unexpected = sorted(set(by_tag) - source_tags)
    tag_only = sorted(set(known_tags) - set(by_tag))
    if tag_only:
        issues.append("Tags without a GitHub Release require review: " + ", ".join(tag_only))
    if unexpected:
        issues.append("Other published releases require manual classification: " + ", ".join(unexpected))
    return {"repository": REPO, "migrations": report,
            "unmapped_published_tags": unexpected, "tags_without_release": tag_only,
            "blocking_issues": issues,
            "publish_allowed": not issues}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    plan = parse_plan((root / "SEMVER_MIGRATION_PLAN.md").read_text(encoding="utf-8"))
    releases = request(f"repos/{REPO}/releases?per_page=100")
    tags = request(f"repos/{REPO}/tags?per_page=100")
    result = audit(plan, releases, tags)
    args.inventory.parent.mkdir(parents=True, exist_ok=True)
    args.inventory.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"migrations": len(plan), "blocking_issues": result["blocking_issues"]}, ensure_ascii=False))
    if result["blocking_issues"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
