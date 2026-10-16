"""Single physical WinNAT preflight tests."""
import unittest
from winnat_ui import network


class NatPreflightTests(unittest.TestCase):
    def test_direct_add_ignores_other_nat_instances_and_prefixes(self):
        inventory = {"nats": [
            {"Name": "NAT-Ethernet", "InternalIPInterfaceAddressPrefix": "192.168.192.0/24"}]}
        self.assertEqual(network.nat_add_preflight("WinNAT-UI", "192.168.1.0/24", inventory), "create")
        inventory["nats"].append({"Name": "NAT-Other", "InternalIPInterfaceAddressPrefix": "10.77.0.0/16"})
        self.assertEqual(network.nat_add_preflight("NAT-Third", "172.16.0.0/24", inventory), "create")

    def test_direct_add_identical_is_noop(self):
        data = {"nats": [{"Name": "MyNAT", "InternalIPInterfaceAddressPrefix": "192.168.1.0/24"}]}
        self.assertEqual(network.nat_add_preflight("MyNAT", "192.168.1.0/24", data), "already-present")

    def test_direct_add_same_name_different_prefix_is_only_preflight_conflict(self):
        data = {"nats": [{"Name": "MyNAT", "InternalIPInterfaceAddressPrefix": "192.168.1.0/24"}]}
        with self.assertRaisesRegex(ValueError, "configurazione differente"):
            network.nat_add_preflight("MyNAT", "192.168.192.0/24", data)

    def test_direct_add_never_calls_expand_or_remove(self):
        import unittest.mock as mock
        inventory = {"nats": [{"Name": "NAT-Ethernet", "InternalIPInterfaceAddressPrefix": "192.168.192.0/24"}]}
        with mock.patch("winnat_ui.network.ps", return_value="") as ps:
            self.assertEqual(network.nat_add_preflight("NewName", "192.168.1.0/24", inventory), "create")
            network.create_nat("NewName", "192.168.1.0/24")
            script = ps.call_args[0][0]
            self.assertIn("New-NetNat", script)
            self.assertNotIn("Remove-NetNat", script)
            self.assertNotIn("Set-NetNat", script)
            self.assertNotIn("New-NetIPAddress", script)

    def test_empty_inventory_creates_physical_nat(self):
        self.assertEqual(network.nat_network_preflight("NAT", "192.168.1.0/24", {"nats": []}), "create")

    def test_identical_is_covered(self):
        data = {"nats": [{"Name": "NAT", "InternalIPInterfaceAddressPrefix": "192.168.1.0/24"}]}
        self.assertEqual(network.nat_network_preflight("Other", "192.168.1.0/24", data), "already-covered")

    def test_aggregate_covers_two_subnets(self):
        data = {"nats": [{"Name": "NAT-Ethernet", "InternalIPInterfaceAddressPrefix": "192.168.0.0/16"}]}
        for prefix in ("192.168.1.0/24", "192.168.192.0/24"):
            self.assertEqual(network.nat_network_preflight("WinNAT-UI", prefix, data), "already-covered")

    def test_insufficient_existing_prefix_requires_expansion(self):
        data = {"nats": [{"Name": "NAT-Ethernet", "InternalIPInterfaceAddressPrefix": "192.168.192.0/24"}]}
        self.assertEqual(network.nat_network_preflight("WinNAT-UI", "192.168.1.0/24", data), "expand")
        self.assertEqual(network.shared_nat_prefix("192.168.192.0/24", "192.168.1.0/24"),
                         "192.168.0.0/16")
        script = network.nat_expansion_script("192.168.1.0/24", data)
        self.assertIn("$newPrefix = '192.168.0.0/16'", script)
        self.assertIn("$name = 'NAT-Ethernet'", script)
        self.assertIn("Get-NetNatStaticMapping", script)
        self.assertIn("Restore-Mappings", script)
        self.assertIn("RIPRISTINO INCOMPLETO", script)
        self.assertIn("Get-NetNatExternalAddress", script)
        self.assertNotIn("New-NetIPAddress", script)

    def test_two_physical_nats_are_not_created(self):
        data = {"nats": [
            {"Name": "NAT-A", "InternalIPInterfaceAddressPrefix": "192.168.1.0/24"},
            {"Name": "NAT-B", "InternalIPInterfaceAddressPrefix": "192.168.192.0/24"}]}
        with self.assertRaisesRegex(ValueError, "WinNAT rilevati"):
            network.nat_network_preflight("NAT-C", "192.168.1.0/24", data)


if __name__ == "__main__":
    unittest.main()
