"""Release helpers driven by version.py and CHANGELOG.md.

  python tools/release.py version          -> print the version (e.g. 1.7.3)
  python tools/release.py notes            -> print the CHANGELOG section of that version
  python tools/release.py bump 1.8.0       -> update version.py and version_info.txt
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


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


def bump(new):
    if not SEMVER.match(new):
        raise SystemExit("Versione non valida (atteso MAJOR.MINOR.PATCH): " + new)
    vp = ROOT / "version.py"
    vp.write_text(re.sub(r'VERSION = "[^"]+"', 'VERSION = "%s"' % new, vp.read_text(encoding="utf-8")), encoding="utf-8")
    vi = ROOT / "version_info.txt"
    text = vi.read_text(encoding="utf-8")
    tup = "(%s, 0)" % ", ".join(SEMVER.match(new).groups())
    text = re.sub(r"(filevers|prodvers)=\([^)]*\)", lambda m: m.group(1) + "=" + tup, text)
    text = re.sub(r"('(?:FileVersion|ProductVersion)', ')[^']*'", lambda m: m.group(1) + new + ".0'", text)
    vi.write_text(text, encoding="utf-8")
    print("Versione impostata a " + new + ". Aggiungi la sezione ## [" + new + "] in CHANGELOG.md.")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "version"
    if cmd == "version":
        print(version())
    elif cmd == "notes":
        sys.stdout.reconfigure(encoding="utf-8")
        print(notes())
    elif cmd == "bump" and len(sys.argv) == 3:
        bump(sys.argv[2])
    else:
        raise SystemExit(__doc__)
