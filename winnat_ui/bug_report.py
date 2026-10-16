"""Privacy-first GitHub bug reporting.

No raw Windows network configuration, shell commands, stdout/stderr, filenames,
usernames, credentials or traceback text are copied to the report or issue URL.
Only strictly allowlisted diagnostic facts are extracted.
"""
import re
from urllib.parse import urlencode

ISSUE_URL = "https://github.com/matiz311/WinNAT-UI/issues/new"
SAFE_OPERATIONS = {"Commit", "Aggiornamenti", "Download aggiornamento", "Update",
                   "Refresh", "Aggiorna", "Sessioni"}
SAFE_MODULES = {"app.py", "network.py", "network_guide.py", "network_rollback.py",
                "network_plan.py", "updater.py", "ui_theme.py", "bug_report.py"}
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


def make_report(operation, message, traceback_text, version):
    """Build an allowlist-only report: never include any raw log fragments."""
    from_version = re.fullmatch(r"\d+\.\d+\.\d+", str(version))
    version_value = str(version) if from_version else "Non determinata"
    operation_value = operation if operation in SAFE_OPERATIONS else "Altra operazione"
    code_match = re.search(r"(?:PowerShell (?:exit code|terminato con codice)|Exit code:)\s*(\d{1,4})",
                           str(message or ""), re.IGNORECASE)
    code = code_match.group(1) if code_match else "Non disponibile"
    exception = _exception_type(traceback_text)
    modules = _stack_modules(traceback_text)
    category = _category(message)
    title = "[Bug] " + operation_value + " - " + category
    body = (
        "## Report automatico anonimizzato\n\n"
        "**Versione WinNAT-UI:** " + version_value + "\n"
        "**Operazione:** " + operation_value + "\n"
        "**Categoria:** " + category + "\n"
        "**Eccezione Python:** " + exception + "\n"
        "**Codice uscita PowerShell:** " + code + "\n"
        "**Moduli coinvolti:** " + (", ".join(modules) if modules else "Non disponibili") + "\n\n"
        "## Comportamento osservato\n"
        "L'operazione indicata non è stata completata correttamente.\n\n"
        "## Riproduzione (da completare)\n"
        "1. \n2. \n\n"
        "## Risultato atteso (da completare)\n\n"
        "## Privacy e verifica\n"
        "Il report include solo categorie e metadati da elenchi predefiniti. "
        "Non include indirizzi IP, nomi di interfacce, configurazioni, comandi, "
        "STDOUT/STDERR, percorsi, credenziali o traceback grezzo. "
        "Verificare e completare i campi prima di inviare il bug su GitHub.\n"
    )
    return title, body


def issue_link(operation, message, traceback_text, version):
    title, body = make_report(operation, message, traceback_text, version)
    return ISSUE_URL + "?" + urlencode({"title": title, "body": body})
