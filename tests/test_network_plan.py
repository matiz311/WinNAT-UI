"""Tests for the legacy LAN/WAN profile, with no changes to the test host."""
import unittest
from unittest.mock import patch

from winnat_ui import network_plan


def inventory(origin="Dhcp"):
    return {
        "adapters": [{"Name": "LAN", "InterfaceIndex": 5},
                     {"Name": "WAN", "InterfaceIndex": 10}],
        "interfaces": [{"InterfaceAlias": "LAN", "InterfaceIndex": 5,
                        "Dhcp": "Enabled" if origin == "Dhcp" else "Disabled"}],
        "ips": [{"InterfaceAlias": "LAN", "InterfaceIndex": 5,
                 "IPAddress": "192.168.1.42" if origin == "Dhcp" else "10.10.10.1",
                 "PrefixLength": 24, "PrefixOrigin": origin}],
        "routes": [{"InterfaceAlias": "WAN", "DestinationPrefix": "0.0.0.0/0",
                    "NextHop": "192.0.2.1"}],
        "icsConnections": [], "nats": [],
    }


class LegacyProfileTests(unittest.TestCase):
    plan = {"lan": "LAN", "wan": "WAN",
            "prefix": "10.10.10.0/24", "gateway": "10.10.10.1"}

    def test_dhcp_conversion_is_applied_before_creating_static_ipv4(self):
        with patch("winnat_ui.network_plan.network.ps", return_value="OK") as ps:
            result = network_plan.apply_profile(self.plan, inventory())
        script = ps.call_args.args[0]
        self.assertLess(script.index("-Dhcp Disabled"), script.index("New-NetIPAddress"))
        self.assertIn("PrefixOrigin -eq 'Dhcp'", script)
        self.assertIn("Remove-NetIPAddress -Confirm:$false", script)
        self.assertIn("-SkipAsSource $skipAsSource", script)
        self.assertFalse(result["existing_ip"])

    def test_dhcp_target_lease_is_not_counted_as_existing_static_ip(self):
        data = inventory()
        data["ips"][0]["IPAddress"] = "10.10.10.1"
        with patch("winnat_ui.network_plan.network.ps", return_value="OK"):
            result = network_plan.apply_profile(self.plan, data)
        self.assertFalse(result["existing_ip"])

    def test_existing_manual_ip_is_not_replaced(self):
        data = inventory(origin="Manual")
        with patch("winnat_ui.network_plan.network.ps", return_value="OK") as ps:
            result = network_plan.apply_profile(self.plan, data)
        self.assertTrue(result["existing_ip"])
        self.assertIn("PrefixOrigin -ne 'Dhcp'", ps.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
