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


def manual_payload(title, description, kind="Problema esterno", version=VERSION,
                   inventory=None, is_admin=None):
    """Build a report with no exception, traceback or network operation required.

    Reuse the existing gateway schema: older deployed Workers already support
    the report, while the user-supplied title provides a stable distinct signature.
    """
    subject = str(title or "").strip()
    details = str(description or "").strip()
    allowed = ("Problema esterno", "Incompatibilità", "Comportamento inatteso", "Altro problema")
    if not subject or len(subject) > 120 or "\n" in subject or "\r" in subject:
        raise ValueError("Inserisci un titolo descrittivo di massimo 120 caratteri.")
    if not details or len(details) > 8000:
        raise ValueError("Inserisci una descrizione di massimo 8000 caratteri.")
    if kind not in allowed:
        raise ValueError("Tipologia di segnalazione non riconosciuta.")
    message = (subject + " [" + kind + "]\n\n"
               "Segnalazione manuale: nessuna eccezione generata da WinNAT-UI.\n"
               "Tipo: " + kind + "\n\nDettagli e riproduzione:\n" + details)
    payload = safe_payload("Segnalazione manuale", message, "", version,
                           inventory=inventory, is_admin=is_admin)
    # A broad recurring title can describe different external problems.
    # Include the actual description in deduplication without publishing its hash input.
    stable = json.dumps({"title": subject.casefold(), "kind": kind,
                         "details": re.sub(r"\s+", " ", details).casefold()},
                        ensure_ascii=False, sort_keys=True)
    payload["signature"] = hashlib.sha256(stable.encode("utf-8")).hexdigest()[:24]
    return payload


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
    # A linked GitHub issue and an in-app report must occupy just one row.
    entries = [e for e in history() if e.get("number") != record["number"]]
    entries.insert(0, record)
    path = store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(entries[:MAX_HISTORY], ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)
    return record


def issue_number(reference):
    """Accept only numeric IDs or canonical issue links in this repository."""
    value = str(reference or "").strip()
    if re.fullmatch(r"#?\d{1,9}", value):
        number = int(value.lstrip("#"))
    else:
        parts = urlsplit(value)
        if (parts.scheme != "https" or parts.hostname != "github.com"
                or parts.username or parts.password or parts.port
                or parts.query or parts.fragment):
            raise ValueError("Usa il numero o l'URL della Issue GitHub ufficiale.")
        match = re.fullmatch(r"/" + re.escape(REPO) + r"/issues/(\d{1,9})/?", parts.path)
        if not match:
            raise ValueError("La Issue deve appartenere al repository WinNAT-UI.")
        number = int(match.group(1))
    if number <= 0:
        raise ValueError("Il numero della Issue deve essere positivo.")
    return number


def issue_metadata(item):
    """Strictly validate metadata returned by GitHub, excluding pull requests."""
    if (not isinstance(item, dict) or "pull_request" in item
            or type(item.get("number")) is not int or item["number"] <= 0):
        raise RemoteIssueError("invalid_response", "L'elemento GitHub non è una Issue valida.")
    number = item["number"]
    url = "https://github.com/" + REPO + "/issues/" + str(number)
    if item.get("html_url") != url or item.get("state") not in ("open", "closed"):
        raise RemoteIssueError("invalid_response", "Identità della Issue GitHub non valida.")
    labels = [label.get("name", "") for label in item.get("labels", [])
              if isinstance(label, dict)]
    fixed = next((label.split("v", 1)[1] for label in labels
                  if re.fullmatch(r"fixed-in/v\d+\.\d+\.\d+(?:\.\d+)?", label)), None)
    triage = next((label[len("triage:"):] for label in labels
                   if label.startswith("triage:")), None)
    priority = next((label[len("priority:"):] for label in labels
                     if label.startswith("priority:")), None)
    return {"number": number, "url": url, "state": item["state"],
            "fixed_in": fixed, "title": str(item.get("title") or "")[:240],
            "triage": triage, "priority": priority,
            "comments": item.get("comments") if type(item.get("comments")) is int else None,
            "updated_at": item.get("updated_at")}


def read_issue(number):
    """Read a single public GitHub issue without client credentials."""
    number = issue_number(number)
    item = _read_json(GITHUB_API + "/issues/" + str(number))
    metadata = issue_metadata(item)
    if metadata["number"] != number:
        raise RemoteIssueError("invalid_response", "Numero Issue GitHub inatteso.")
    return metadata


def track_issue(reference):
    """Add a pre-existing GitHub issue to local tracking, avoiding duplicates."""
    number = issue_number(reference)
    metadata = read_issue(number)
    entries = history()
    existing = next((r for r in entries if r.get("number") == number), None)
    if existing is not None:
        return existing, False
    from datetime import datetime, timezone
    record = {"number": number, "url": metadata["url"], "fingerprint": None,
              "tracked_via": "github", "operation": "Issue GitHub collegata",
              "category": "Segnalazione esterna", "version": None,
              "reported_at": datetime.now(timezone.utc).isoformat(),
              "state": metadata["state"], "fixed_in": metadata["fixed_in"],
              "title": metadata["title"], "triage": metadata["triage"],
              "priority": metadata["priority"], "updated_at": metadata["updated_at"],
              "comments": metadata["comments"], "timeline": []}
    entries.insert(0, record)
    _write_history(entries)
    return record, True


def _write_history(entries):
    path = store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(entries[:MAX_HISTORY], ensure_ascii=False, indent=2),
                    encoding="utf-8")
    temp.replace(path)


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
            candidate = issue_metadata(item)
            candidate["fingerprint"] = match.group(1)
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


def synchronize(installed=VERSION, remote=None, latest_version=None, remote_by_number=None):
    """Sync auto-reported and explicitly followed issues with GitHub metadata."""
    entries = history()
    listed = remote if remote is not None else public_issues()
    by_number = remote_by_number if remote_by_number is not None else {}
    if remote is None and remote_by_number is None:
        # Read linked issues directly: they may have neither bug-report labels
        # nor a fingerprint. Network failures leave local history untouched.
        for record in entries:
            if record.get("tracked_via") == "github":
                by_number[record["number"]] = read_issue(record["number"])
    for record in entries:
        if record.get("tracked_via") == "github":
            issue = by_number.get(record["number"])
            matches = [issue] if issue is not None else []
        else:
            matches = [x for x in listed.get(record.get("fingerprint"), [])
                       if x["number"] == record["number"]]
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
            for field in ("title", "triage", "priority", "updated_at", "state", "fixed_in", "comments"):
                if field in issue:
                    record[field] = issue.get(field)
            record["fix_available"] = (bool(issue["fixed_in"]) and latest_version is not None
                                       and comparable_release(latest_version, issue["fixed_in"])
                                       and not comparable_release(installed, issue["fixed_in"]))
    if entries:
        _write_history(entries)
    return entries, listed


def find_similar(payload, issues):
    return issues.get(fingerprint(payload), [])
