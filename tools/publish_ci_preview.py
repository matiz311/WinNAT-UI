"""Publish verified successful CI artifacts as PUBLIC experimental GitHub previews.

This script runs exclusively from the trusted default-branch workflow_run context.
It never executes downloaded code. The official stable release gate is untouched.
"""
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile

REPO = "matiz311/WinNAT-UI"
API = "https://api.github.com/repos/" + REPO
INDEX_BRANCH = "ci-builds"
PREVIEW_ASSET = "WinNAT-UI-Windows.zip"
LIMIT = 12
MAX_DOWNLOAD = 150 * 1024 * 1024
_SHA = re.compile(r"^[0-9a-f]{40}$")
_DIGEST = re.compile(r"^sha256:([0-9a-fA-F]{64})$")
_ARTIFACT = re.compile(r"^WinNAT-UI-Windows-(\d+)-([0-9a-f]{40})$")
_VERSION = re.compile(r"^\d+\.\d+\.\d+(?:\.\d+)?$")
_BUILD = re.compile(r"^(\d+\.\d+\.\d+(?:\.\d+)?)\+ci\.(\d+)\.([0-9a-f]{8})$")


def _request(path, method="GET", body=None):
    if not path.startswith("/") or path.startswith("//") or ".." in path:
        raise ValueError("Unsafe GitHub API path")
    token = os.environ.get("GH_TOKEN", "")
    if not token:
        raise ValueError("GH_TOKEN is required")
    headers = {"Authorization": "Bearer " + token,
               "Accept": "application/vnd.github+json",
               "User-Agent": "WinNAT-UI-CIPreviewPublisher"}
    data = None if body is None else json.dumps(body).encode("utf-8")
    if data is not None:
        headers["Content-Type"] = "application/json"
    return urllib.request.Request(API + path, data=data, headers=headers, method=method)


