"""Verified updates from the official WinNAT-UI GitHub Releases.

Only published releases are candidates. Download and verify an entire ZIP before
extraction; never execute files downloaded before user confirmation.
"""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

REPOSITORY = "matiz311/WinNAT-UI"
API_URL = "https://api.github.com/repos/" + REPOSITORY + "/releases/latest"
ASSET_NAME = "WinNAT-UI-Windows.zip"
MAX_ZIP_BYTES = 150 * 1024 * 1024
MAX_EXPANDED_BYTES = 500 * 1024 * 1024
MAX_ENTRIES = 3000
VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


def version_tuple(value):
    matched = VERSION_RE.fullmatch(str(value))
    if not matched:
        raise ValueError("Versione GitHub non valida: " + str(value))
    return tuple(int(n) for n in matched.groups())


def newer(release_tag, installed):
    return version_tuple(release_tag) > version_tuple(installed)


def _request(url, *, timeout=20):
    if not url.startswith("https://api.github.com/") and not url.startswith(
            "https://github.com/" + REPOSITORY + "/releases/download/"):
        raise ValueError("URL aggiornamento non autorizzato.")
    return urllib.request.Request(url, headers={
        "User-Agent": "WinNAT-UI-Updater",
        "Accept": "application/vnd.github+json" if "api.github.com" in url
                  else "application/octet-stream"
    })


def release_info(installed):
    with urllib.request.urlopen(_request(API_URL), timeout=20) as response:
        data = json.load(response)
    tag = data.get("tag_name", "")
    version_tuple(tag)
    if data.get("draft") or data.get("prerelease"):
        raise ValueError("L'ultima release non è una versione stabile pubblicata.")
    assets = [a for a in data.get("assets", []) if a.get("name") == ASSET_NAME]
    if len(assets) != 1:
        raise ValueError("Release senza archivio Windows ufficiale univoco.")
    asset = assets[0]
    url = asset.get("browser_download_url", "")
    expected = ("https://github.com/" + REPOSITORY + "/releases/download/"
                + tag + "/" + ASSET_NAME)
    if url != expected:
        raise ValueError("URL dell'asset non corrispondente alla release ufficiale.")
    digest = asset.get("digest", "")
    if not re.fullmatch(r"sha256:[a-fA-F0-9]{64}", digest):
        raise ValueError("GitHub non fornisce un digest SHA256 verificabile per l'archivio.")
    return {"version": tag.lstrip("v"), "tag": tag, "url": url,
            "sha256": digest.split(":", 1)[1].lower(),
            "size": int(asset.get("size") or 0),
            "available": newer(tag, installed),
            "page": data.get("html_url", "")}


def _download(url, target, expected_digest):
    digest = hashlib.sha256()
    size = 0
    with urllib.request.urlopen(_request(url), timeout=60) as response, open(target, "wb") as dest:
        # urllib redirects only to GitHub's release asset storage after initial
        # official URL. SHA256 supplied by the GitHub API authenticates the bytes.
        while True:
            block = response.read(1024 * 1024)
            if not block:
                break
            size += len(block)
            if size > MAX_ZIP_BYTES:
                raise ValueError("Archivio eccessivamente grande.")
            digest.update(block)
            dest.write(block)
    if digest.hexdigest() != expected_digest:
        raise ValueError("SHA256 dell'archivio differente da quello pubblicato su GitHub.")
    return size


def _safe_members(archive):
    members = archive.infolist()
    if len(members) > MAX_ENTRIES:
        raise ValueError("Troppi file nell'archivio.")
    expanded = 0
    files = []
    for member in members:
        name = member.filename.replace("\\", "/")
        path = PurePosixPath(name)
        if (not name or name.startswith(("/", "\\")) or ":" in name
                or not path.parts or any(p in ("", ".", "..") for p in path.parts)):
            raise ValueError("Percorso ZIP non sicuro: " + name)
        # Windows links and reparse points cannot be allowed in the release.
        mode = (member.external_attr >> 16) & 0xFFFF
        if (mode & 0o170000) == 0o120000:
            raise ValueError("Link simbolico non consentito: " + name)
        expanded += member.file_size
        if expanded > MAX_EXPANDED_BYTES:
            raise ValueError("Archivio espanso troppo grande.")
        files.append((member, path))
    return files


