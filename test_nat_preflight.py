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

    def test_foreign_nat_blocked_with_name_and_prefix(self):
        inventory = {"nats": [{"Name": "HyperV", "InternalIPInterfaceAddressPrefix": "172.20.0.0/16"}],
                     "icsConnections": []}
        with self.assertRaisesRegex(ValueError, r"HyperV.*172.20.0.0/16"):
            network.nat_add_preflight("NAT-A", "10.0.0.0/24", inventory)

    def test_same_name_different_prefix_is_conflict(self):
        inventory = {"nats": [{"Name": "NAT-A", "InternalIPInterfaceAddressPrefix": "10.1.0.0/24"}],
                     "icsConnections": []}
        with self.assertRaises(ValueError):
            network.nat_add_preflight("NAT-A", "10.0.0.0/24", inventory)

    def test_ics_unverified_is_blocked(self):
        with self.assertRaisesRegex(ValueError, "non verificabile"):
            network.nat_add_preflight("NAT-A", "10.0.0.0/24",
                {"nats": [], "icsConnections": [{"Error": "COM failure"}]})


if __name__ == "__main__":
    unittest.main()
