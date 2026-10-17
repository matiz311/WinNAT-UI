"""Read-only GitHub build catalogue and verified staging of CI artifacts.

An Actions artifact is not a release: it requires GitHub authentication to
download, has a retention deadline and is executable code from the selected
commit. No credentials are bundled, logged or persisted by this module.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile

from . import updater

API = "https://api.github.com/repos/" + updater.REPOSITORY
MAX_JSON_BYTES = 3 * 1024 * 1024
MAX_BUILD_ROWS = 12
_SHA256 = re.compile(r"^sha256:([0-9a-fA-F]{64})$")
_SHA = re.compile(r"^[0-9a-f]{40}$")
_ARTIFACT = re.compile(r"^WinNAT-UI-Windows-(\d+)-([0-9a-f]{40})$")
_BUILD_ID = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:\.[0-9]+)?\+ci\.[0-9]+\.[0-9a-f]{8}$")


def _api_json(path, token=None):
    """Fixed GitHub API origin; bounded response and no untrusted arbitrary URLs."""
    if not path.startswith("/") or path.startswith("//"):
        raise ValueError("Percorso API non valido.")
    headers = {"User-Agent": "WinNAT-UI-Catalog", "Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(API + path, headers=headers)
    with urllib.request.urlopen(request, timeout=20) as response:
        raw = response.read(MAX_JSON_BYTES + 1)
    if len(raw) > MAX_JSON_BYTES:
        raise ValueError("Risposta GitHub troppo grande.")
    return json.loads(raw)


def release_catalog():
    """Validated official releases, including older versions and pagination.

    Experimental GitHub prereleases share this endpoint; paginate past them
    so repeated CI previews never hide historical stable rollback versions.
    """
    rows = []
    for page in range(1, 6):
        response = _api_json(f"/releases?per_page=100&page={page}")
        if not isinstance(response, list):
            raise ValueError("Catalogo release non valido.")
        for item in response:
            if not isinstance(item, dict) or item.get("draft") or item.get("prerelease"):
                continue
            tag = item.get("tag_name")
            try:
                updater.version_tuple(tag)
            except (ValueError, TypeError):
                continue
            assets = item.get("assets")
            if not isinstance(assets, list):
                continue
            matches = [a for a in assets if isinstance(a, dict) and a.get("name") == updater.ASSET_NAME]
            if len(matches) != 1:
                continue
            a = matches[0]
            expected = (f"https://github.com/{updater.REPOSITORY}/releases/download/"
                        f"{tag}/{updater.ASSET_NAME}")
            digest = a.get("digest")
            size = a.get("size")
            if (a.get("browser_download_url") != expected or
                    not isinstance(digest, str) or not _SHA256.fullmatch(digest) or
                    type(size) is not int or not 0 < size <= updater.MAX_ZIP_BYTES):
                continue
            rows.append({"kind": "release", "id": tag, "label": tag + " · Ufficiale",
                         "version": tag.lstrip("v"), "tag": tag, "url": expected,
                         "sha256": digest.split(":", 1)[1].lower(), "size": size,
                         "available": True, "page": item.get("html_url", ""),
                         "date": item.get("published_at") or "",
                         "commit": item.get("target_commitish") or ""})
            if len(rows) >= 50:
                return rows
        if len(response) < 100:
            break
    return rows


def actions_build_catalog(limit=MAX_BUILD_ROWS):
    """Legacy authenticated Actions artifact list (not used by the desktop UI)."""
    data = _api_json("/actions/runs?status=success&per_page=75")
    if not isinstance(data, dict) or not isinstance(data.get("workflow_runs"), list):
        raise ValueError("Elenco workflow GitHub non valido.")
    results = []
    for run in data["workflow_runs"]:
        if len(results) >= limit:
            break
        if (not isinstance(run, dict) or run.get("path") != ".github/workflows/build.yml" or
                run.get("status") != "completed" or run.get("conclusion") != "success" or
                run.get("event") not in ("push", "pull_request", "workflow_dispatch")):
            continue
        sha, run_id, number = run.get("head_sha"), run.get("id"), run.get("run_number")
        repo = run.get("head_repository")
        if (not isinstance(sha, str) or not _SHA.fullmatch(sha) or
                type(run_id) is not int or type(number) is not int or
                not isinstance(repo, dict) or repo.get("full_name") != updater.REPOSITORY):
            continue
        try:
            artifacts = _api_json(f"/actions/runs/{run_id}/artifacts?per_page=30")
        except (OSError, ValueError, urllib.error.URLError):
            continue
        if not isinstance(artifacts, dict) or not isinstance(artifacts.get("artifacts"), list):
            continue
        # On pull_request builds, GITHUB_SHA in the archive name is the
        # synthetic PR merge commit, not run.head_sha (source branch HEAD).
        # The artifact is still bound to this run by its GitHub run endpoint
        # and by the workflow_run metadata; validate both.
        found = []
        for candidate in artifacts["artifacts"]:
            if not isinstance(candidate, dict) or candidate.get("expired"):
                continue
            match = _ARTIFACT.fullmatch(str(candidate.get("name", "")))
            association = candidate.get("workflow_run")
            if (not match or int(match.group(1)) != number or
                    not isinstance(association, dict) or
                    association.get("id") != run_id or
                    association.get("head_sha") != sha):
                continue
            build_sha = match.group(2)
            if run["event"] != "pull_request" and build_sha != sha:
                continue
            found.append((candidate, build_sha))
        if len(found) != 1:
            continue
        art, build_sha = found[0]
        digest = art.get("digest")
        artifact_id = art.get("id")
        size = art.get("size_in_bytes")
        if (type(artifact_id) is not int or type(size) is not int or
                not 0 < size <= updater.MAX_ZIP_BYTES or
                not isinstance(digest, str) or not _SHA256.fullmatch(digest) or
                art.get("archive_download_url") != f"{API}/actions/artifacts/{artifact_id}/zip"):
            continue
        results.append({"kind": "build", "id": str(artifact_id),
                        "label": f"Build #{number} · {build_sha[:8]} · Test",
                        "run_id": run_id, "run_number": number,
                        "commit": build_sha, "source_commit": sha,
                        "branch": run.get("head_branch") or "",
                        "event": run.get("event"), "date": run.get("created_at") or "",
                        "expires": art.get("expires_at") or "",
                        "page": run.get("html_url") or "",
                        "url": f"{API}/actions/artifacts/{artifact_id}/zip",
                        "sha256": digest.split(":", 1)[1].lower(), "size": size})
    return results


_PREVIEW_INDEX = ("https://raw.githubusercontent.com/" + updater.REPOSITORY
                  + "/ci-builds/index.json")
_PREVIEW_TAG = re.compile(r"^ci-run-([1-9][0-9]*)$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _index_json():
    """Fetch public index from one fixed official repository branch, no credentials."""
    req = urllib.request.Request(_PREVIEW_INDEX, headers={"User-Agent": "WinNAT-UI-Catalog"})
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            raw = response.read(MAX_JSON_BYTES + 1)
    except urllib.error.HTTPError as error:
        # The orphan catalog branch does not exist until the first successful
        # post-integration CI publication. A missing preview index is not fatal.
        if error.code == 404:
            return {"schema_version": 1, "repository": updater.REPOSITORY, "builds": []}
        raise
    if len(raw) > MAX_JSON_BYTES:
        raise ValueError("Catalogo preview GitHub troppo grande.")
    return json.loads(raw)


def build_catalog(limit=MAX_BUILD_ROWS):
    """Read token-free CI previews, cross-checking each entry with GitHub Releases.

    A branch record by itself is never accepted as trusted download metadata:
    official GitHub release assets must match exact URL, digest and size.
    """
    index = _index_json()
    if (not isinstance(index, dict) or index.get("schema_version") != 1 or
            index.get("repository") != updater.REPOSITORY or
            not isinstance(index.get("builds"), list) or
            len(index["builds"]) > 50):
        raise ValueError("Indice delle build CI non valido.")
    if not index["builds"]:
        return []
    releases = _api_json("/releases?per_page=100")
    if not isinstance(releases, list):
        raise ValueError("Metadati GitHub Releases non validi.")
    by_tag = {r.get("tag_name"): r for r in releases if isinstance(r, dict)
              and isinstance(r.get("tag_name"), str)}
    rows = []
    seen = set()
    for entry in index["builds"]:
        if not isinstance(entry, dict):
            continue
        tag = entry.get("tag")
        match = _PREVIEW_TAG.fullmatch(str(tag))
        run_id, run_number, size = entry.get("run_id"), entry.get("run_number"), entry.get("size")
        commit, source = entry.get("commit"), entry.get("source_commit")
        digest, version, event = entry.get("sha256"), entry.get("version"), entry.get("event")
        if (not match or int(match.group(1)) != run_id or tag in seen or
                type(run_id) is not int or type(run_number) is not int or run_number < 1 or
                type(size) is not int or not 0 < size <= updater.MAX_ZIP_BYTES or
                not _SHA.fullmatch(str(commit)) or not _SHA.fullmatch(str(source)) or
                not _HEX64.fullmatch(str(digest)) or
                event not in ("push", "pull_request", "workflow_dispatch")):
            continue
        try:
            updater.version_tuple(version)
        except (ValueError, TypeError):
            continue
        if event != "pull_request" and source != commit:
            continue
        expected = (f"https://github.com/{updater.REPOSITORY}/releases/download/"
                    f"{tag}/{updater.ASSET_NAME}")
        release = by_tag.get(tag, {})
        if not release or release.get("draft") or not release.get("prerelease"):
            continue
        if release.get("target_commitish") != source:
            continue
        assets = release.get("assets")
        if not isinstance(assets, list):
            continue
        matched = [a for a in assets if isinstance(a, dict) and
                   a.get("name") == updater.ASSET_NAME]
        if len(matched) != 1:
            continue
        asset = matched[0]
        if (asset.get("browser_download_url") != expected or
                asset.get("digest", "").lower() != "sha256:" + digest or
                asset.get("size") != size):
            continue
        seen.add(tag)
        branch = entry.get("branch")
        rows.append({"kind": "build", "delivery": "preview", "id": tag,
                     "label": f"Build #{run_number} · {commit[:8]} · Test",
                     "run_id": run_id, "run_number": run_number,
                     "commit": commit, "source_commit": source,
                     "branch": branch if isinstance(branch, str) else "",
                     "event": event, "date": entry.get("date") or "",
                     "version": version, "expires": "Archiviata come pre-release",
                     "page": f"https://github.com/{updater.REPOSITORY}/releases/tag/{tag}",
                     "url": expected, "sha256": digest, "size": size})
        if len(rows) >= limit:
            break
    return rows


def download_build(info, output, token=None):
    """Atomically download a public CI preview; never require Actions credentials."""
    if info.get("delivery") != "preview":
        return _download_build(info, output, token)
    tag = info.get("id")
    if not _PREVIEW_TAG.fullmatch(str(tag)):
        raise ValueError("Tag della build CI non valido.")
    expected = (f"https://github.com/{updater.REPOSITORY}/releases/download/"
                f"{tag}/{updater.ASSET_NAME}")
    if (info.get("url") != expected or
            not _HEX64.fullmatch(str(info.get("sha256", ""))) or
            type(info.get("size")) is not int or
            not 0 < info["size"] <= updater.MAX_ZIP_BYTES):
        raise ValueError("Metadati di download della build non validi.")
    partial = Path(str(output) + ".partial")
    try:
        received = updater._download(expected, partial, info["sha256"])
        if received != info["size"]:
            raise ValueError("Dimensione della build CI non corrispondente al catalogo.")
        os.replace(partial, output)
        return received
    finally:
        try:
            partial.unlink()
        except FileNotFoundError:
            pass


def gh_cli_token():
    """Optional existing GitHub CLI login; never stores or logs the token."""
    try:
        options = {"capture_output": True, "text": True, "timeout": 5, "check": True}
        if sys.platform == "win32":
            options["creationflags"] = subprocess.CREATE_NO_WINDOW
        response = subprocess.run(["gh", "auth", "token"], **options)
        return response.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def _trusted_artifact_location(location):
    parsed = urllib.parse.urlsplit(location)
    host = (parsed.hostname or "").lower()
    return (parsed.scheme == "https" and not parsed.username and not parsed.password
            and parsed.port in (None, 443) and
            (host == "objects.githubusercontent.com" or
             host.endswith(".blob.core.windows.net") or
             host.endswith(".actions.githubusercontent.com")))


def _download_build(info, output, token):
    if not token or not isinstance(token, str) or "\n" in token or "\r" in token:
        raise ValueError("Per scaricare una build di test serve l'accesso GitHub (Actions: read).")
    artifact_id = info.get("id")
    expected = f"{API}/actions/artifacts/{artifact_id}/zip"
    if not str(artifact_id).isdigit() or info.get("url") != expected:
        raise ValueError("Artifact GitHub non autorizzato.")
    req = urllib.request.Request(expected, headers={
        "User-Agent": "WinNAT-UI-Catalog", "Accept": "application/vnd.github+json",
        "Authorization": "Bearer " + token})
    opener = urllib.request.build_opener(_NoRedirect)
    try:
        with opener.open(req, timeout=30):
            raise ValueError("GitHub non ha restituito il collegamento di download.")
    except urllib.error.HTTPError as error:
        if error.code in (401, 403):
            raise ValueError("Accesso GitHub non autorizzato: occorre un token con permesso Actions: read.") from error
        if error.code == 410:
            raise ValueError("Artifact scaduto o non più disponibile.") from error
        if error.code != 302:
            raise ValueError(f"Impossibile scaricare la build: GitHub HTTP {error.code}.") from error
        location = error.headers.get("Location", "")
    if not _trusted_artifact_location(location):
        raise ValueError("Redirect dell'artifact non attendibile.")
    # Never forward an access token to GitHub's temporary artifact-storage URL.
    req_storage = urllib.request.Request(location, headers={"User-Agent": "WinNAT-UI-Catalog"})
    hash_value = hashlib.sha256()
    total = 0
    partial = Path(str(output) + ".partial")
    try:
        with urllib.request.urlopen(req_storage, timeout=60) as source, open(partial, "wb") as target:
            while True:
                chunk = source.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > updater.MAX_ZIP_BYTES:
                    raise ValueError("Artifact eccessivamente grande.")
                hash_value.update(chunk)
                target.write(chunk)
        if total != info["size"] or hash_value.hexdigest() != info["sha256"]:
            raise ValueError("Integrità della build non verificata: dimensione o SHA256 differente.")
        os.replace(partial, output)
        return total
    finally:
        try:
            partial.unlink()
        except FileNotFoundError:
            pass


def prepare_build(info, token=None):
    """Stage a successful Windows artifact without touching the installation."""
    if info.get("kind") != "build" or not _SHA.fullmatch(str(info.get("commit", ""))):
        raise ValueError("Build non valida.")
    stage = Path(tempfile.mkdtemp(prefix="WinNAT-TestBuild-"))
    try:
        file = stage / "artifact.zip"
        download_build(info, file, token)
        target = stage / "new"
        target.mkdir()
        with zipfile.ZipFile(file) as archive:
            for entry, relative in updater._safe_members(archive):
                dest = target.joinpath(*relative.parts)
                if entry.is_dir():
                    dest.mkdir(parents=True, exist_ok=True)
                else:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(entry) as source, open(dest, "wb") as output:
                        shutil.copyfileobj(source, output)
        exe = target / "WinNAT-UI.exe"
        build_file = target / "BUILD_INFO.txt"
        manifest = target / "SHA256.txt"
        scan = target / "DEFENDER_SCAN.txt"
        if not all(f.is_file() for f in (exe, build_file, manifest, scan)):
            raise ValueError("Build incompleta: EXE o manifest di verifica assenti.")
        build_text = build_file.read_text(encoding="utf-8-sig")
        meta = dict(line.split(": ", 1) for line in build_text.splitlines() if ": " in line)
        build_id = meta.get("Build identifier", "")
        if (not _BUILD_ID.fullmatch(build_id) or
                meta.get("Git commit") != info["commit"] or
                meta.get("Workflow") != str(info["run_id"]) or
                not build_id.endswith(f".{info['run_number']}.{info['commit'][:8]}")):
            raise ValueError("Metadati della build incoerenti con GitHub Actions.")
        version = meta.get("Functional version", "")
        if updater.version_tuple(version) != updater.version_tuple(build_id.split("+", 1)[0]):
            raise ValueError("Versione della build non coerente.")
        sha256 = hashlib.sha256(exe.read_bytes()).hexdigest()
        if sha256.lower() not in manifest.read_text(encoding="utf-8-sig").lower():
            raise ValueError("SHA256 dell'eseguibile non corrispondente al manifest.")
        if not scan.read_text(encoding="utf-8-sig").strip():
            raise ValueError("Rapporto Defender della build vuoto.")
        return stage, build_id
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def installed_build_info(executable=None):
    """Metadata for packaged installs; source checkouts have no CI marker."""
    path = Path(executable or sys.executable)
    build = path.parent / "BUILD_INFO.txt"
    try:
        if build.stat().st_size > 4096:
            return {}
        text = build.read_text(encoding="utf-8-sig")
        return dict(line.split(": ", 1) for line in text.splitlines() if ": " in line)
    except OSError:
        return {}
