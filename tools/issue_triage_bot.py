#!/usr/bin/env python3
"""Conservative, dependency-free initial triage for WinNAT-UI GitHub Issues.

No code execution from an Issue, no LLM, no automated resolution or release claim.
See docs/issue-triage.md and docs/issue-triage-automation.md.
"""
from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

MARKER = "<!-- winnat-auto-triage:v1 -->"
FINGERPRINT = re.compile(r"<!-- winnat-fingerprint:([a-f0-9]{24}) -->")
REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
TRIAGE_PREFIX = "triage:"
STATES = ("ricevuto", "in-analisi", "informazioni-richieste", "confermato",
          "in-correzione", "correzione-disponibile", "risolto", "duplicato",
          "non-riproducibile")
GENERIC = ("errore operativo non classificato", "altra operazione",
           "unknown error", "bug report", "segnalazione bug")


@dataclass(frozen=True)
class Assessment:
    component: str
    kind: str
    observation: str
    hypothesis: str
    requests: tuple[str, ...]
    next_step: str
    state: str
    suggested_title: str | None


def _normal(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def assess(title: str, body: str, number: int) -> Assessment:
    """Rule-based hints only; no causal or severity assertion is automated."""
    title = _normal(title)
    body = body or ""
    # Explicit title and structured diagnostic fields carry more weight than
    # incidental mentions of modules, releases or unrelated features in prose.
    data = (title + "\n" + body).casefold()
    title_lower = title.casefold()
    feature = any(x in title_lower for x in ("[feature]", "[enhancement]", "[richiesta]"))
    kind = "Miglioramento" if feature else "Anomalia segnalata"
    report_fields = re.findall(
        r"(?im)^\s*\*{0,2}(?:operazione|moduli|componente|categoria)\*{0,2}\s*:\s*([^\n]+)",
        body,
    )
    focus = (title + "\n" + "\n".join(report_fields)).casefold()
    generic_title = (not title or any(term in title_lower for term in GENERIC))
    if generic_title:
        # Legacy/generic titles may lack structured fields. The opening
        # description is relevant, but later remediation/release notes are not.
        focus += "\n" + body[:400].casefold()
    vpn_context = any(word in focus for word in ("vpn", "full tunnel", "fulltunnel"))

    if vpn_context and "malwarebytes" in data:
        component = "VPN Full Tunnel"
        observation = ("Segnalata difficoltà nel collegamento Malwarebytes VPN con "
                       "configurazione WinNAT presente; riportato ripristino dopo rimozione.")
        hypothesis = ("Possibile interazione fra VPN, route, metriche, forwarding e WinNAT; "
                      "la relazione causale non è ancora verificata.")
        requests = (
            "Versioni WinNAT-UI, Windows e Malwarebytes VPN; interfacce WAN/LAN utilizzate.",
            "Il tunnel non viene stabilito, oppure risulta connesso ma senza traffico? Riportare l'errore esatto.",
            "Confrontare tre prove A/B/C (prima di WinNAT, dopo attivazione, dopo rollback).",
            "Confrontare route, interfacce, forwarding, Get-NetNat e log VPN, condividendo solo differenze pertinenti e filtrate.",
        )
        next_step = "Segnalante: fornire esiti e dati minimi; manutentore: isolare la modifica di rete che altera la connessione."
    elif vpn_context:
        component = "VPN e rete"
        observation = "Segnalata anomalia nel comportamento di una connessione VPN."
        hypothesis = "Da verificare se il problema riguardi tunnel, instradamento o un errore indipendente da WinNAT."
        requests = (
            "Specificare client VPN, versione Windows/WinNAT-UI ed errore testuale esatto.",
            "Distinguere tunnel non stabilito da tunnel connesso ma traffico interrotto.",
            "Fornire confronto prima/dopo WinNAT, route e metriche filtrate e test di ripristino.",
        )
        next_step = "Segnalante: riprodurre e condividere le evidenze minime; manutentore: confrontare percorsi di rete."
    elif any(x in focus for x in ("aggiornament", "updater", "httperror", "controllo release")):
        component = "Aggiornamenti"
        observation = "Segnalato errore nel flusso di controllo o installazione degli aggiornamenti."
        hypothesis = ("Da distinguere endpoint/release assente, asset non disponibile, errore HTTP, "
                      "problema di connettività e difetto applicativo.")
        requests = (
            "Indicare versione installata e passaggio esatto (verifica, download, verifica SHA256, installazione).",
            "Fornire HTTP status o codice errore e ora UTC, se disponibili.",
            "Verificare separatamente disponibilità della release ufficiale e asset Windows, senza aggirare i controlli di integrità.",
        )
        next_step = "Segnalante: confermare fase e codice errore; manutentore: confrontare codice della versione segnalata."
    elif any(x in focus for x in ("dhcp", "interfaccia lan", "indirizzo statico", "new-netnat", "forwarding")):
        component = "Configurazione di rete"
        observation = "Segnalata anomalia durante la configurazione delle interfacce o di WinNAT."
        hypothesis = "Da confrontare stato iniziale, piano applicato, errore PowerShell e rollback; nessuna causa automatica."
        requests = (
            "Indicare versione WinNAT-UI, interfacce coinvolte e operazione esatta.",
            "Riportare comando/step fallito e codice errore filtrato.",
            "Confrontare piano prima/dopo e indicare se il rollback ha ripristinato lo stato precedente.",
        )
        next_step = "Segnalante: fornire piano e step fallito; manutentore: controllare validazioni e modifica mirata."
    elif any(x in focus for x in ("stato bug", "issue_tracker", "github issue", "getaddrinfo", "dns")):
        component = "Stato bug e connettività"
        observation = "Segnalata anomalia nel collegamento al servizio Issue o nella risoluzione nomi."
        hypothesis = "Problema remoto/offline e gestione applicativa dell'errore da distinguere; non provato un difetto WinNAT."
        requests = (
            "Indicare versione, operazione e connettività intenzionale del PC al momento del fatto.",
            "Riportare eccezione precisa e stato DNS/HTTPS verso l'endpoint richiesto, senza credenziali.",
            "Verificare che cronologia locale e pulsante Riprova funzionino in assenza di rete.",
        )
        next_step = "Segnalante: confermare stato connessione; manutentore: verificare gestione degli errori remoti."
    else:
        component = "Generale"
        observation = "Segnalazione ricevuta; non sono ancora identificati componente e comportamento riproducibile."
        hypothesis = "Nessuna causa determinabile dai soli dati presenti."
        requests = (
            "Indicare versione WinNAT-UI, Windows e funzione/operazione coinvolta.",
            "Descrivere passaggi per riprodurre, risultato ottenuto e risultato atteso.",
            "Fornire errore esatto, ora UTC e solo le parti rilevanti della diagnostica.",
        )
        next_step = "Segnalante: integrare le informazioni; manutentore: valutare componente, impatto e riproduzione."

    version_match = re.search(
        r"(?:\bversione(?:\s+winnat-ui)?\b|\bversion\b)\*{0,2}\s*:\s*\*{0,2}\s*v?(\d+\.\d+(?:\.\d+){0,2})",
        body, re.I,
    )
    has_version = bool(version_match and version_match.group(1) != "0.0.0")
    has_evidence = bool(re.search(r"traceback|eccezione|exception|exit code|errore principale|passaggi|riprod", body, re.I))
    enough = has_version and has_evidence and len(body.strip()) >= 160
    state = "triage:in-analisi" if enough else "triage:informazioni-richieste"
    replacement = None
    if generic_title:
        prefix = "[Feature]" if feature else "[Bug]"
        replacement = f"{prefix}[{component}] Diagnostica da approfondire (#{number})"
    return Assessment(component, kind, observation, hypothesis, requests, next_step, state, replacement)


def make_comment(issue: dict, analysis: Assessment, correlations: list[int]) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    number = issue["number"]
    version = "non verificata"
    found = re.search(r"(?:versione(?: WinNAT-UI)?|version)\*{0,2}\s*:\s*\*{0,2}\s*(v?\d+\.\d+(?:\.\d+){0,2})", issue.get("body") or "", re.I)
    if found and found.group(1) not in ("0.0.0", "v0.0.0"):
        version = found.group(1)
    lines = [
        MARKER,
        f"## Triage automatico preliminare — {now}",
        "",
        f"**Issue:** #{number} · **Componente:** {analysis.component} · **Tipologia:** {analysis.kind}",
        f"**Versione riportata:** {version} (non convalidata con EXE/build).",
        f"**Stato:** `{analysis.state}`; **priorità:** da valutare con evidenze di impatto.",
        "",
        "### Evidenze disponibili",
        analysis.observation,
        "",
        "### Ipotesi (non confermate)",
        analysis.hypothesis,
        "**Cause escluse:** nessuna. Nessuna riproduzione o ispezione end-to-end del codice effettuata dal bot.",
        "",
        "### Informazioni richieste e test consigliati",
    ]
    lines.extend(f"{i}. {entry}" for i, entry in enumerate(analysis.requests, start=1))
    if correlations:
        links = ", ".join(f"#{n}" for n in correlations[:5])
        lines += ["", f"**Possibili segnalazioni correlate (non duplicati confermati):** {links}. Confrontare cause e contesto."]
    lines += [
        "",
        "**Responsabile / prossima azione:** " + analysis.next_step,
        "**PR/commit/release risolutiva:** nessuno verificato. **Collaudo:** non eseguito.",
        "",
        "_Questo commento è prodotto automaticamente con regole conservative. Non costituisce diagnosi,",
        "conferma della priorità, prova di duplicazione o autorizzazione a modificare configurazioni di rete._",
    ]
    return "\n".join(lines)


class Github:
    def __init__(self, repo: str, token: str):
        if not REPO.fullmatch(repo):
            raise ValueError("Invalid GitHub repository name")
        if not token:
            raise ValueError("GITHUB_TOKEN is required")
        self.base = "https://api.github.com/repos/" + repo
        self.token = token

    def api(self, path: str, method: str = "GET", payload=None):
        url = self.base + path
        headers = {
            "Authorization": "Bearer " + self.token,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "winnat-ui-initial-triage",
        }
        data = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(url, headers=headers, data=data, method=method)
        with urlopen(request, timeout=15) as response:
            data = response.read(2_000_000)
        return json.loads(data.decode("utf-8")) if data else None


def issue_labels(issue: dict) -> list[str]:
    return [label["name"] if isinstance(label, dict) else label
            for label in issue.get("labels", [])]


def candidate_fingerprints(api: Github, issue: dict) -> list[int]:
    match = FINGERPRINT.search(issue.get("body") or "")
    if not match:
        return []
    try:
        issues = api.api("/issues?state=all&per_page=100&sort=updated&direction=desc")
    except (HTTPError, URLError, ValueError) as exc:
        print("Correlation lookup unavailable:", type(exc).__name__)
        return []
    return [int(other["number"]) for other in issues
            if other.get("number") != issue["number"]
            and "pull_request" not in other
            and FINGERPRINT.search(other.get("body") or "")
            and FINGERPRINT.search(other.get("body") or "").group(1) == match.group(1)][:5]


def triage(api: Github, issue_number: int, dry_run: bool = False) -> str:
    if issue_number <= 0:
        raise ValueError("Issue number must be a positive integer")
    issue = api.api("/issues/" + str(issue_number))
    if "pull_request" in issue or issue.get("state") != "open":
        return "Not an open Issue: skipped."
    labels = issue_labels(issue)
    current = [name for name in labels if name.startswith(TRIAGE_PREFIX)]
    if any(name != "triage:ricevuto" for name in current):
        return "Already assigned a manual/noninitial triage state: skipped."
    comments = api.api(f"/issues/{issue_number}/comments?per_page=100")
    if any(MARKER in (item.get("body") or "") for item in comments):
        return "Already triaged by automation: skipped."
    analysis = assess(issue.get("title") or "", issue.get("body") or "", issue_number)
    correlations = candidate_fingerprints(api, issue)
    comment = make_comment(issue, analysis, correlations)
    if dry_run:
        print(json.dumps({"title": analysis.suggested_title, "state": analysis.state,
                          "comment": comment}, ensure_ascii=False, indent=2))
        return "Dry run completed (no writes)."
    next_labels = [name for name in labels if not name.startswith(TRIAGE_PREFIX)]
    next_labels.append(analysis.state)
    changes = {"labels": next_labels}
    if analysis.suggested_title:
        changes["title"] = analysis.suggested_title
    api.api("/issues/" + str(issue_number), "PATCH", changes)
    api.api(f"/issues/{issue_number}/comments", "POST", {"body": comment})
    after = api.api("/issues/" + str(issue_number))
    if analysis.state not in issue_labels(after):
        raise RuntimeError("Triage label not persisted by GitHub")
    print(f"Issue #{issue_number}: {analysis.state}; comment created.")
    return "Triage completed."


def main() -> int:
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    token = os.environ.get("GITHUB_TOKEN", "")
    raw = os.environ.get("ISSUE_NUMBER", "")
    if not re.fullmatch(r"[1-9][0-9]{0,9}", raw):
        raise ValueError("ISSUE_NUMBER must be a numeric Issue identifier")
    client = Github(repo, token)
    print(triage(client, int(raw), os.environ.get("DRY_RUN") == "1"))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (HTTPError, URLError, ValueError, RuntimeError) as error:
        print(f"Triage failed: {type(error).__name__}: {error}", file=sys.stderr)
        sys.exit(1)
