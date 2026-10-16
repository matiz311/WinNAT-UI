"""Offline regression tests for migration failure and recovery paths.

All external commands are mocked: no tags or Releases are modified.
"""
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch, call as mock_call
from subprocess import CompletedProcess

sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))
import execute_semver_migration as migration
import restore_semver_history


class MigrationSafetyTests(unittest.TestCase):
    def test_call_reports_missing_stderr_instead_of_type_error(self):
        process = CompletedProcess(["git", "push"], 1, stdout=None, stderr=None)
        with patch.object(migration.subprocess, "run", return_value=process):
            with self.assertRaisesRegex(RuntimeError, "unknown subprocess error"):
                migration.call("git", "push", "origin", "refs/tags/test")

    @patch.dict(os.environ, {"GITHUB_RUN_ID": "123456789"}, clear=False)
    def test_permission_probe_rejects_failed_git_push(self):
        events = []

        def command(*args, **kwargs):
            events.append(args)
            if args[:3] == ("git", "push", "origin"):
                raise RuntimeError("Insufficient workflow permission")
            return ""

        no_release = CompletedProcess([], 1, "", "release not found")
        no_ref = CompletedProcess([], 1, "", "HTTP 404")
        local_cleanup = CompletedProcess([], 0, "", "")
        with patch.object(migration, "call", side_effect=command), patch.object(
                migration.subprocess, "run",
                side_effect=[no_release, no_ref, local_cleanup]):
            with self.assertRaisesRegex(RuntimeError, "Insufficient workflow permission"):
                migration._probe_publishing_permissions("a" * 40)
        self.assertEqual(events[0][:2], ("git", "tag"))
        self.assertEqual(events[1][:3], ("git", "push", "origin"))
        self.assertFalse(any(e[:3] == ("gh", "release", "create") for e in events))

    @patch.dict(os.environ, {"GITHUB_RUN_ID": "123456789"}, clear=False)
    def test_permission_probe_cleans_remote_test_refs(self):
        ok = CompletedProcess([], 0, "", "")
        commands = []
        with patch.object(migration, "call", side_effect=lambda *args, **kw: commands.append(args)), patch.object(
                migration.subprocess, "run", side_effect=[ok, ok, ok]):
            migration._probe_publishing_permissions("a" * 40)
        self.assertTrue(any(e[:3] == ("gh", "release", "delete") for e in commands))
        self.assertTrue(any(e[:3] == ("gh", "api", "-X") and "DELETE" in e for e in commands))

    def test_rollback_uses_rest_recovery_not_force_push(self):
        with patch.object(restore_semver_history, "main") as restore, patch.object(
                migration, "call") as command:
            migration._restore({"original_releases": []}, Path("/virtual-backup"), [])
        restore.assert_called_once_with(Path("/virtual-backup"))
        command.assert_not_called()


if __name__ == "__main__":
    unittest.main()
