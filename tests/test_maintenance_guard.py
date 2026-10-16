"""Unit tests for the PR #68 maintenance guard (no GitHub API needed)."""
import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import maintenance_guard as guard


class MaintenanceRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.history = json.loads((guard.ROOT / guard.HISTORY).read_text(encoding="utf-8"))
        cls.status = json.loads((guard.ROOT / guard.STATUS).read_text(encoding="utf-8"))

    def documents(self):
        return copy.deepcopy(self.history), copy.deepcopy(self.status)

    def test_bootstrap_is_explicitly_unknown(self):
        history, status = self.documents()
        guard.validate(history, status)
        self.assertTrue(all(v["status"] == "unknown" for v in status["services"].values()))

    def test_status_cannot_claim_operational_without_observation(self):
        history, status = self.documents()
        status["services"]["github-releases"]["status"] = "operational"
        with self.assertRaisesRegex(ValueError, "observation"):
            guard.validate(history, status)

    def test_reject_duplicate_maintenance_ids(self):
        history, status = self.documents()
        history["events"].append(copy.deepcopy(history["events"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            guard.validate(history, status)

    def test_reject_invalid_timestamp(self):
        history, status = self.documents()
        history["events"][0]["registered_at"] = "2026-10-16T12:30:00+02:00"
        with self.assertRaisesRegex(ValueError, "UTC"):
            guard.validate(history, status)

    def test_completed_event_requires_verified_evidence(self):
        history, status = self.documents()
        event = history["events"][0]
        event["status"] = "completed"
        event["evidence"] = []
        event["started_at"] = "2026-10-16T22:30:00Z"
        event["ended_at"] = "2026-10-16T22:40:00Z"
        with self.assertRaisesRegex(ValueError, "verification evidence"):
            guard.validate(history, status)

    def test_no_unknown_event_reference(self):
        history, status = self.documents()
        status["services"]["bug-gateway"]["event_id"] = "MAINT-20260101-999"
        with self.assertRaisesRegex(ValueError, "unknown maintenance"):
            guard.validate(history, status)

    def test_missing_prior_registration_fails_pr(self):
        def fake_git(*args):
            if args[0] == "merge-base":
                return "base"
            if args[0] == "rev-list":
                return "change"
            if args[0] == "diff-tree":
                return ".github/workflows/new.yml"
            if args[0] == "rev-parse":
                return "previous"
            raise AssertionError(args)
        with (patch.object(guard, "git", side_effect=fake_git),
              patch.object(guard, "at_commit", return_value={"events": []})):
            with self.assertRaisesRegex(ValueError, "PREVIOUS-COMMIT"):
                guard.check_pr("base", 68)

    def test_prior_registration_allows_workflow_change(self):
        event = copy.deepcopy(self.history["events"][0])
        event["status"] = "planned"

        def fake_git(*args):
            if args[0] == "merge-base":
                return "base"
            if args[0] == "rev-list":
                return "change"
            if args[0] == "diff-tree":
                return ".github/workflows/new.yml"
            if args[0] == "rev-parse":
                return "previous"
            raise AssertionError(args)

        def fake_registry(commit, path):
            return {"events": [] if commit == "base" else [event]}
        with (patch.object(guard, "git", side_effect=fake_git),
              patch.object(guard, "at_commit", side_effect=fake_registry)):
            guard.check_pr("base", 68)


if __name__ == "__main__":
    unittest.main()
