"""Regression tests for NAT creation preflight."""
import unittest
import network


class NatPreflightTests(unittest.TestCase):
    def test_empty_inventory_creates(self):
        self.assertEqual(network.nat_add_preflight("NAT-A", "10.0.0.0/24",
                         {"nats": [], "icsConnections": []}), "create")

    def test_identical_is_noop(self):
        inventory = {"nats": [{"Name": "NAT-A", "InternalIPInterfaceAddressPrefix": "10.0.0.0/24",
                               "ExternalIPInterfaceAddressPrefix": None}], "icsConnections": []}
        self.assertEqual(network.nat_add_preflight("NAT-A", "10.0.0.0/24", inventory),
                         "already-present")

    def test_foreign_nat_is_not_a_blocker(self):
        inventory = {"nats": [{"Name": "NAT-Ethernet", "InternalIPInterfaceAddressPrefix": "192.168.192.0/24"}],
                     "icsConnections": []}
        self.assertEqual(network.nat_add_preflight("WinNAT-UI", "192.168.1.0/24", inventory), "create")

    def test_identical_with_other_nats_is_noop(self):
        inventory = {"nats": [
            {"Name": "NAT-A", "InternalIPInterfaceAddressPrefix": "10.0.0.0/24"},
            {"Name": "NAT-B", "InternalIPInterfaceAddressPrefix": "172.20.0.0/16"}]}
        self.assertEqual(network.nat_add_preflight("NAT-A", "10.0.0.0/24", inventory), "already-present")

    def test_same_name_different_prefix_is_conflict(self):
        inventory = {"nats": [{"Name": "NAT-A", "InternalIPInterfaceAddressPrefix": "10.1.0.0/24"}],
                     "icsConnections": []}
        with self.assertRaises(ValueError):
            network.nat_add_preflight("NAT-A", "10.0.0.0/24", inventory)

    def test_ics_inventory_does_not_block_independent_nat(self):
        self.assertEqual(network.nat_add_preflight("NAT-A", "10.0.0.0/24",
            {"nats": [], "icsConnections": [{"Error": "COM failure"}]}), "create")


if __name__ == "__main__":
    unittest.main()
