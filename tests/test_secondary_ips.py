"""Secondary LAN IPv4 UI/backend regression tests; no Windows writes performed."""
import unittest
from unittest.mock import patch

from winnat_ui import network_rollback, secondary_ips


def inventory():
    return {
        "adapters": [{"Name": "LAN", "InterfaceIndex": 8},
                     {"Name": "WAN", "InterfaceIndex": 9}],
        "interfaces": [{"InterfaceAlias": "LAN", "InterfaceIndex": 8,
                        "Dhcp": "Disabled", "Forwarding": "Enabled"},
                       {"InterfaceAlias": "WAN", "InterfaceIndex": 9, "Dhcp": "Enabled"}],
        "ips": [{"InterfaceAlias": "LAN", "InterfaceIndex": 8,
                 "IPAddress": "10.0.0.1", "PrefixLength": 24,
                 "SkipAsSource": False, "PrefixOrigin": "Manual"},
                {"InterfaceAlias": "LAN", "InterfaceIndex": 8,
                 "IPAddress": "10.0.1.1", "PrefixLength": 24,
                 "SkipAsSource": True, "PrefixOrigin": "Manual"},
                {"InterfaceAlias": "WAN", "InterfaceIndex": 9,
                 "IPAddress": "192.0.2.2", "PrefixLength": 24,
                 "SkipAsSource": False, "PrefixOrigin": "Dhcp"}],
        "routes": [], "nats": [], "globalRouter": 0,
    }


