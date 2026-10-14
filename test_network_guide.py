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

    def test_failed_commit_includes_inventory_before_and_after(self):
        fp = guide.fingerprint(self.profile, self.data)
        post = dict(self.data)
        post["globalRouter"] = 1
        with patch("network_guide.network.snapshot", return_value="x"), patch(
                "network_guide.network.ps", side_effect=RuntimeError("netsh exit 1")), patch(
                "network_guide.network.collect", return_value=post):
            with self.assertRaisesRegex(RuntimeError, "OPERAZIONE GUIDATA FALLITA") as caught:
                guide.execute("apply", self.profile, self.data, fp)
        message = str(caught.exception)
        self.assertIn("ERRORE ORIGINALE:", message)
        self.assertIn("netsh exit 1", message)
        self.assertIn("CONFIGURAZIONE RILEVATA PRIMA", message)
        self.assertIn("CONFIGURAZIONE RILEVATA DOPO", message)
        self.assertIn('"globalRouter": 1', message)
        self.assertIn("IPv4 atteso: 10.10.10.1/24", message)

    def test_inventory_failure_preserves_original_error(self):
        fp = guide.fingerprint(self.profile, self.data)
        with patch("network_guide.network.snapshot", return_value="x"), patch(
                "network_guide.network.ps", side_effect=RuntimeError("original failure")), patch(
                "network_guide.network.collect", side_effect=RuntimeError("inventory failure")):
            with self.assertRaises(RuntimeError) as caught:
                guide.execute("apply", self.profile, self.data, fp)
        self.assertIn("original failure", str(caught.exception))
        self.assertIn("inventory failure", str(caught.exception))

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
        self.assertIn("netsh.exe interface ipv4 set address",text)
        self.assertIn('"source=static"',text)
        self.assertIn('"gateway=none"',text)
        self.assertIn('"store=persistent"',text)
        self.assertIn("255.255.255.0",text)
        self.assertIn("10.10.10.1",text)
        self.assertIn("Get-NetIPInterface -InterfaceAlias $lan",text)
        self.assertNotIn("New-NetIPAddress",text)
        self.assertNotIn("Remove-NetIPAddress",text)
        self.assertEqual(result["backup"],"backup.json")

    def test_static_lan_checks_existing_address_before_netsh(self):
        fp = guide.fingerprint(self.profile, self.data)
        with patch("network_guide.network.snapshot", return_value="x"), patch(
                "network_guide.network.ps", return_value="") as call:
            guide.execute("apply", self.profile, self.data, fp)
        script = call.call_args.args[0]
        self.assertIn("$duplicate = @(Get-NetIPAddress", script)
        self.assertIn("$_ .InterfaceIndex".replace(" ", ""), script)
        self.assertIn("$alreadyConfigured =", script)
        self.assertIn("if (-not $alreadyConfigured) {", script)
        self.assertIn("$netshExitCode = $LASTEXITCODE", script)
        self.assertIn("$validState =", script)
        self.assertIn("if (-not $validState) {", script)
        self.assertIn("IPv4 rilevati=[", script)
        self.assertNotIn("if ($LASTEXITCODE -ne 0) { throw ('Impossibile impostare IP statico LAN", script)

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
        self.assertIn('"source=dhcp"',text)
        self.assertIn("netsh.exe interface ipv4 set address",text)
        self.assertNotIn("New-NetIPAddress",text)
        self.assertIn("Remove-NetRoute",text)
        self.assertIn("AutomaticMetric Enabled",text)
        self.assertIn("IPEnableRouter -Value 0",text)

    def test_reset_dhcp_is_idempotent(self):
        """When DHCP is already enabled, reset must not fail on netsh exit 1."""
        fp = guide.fingerprint(self.profile, self.data)
        with patch("network_guide.network.snapshot", return_value="x"), patch(
                "network_guide.network.ps", return_value="") as call, patch(
                "network_guide.network.managed_state", return_value=None):
            guide.execute("reset", self.profile, self.data, fp)
        script = call.call_args.args[0]
        self.assertIn("if ($lanDhcp -ne 'Enabled') {", script)
        self.assertIn("$netshExitCode = $LASTEXITCODE", script)
        self.assertIn("if ($lanDhcp -ne 'Enabled') { throw", script)
        self.assertIn("LAN: DHCP IPv4 non attivo", script)
        self.assertIn("Remove-NetRoute", script)

    def test_apply_after_partial_failed_commit(self):
        """Previous 1.6.0 commit may have removed LAN IP and disabled DHCP."""
        self.data["ips"] = []
        self.data["routes"] = [r for r in self.data["routes"]
                               if r["InterfaceAlias"] != "Ethernet"]
        self.data["interfaces"][0]["Dhcp"] = "Disabled"
        fp = guide.fingerprint(self.profile, self.data)
        with patch("network_guide.network.snapshot", return_value="x"), patch(
                "network_guide.network.ps", return_value="") as call:
            guide.execute("apply", self.profile, self.data, fp)
        text = call.call_args.args[0]
        self.assertIn('"source=static"', text)
        self.assertIn("gateway=none", text)
        self.assertNotIn("New-NetIPAddress", text)

    def test_static_setup_with_non_default_subnet(self):
        self.profile["prefix"] = "192.168.192.0/25"
        self.profile["gateway"] = "192.168.192.126"
        fp = guide.fingerprint(self.profile, self.data)
        with patch("network_guide.network.snapshot", return_value="x"), patch(
                "network_guide.network.ps", return_value="") as call:
            guide.execute("apply", self.profile, self.data, fp)
        text = call.call_args.args[0]
        self.assertIn("255.255.255.128", text)
        self.assertIn("192.168.192.126", text)
        self.assertIn('"gateway=none"', text)

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
