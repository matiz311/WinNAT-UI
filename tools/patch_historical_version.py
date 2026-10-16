"""Rebuild a historical source checkout with only its version identity changed.

No network access, no Git operations, no app feature patches.
Every replacement is deliberately narrow and verified before packaging.
"""
import argparse
from pathlib import Path
import re

VERSION = re.compile(r"^\d+\.\d+\.\d+(?:\.\d+)?$")


def update_version(source: Path, old: str, new: str):
    if not VERSION.fullmatch(old) or not VERSION.fullmatch(new):
        raise ValueError("Unexpected version syntax")
    app_path = source / "app.py"
    app = app_path.read_text(encoding="utf-8")
    version_path = source / "version.py"
    if version_path.exists():
        old_text = version_path.read_text(encoding="utf-8")
        pattern = r'(?m)^VERSION = "' + re.escape(old) + r'"$'
        updated, count = re.subn(pattern, 'VERSION = "' + new + '"', old_text)
        if count != 1:
            raise ValueError("Unexpected version.py version for " + old)
        version_path.write_text(updated, encoding="utf-8")
    else:
        # Before 1.7.5, app.py itself declares VERSION.
        pattern = r'(?m)^VERSION = "' + re.escape(old) + r'"$'
        updated, count = re.subn(pattern, 'VERSION = "' + new + '"', app)
        if not count and old == "1.2.0":
            # Original 1.2.0 window title contained the acknowledged 1.1.0 typo.
            needle = 'self.title("WinNAT UI 1.1.0 | Windows NAT Manager")'
            if app.count(needle) != 1:
                raise ValueError("Missing legacy 1.2.0 title")
            updated = app.replace(needle, 'self.title("WinNAT UI ' + new + ' | Windows NAT Manager")')
            count = 1
        if count != 1:
            raise ValueError("Unexpected app.py VERSION for " + old)
        app_path.write_text(updated, encoding="utf-8")

    info_path = source / "version_info.txt"
    text = info_path.read_text(encoding="utf-8")
    parts = [int(p) for p in new.split(".")]
    parts += [0] * (4 - len(parts))
    vers = "(" + ", ".join(str(p) for p in parts) + ")"
    for key in ("filevers", "prodvers"):
        text, count = re.subn(r"(?m)^(\s*" + key + r"=)\([^)]*\)",
                              lambda m: m.group(1) + vers, text)
        if count != 1:
            raise ValueError("Expected exactly one " + key)
    win_version = new if new.count(".") == 3 else new + ".0"
    for key in ("FileVersion", "ProductVersion"):
        text, count = re.subn(
            r"('"+key+r"',\s*')[^']+'",
            lambda m: m.group(1) + win_version + "'", text)
        if count != 1:
            raise ValueError("Expected exactly one " + key)
    info_path.write_text(text, encoding="utf-8")
    if win_version not in text:
        raise ValueError("Version resource not written")
    print("Rebuild version identity " + old + " -> " + new)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("source", type=Path)
    p.add_argument("old")
    p.add_argument("new")
    args = p.parse_args()
    update_version(args.source, args.old, args.new)
