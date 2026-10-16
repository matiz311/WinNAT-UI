"""Single source of truth for the WinNAT UI version.

Change ONLY this value when preparing a release, then add the matching
section to CHANGELOG.md. CI derives the Windows file version, the git tag
and the release notes from here; test_version.py fails if anything drifts.
"""
VERSION = "1.15.1"
