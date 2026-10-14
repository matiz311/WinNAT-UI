"""Unit tests for Windows 11 NAT/router profile planning; no host modifications."""
import copy
import unittest
from unittest.mock import patch
import network_guide as guide


def inventory():
    return {
        "adapters": [{"Name":n,"Status":"Up","InterfaceIndex":i} for n,i in
                     [("Ethernet",5),("USB-C",10),("Wi-Fi",11)]],
        "interfaces": [{"InterfaceAlias":n, "InterfaceIndex":i,"Forwarding":"Disabled",
                        "Dhcp":"Enabled","AutomaticMetric":"Enabled","InterfaceMetric":25}
                       for n,i in [("Ethernet",5),("USB-C",10),("Wi-Fi",11)]],
        "ips": [{"InterfaceAlias":"Ethernet","IPAddress":"192.168.90.254",
                 "InterfaceIndex":5,"PrefixLength":24,"AddressState":"Preferred"}],
        "routes": [{"InterfaceAlias":"Ethernet","DestinationPrefix":"192.168.90.0/24",
                    "InterfaceIndex":5,"NextHop":"0.0.0.0","RouteMetric":256},
                   {"InterfaceAlias":"USB-C","DestinationPrefix":"0.0.0.0/0",
                    "InterfaceIndex":10,"NextHop":"10.0.0.1","RouteMetric":0},
                   {"InterfaceAlias":"Wi-Fi","DestinationPrefix":"0.0.0.0/0",
                    "InterfaceIndex":11,"NextHop":"10.1.0.1","RouteMetric":0}],
        "nats": [], "icsConnections": [],"globalRouter":0
    }


class GuideTests(unittest.TestCase):
    def setUp(self):
        self.profile = dict(guide.DEFAULTS)
        self.data = inventory()

    def test_apply_from_existing_lan(self):
        lines = guide.preview("apply", self.profile, self.data)
        self.assertTrue(any("DHCP IPv4 disabilitato" in line for line in lines))
        self.assertTrue(any("IPEnableRouter = 1" in line for line in lines))
        fp = guide.fingerprint(self.profile, self.data)
        with patch("network_guide.network.snapshot",return_value="backup.json"),patch(
                "network_guide.network.ps",return_value="OK") as call:
            result=guide.execute("apply",self.profile,self.data,fp)
        text=call.call_args.args[0]
        self.assertIn("Set-NetIPInterface -InterfaceAlias $wan1",text)
        self.assertIn("InterfaceMetric 10",text)
        self.assertIn("InterfaceMetric 50",text)
        self.assertIn("New-NetNat -Name 'NAT-Firewall'",text)
        self.assertIn("Remove-NetRoute",text)
        self.assertIn("Remove-NetIPAddress",text)
        self.assertEqual(result["backup"],"backup.json")

    def test_disable_preserves_ip_addresses(self):
        self.data["nats"]=[{"Name":"FromAnotherApp","InternalIPInterfaceAddressPrefix":"10.10.10.0/24"}]
        fp=guide.fingerprint(self.profile,self.data)
        with patch("network_guide.network.snapshot",return_value="x"),patch(
                "network_guide.network.ps",return_value="") as call:
            guide.execute("disable",self.profile,self.data,fp)
        text=call.call_args.args[0]
        self.assertIn("Remove-NetNat",text)
        self.assertIn("IPEnableRouter -Value 0",text)
        self.assertNotIn("Remove-NetIPAddress",text)
        self.assertNotIn("AutomaticMetric Enabled",text)

    def test_reset_cleans_regardless_of_owner(self):
        self.data["nats"]=[{"Name":"NotManaged","InternalIPInterfaceAddressPrefix":"192.168.90.0/24"}]
        fp=guide.fingerprint(self.profile,self.data)
        with patch("network_guide.network.snapshot",return_value="x"),patch(
                "network_guide.network.ps",return_value="") as call,patch(
                "network_guide.network.managed_state",return_value=None):
            guide.execute("reset",self.profile,self.data,fp)
        text=call.call_args.args[0]
        self.assertIn("Remove-NetNat",text)
        self.assertIn("Remove-NetIPAddress",text)
        self.assertIn("Remove-NetRoute",text)
        self.assertIn("AutomaticMetric Enabled",text)
        self.assertIn("Dhcp Enabled",text)
        self.assertIn("IPEnableRouter -Value 0",text)

    def test_detect_conflicts_before_apply(self):
        self.data["nats"]=[{"Name":"HyperV","InternalIPInterfaceAddressPrefix":"172.20.0.0/16"}]
        with self.assertRaisesRegex(ValueError,"WinNAT"):
            guide.validate(self.profile,self.data,"apply")

    def test_changes_since_preview_block_commit(self):
        fp=guide.fingerprint(self.profile,self.data)
        newer=copy.deepcopy(self.data)
        newer["routes"].append({"InterfaceAlias":"Ethernet","DestinationPrefix":"0.0.0.0/0",
                                 "InterfaceIndex":5,"NextHop":"1.1.1.1","RouteMetric":1})
        with patch("network_guide.network.ps") as ps:
            with self.assertRaisesRegex(ValueError,"modificata"):
                guide.execute("reset",self.profile,newer,fp)
        ps.assert_not_called()

    def test_wan_aliases_distinct(self):
        self.profile["wan1"] = "Ethernet"
        with self.assertRaisesRegex(ValueError,"distinte"):
            guide.validate(self.profile,self.data,"apply")

    def test_secondary_wan_can_be_omitted(self):
        self.profile["wan2"] = ""
        self.assertEqual(guide.validate(self.profile,self.data,"apply")["wan2"],"")

    def test_unknown_action_is_rejected(self):
        with self.assertRaises(ValueError):
            guide.validate(self.profile,self.data,"delete-all")


if __name__ == "__main__":
    unittest.main()