def _api(path, method="GET", body=None, allow_404=False):
    try:
        with urllib.request.urlopen(_request(path, method, body), timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as exc:
        if allow_404 and exc.code == 404:
            return None
        raise


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _download_artifact(asset, target):
    aid = asset["id"]
    if type(aid) is not int or asset.get("archive_download_url") != API + f"/actions/artifacts/{aid}/zip":
        raise ValueError("Unexpected Actions artifact URL")
    digest = asset.get("digest")
    if not isinstance(digest, str) or not _DIGEST.fullmatch(digest):
        raise ValueError("Missing Actions SHA256")
    req = _request(f"/actions/artifacts/{aid}/zip")
    try:
        with urllib.request.build_opener(_NoRedirect).open(req, timeout=30):
            raise ValueError("Expected an artifact redirect")
    except urllib.error.HTTPError as exc:
        if exc.code != 302:
            raise
        location = exc.headers.get("Location", "")
    loc = urllib.parse.urlsplit(location)
    host = (loc.hostname or "").lower()
    if (loc.scheme != "https" or loc.username or loc.password or loc.port not in (None, 443) or
            not (host == "objects.githubusercontent.com" or
                 host.endswith(".blob.core.windows.net") or
                 host.endswith(".actions.githubusercontent.com"))):
        raise ValueError("Unsafe artifact storage redirect")
    # Never send GH_TOKEN to temporary storage or to release asset CDN.
    size = 0
    checksum = hashlib.sha256()
    with urllib.request.urlopen(urllib.request.Request(location, headers={
            "User-Agent": "WinNAT-UI-CIPreviewPublisher"}), timeout=60) as r, open(target, "wb") as output:
        while True:
            block = r.read(1024 * 1024)
            if not block:
                break
            size += len(block)
            if size > MAX_DOWNLOAD:
                raise ValueError("Artifact ZIP exceeds size limit")
            checksum.update(block)
            output.write(block)
    if size != asset["size_in_bytes"] or checksum.hexdigest().lower() != digest[7:].lower():
        raise ValueError("Artifact ZIP digest / size mismatch")
    return size, checksum.hexdigest().lower()


def _validate_zip(path, run, build_sha):
    """Check explicit manifests, safe ZIP members and EXE; never execute a payload."""
    names = {"WinNAT-UI.exe", "BUILD_INFO.txt", "SHA256.txt", "DEFENDER_SCAN.txt"}
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        if len(members) > 3000 or sum(m.file_size for m in members) > 500 * 1024 * 1024:
            raise ValueError("Archive is too large")
        seen = set()
        for m in members:
            normalized = m.filename.replace("\\", "/")
            if (normalized.startswith("/") or "\x00" in normalized or
                    any(p in ("", ".", "..") for p in normalized.strip("/").split("/")) or
                    ":" in normalized or normalized in seen or
                    (m.external_attr >> 16) & 0o170000 == 0o120000):
                raise ValueError("Unsafe ZIP member")
            seen.add(normalized)
        if not names.issubset(seen):
            raise ValueError("Required build manifests missing")
        if any(archive.getinfo(name).file_size > MAX_DOWNLOAD for name in names):
            raise ValueError("Build manifest too large")
        metadata = archive.read("BUILD_INFO.txt").decode("utf-8-sig")
        details = dict(line.split(": ", 1) for line in metadata.splitlines() if ": " in line)
        match = _BUILD.fullmatch(details.get("Build identifier", ""))
        if (not match or match.group(2) != str(run["run_number"]) or
                match.group(3) != build_sha[:8] or
                details.get("Functional version") != match.group(1) or
                details.get("Git commit") != build_sha or
                details.get("Workflow") != str(run["id"])):
            raise ValueError("BUILD_INFO does not match successful workflow")
        hash_text = archive.read("SHA256.txt").decode("utf-8-sig")
        exe_hash = hashlib.sha256(archive.read("WinNAT-UI.exe")).hexdigest()
        if not re.search(r"\b" + exe_hash + r"\b", hash_text, flags=re.I):
            raise ValueError("Executable SHA256 mismatch")
        if not archive.read("DEFENDER_SCAN.txt").decode("utf-8-sig").strip():
            raise ValueError("Defender manifest empty")
        return match.group(1)


def _get_run_artifact(run):
    if (run.get("conclusion") != "success" or run.get("status") != "completed" or
            run.get("path") != ".github/workflows/build.yml" or
            run.get("name") != "Build Windows executable" or
            run.get("event") not in ("push", "pull_request", "workflow_dispatch") or
            run.get("head_repository", {}).get("full_name") != REPO or
            run.get("repository", {}).get("full_name") != REPO or
            not _SHA.fullmatch(str(run.get("head_sha", ""))) or
            type(run.get("id")) is not int or type(run.get("run_number")) is not int):
        return None
    # Ignore forks, failed/partial builds and other workflows.
    payload = _api(f"/actions/runs/{run['id']}/artifacts?per_page=100")
    matches = []
    for asset in payload.get("artifacts", []):
        if not isinstance(asset, dict) or asset.get("expired"):
            continue
        name_match = _ARTIFACT.fullmatch(str(asset.get("name", "")))
        association = asset.get("workflow_run") or {}
        if (name_match and int(name_match.group(1)) == run["run_number"] and
                association.get("id") == run["id"] and
                association.get("head_sha") == run["head_sha"] and
                type(asset.get("size_in_bytes")) is int and
                0 < asset["size_in_bytes"] <= MAX_DOWNLOAD):
            build_sha = name_match.group(2)
            if run["event"] != "pull_request" and build_sha != run["head_sha"]:
                continue
            matches.append((asset, build_sha))
    if len(matches) != 1:
        raise ValueError("Exactly one valid Windows artifact expected")
    return matches[0]


def _record(run, tag, build_sha, checksum, size, version):
    return {
        "tag": tag,
        "run_id": run["id"],
        "run_number": run["run_number"],
        "commit": build_sha,
        "source_commit": run["head_sha"],
        "branch": run.get("head_branch") or "",
        "event": run["event"],
        "date": run.get("created_at") or "",
        "version": version,
        "sha256": checksum,
        "size": size,
        "url": f"https://github.com/{REPO}/releases/download/{tag}/{PREVIEW_ASSET}",
        "page": f"https://github.com/{REPO}/releases/tag/{tag}"
    }


def _publish_preview(run, zip_path, tag, checksum, size):
    release = _api(f"/releases/tags/{tag}", allow_404=True)
    if release is None:
        notes = (
            f"Build CI sperimentale #{run['run_number']}, workflow "
            f"https://github.com/{REPO}/actions/runs/{run['id']}.\n\n"
            "NON È UNA RELEASE UFFICIALE. Compilazione con controlli CI e Defender: "
            "non sostituiscono firma del codice né validazione su host reale. "
            "Verificare SHA-256 prima dell'esecuzione. "
            "Il rollback dell'app non ripristina le impostazioni di rete.\n"
        )
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".md", delete=False) as file:
            file.write(notes)
            notes_path = file.name
        try:
            subprocess.run(["gh", "release", "create", tag, str(zip_path),
                            "--repo", REPO, "--target", run["head_sha"],
                            "--title", f"WinNAT UI CI #{run['run_number']} (NON UFFICIALE)",
                            "--notes-file", notes_path, "--prerelease"],
                           check=True)
        finally:
            os.unlink(notes_path)
        release = _api(f"/releases/tags/{tag}")
    if release.get("draft") or not release.get("prerelease") or release.get("tag_name") != tag:
        raise ValueError("Preview release tag has unexpected status")
    matches = [a for a in release.get("assets", []) if a.get("name") == PREVIEW_ASSET]
    if (len(matches) != 1 or matches[0].get("digest", "").lower() != f"sha256:{checksum}" or
            matches[0].get("size") != size or
            matches[0].get("browser_download_url") !=
            f"https://github.com/{REPO}/releases/download/{tag}/{PREVIEW_ASSET}"):
        raise ValueError("Published preview release asset mismatch")


