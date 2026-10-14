"""Rollback unit tests use inventory mocks and never modify host networking."""
import copy
import unittest
from unittest.mock import patch
import network_rollback as rb


def state():
    return {
        "nats": [], "ips": [],
        "routes": [],
        "interfaces": [
            {"InterfaceAlias": "Loopback0", "InterfaceIndex": 39,
             "Dhcp": 0, "Forwarding": 0, "AutomaticMetric": 1, "InterfaceMetric": 25},
            {"InterfaceAlias": "Wi-Fi", "InterfaceIndex": 18,
             "Dhcp": 1, "Forwarding": 0, "AutomaticMetric": 1, "InterfaceMetric": 40}
        ],
        "globalRouter": 0
    }


class RollbackTests(unittest.TestCase):
    def test_scope_of_guide_contains_only_involved_network_interfaces(self):
        before = state()
        p = dict(lan="Loopback0", wan1="Wi-Fi", wan2="",
                 prefix="10.10.10.0/24", gateway="10.10.10.1",
                 nat="NAT-Firewall")
        scope = rb.scope_for("guide", ("apply", p, "fingerprint"), before)
        self.assertEqual(scope["ips"], {"Loopback0"})
        self.assertEqual(scope["forwarding"], {"Loopback0", "Wi-Fi"})
        self.assertEqual(scope["nats"], {"NAT-Firewall"})
        self.assertTrue(scope["router"])

    def test_no_changes_requires_no_mutations(self):
        before = state()
        scope = rb.scope_for("add", ("NAT-Firewall", "10.10.10.0/24"), before)
        with patch("network_rollback.network.collect", return_value=copy.deepcopy(before)), patch(
                "network_rollback.network.ps") as ps:
            result = rb.rollback(before, scope, "backup.json")
        self.assertIn("nessuna differenza", result)
        ps.assert_not_called()

    def test_created_nat_removed_and_final_state_verified(self):
        before = state()
        after = copy.deepcopy(before)
        after["nats"] = [{"Name": "NAT-Firewall",
                          "InternalIPInterfaceAddressPrefix": "10.10.10.0/24"}]
        scope = rb.scope_for("add", ("NAT-Firewall", "10.10.10.0/24"), before)
        with patch("network_rollback.network.collect", side_effect=[after, before]), patch(
                "network_rollback.network.ps") as ps:
            outcome = rb.rollback(before, scope, "backup.json")
        self.assertIn("ROLLBACK VERIFICATO", outcome)
        self.assertIn("Remove-NetNat", ps.call_args.args[0])

    def test_partial_rollback_is_never_claimed_successful(self):
        before = state()
        after = copy.deepcopy(before)
        after["nats"] = [{"Name": "NAT-Firewall",
                          "InternalIPInterfaceAddressPrefix": "10.10.10.0/24"}]
        scope = rb.scope_for("add", ("NAT-Firewall", "10.10.10.0/24"), before)
        with patch("network_rollback.network.collect", return_value=after), patch(
                "network_rollback.network.ps"):
            with self.assertRaisesRegex(RuntimeError, "ROLLBACK INCOMPLETO") as raised:
                rb.rollback(before, scope, "backup.json")
        self.assertIn("DIFFERENZE RESIDUE", str(raised.exception))

    def test_invalid_snapshot_does_not_execute_changes(self):
        before = state()
        scope = rb.scope_for("add", ("NAT-Firewall", "10.10.10.0/24"), before)
        with patch("network_rollback.network.ps") as ps:
            with self.assertRaisesRegex(RuntimeError, "snapshot"):
                rb.rollback(before, scope, "")
        ps.assert_not_called()

    def test_changed_interface_index_prevents_address_write(self):
        before = state()
        after = copy.deepcopy(before)
        after["interfaces"][0]["InterfaceIndex"] = 99
        after["ips"].append({"InterfaceAlias": "Loopback0", "IPAddress": "10.10.10.1", "PrefixLength": 24})
        scope = rb.scope_for("guide", ("apply", dict(lan="Loopback0", wan1="Wi-Fi",
                           wan2="", nat="NAT-Firewall"), "fingerprint"), before)
        with patch("network_rollback.network.collect", return_value=after), patch(
                "network_rollback.network.ps") as ps:
            with self.assertRaisesRegex(RuntimeError, "ROLLBACK INCOMPLETO"):
                rb.rollback(before, scope, "backup.json")
        ps.assert_not_called()


if __name__ == "__main__":
    unittest.main()
