"""Read-only advisory maintenance status: failure never blocks the updater."""
import json
import re
from datetime import datetime, timezone
from urllib.parse import urlsplit
import urllib.request

STATUS_URL = ("https://raw.githubusercontent.com/matiz311/WinNAT-UI/"
              "main/.github/maintenance/maintenance-status.json")
VALID_STATES = {"operational", "maintenance", "degraded", "unavailable", "unknown"}
MAX_BYTES = 32 * 1024
MAX_AGE_SECONDS = 900


def _utc_timestamp(value):
    if not isinstance(value, str) or not value.endswith("Z"):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.utcoffset().total_seconds() == 0 else None


def parse_status(document, *, now=None):
    """Only fresh, schema-valid service records may be presented as current."""
    if not isinstance(document, dict) or document.get("schema_version") != 1:
        return {}
    updated = _utc_timestamp(document.get("updated_at"))
    current = now or datetime.now(timezone.utc)
    if updated is None or not (0 <= (current - updated).total_seconds() <= MAX_AGE_SECONDS):
        return {}
    services = document.get("services")
    if not isinstance(services, dict):
        return {}
    parsed = {}
    for name, record in services.items():
        if not isinstance(name, str) or not isinstance(record, dict):
            continue
        status = record.get("status")
        event_id = record.get("event_id")
        if status not in VALID_STATES:
            continue
        if event_id is not None and (not isinstance(event_id, str)
                                     or not re.fullmatch(r"MAINT-[0-9]{8}-[0-9]{3}", event_id)):
            continue
        # Mirror registry guard in PR #68: a live maintenance claim is traceable.
        if status == "maintenance" and event_id is None:
            continue
        parsed[name] = {"status": status, "event_id": event_id}
    return parsed


def current_services(*, timeout=3):
    """Return empty on network error, invalid status, or stale data: fail open."""
    try:
        request = urllib.request.Request(STATUS_URL, headers={
            "User-Agent": "WinNAT-UI-Maintenance", "Accept": "application/json"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            final_url = urlsplit(response.geturl())
            if (final_url.scheme != "https"
                    or final_url.hostname != "raw.githubusercontent.com"):
                return {}
            data = response.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            return {}
        return parse_status(json.loads(data))
    except (OSError, ValueError, TypeError, AttributeError):
        return {}


def maintenance_hint(service="github-releases"):
    """An informational hint only: maintenance is not proof of the error cause."""
    service_status = current_services().get(service, {})
    if service_status.get("status") != "maintenance":
        return None
    event = service_status.get("event_id")
    return ("Manutenzione GitHub segnalata" + (" (" + event + ")" if event else "")
            + "; possibile correlazione, causa dell'errore non confermata.")