def prepare(info):
    """Stage a verified release outside installation path; no running files touched."""
    if not info.get("available"):
        raise ValueError("Non esiste una versione successiva.")
    temp = Path(tempfile.mkdtemp(prefix="WinNAT-Update-"))
    try:
        archive_path = temp / "package.zip"
        size = _download(info["url"], archive_path, info["sha256"])
        if info.get("size") and size != info["size"]:
            raise ValueError("Dimensione ZIP diversa dai metadati GitHub.")
        staged = temp / "new"
        staged.mkdir()
        with zipfile.ZipFile(archive_path) as archive:
            items = _safe_members(archive)
            for entry, path in items:
                target = staged.joinpath(*path.parts)
                if entry.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(entry) as source, open(target, "wb") as dest:
                        shutil.copyfileobj(source, dest)
        exe = staged / "WinNAT-UI.exe"
        if not exe.is_file():
            raise ValueError("La release non contiene WinNAT-UI.exe nella cartella prevista.")
        return temp
    except Exception:
        shutil.rmtree(temp, ignore_errors=True)
        raise


# This script runs separately while the main EXE exits. Rollback is a directory
# restoration (no network settings are changed by the updater).
HELPER_PS = r'''
param(
    [Parameter(Mandatory=$true)][int]$ParentPid,
    [Parameter(Mandatory=$true)][string]$InstallDir,
    [Parameter(Mandatory=$true)][string]$StageRoot
)
$ErrorActionPreference = 'Stop'
$backup = Join-Path $StageRoot 'previous'
$source = Join-Path $StageRoot 'new'
$log = Join-Path $StageRoot 'update-log.txt'
$installed = Join-Path $InstallDir 'WinNAT-UI.exe'
try {
    try { Wait-Process -Id $ParentPid -Timeout 45 -ErrorAction Stop }
    catch { if (Get-Process -Id $ParentPid -ErrorAction SilentlyContinue) { throw 'Applicazione ancora aperta.' } }
    if (-not (Test-Path -LiteralPath (Join-Path $source 'WinNAT-UI.exe'))) {
        throw 'Eseguibile nuovo assente.'
    }
    New-Item -ItemType Directory -Path $backup -Force | Out-Null
    # Copy old program before any destructive operation.
    Copy-Item -LiteralPath (Join-Path $InstallDir '*') -Destination $backup -Recurse -Force -ErrorAction Stop
    try {
        Copy-Item -Path (Join-Path $source '*') -Destination $InstallDir -Recurse -Force -ErrorAction Stop
    } catch {
        Copy-Item -Path (Join-Path $backup '*') -Destination $InstallDir -Recurse -Force -ErrorAction Stop
        throw ('Installazione fallita; tentato ripristino: ' + $_.Exception.Message)
    }
    if (-not (Test-Path -LiteralPath $installed)) { throw 'Installazione priva di EXE.' }
    Start-Process -FilePath $installed -WorkingDirectory $InstallDir
    ('Aggiornamento completato: ' + (Get-Date -Format o)) | Out-File $log -Encoding utf8
} catch {
    ('Aggiornamento fallito: ' + $_.Exception.ToString()) | Out-File $log -Encoding utf8
    if (Test-Path -LiteralPath $backup) {
        try { Copy-Item -Path (Join-Path $backup '*') -Destination $InstallDir -Recurse -Force -ErrorAction Stop }
        catch { ('Anche il ripristino e fallito: ' + $_.Exception.ToString()) | Add-Content $log }
    }
    exit 1
}
'''


def launch(staging, install_dir=None, parent_pid=None):
    """Schedule update after process exit; only for a packaged Windows EXE."""
    if sys.platform != "win32" or not getattr(sys, "frozen", False):
        raise RuntimeError("Aggiornamento automatico disponibile solo nell'EXE Windows installato.")
    install_dir = Path(install_dir or sys.executable).resolve()
    if install_dir.is_file():
        install_dir = install_dir.parent
    staging = Path(staging).resolve()
    if not (staging / "new" / "WinNAT-UI.exe").is_file():
        raise ValueError("Pacchetto staged non valido.")
    script = staging / "apply-update.ps1"
    script.write_text(HELPER_PS, encoding="utf-8")
    subprocess.Popen(["powershell.exe", "-NoProfile", "-NonInteractive",
                      "-ExecutionPolicy", "Bypass", "-File", str(script),
                      "-ParentPid", str(parent_pid or os.getpid()),
                      "-InstallDir", str(install_dir),
                      "-StageRoot", str(staging)],
                     creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
