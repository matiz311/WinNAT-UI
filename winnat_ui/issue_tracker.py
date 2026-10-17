"""Opt-in diagnostic reporting and local GitHub issue tracking.

The executable contains no GitHub credentials. Detailed diagnostics are sent
only after the user confirms publication through the maintainer's HTTPS gateway.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import ssl
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


def safe_payload(operation, error, stack, version=VERSION, inventory=None, is_admin=None, pending=None):
    """Preserve actionable diagnostics; mask recognizable secrets before upload."""
    return bug_report.build_payload(operation, error, stack, version,
                                    inventory=inventory, is_admin=is_admin, pending=pending)


def fingerprint(payload):
    # Avoid volatile values (version, exit code) to match recurring errors.
    scope = {key: payload[key] for key in ("operation", "category", "exception")}
    scope["modules"] = sorted(payload["modules"])
    if payload.get("signature"):
        scope["signature"] = payload["signature"]
    return hashlib.sha256(json.dumps(scope, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()[:24]



class RemoteIssueError(RuntimeError):
    """Expected failure of the external issue service, not a WinNAT fault."""

    def __init__(self, category, detail, status=None):
        super().__init__(detail)
        self.category = category
        self.status = status


def classify_remote_error(exc):
    """Retain diagnostic category without leaking URLs or credentials in the UI."""
    if isinstance(exc, urllib.error.HTTPError):
        return RemoteIssueError("http_failure", "Servizio GitHub non disponibile (HTTP %d)." % exc.code, exc.code)
    if isinstance(exc, (socket.gaierror,)) or (
        isinstance(exc, urllib.error.URLError) and isinstance(exc.reason, socket.gaierror)
    ):
        return RemoteIssueError("dns_failure", "Risoluzione DNS del servizio GitHub non riuscita.")
    reason = exc.reason if isinstance(exc, urllib.error.URLError) else exc
    if isinstance(reason, (TimeoutError, socket.timeout)):
        return RemoteIssueError("offline_or_unreachable", "Connessione al servizio GitHub scaduta.")
    if isinstance(reason, (ssl.SSLError, ssl.CertificateError)):
        return RemoteIssueError("tls_failure", "Verifica TLS del servizio GitHub non riuscita.")
    if isinstance(exc, (urllib.error.URLError, OSError)):
        return RemoteIssueError("offline_or_unreachable", "Servizio GitHub non raggiungibile.")
    if isinstance(exc, (json.JSONDecodeError, UnicodeDecodeError)):
        return RemoteIssueError("invalid_response", "Risposta GitHub non valida.")
    return RemoteIssueError("invalid_response", "Risposta del servizio GitHub non valida.")


def _read_json(url, *, timeout=10):
    request = urllib.request.Request(url, headers={"User-Agent": "WinNAT-UI-Issues",
                                                   "Accept": "application/vnd.github+json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if response.status != 200:
                raise RemoteIssueError("http_failure", "Risposta HTTP GitHub inattesa.", response.status)
            if int(response.headers.get("Content-Length") or 0) > 512 * 1024:
                raise RemoteIssueError("invalid_response", "Risposta GitHub eccessivamente grande.")
            raw = response.read(512 * 1024 + 1)
        if len(raw) > 512 * 1024:
            raise RemoteIssueError("invalid_response", "Risposta GitHub eccessivamente grande.")
        return json.loads(raw)
    except RemoteIssueError:
        raise
    except (urllib.error.URLError, OSError, TimeoutError, ssl.SSLError,
            json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise classify_remote_error(exc) from exc


def service_endpoint():
    """The official repo publishes an endpoint after the gateway is deployed."""
    try:
        config = _read_json(SERVICE_CONFIG)
    except (OSError, ValueError, KeyError, RemoteIssueError):
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



MANUAL_CATEGORIES = ("Problema applicativo", "Problema esterno",
                     "Miglioramento", "Richiesta supporto")


def manual_fingerprint(title):
    return hashlib.sha256(("manual-issue:" + title.strip()).encode("utf-8")).hexdigest()[:24]


def submit_manual(title, body, category, issue_number=None, endpoint=None):
    """Publish the edited preview exactly as approved by the user."""
    if not isinstance(title, str) or not 5 <= len(title.strip()) <= 180 or "\n" in title:
        raise ValueError("Titolo segnalazione non valido (5-180 caratteri).")
    if not isinstance(body, str) or not body.strip() or len(body) > 24000:
        raise ValueError("Report vuoto o troppo lungo (massimo 24000 caratteri).")
    if category not in MANUAL_CATEGORIES:
        raise ValueError("Tipo segnalazione non valido.")
    if issue_number is not None and (not isinstance(issue_number, int) or isinstance(issue_number, bool)
                                     or not 1 <= issue_number <= 99999999):
        raise ValueError("Numero Issue non valido.")
    data = {"mode": "manual", "title": title.strip(), "body": body,
            "category": category, "version": VERSION, "issue_number": issue_number}
    return submit(data, endpoint=endpoint)


def save_manual_entry(title, category, issue):
    """Create or refresh a local tracking entry after a successful submission."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    number = issue["number"]
    if not isinstance(number, int) or number <= 0:
        raise ValueError("Numero Issue non valido.")
    items = history()
    existing = next((entry for entry in items if entry.get("number") == number), None)
    if existing:
        existing["updated_at"] = now
        existing["title"] = existing.get("title") or title
        record = existing
    else:
        record = {"fingerprint": manual_fingerprint(title), "number": number,
                  "url": issue["url"], "operation": "Segnalazione manuale",
                  "category": category, "version": VERSION, "reported_at": now,
                  "state": "open", "fixed_in": None, "title": title,
                  "triage": None, "priority": None, "updated_at": now,
                  "timeline": [], "manually_added": bool(issue.get("already_exists"))}
    items = [entry for entry in items if entry.get("number") != number]
    items.insert(0, record)
    path = store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(items[:MAX_HISTORY], ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)
    return record


