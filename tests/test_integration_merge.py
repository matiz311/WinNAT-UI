"""Integration checks for DHCP-to-static and secondary IPv4 on a shared LAN."""
import unittest
from winnat_ui import network_guide, secondary_ips

class GatewayIntegrationTests(unittest.TestCase):
    def fixture(self, dhcp):
        return {
            "adapters": [{"Name": "LAN", "InterfaceIndex": 8}, {"Name": "WAN", "InterfaceIndex": 9}],
            "interfaces": [{"InterfaceAlias": "LAN", "InterfaceIndex": 8,
                            "Dhcp": "Enabled" if dhcp else "Disabled"},
                           {"InterfaceAlias": "WAN", "InterfaceIndex": 9, "Dhcp": "Enabled"}],
            "ips": [{"InterfaceAlias": "LAN", "InterfaceIndex": 8,
                     "IPAddress": "192.168.1.100" if dhcp else "10.10.10.1",
                     "PrefixLength": 24, "PrefixOrigin": "Dhcp" if dhcp else "Manual",
                     "SkipAsSource": False}],
            "routes": [], "nats": [], "icsConnections": []
        }

    def test_dhcp_default_then_secondary_setup(self):
        data = self.fixture(True)
        detected = network_guide.detect_lan_subnet(data, "LAN")
        self.assertEqual((detected["prefix"], detected["gateway"]), ("10.10.10.0/24", "10.10.10.1"))
        with self.assertRaisesRegex(ValueError, "DHCP"):
            secondary_ips.plan("add", "LAN", "10.10.20.1", 24, data)
        result = secondary_ips.plan("add", "LAN", "10.10.20.1", 24, self.fixture(False))
        self.assertEqual((result["ip"], result["index"]), ("10.10.20.1", 8))

    def test_secondary_does_not_override_primary_gateway(self):
        data = self.fixture(False)
        data["ips"].append({"InterfaceAlias": "LAN", "InterfaceIndex": 8,
                            "IPAddress": "10.10.9.1", "PrefixLength": 24,
                            "PrefixOrigin": "Manual", "SkipAsSource": True})
        self.assertEqual(network_guide.detect_lan_subnet(data, "LAN")["gateway"], "10.10.10.1")
