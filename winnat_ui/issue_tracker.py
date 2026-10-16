"""Opt-in diagnostic reporting and local GitHub issue tracking.

The executable contains no GitHub credentials. Detailed diagnostics are sent
only after the user confirms publication through the maintainer's HTTPS gateway.
"""
import hashlib
import json
import os
from pathlib import Path
import re
from urllib.parse import urlsplit
import urllib.error
import urllib.request

from . import bug_report
from version import VERSION

REPO = "matiz311/WinNAT-UI"
GITHUB_API = "https://api.github.com/repos/" + REPO
SERVICE_CONFIG = "https://raw.githubusercontent.com/" + REPO + "/main/bug-service.json"
MAX_HISTORY = 150
SAFE_CATEGORIES = {label for _pattern, label in bug_report.KNOWN_ERRORS} | {"Errore operativo non classificato"}


def safe_payload(operation, error, stack, version=VERSION, inventory=None, is_admin=None):
    """Preserve actionable diagnostics; mask recognizable secrets before upload."""
    return bug_report.build_payload(operation, error, stack, version,
                                    inventory=inventory, is_admin=is_admin)


def fingerprint(payload):
    # Avoid volatile values (version, exit code) to match recurring errors.
    scope = {key: payload[key] for key in ("operation", "category", "exception")}
    scope["modules"] = sorted(payload["modules"])
    if payload.get("signature"):
        scope["signature"] = payload["signature"]
    return hashlib.sha256(json.dumps(scope, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()[:24]


def _read_json(url, *, timeout=10):
    request = urllib.request.Request(url, headers={"User-Agent": "WinNAT-UI-Issues",
                                                   "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        if response.status != 200:
            raise RuntimeError("Risposta remota non valida.")
        if int(response.headers.get("Content-Length") or 0) > 512 * 1024:
            raise RuntimeError("Risposta remota eccessivamente grande.")
        raw = response.read(512 * 1024 + 1)
    if len(raw) > 512 * 1024:
        raise RuntimeError("Risposta remota eccessivamente grande.")
    return json.loads(raw)


def service_endpoint():
    """The official repo publishes an endpoint after the gateway is deployed."""
    try:
        config = _read_json(SERVICE_CONFIG)
    except (OSError, ValueError, KeyError):
        return None
    endpoint = config.get("submit_url") if isinstance(config, dict) else None
    if not isinstance(endpoint, str):
        return None
    parts = urlsplit(endpoint)
    if (parts.scheme != "https" or not parts.hostname or parts.username or parts.password
            or parts.query or parts.fragment or parts.port not in (None, 443)
            or not parts.hostname.endswith(".workers.dev") or not parts.path.endswith("/report")):
        return None
    return endpoint


def submit(payload, endpoint=None):
    """POST allowlisted fields, then validate returned GitHub issue identity."""
    endpoint = endpoint or service_endpoint()
    if endpoint is None:
        raise RuntimeError("Servizio di segnalazione anonima non ancora configurato.")
    body = json.dumps(payload, separators=(",", ":")).encode()
    request = urllib.request.Request(endpoint, data=body, method="POST",
                                     headers={"Content-Type": "application/json",
                                              "User-Agent": "WinNAT-UI-Issues"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            data = json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            raise RuntimeError("Limite di segnalazioni raggiunto. Riprova più tardi.") from exc
        raise RuntimeError("Servizio di segnalazione non disponibile (HTTP " + str(exc.code) + ").") from exc
    number = data.get("number") if isinstance(data, dict) else None
    url = data.get("url") if isinstance(data, dict) else None
    expected = ("https://github.com/" + REPO + "/issues/" + str(number))
    if not isinstance(number, int) or number <= 0 or url != expected:
        raise RuntimeError("Risposta del servizio bug non valida.")
    return {"number": number, "url": url, "already_exists": bool(data.get("already_exists"))}


def store_path():
    root = os.environ.get("LOCALAPPDATA") or str(Path.home() / ".local" / "share")
    return Path(root) / "WinNAT-UI" / "reported-issues.json"


def history():
    try:
        data = json.loads(store_path().read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def save_entry(payload, issue):
    """Atomic local file replacement; store only sanitized metadata."""
    from datetime import datetime, timezone
    record = {"fingerprint": fingerprint(payload), "number": issue["number"],
              "url": issue["url"], "operation": payload["operation"],
              "category": payload["category"], "version": payload["version"],
              "reported_at": datetime.now(timezone.utc).isoformat(),
              "state": "open", "fixed_in": None}
    entries = [e for e in history() if not (
        e.get("fingerprint") == record["fingerprint"] and e.get("number") == record["number"])]
    entries.insert(0, record)
    path = store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(entries[:MAX_HISTORY], ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)
    return record


def public_issues():
    """Read public labeled issues, not their raw bodies (which may contain secrets)."""
    issues = _read_json(GITHUB_API + "/issues?state=all&labels=bug-report&per_page=100")
    found = {}
    if not isinstance(issues, list):
        return found
    for item in issues:
        if "pull_request" in item:
            continue
        body = item.get("body") or ""
        signature = re.search(r"<!-- winnat-fingerprint:([a-f0-9]{24}) -->", body)
        if not signature:
            continue
        fixed = None
        for label in item.get("labels", []):
            value = label.get("name", "") if isinstance(label, dict) else ""
            if re.fullmatch(r"fixed-in/v\d+\.\d+\.\d+", value):
                fixed = value.split("v", 1)[1]
        candidate = {"number": item.get("number"), "url": item.get("html_url"),
                     "state": item.get("state"), "fixed_in": fixed, "fingerprint": signature.group(1)}
        found.setdefault(signature.group(1), []).append(candidate)
    return found


def comparable_release(a, b):
    def version(s):
        if not isinstance(s, str) or not re.fullmatch(r"\d+\.\d+\.\d+", s):
            return None
        return tuple(map(int, s.split(".")))
    aa, bb = version(a), version(b)
    return aa is not None and bb is not None and aa >= bb


def synchronize(installed=VERSION, remote=None, latest_version=None):
    """Update locally reported issues from public GitHub state, no personal data uploaded."""
    listed = remote if remote is not None else public_issues()
    entries = history()
    for record in entries:
        matches = [x for x in listed.get(record["fingerprint"], [])
                   if x["number"] == record["number"]]
        if matches:
            issue = matches[0]
            record["state"] = issue["state"]
            record["fixed_in"] = issue["fixed_in"]
            record["fix_available"] = (bool(issue["fixed_in"]) and latest_version is not None
                                       and comparable_release(latest_version, issue["fixed_in"])
                                       and not comparable_release(installed, issue["fixed_in"]))
    path = store_path()
    if entries:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(entries[:MAX_HISTORY], ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(path)
    return entries, listed


def find_similar(payload, issues):
    return issues.get(fingerprint(payload), [])
