"""Release helpers driven by version.py and CHANGELOG.md.

  python tools/release.py version          -> print the version (e.g. 1.7.3)
  python tools/release.py notes            -> print the CHANGELOG section of that version
  python tools/release.py bump 1.8.0       -> update version.py and version_info.txt
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:\.(\d+))?$")


def version():
    text = (ROOT / "version.py").read_text(encoding="utf-8")
    return re.search(r'VERSION = "([^"]+)"', text).group(1)


def notes(ver=None):
    ver = ver or version()
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    match = re.search(r"^## \[" + re.escape(ver) + r"\][^\n]*\n(.*?)(?=^## \[|\Z)", text, re.S | re.M)
    if not match:
        raise SystemExit("CHANGELOG.md non contiene la sezione ## [" + ver + "]")
    return match.group(1).strip()


def release_kind(previous, current):
    """Classify an actual version change, not an individual CI build."""
    before, after = SEMVER.fullmatch(previous), SEMVER.fullmatch(current)
    if not before or not after:
        raise ValueError("Versione non valida: usare MAJOR.MINOR.PATCH[.HOTFIX].")
    a = tuple(int(x or 0) for x in before.groups())
    b = tuple(int(x or 0) for x in after.groups())
    if a == b:
        return "same"
    if b < a:
        raise ValueError("La versione non può diminuire.")
    if b[0] != a[0]:
        if b != (a[0] + 1, 0, 0, 0):
            raise ValueError("Incremento MAJOR non sequenziale.")
        return "major"
    if b[1] != a[1]:
        if b != (a[0], a[1] + 1, 0, 0):
            raise ValueError("Incremento MINOR non sequenziale.")
        return "minor"
    if b[2] != a[2]:
        if b != (a[0], a[1], a[2] + 1, 0):
            raise ValueError("Incremento PATCH non sequenziale.")
        return "patch"
    if b[3] == a[3] + 1:
        return "hotfix"
    raise ValueError("Incremento HOTFIX non sequenziale.")


def validate_release_notes(kind, current, content=None):
    """A MINOR release needs an actual feature/fix summary, not just a label."""
    if kind not in ("minor", "major"):
        return
    content = notes(current) if content is None else content
    headings = ("### Sintesi", "### Funzionalità", "### Correzioni")
    missing = [h for h in headings if h not in content]
    if missing:
        raise ValueError("Release MINOR senza riepilogo obbligatorio: " + ", ".join(missing))
    for index, heading in enumerate(headings):
        start = content.index(heading) + len(heading)
        next_start = min((content.find("### ", start) if content.find("### ", start) >= 0 else len(content)),
                         len(content))
        section = content[start:next_start]
        if not section.strip() or (heading != "### Sintesi" and not any(
                line.lstrip().startswith("- ") for line in section.splitlines())):
            raise ValueError("La sezione " + heading + " deve contenere informazioni concrete.")
    if len(content.strip()) < 250:
        raise ValueError("Riepilogo MINOR troppo breve: descrivere il valore e le correzioni incluse.")


def publication_gate(previous, current, manual=False, minor_approved=False, content=None):
    """Return whether publication is permitted; CI may always create artifacts."""
    kind = release_kind(previous, current)
    validate_release_notes(kind, current, content)
    if kind == "same":
        return False, kind
    if kind in ("minor", "major") and not (manual and minor_approved):
        return False, kind
    return True, kind


def bump(new):
    if not SEMVER.fullmatch(new):
        raise SystemExit("Versione non valida (atteso MAJOR.MINOR.PATCH[.HOTFIX]): " + new)
    vp = ROOT / "version.py"
    vp.write_text(re.sub(r'VERSION = "[^"]+"', 'VERSION = "%s"' % new, vp.read_text(encoding="utf-8")), encoding="utf-8")
    vi = ROOT / "version_info.txt"
    text = vi.read_text(encoding="utf-8")
    parts = [int(n or 0) for n in SEMVER.fullmatch(new).groups()]
    tup = "(" + ", ".join(map(str, parts)) + ")"
    text = re.sub(r"(filevers|prodvers)=\([^)]*\)", lambda m: m.group(1) + "=" + tup, text)
    text = re.sub(r"('(?:FileVersion|ProductVersion)', ')[^']*'", lambda m: m.group(1) + new + ("" if new.count(".") == 3 else ".0") + "'", text)
    vi.write_text(text, encoding="utf-8")
    print("Versione impostata a " + new + ". Aggiungi la sezione ## [" + new + "] in CHANGELOG.md.")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "version"
    if cmd == "version":
        print(version())
    elif cmd == "notes":
        sys.stdout.reconfigure(encoding="utf-8")
        print(notes())
    elif cmd == "gate" and len(sys.argv) >= 3:
        permitted, kind = publication_gate(
            sys.argv[2], version(),
            manual="--manual" in sys.argv[3:],
            minor_approved="--approved" in sys.argv[3:])
        print(("allowed" if permitted else "blocked") + ":" + kind)
    elif cmd == "bump" and len(sys.argv) == 3:
        bump(sys.argv[2])
    else:
        raise SystemExit(__doc__)
