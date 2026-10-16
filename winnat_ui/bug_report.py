"""Detailed opt-in diagnostics for GitHub Issues.

Retain errors, PowerShell output, traceback and network topology. Redact recognizable
credentials and personal identifiers; IP addresses and adapter names are deliberately
preserved because they are often essential to troubleshooting.
"""
import hashlib
import json
import platform
import re
import sys
from datetime import datetime, timezone
from urllib.parse import urlencode

ISSUE_URL = "https://github.com/matiz311/WinNAT-UI/issues/new"
SAFE_OPERATIONS = {"Commit", "Aggiornamenti", "Download aggiornamento", "Update",
                   "Refresh", "Aggiorna", "Sessioni"}
SAFE_MODULES = {"app.py", "network.py", "network_guide.py", "network_rollback.py",
                "network_plan.py", "updater.py", "ui_theme.py", "bug_report.py",
                "issue_tracker.py", "nat_backend.py", "version.py"}
SAFE_EXCEPTION_TYPES = {
    "RuntimeError", "ValueError", "TypeError", "KeyError", "OSError",
    "PermissionError", "FileNotFoundError", "TimeoutError", "CalledProcessError",
    "ConnectionError", "HTTPError", "URLError", "Exception", "AttributeError",
    "IndexError", "NotImplementedError", "JSONDecodeError",
}
# Fixed error patterns -> fixed human-readable labels, never copy matches.
KNOWN_ERRORS = (
    (r"configurazione (?:rilevante )?modificata dopo l.anteprima", "Configurazione modificata dopo l'anteprima"),
    (r"(?:oggetto esiste gi[àa]|object already exists|already exists)", "Oggetto Windows già esistente"),
    (r"(?:indirizzo .+ gi[àa] (?:presente|assegnato)|duplicate.*(?:ip|address))", "Conflitto di indirizzo IP"),
    (r"(?:rollback incompleto|rollback.*failed)", "Ripristino non completato"),
    (r"(?:accesso negato|access is denied|permission denied)", "Accesso negato"),
    (r"(?:timeout|timed out|scadut[oa])", "Operazione scaduta"),
    (r"(?:network.*unreachable|rete.*non raggiungibile)", "Rete non raggiungibile"),
    (r"(?:netsh.*(?:failed|errore)|impossibile impostare ip statico)", "Errore di configurazione LAN tramite netsh"),
)


def _category(message):
    text = str(message or "")
    for expression, label in KNOWN_ERRORS:
        if re.search(expression, text, flags=re.IGNORECASE):
            return label
    return "Errore operativo non classificato"


def _exception_type(traceback_text):
    # Extract only a fixed set of standard exception type identifiers.
    result = re.findall(r"(?m)^(?:[\w.]+\.)?([A-Za-z]+Error|Exception):", str(traceback_text or ""))
    for value in reversed(result):
        if value in SAFE_EXCEPTION_TYPES:
            return value
    return "Non determinato"


def _stack_modules(traceback_text):
    # Basenames are from the local fixed allowlist, no absolute path or function.
    result = []
    for filename in re.findall(r'File "[^"\r\n]*?([A-Za-z_]+\.py)"', str(traceback_text or "")):
        if filename in SAFE_MODULES and filename not in result:
            result.append(filename)
    return result[:8]


def _limit(text, size):
    """Keep diagnostic sections bounded and announce truncation explicitly."""
    value = str(text or "")
    if len(value) <= size:
        return value
    suffix = "\n\n[TRONCATO: " + str(len(value) - size) + " caratteri non inclusi]"
    return value[:max(0, size - len(suffix))] + suffix


def redact(text):
    """Best-effort targeted masking. Preserve commands, IPs and network names."""
    value = str(text or "")
    value = re.sub(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
                   "[CHIAVE PRIVATA OSCURATA]", value, flags=re.I | re.S)
    value = re.sub(r"(?i)\b(?:bearer|basic)\s+[A-Za-z0-9._~+/\-=]{8,}",
                   "[TOKEN DI AUTORIZZAZIONE OSCURATO]", value)
    value = re.sub(r"(?i)([a-z][a-z0-9+.-]*://)[^/@\s:]+:[^/@\s]+@",
                   r"\1[credenziali oscurate]@", value)
    value = re.sub(r"(?i)(\b(?:password|passwd|pwd|api[_-]?key|access[_-]?token|"
                   r"refresh[_-]?token|secret|authorization|client[_-]?secret|"
                   r"cookie|set-cookie)\b\s*[:=]\s*)"
                   r"(?:\"[^\"\r\n]*\"|'[^'\r\n]*'|[^\s,;]+)",
                   r"\1[OSCURATO]", value)
    value = re.sub(r"(?i)(-{1,2}(?:password|token|api-key|secret)\s+)"
                   r"(?:\"[^\"\r\n]*\"|'[^'\r\n]*'|[^\s;]+)",
                   r"\1[OSCURATO]", value)
    value = re.sub(r"(?i)(convertto-securestring\s+)"
                   r"(?:\"[^\"\r\n]*\"|'[^'\r\n]*')",
                   r"\1[OSCURATO]", value)
    value = re.sub(r"(?i)([A-Z]:\\Users\\)[^\\\r\n]+", r"\1[utente]", value)
    value = re.sub(r"(?i)(/(?:home|Users)/)[^/\r\n]+", r"\1[utente]", value)
    value = re.sub(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
                   "[email oscurata]", value)
    return value


