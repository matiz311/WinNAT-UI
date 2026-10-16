import unittest
from tools.migrate_release_history import audit, parse_plan, version_tuple


class MigrationTests(unittest.TestCase):
    def test_four_digits_are_ordered(self):
        self.assertLess(version_tuple("v1.13.0"), version_tuple("v1.13.0.1"))
        self.assertLess(version_tuple("v1.13.0.2"), version_tuple("v1.13.1"))

    def test_duplicate_target_rejected(self):
        source = ("| `v1.2.0` | `v1.2.0` | MINOR |\n"
                  "| `v1.3.0` | `v1.2.0` | PATCH |")
        with self.assertRaises(ValueError):
            parse_plan(source)

    def test_missing_asset_blocks_publication(self):
        p = [("v1.9.15.1", "v1.13.0.1", "HOTFIX")]
        releases = [{"tag_name": "v1.9.15.1", "id": 12, "assets": []}]
        tags = [{"name": "v1.9.15.1"}]
        self.assertFalse(audit(p, releases, tags)["publish_allowed"])


if __name__ == "__main__":
    unittest.main()