def issue_by_number(number):
    """Read an existing GitHub issue; do not import pull requests."""
    if not isinstance(number, int) or isinstance(number, bool) or not 1 <= number <= 99999999:
        raise ValueError("Numero Issue non valido.")
    obj = _read_json(GITHUB_API + "/issues/" + str(number))
    if not isinstance(obj, dict) or obj.get("number") != number or "pull_request" in obj:
        raise ValueError("Issue GitHub non valida.")
    names = [lab.get("name") if isinstance(lab, dict) else lab
             for lab in obj.get("labels", [])]
    fixed = next((name.split("v", 1)[1] for name in names
                  if isinstance(name, str) and re.fullmatch(r"fixed-in/v\d+\.\d+\.\d+(?:\.\d+)?", name)), None)
    return {"number": number, "url": "https://github.com/" + REPO + "/issues/" + str(number),
            "title": str(obj.get("title") or "")[:240], "state": obj.get("state"),
            "triage": next((name[7:] for name in names if isinstance(name, str) and name.startswith("triage:")), None),
            "priority": next((name[9:] for name in names if isinstance(name, str) and name.startswith("priority:")), None),
            "fixed_in": fixed, "updated_at": obj.get("updated_at")}


def track_issue(number):
    """Follow a GitHub issue independently of any local error report."""
    info = issue_by_number(number)
    save_manual_entry(info["title"], "Richiesta supporto", {**info, "already_exists": True})
    return info


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
              "state": "open", "fixed_in": None,
              "title": None, "triage": "ricevuto", "priority": None,
              "updated_at": None, "timeline": []}
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
    """Read GitHub metadata, including renamed titles and triage labels."""
    found = {}
    for page in range(1, 11):
        issues = _read_json(GITHUB_API + "/issues?state=all&labels=bug-report&per_page=100&page=" + str(page))
        if not isinstance(issues, list):
            raise ValueError("Risposta GitHub Issue non valida")
        for item in issues:
            if not isinstance(item, dict) or "pull_request" in item:
                continue
            body = item.get("body") or ""
            match = re.search(r"<!-- winnat-fingerprint:([a-f0-9]{24}) -->", body)
            if not match:
                continue
            labels = [label.get("name", "") for label in item.get("labels", [])
                      if isinstance(label, dict)]
            fixed = next((label.split("v", 1)[1] for label in labels
                          if re.fullmatch(r"fixed-in/v\d+\.\d+\.\d+(?:\.\d+)?", label)), None)
            triage = next((label[len("triage:"):] for label in labels
                           if label.startswith("triage:")), None)
            priority = next((label[len("priority:"):] for label in labels
                             if label.startswith("priority:")), None)
            candidate = {"number": item.get("number"), "url": item.get("html_url"),
                         "state": item.get("state"), "fixed_in": fixed,
                         "fingerprint": match.group(1),
                         "title": str(item.get("title") or "")[:240],
                         "triage": triage, "priority": priority,
                         "updated_at": item.get("updated_at")}
            found.setdefault(match.group(1), []).append(candidate)
        if len(issues) < 100:
            break
    return found


def comparable_release(a, b):
    def version(s):
        if not isinstance(s, str) or not re.fullmatch(r"\d+\.\d+\.\d+(?:\.\d+)?", s):
            return None
        components = tuple(map(int, s.split(".")))
        return components + (0,) * (4 - len(components))
    aa, bb = version(a), version(b)
    return aa is not None and bb is not None and aa >= bb


def synchronize(installed=VERSION, remote=None, latest_version=None):
    """Update locally reported issues from public GitHub state, no personal data uploaded."""
    listed = remote if remote is not None else public_issues()
    entries = history()
    for record in entries:
        matches = [x for x in listed.get(record["fingerprint"], [])
                   if x["number"] == record["number"]]
        if record.get("manually_added"):
            try:
                matches = [issue_by_number(record["number"])]
            except (ValueError, RemoteIssueError):
                matches = []
        if matches:
            issue = matches[0]
            from datetime import datetime, timezone
            tracked_fields = ("title", "triage", "priority", "state", "fixed_in")
            changes = {field: {"from": record.get(field), "to": issue.get(field)}
                       for field in tracked_fields if record.get(field) != issue.get(field)}
            # The timestamp is the time this client observed the change,
            # not an invented GitHub transition timestamp.
            if changes:
                timeline = record.get("timeline")
                if not isinstance(timeline, list):
                    timeline = []
                timeline.append({"observed_at": datetime.now(timezone.utc).isoformat(),
                                 "changes": changes})
                record["timeline"] = timeline[-50:]
            for field in ("title", "triage", "priority", "updated_at", "state", "fixed_in"):
                record[field] = issue.get(field)
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