def _summary(message):
    text = str(message or "")
    stderr = re.search(r"(?im)^STDERR(?: \(integrale\))?:\s*\n([^\r\n]+)", text)
    if stderr:
        return _limit(redact(stderr.group(1)).strip(), 180)
    ignored = ("ESECUZIONE POWERSHELL", "Exit code:", "PowerShell exit code:",
               "Interprete:", "Timeout configurato:", "STDERR:", "STDOUT:")
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith(ignored) and line != "(vuoto)":
            return _limit(redact(line), 180)
    return "Errore non classificato (consultare dettagli e traceback)"


def build_payload(operation, message, traceback_text, version, inventory=None, is_admin=None, pending=None):
    """One source of truth for manually copied and automatically submitted reports."""
    op = redact(str(operation or "")).strip()
    if not re.fullmatch(r"[w .:()/+-]{1,80}", op):
        op = "Altra operazione"
    ver = str(version) if re.fullmatch(r"\d{1,3}\.\d{1,3}\.\d{1,3}(?:\.\d{1,3})?", str(version)) else "0.0.0"
    original = str(message or "")
    match = re.search(r"(?:PowerShell (?:exit code|terminato con codice)|Exit code:)\s*(\d{1,4})",
                      original, re.I)
    modules = _stack_modules(traceback_text)
    environment = {
        "ora_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sistema": platform.platform(),
        "architettura": platform.machine(),
        "python": platform.python_version(),
        "eseguibile_compilato": bool(getattr(sys, "frozen", False)),
        "amministratore": is_admin if isinstance(is_admin, bool) else None,
    }
    snapshot = "(inventario non disponibile: aggiornamento non ancora completato)"
    if inventory is not None:
        try:
            # The cached inventory already collected by the UI; no commands run
            # during the reporting flow, and no private application state dumped.
            if isinstance(inventory, dict):
                keys = ("adapters", "ips", "routes", "interfaces", "nats", "natMappings",
                        "ics", "icsConnections", "dns", "globalRouter")
                inventory = {k: inventory[k] for k in keys if k in inventory}
            if pending:
                inventory = {"network": inventory, "pending_changes": pending}
            snapshot = json.dumps(inventory, ensure_ascii=False, indent=2, default=str)
        except (TypeError, ValueError):
            snapshot = "(serializzazione inventario non riuscita)"
    summary = _summary(original)
    # Hash the actual failure line, not the entire script, inventory or version.
    # Different errors in the same broad category must not overwrite each other.
    normalized = re.sub(r"\s+", " ", summary).casefold()
    signature = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24]
    return {
        "operation": op,
        "category": _category(original),
        "exception": _exception_type(traceback_text),
        "modules": modules,
        "version": ver,
        "exit_code": int(match.group(1)) if match else None,
        "signature": signature,
        "summary": summary,
        "message": _limit(redact(original), 16000),
        "traceback": _limit(redact(traceback_text), 13000),
        "environment": _limit(redact(json.dumps(environment, ensure_ascii=False, indent=2)), 1500),
        "inventory": _limit(redact(snapshot), 14000),
    }


def _code_section(value):
    # Four-space indent treats every line as literal text, not injected Markdown.
    return "\n".join("    " + line for line in (value or "(non disponibile)").splitlines())


def format_report(payload):
    """Human-readable GitHub issue draft including the complete bounded evidence."""
    title = "[Bug] " + payload["operation"] + " - " + payload["category"]
    if payload.get("summary"):
        title += " | " + payload["summary"][:100]
    title = re.sub(r"[\r\n]+", " ", title)[:240]
    body = [
        "## Diagnostica automatica WinNAT-UI",
        "",
        "**Versione:** " + payload["version"],
        "**Operazione:** " + payload["operation"],
        "**Categoria:** " + payload["category"],
        "**Eccezione Python:** " + payload["exception"],
        "**Codice uscita PowerShell:** " + str(payload["exit_code"] if payload["exit_code"] is not None else "Non disponibile"),
        "**Moduli:** " + (", ".join(payload["modules"]) or "Non disponibili"),
        "",
        "### Errore principale",
        _code_section(payload.get("summary")),
        "",
        "### Messaggio originale, PowerShell, comandi e output",
        _code_section(payload.get("message")),
        "",
        "### Traceback Python",
        _code_section(payload.get("traceback")),
        "",
        "### Ambiente di esecuzione",
        _code_section(payload.get("environment")),
        "",
        "### Inventario rete acquisito dall'interfaccia",
        _code_section(payload.get("inventory")),
        "",
        "### Riproduzione / comportamento atteso",
        "Aggiungere eventuali passaggi necessari alla riproduzione e il risultato atteso.",
        "",
        "### Trattamento dei dati",
        "La segnalazione è destinata a una Issue GitHub pubblica. Sono oscurati, per quanto",
        "riconoscibili, credenziali, token, email e nomi utente nei percorsi. Indirizzi IP,",
        "nomi delle interfacce, comandi e topologia vengono mantenuti per la diagnosi.",
        "La rimozione automatica dei segreti non è garantita: verificare la bozza.",
    ]
    return title, "\n".join(body)


def make_report(operation, message, traceback_text, version, inventory=None, is_admin=None):
    return format_report(build_payload(operation, message, traceback_text,
                                       version, inventory=inventory, is_admin=is_admin))


def issue_link(operation, message, traceback_text, version):
    # Huge prefilled issue URLs can be rejected by browsers/proxies. Copy the
    # full report separately and open the blank GitHub issue composer instead.
    title, body = make_report(operation, message, traceback_text, version)
    url = ISSUE_URL + "?" + urlencode({"title": title, "body": body})
    return url if len(url) < 7000 else ISSUE_URL + "?" + urlencode({"title": title})
