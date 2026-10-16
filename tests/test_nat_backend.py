"""Headless multi-mapping and secondary IPv4 regression coverage."""
import unittest
from unittest.mock import patch
from winnat_ui import nat_backend


class BackendTests(unittest.TestCase):
    def setUp(self):
        self.inventory = {
            "adapters": [{"Name": "LAN"}],
            "interfaces": [{"InterfaceAlias": "LAN", "Dhcp": "Disabled"}],
            "ips": [{"InterfaceAlias": "LAN", "IPAddress": "10.0.0.1", "PrefixLength": 24}],
            "nats": [{"Name": "NAT", "InternalIPInterfaceAddressPrefix": "10.0.0.0/24"}],
            "natMappings": []}

    def test_secondary_is_additive(self):
        with patch("winnat_ui.nat_backend.network.ps", return_value="") as ps:
            self.assertTrue(nat_backend.ensure_secondary_ipv4("LAN", "10.0.0.2", 24, self.inventory))
            self.assertIn("New-NetIPAddress", ps.call_args[0][0])
            self.assertIn("-SkipAsSource $true", ps.call_args[0][0])
            self.assertNotIn("netsh", ps.call_args[0][0])

    def test_secondary_existing_is_noop(self):
        with patch("winnat_ui.nat_backend.network.ps") as ps:
            self.assertFalse(nat_backend.ensure_secondary_ipv4("LAN", "10.0.0.1", 24, self.inventory))
            ps.assert_not_called()

    def test_secondary_dhcp_does_not_get_disabled(self):
        self.inventory["interfaces"][0]["Dhcp"] = "Enabled"
        with self.assertRaisesRegex(ValueError, "DHCP"):
            nat_backend.ensure_secondary_ipv4("LAN", "10.0.0.2", 24, self.inventory)

    def test_mapping_multiple_external_ports(self):
        with patch("winnat_ui.nat_backend.network.ps", return_value="") as ps:
            self.assertTrue(nat_backend.ensure_nat_mapping("NAT", "TCP", 8080, "10.0.0.2", 80, self.inventory))
            self.assertIn("Add-NetNatStaticMapping", ps.call_args[0][0])

    def test_mapping_noop(self):
        self.inventory["natMappings"] = [{"NatName": "NAT", "Protocol": "TCP",
                                          "ExternalPort": 8080, "ExternalIPAddress": "0.0.0.0",
                                          "InternalIPAddress": "10.0.0.2", "InternalPort": 80}]
        with patch("winnat_ui.nat_backend.network.ps") as ps:
            self.assertFalse(nat_backend.ensure_nat_mapping("NAT", "TCP", 8080, "10.0.0.2", 80, self.inventory))
            ps.assert_not_called()

    def test_mapping_conflict(self):
        self.inventory["natMappings"] = [{"NatName": "NAT", "Protocol": 6,
                                          "ExternalPort": 8080, "ExternalIPAddress": "0.0.0.0",
                                          "InternalIPAddress": "10.0.0.3", "InternalPort": 80}]
        with self.assertRaisesRegex(ValueError, "occupato"):
            nat_backend.ensure_nat_mapping("NAT", "TCP", 8080, "10.0.0.2", 80, self.inventory)

    def test_reject_second_nat_and_foreign_subnet(self):
        with self.assertRaises(ValueError):
            nat_backend.ensure_nat_mapping("NAT2", "TCP", 8080, "10.0.0.2", 80, self.inventory)
        with self.assertRaisesRegex(ValueError, "fuori dal prefisso"):
            nat_backend.ensure_nat_mapping("NAT", "TCP", 8080, "192.168.1.2", 80, self.inventory)


if __name__ == "__main__":
    unittest.main()
