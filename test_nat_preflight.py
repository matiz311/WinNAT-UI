"""Single physical WinNAT preflight tests."""
import unittest
import network


class NatPreflightTests(unittest.TestCase):
    def test_empty_inventory_creates_physical_nat(self):
        self.assertEqual(network.nat_add_preflight("NAT", "192.168.1.0/24", {"nats": []}), "create")

    def test_identical_is_covered(self):
        data = {"nats": [{"Name": "NAT", "InternalIPInterfaceAddressPrefix": "192.168.1.0/24"}]}
        self.assertEqual(network.nat_add_preflight("Other", "192.168.1.0/24", data), "already-covered")

    def test_aggregate_covers_two_subnets(self):
        data = {"nats": [{"Name": "NAT-Ethernet", "InternalIPInterfaceAddressPrefix": "192.168.0.0/16"}]}
        for prefix in ("192.168.1.0/24", "192.168.192.0/24"):
            self.assertEqual(network.nat_add_preflight("WinNAT-UI", prefix, data), "already-covered")

    def test_insufficient_existing_prefix_requires_expansion(self):
        data = {"nats": [{"Name": "NAT-Ethernet", "InternalIPInterfaceAddressPrefix": "192.168.192.0/24"}]}
        with self.assertRaisesRegex(ValueError, "prefisso interno aggregato"):
            network.nat_add_preflight("WinNAT-UI", "192.168.1.0/24", data)

    def test_two_physical_nats_are_not_created(self):
        data = {"nats": [
            {"Name": "NAT-A", "InternalIPInterfaceAddressPrefix": "192.168.1.0/24"},
            {"Name": "NAT-B", "InternalIPInterfaceAddressPrefix": "192.168.192.0/24"}]}
        with self.assertRaisesRegex(ValueError, "più istanze"):
            network.nat_add_preflight("NAT-C", "192.168.1.0/24", data)


if __name__ == "__main__":
    unittest.main()
