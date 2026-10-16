"""Offline and stale-status tests for advisory maintenance detection."""
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from winnat_ui import maintenance


class MaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)
        self.record = {
            "schema_version": 1,
            "updated_at": "2026-10-17T11:58:00Z",
            "services": {"github-releases": {
                "status": "maintenance", "event_id": "MAINT-20261017-001"}}}

    def test_fresh_status_recognized(self):
        result = maintenance.parse_status(self.record, now=self.now)
        self.assertEqual(result["github-releases"]["status"], "maintenance")

    def test_missing_or_stale_timestamp_is_unknown(self):
        for date in [None, "2026-10-16T11:00:00Z",
                     "2026-10-17T13:00:00Z", "invalid"]:
            with self.subTest(date=date):
                record = dict(self.record, updated_at=date)
                self.assertEqual(maintenance.parse_status(record, now=self.now), {})

    def test_invalid_state_never_reports_maintenance(self):
        record = dict(self.record, services={"github-releases": {
            "status": "anything", "event_id": None}})
        self.assertEqual(maintenance.parse_status(record, now=self.now), {})

    def test_network_failure_is_nonblocking(self):
        with patch("winnat_ui.maintenance.urllib.request.urlopen",
                   side_effect=OSError("offline")):
            self.assertEqual(maintenance.current_services(), {})

    def test_hint_requires_confirmed_fresh_maintenance_status(self):
        with patch("winnat_ui.maintenance.current_services",
                   return_value={"github-releases": {
                       "status": "maintenance", "event_id": "MAINT-20261017-001"}}):
            hint = maintenance.maintenance_hint()
        self.assertIn("possibile correlazione", hint)
        self.assertIn("MAINT-20261017-001", hint)
        with patch("winnat_ui.maintenance.current_services", return_value={}):
            self.assertIsNone(maintenance.maintenance_hint())


if __name__ == "__main__":
    unittest.main()
