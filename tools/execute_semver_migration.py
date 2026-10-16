"""One-time, guarded GitHub Release renumbering.

preflight: back up all 28 actual release assets, refs and published metadata;
           download and SHA256-check all 28 newly staged packages.
publish:   create version-correct source commits, replace tags/releases, and
           automatically restore originals if publication fails.

Intended only for the protected one-shot migration Actions workflow.
Never import into the main application's runtime.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from migrate_release_history import audit, parse_plan, request
from patch_historical_version import update_version

REPO = "matiz311/WinNAT-UI"
NAME = "WinNAT-UI-Windows.zip"


def call(*args, capture=False, cwd=None, input_data=None):
    result = subprocess.run(
        list(map(str, args)), cwd=cwd, input=input_data,
        stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
        stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
    if result.returncode:
        raise RuntimeError("Command failed: " + " ".join(map(str, args[:4]))
                           + "\n" + (result.stderr or "unknown subprocess error")[-1200:])
    return (result.stdout or "").strip() if capture else ""


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _validate_staged(stage: Path, old: str, new: str):
    path = stage / ("staged-" + new + "-from-" + old)
    archive = path / NAME
    expected_file = path / "PACKAGE_SHA256.txt"
    if not archive.is_file() or not expected_file.is_file():
        raise ValueError("Staged Windows archive is missing: " + str(path))
    match = re.fullmatch(
        r"sha256:([0-9a-fA-F]{64})\s+WinNAT-UI-Windows\.zip",
        expected_file.read_text(encoding="utf-8-sig").strip())
    if not match or match.group(1).lower() != sha256(archive):
        raise ValueError("Staged archive digest mismatch: " + new)
    return archive


def backup(plan_file: Path, work: Path, run_id: int):
    plan = parse_plan(plan_file.read_text(encoding="utf-8"))
    releases = request(f"repos/{REPO}/releases?per_page=100")
    tags = request(f"repos/{REPO}/git/refs/tags?per_page=100")
    tags = [{"name": r["ref"].split("/")[-1], "commit": {"sha": r["object"]["sha"]}}
            for r in tags]
    result = audit(plan, releases, tags)
    if result["blocking_issues"]:
        raise ValueError("Blocking preflight: " + json.dumps(result["blocking_issues"]))
    expected = {old for old, _, _ in plan}
    if set(x["tag_name"] for x in releases) != expected:
        raise ValueError("New releases appeared after the staging run")
    backup_dir = work / "originals"
    stage = work / "staged"
    backup_dir.mkdir(parents=True)
    stage.mkdir(parents=True)
    print("Downloading and verifying " + str(len(plan)) + " historical release ZIPs", flush=True)
    metadata = []
    for old, new, kind in plan:
        release = next(x for x in releases if x["tag_name"] == old)
        asset = next(x for x in release["assets"] if x["name"] == NAME)
        dest = backup_dir / old
        dest.mkdir()
        call("gh", "release", "download", old, "--repo", REPO,
             "--pattern", NAME, "--dir", dest)
        original_zip = dest / NAME
        digest = (asset.get("digest") or "").removeprefix("sha256:").lower()
        if not re.fullmatch("[0-9a-f]{64}", digest) or digest != sha256(original_zip):
            raise ValueError("Historical release ZIP checksum mismatch: " + old)
        metadata.append({
            "old": old, "new": new, "kind": kind,
            "ref_sha": next(t["commit"]["sha"] for t in tags if t["name"] == old),
            "release_body": release.get("body") or "",
            "original_sha256": digest, "staged_sha256": None,
        })
    print("Downloading the successful staging run artifacts", flush=True)
    call("gh", "run", "download", str(run_id), "--repo", REPO,
         "--pattern", "staged-*", "--dir", stage)
    for item in metadata:
        path = _validate_staged(stage, item["old"], item["new"])
        item["staged_sha256"] = sha256(path)
    result["original_releases"] = metadata
    result["staging_run_id"] = run_id
    result["verified_original_assets"] = len(plan)
    result["verified_staged_assets"] = len(plan)
    (work / "migration_manifest.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("READY: " + str(len(plan)) + " originals and staged packages verified", flush=True)


def _probe_publishing_permissions(source_sha):
    """Verify ability to create/delete a workflow-bearing tag and draft Release.

    Do this before touching any published historical reference.
    """
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    if not re.fullmatch(r"\d{5,20}", run_id):
        raise RuntimeError("Permission probe requires a GitHub Actions run ID.")
    probe = "winnat-migration-capability-" + run_id
    if not re.fullmatch(r"[0-9a-f]{40}", source_sha):
        raise ValueError("Unverified historical commit SHA.")
    tag_created = False
    release_created = False
    try:
        print("Preflight: testing Git tag and Release write permissions", flush=True)
        # Check the same authenticated transport used by the migration,
        # rather than only testing permission to write a REST API ref.
        call("git", "tag", probe, source_sha)
        call("git", "push", "origin", "refs/tags/" + probe)
        tag_created = True
        call("gh", "release", "create", probe, "--repo", REPO,
             "--draft", "--verify-tag", "--title", "Migration capability probe",
             "--notes", "Temporary permission preflight; automatically deleted.")
        release_created = True
    finally:
        failures = []
        if release_created:
            try:
                call("gh", "release", "delete", probe, "--repo", REPO, "--yes")
            except Exception as exc:
                failures.append("draft Release: " + str(exc))
        if tag_created:
            try:
                call("gh", "api", "-X", "DELETE",
                     f"repos/{REPO}/git/refs/tags/{probe}")
            except Exception as exc:
                failures.append("temporary tag: " + str(exc))
        if failures:
            raise RuntimeError("Permission preflight cleanup failed: " +
                               "; ".join(failures))
    if not release_created:
        raise RuntimeError("Release write permission was not verified.")
    print("Capability preflight succeeded; no temporary refs remain", flush=True)


def _restore(manifest, work, created):
    """Attempt original release recovery through the successfully tested REST path.

    Restore original GitHub Releases from verified backup, never by force-pushing
    historic refs. Stop and report cleanup errors rather than overwrite unknown refs.
    """
    from restore_semver_history import main as restore_originals

    print("RESTORING original Releases after migration error", flush=True)
    for tag in reversed(created):
        release_exists = subprocess.run(
            ["gh", "release", "view", tag, "--repo", REPO],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
        if release_exists:
            call("gh", "release", "delete", tag, "--repo", REPO, "--yes")
        tag_exists = subprocess.run(
            ["gh", "api", f"repos/{REPO}/git/ref/tags/{tag}"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
        if tag_exists:
            call("gh", "api", "-X", "DELETE", f"repos/{REPO}/git/refs/tags/{tag}")

    restore_originals(work)
    print("Original release recovery completed", flush=True)


def _create_snapshot_tags(items, source: Path, workspace: Path):
    """Create version-adjusted commit objects locally, before remote mutations."""
    call("git", "config", "user.name", "WinNAT-UI Migration")
    call("git", "config", "user.email", "actions@users.noreply.github.com")
    commits = {}
    for index, item in enumerate(items):
        old, new = item["old"], item["new"]
        directory = workspace / ("history-" + str(index))
        call("git", "worktree", "add", "--detach", directory, old)
        update_version(directory, old[1:], new[1:])
        dirty = bool(call("git", "status", "--porcelain", capture=True, cwd=directory))
        if dirty:
            call("git", "add", "app.py", "version_info.txt", cwd=directory) if not (
                directory / "version.py").exists() else call(
                    "git", "add", "version.py", "version_info.txt", cwd=directory)
            call("git", "commit", "-m", "release: republish historical " + old +
                 " as " + new + " (version-only)", cwd=directory)
        commits[new] = call("git", "rev-parse", "HEAD", cwd=directory, capture=True)
        call("git", "worktree", "remove", "--force", directory)
    return commits


def publish(work: Path, docs: Path):
    manifest = json.loads((work / "migration_manifest.json").read_text(encoding="utf-8"))
    items = manifest["original_releases"]
    if len(items) != 28:
        raise ValueError("Unexpected published release count")
    for item in items:
        if sha256(work / "originals" / item["old"] / NAME) != item["original_sha256"]:
            raise ValueError("Original backup corruption: " + item["old"])
        if sha256(_validate_staged(work / "staged", item["old"], item["new"])) != item["staged_sha256"]:
            raise ValueError("Staged package corruption: " + item["new"])
    plan = parse_plan((Path(__file__).resolve().parents[1] /
                       "SEMVER_MIGRATION_PLAN.md").read_text(encoding="utf-8"))
    if [(o, n) for o,n,_ in plan] != [(x["old"],x["new"]) for x in items]:
        raise ValueError("Mapping has changed since stage")
    refs = request(f"repos/{REPO}/git/refs/tags?per_page=100")
    actual = {r["ref"].split("/")[-1]: r["object"]["sha"] for r in refs}
    for item in items:
        if actual.get(item["old"]) != item["ref_sha"]:
            raise ValueError("Original source tag moved: " + item["old"])
    releases = request(f"repos/{REPO}/releases?per_page=100")
    if set(x["tag_name"] for x in releases) != {x["old"] for x in items}:
        raise ValueError("Published Releases changed while staging")
    # Never repeat the previous deletion-before-permission-check failure.
    _probe_publishing_permissions(items[0]["ref_sha"])
    # Build all replacement source commits before removing any historical ref.
    workspace = Path(tempfile.mkdtemp(prefix="winnat-source-snapshots-"))
    commits = _create_snapshot_tags(items, Path.cwd(), workspace)
    # Parse release sections from the updated canonical CHANGELOG.
    changelog = (docs / "CHANGELOG.md").read_text(encoding="utf-8")
    notes = {}
    for item in items:
        n = item["new"].removeprefix("v")
        m = re.search(r"(?ms)^## \[" + re.escape(n) +
                      r"\][^\n]*\n(.*?)(?=^## \[|\Z)", changelog)
        if not m:
            raise ValueError("No canonical notes for " + n)
        notes[item["new"]] = m.group(1).strip()
    for item in items:
        # Test alternate names before delete; historical collisions are expected.
        if item["new"] not in commits:
            raise ValueError("Replacement commit not prepared")

    created = []
    mutation_started = False
    try:
        print("Beginning guarded tag and GitHub Release migration", flush=True)
        mutation_started = True
        for item in reversed(items):
            call("gh", "release", "delete", item["old"], "--repo", REPO, "--yes")
        for item in items:
            call("git", "push", "origin", ":refs/tags/" + item["old"])
        for item in items:
            call("git", "tag", "-d", item["old"])
        for item in items:
            call("git", "tag", item["new"], commits[item["new"]])
            call("git", "push", "origin", "refs/tags/" + item["new"])
            created.append(item["new"])
        for i, item in enumerate(items):
            new = item["new"]
            note_file = work / (new + "-notes.md")
            note_file.write_text(
                "## WinNAT-UI " + new + " — " + item["kind"] + "\n\n" +
                notes[new] + "\n\n"
                "### Open Issues\nhttps://github.com/" + REPO +
                "/issues?q=is%3Aissue+is%3Aopen\n\n"
                "### Documentazione\nhttps://github.com/" + REPO +
                "/blob/main/RELEASE_NOTES.it.md\n\n"
                "---\n**UNSIGNED DEVELOPMENT BUILD**. Verify Windows executable "
                "and ZIP integrity; the Defender scan does not replace code signing.\n",
                encoding="utf-8")
            call("gh", "release", "create", new,
                 str(_validate_staged(work / "staged", item["old"], new)),
                 "--verify-tag", "--repo", REPO, "--title", "WinNAT UI " + new,
                 "--notes-file", note_file,
                 "--latest" if i == len(items) - 1 else "--latest=false")
        final = request(f"repos/{REPO}/releases?per_page=100")
        if set(x["tag_name"] for x in final) != {x["new"] for x in items}:
            raise ValueError("Post-migration GitHub Release audit failed")
        print("SUCCESS: " + str(len(items)) + " correctly republished releases", flush=True)
    except Exception as error:
        print("MIGRATION FAILURE: " + str(error), flush=True)
        if mutation_started:
            _restore(manifest, work, created)
        raise


def main():
    p = argparse.ArgumentParser()
    p.add_argument("action", choices=("backup", "publish"))
    p.add_argument("--work", type=Path, required=True)
    p.add_argument("--plan", type=Path)
    p.add_argument("--run-id", type=int)
    p.add_argument("--docs", type=Path)
    opts = p.parse_args()
    if opts.action == "backup":
        backup(opts.plan, opts.work, opts.run_id)
    else:
        publish(opts.work, opts.docs)


if __name__ == "__main__":
    main()