def _update_index(new_record):
    ref = _api(f"/git/ref/heads/{INDEX_BRANCH}", allow_404=True)
    previous = []
    if ref:
        try:
            info = _api(f"/contents/index.json?ref={INDEX_BRANCH}")
            data = json.loads(__import__("base64").b64decode(info["content"]).decode("utf-8"))
            if data.get("schema_version") != 1 or data.get("repository") != REPO:
                raise ValueError("Unexpected preview index schema")
            previous = data.get("builds", [])
            if not isinstance(previous, list):
                raise ValueError("Invalid preview index")
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise
    items = [new_record] + [item for item in previous if item.get("run_id") != new_record["run_id"]]
    items.sort(key=lambda v: v["run_id"], reverse=True)
    payload = {"schema_version": 1, "repository": REPO, "builds": items[:LIMIT]}
    blob = _api("/git/blobs", "POST", {
        "content": json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        "encoding": "utf-8"})
    tree = _api("/git/trees", "POST", {
        "tree": [{"path": "index.json", "mode": "100644", "type": "blob", "sha": blob["sha"]}]})
    old = ref["object"]["sha"] if ref else None
    commit = _api("/git/commits", "POST", {
        "message": f"catalog: CI preview #{new_record['run_number']}",
        "tree": tree["sha"], "parents": [old] if old else []})
    if old:
        _api(f"/git/refs/heads/{INDEX_BRANCH}", "PATCH", {
            "sha": commit["sha"], "force": False})
    else:
        _api("/git/refs", "POST", {
            "ref": f"refs/heads/{INDEX_BRANCH}", "sha": commit["sha"]})
    return commit["sha"]


def main():
    if len(sys.argv) != 2 or not sys.argv[1].isdigit():
        raise SystemExit("Usage: publish_ci_preview.py <completed_run_id>")
    run_id = int(sys.argv[1])
    run = _api(f"/actions/runs/{run_id}")
    found = _get_run_artifact(run)
    if not found:
        print("Ignored untrusted / unsuccessful workflow")
        return
    asset, build_sha = found
    with tempfile.TemporaryDirectory(prefix="WinNAT-CI-preview-") as folder:
        output = Path(folder) / PREVIEW_ASSET
        size, checksum = _download_artifact(asset, output)
        version = _validate_zip(output, run, build_sha)
        tag = f"ci-run-{run_id}"
        _publish_preview(run, output, tag, checksum, size)
        index_sha = _update_index(_record(run, tag, build_sha, checksum, size, version))
    print(f"Published experimental preview {tag}, branch {INDEX_BRANCH}@{index_sha}")


if __name__ == "__main__":
    main()
