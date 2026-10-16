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


    def test_complete_inventory_allows_publication(self):
        p = [("v1.9.15.1", "v1.13.0.1", "HOTFIX")]
        releases = [{"tag_name": "v1.9.15.1", "id": 12,
                     "assets": [{"name": "WinNAT-UI-Windows.zip",
                                 "size": 1500, "digest": "sha256:" + "a" * 64}]}]
        tags = [{"name": "v1.9.15.1", "commit": {"sha": "f" * 40}}]
        self.assertTrue(audit(p, releases, tags)["publish_allowed"])

    def test_missing_digest_blocks_migration(self):
        p = [("v1.9.15.1", "v1.13.0.1", "HOTFIX")]
        releases = [{"tag_name": "v1.9.15.1", "id": 12,
                     "assets": [{"name": "WinNAT-UI-Windows.zip", "size": 1500}]}]
        tags = [{"name": "v1.9.15.1", "commit": {"sha": "f" * 40}}]
        self.assertFalse(audit(p, releases, tags)["publish_allowed"])

    def test_untracked_tags_block_migration(self):
        p = [("v1.9.15.1", "v1.13.0.1", "HOTFIX")]
        releases = [{"tag_name": "v1.9.15.1", "id": 12,
                     "assets": [{"name": "WinNAT-UI-Windows.zip",
                                 "size": 1500, "digest": "sha256:" + "b" * 64}]}]
        tags = [{"name": "v1.9.15.1", "commit": {"sha": "f" * 40}},
                {"name": "v1.10.1", "commit": {"sha": "a" * 40}}]
        self.assertFalse(audit(p, releases, tags)["publish_allowed"])

if __name__ == "__main__":
    unittest.main()