class SecondaryIpTests(unittest.TestCase):
    def setUp(self):
        self.data = inventory()

    def test_secondary_and_protected_primary_are_distinguishable(self):
        rows = secondary_ips.lan_rows(self.data, "LAN")
        self.assertEqual(len(rows), 2)
        self.assertEqual(sum(secondary_ips.skip_as_source(r["SkipAsSource"]) for r in rows), 1)

    def test_add_only_sets_secondary_and_never_changes_primary_or_nat(self):
        plan = secondary_ips.plan("add", "LAN", "10.0.2.1", 24, self.data)
        script = secondary_ips.script_for(plan)
        self.assertIn("New-NetIPAddress -InterfaceIndex $index", script)
        self.assertIn("-SkipAsSource $true", script)
        for disallowed in ("Set-NetNat", "Remove-NetNat", "New-NetNat",
                           "DefaultGateway", "netsh.exe", "Set-NetIPInterface"):
            self.assertNotIn(disallowed, script)
        with patch("winnat_ui.secondary_ips.network.ps") as ps:
            secondary_ips.apply(plan)
            ps.assert_called_once_with(script)

    def test_delete_only_selected_secondary(self):
        plan = secondary_ips.plan("remove", "LAN", "10.0.1.1", 24, self.data)
        script = secondary_ips.script_for(plan)
        self.assertIn("Remove-NetIPAddress", script)
        self.assertIn("$_."+"SkipAsSource", script)
        self.assertNotIn("New-NetIPAddress", script)

    def test_edit_moves_one_secondary_without_touching_primary(self):
        plan = secondary_ips.plan("edit", "LAN", "10.0.2.2", 24, self.data,
                                 "10.0.1.1", 24, expected_index=8)
        script = secondary_ips.script_for(plan)
        self.assertLess(script.index("New-NetIPAddress"), script.index("Remove-NetIPAddress"))
        self.assertIn("$old[0] | Remove-NetIPAddress", script)
        scope = network_rollback.scope_for(
            "lan_ip", ("edit", "LAN", "10.0.2.2", 24, "10.0.1.1", 24, 8), self.data)
        self.assertEqual(scope["ip_filter"], {"LAN": {"10.0.2.2", "10.0.1.1"}})
        self.assertEqual(scope["ips"], {"LAN"})
        self.assertFalse(scope["nats"])
        self.assertFalse(scope["routes"])

    def test_edit_prefix_in_place_does_not_delete_address(self):
        p = secondary_ips.plan("edit", "LAN", "10.0.1.1", 25, self.data,
                              "10.0.1.1", 24)
        script = secondary_ips.script_for(p)
        self.assertIn("Set-NetIPAddress -PrefixLength $prefix", script)
        self.assertNotIn("Remove-NetIPAddress", script)

    def test_primary_address_cannot_be_removed_or_edited(self):
        with self.assertRaisesRegex(ValueError, "secondario|principale"):
            secondary_ips.plan("remove", "LAN", "10.0.0.1", 24, self.data)
        with self.assertRaisesRegex(ValueError, "secondario|principale"):
            secondary_ips.plan("edit", "LAN", "10.0.0.3", 24, self.data,
                              "10.0.0.1", 24)

    def test_duplicate_on_other_adapter_or_different_prefix(self):
        for address, prefix in (("192.0.2.2", 24), ("10.0.0.1", 24),
                                ("10.0.1.1", 25)):
            with self.subTest(ip=address, prefix=prefix):
                with self.assertRaises(ValueError):
                    secondary_ips.plan("add", "LAN", address, prefix, self.data)

    def test_other_adapter_subnet_overlap_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "sovrappone"):
            secondary_ips.plan("add", "LAN", "192.0.2.10", 24, self.data)

    def test_dhcp_and_missing_primary_are_rejected(self):
        self.data["interfaces"][0]["Dhcp"] = "Enabled"
        with self.assertRaisesRegex(ValueError, "DHCP"):
            secondary_ips.plan("add", "LAN", "10.0.2.1", 24, self.data)
        self.data["interfaces"][0]["Dhcp"] = "Disabled"
        self.data["ips"] = [ip for ip in self.data["ips"]
                            if ip["IPAddress"] != "10.0.0.1"]
        with self.assertRaisesRegex(ValueError, "principale"):
            secondary_ips.plan("add", "LAN", "10.0.2.1", 24, self.data)

    def test_stale_adapter_index_or_secondary_flag_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "indice"):
            secondary_ips.plan("add", "LAN", "10.0.2.1", 24, self.data,
                              expected_index=15)
        self.data["ips"][1]["SkipAsSource"] = False
        with self.assertRaisesRegex(ValueError, "non secondario"):
            secondary_ips.plan("remove", "LAN", "10.0.1.1", 24, self.data)

    def test_broadcast_multicast_apipa_are_rejected(self):
        for addr in ("10.0.1.0", "10.0.1.255", "224.1.1.1",
                     "169.254.100.1", "127.0.0.1", "0.0.0.0"):
            with self.subTest(address=addr):
                with self.assertRaises(ValueError):
                    secondary_ips.plan("add", "LAN", addr, 24, self.data)

    def test_verified_address_requires_skip_as_source(self):
        p = secondary_ips.plan("add", "LAN", "10.0.2.1", 24, self.data)
        with self.assertRaises(RuntimeError):
            secondary_ips.verify(p, self.data)
        self.data["ips"].append({"InterfaceAlias": "LAN", "InterfaceIndex": 8,
                                 "IPAddress": "10.0.2.1", "PrefixLength": 24,
                                 "SkipAsSource": False})
        with self.assertRaises(RuntimeError):
            secondary_ips.verify(p, self.data)
        self.data["ips"][-1]["SkipAsSource"] = True
        secondary_ips.verify(p, self.data)

    def test_rollback_signature_only_tracks_the_target(self):
        args = ("remove", "LAN", "10.0.1.1", 24, None, None, 8)
        scope = network_rollback.scope_for("lan_ip", args, self.data)
        before = network_rollback.signature(self.data, scope)
        self.data["ips"][0]["IPAddress"] = "10.0.0.5"
        self.assertEqual(before, network_rollback.signature(self.data, scope))
        self.data["ips"][1]["SkipAsSource"] = False
        self.assertNotEqual(before, network_rollback.signature(self.data, scope))


if __name__ == "__main__":
    unittest.main()
