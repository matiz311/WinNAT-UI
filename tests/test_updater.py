"""GitHub updater tests run without writing to Windows installation directories."""
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from winnat_ui import updater


class UpdaterTests(unittest.TestCase):
    def test_version_comparison_is_numeric(self):
        self.assertTrue(updater.newer("v1.9.11", "1.9.2"))
        self.assertFalse(updater.newer("v1.9.2", "1.9.2"))
        self.assertFalse(updater.newer("v1.9.1", "1.9.2"))
        with self.assertRaises(ValueError):
            updater.newer("v1.9.3-rc1", "1.9.2")

    def test_four_digit_hotfix_updates(self):
        self.assertTrue(updater.newer("v1.9.15.1", "1.9.15"))
        self.assertFalse(updater.newer("v1.9.15", "1.9.15.1"))
        self.assertTrue(updater.newer("v1.9.16", "1.9.15.9"))
        self.assertFalse(updater.newer("v1.9.15.0", "1.9.15"))

    def test_semver_history_cutover_to_114(self):
        # Original published identifiers can still update to the first
        # post-migration MINOR. The latest release always wins.
        for installed in ("1.9.15", "1.9.15.1", "1.10.0",
                          "1.12.5", "1.13.0", "1.13.0.1"):
            with self.subTest(installed=installed):
                self.assertTrue(updater.newer("v1.14.0", installed))
        self.assertFalse(updater.newer("v1.13.0.1", "1.14.0"))

    def test_github_http_failures_are_actionable(self):
        from urllib.error import HTTPError, URLError
        cases = [(404, "Nessuna release stabile"),
                 (403, "Accesso alle API"),
                 (429, "Accesso alle API"),
                 (502, "temporaneamente non disponibile"),
                 (418, "ha rifiutato")]
        for code, expected in cases:
            with self.subTest(code=code):
                problem = HTTPError(updater.API_URL, code, "remote error", None, None)
                with patch("winnat_ui.updater.urllib.request.urlopen", side_effect=problem):
                    with self.assertRaisesRegex(ValueError, expected):
                        updater.release_info("1.14.0")
        for problem in (URLError("DNS failure"), TimeoutError("connection timed out")):
            with self.subTest(problem=type(problem).__name__):
                with patch("winnat_ui.updater.urllib.request.urlopen", side_effect=problem):
                    with self.assertRaisesRegex(ValueError, "connessione, DNS e proxy"):
                        updater.release_info("1.14.0")

    def test_update_errors_expose_stable_reason_phase_and_status(self):
        from urllib.error import HTTPError, URLError
        mapping = {404: "no_published_release", 403: "rate_limited",
                   429: "rate_limited", 503: "service_unavailable",
                   418: "http_failure"}
        for status, reason in mapping.items():
            with self.subTest(status=status):
                error = HTTPError(updater.API_URL, status, "test", None, None)
                with patch("winnat_ui.updater.urllib.request.urlopen",
                           side_effect=error):
                    with self.assertRaises(updater.UpdateChannelError) as ctx:
                        updater.release_info("1.14.0")
                self.assertIsInstance(ctx.exception, ValueError)
                self.assertEqual(ctx.exception.reason, reason)
                self.assertEqual(ctx.exception.phase, "release_lookup")
                self.assertEqual(ctx.exception.http_status, status)
        with patch("winnat_ui.updater.urllib.request.urlopen",
                   side_effect=URLError("offline")):
            with self.assertRaises(updater.UpdateChannelError) as ctx:
                updater.release_info("1.14.0")
        self.assertEqual(ctx.exception.reason, "network_failure")
        self.assertIsNone(ctx.exception.http_status)

    def test_missing_duplicate_and_invalid_assets_are_classified(self):
        tag = "v1.16.0"
        base_url = ("https://github.com/" + updater.REPOSITORY
                    + "/releases/download/" + tag + "/" + updater.ASSET_NAME)
        valid = {"name": updater.ASSET_NAME, "browser_download_url": base_url,
                 "digest": "sha256:" + "a" * 64, "size": 100}
        cases = [([], "release_without_required_asset"),
                 ([valid, valid], "release_without_required_asset"),
                 ([dict(valid, digest="")], "invalid_asset_metadata"),
                 ([dict(valid, digest=None)], "invalid_asset_metadata"),
                 ([dict(valid, size="invalid")], "invalid_asset_metadata"),
                 ([dict(valid, size=True)], "invalid_asset_metadata"),
                 ([dict(valid, browser_download_url="https://example.com/file.zip")],
                  "invalid_asset_metadata")]
        class Response(io.BytesIO):
            def __enter__(self): return self
            def __exit__(self, *args): return False
        for assets, reason in cases:
            with self.subTest(reason=reason, count=len(assets)):
                payload = {"tag_name": tag, "assets": assets}
                response = Response(json.dumps(payload).encode())
                with patch("winnat_ui.updater.urllib.request.urlopen",
                           return_value=response):
                    with self.assertRaises(updater.UpdateChannelError) as ctx:
                        updater.release_info("1.15.0")
                self.assertEqual(ctx.exception.reason, reason)
                self.assertEqual(ctx.exception.phase, "inspect_asset")
                self.assertIsNone(ctx.exception.http_status)

    def test_malformed_github_release_metadata_is_classified(self):
        cases = [
            (b"not-json", "release_lookup"),
            (b"[]", "release_lookup"),
            (b"null", "release_lookup"),
            (b'{"tag_name":"not-a-version","assets":[]}', "release_lookup"),
            (b'{"tag_name":"v1.16.0","assets":null}', "inspect_asset"),
            (b'{"tag_name":"v1.16.0","assets":[null]}', "inspect_asset"),
        ]

        class Response(io.BytesIO):
            def __enter__(self): return self
            def __exit__(self, *args): return False

        for payload, phase in cases:
            with self.subTest(payload=payload):
                with patch("winnat_ui.updater.urllib.request.urlopen",
                           return_value=Response(payload)):
                    with self.assertRaises(updater.UpdateChannelError) as ctx:
                        updater.release_info("1.15.0")
                self.assertEqual(ctx.exception.reason, "invalid_release_metadata")
                self.assertEqual(ctx.exception.phase, phase)
                self.assertIsNone(ctx.exception.http_status)
                self.assertIsInstance(ctx.exception, ValueError)

    def test_latest_release_requires_verified_official_asset(self):
        digest = "a" * 64
        data = {"tag_name": "v1.9.3", "draft": False, "prerelease": False,
                "assets": [{"name": updater.ASSET_NAME, "size": 123,
                            "digest": "sha256:" + digest,
                            "browser_download_url": "https://github.com/" + updater.REPOSITORY
                            + "/releases/download/v1.9.3/" + updater.ASSET_NAME}]}
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, n=-1): return json.dumps(data).encode()
        with patch("winnat_ui.updater.urllib.request.urlopen", return_value=Response()):
            release = updater.release_info("1.9.2")
        self.assertTrue(release["available"])
        self.assertEqual(release["sha256"], digest)

    def test_release_without_digest_is_rejected(self):
        data = {"tag_name": "v1.9.3", "assets": [
            {"name": updater.ASSET_NAME, "browser_download_url":
             "https://github.com/" + updater.REPOSITORY + "/releases/download/v1.9.3/"
             + updater.ASSET_NAME}]}
        class Response:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, n=-1): return json.dumps(data).encode()
        with patch("winnat_ui.updater.urllib.request.urlopen", return_value=Response()):
            with self.assertRaisesRegex(ValueError, "digest"):
                updater.release_info("1.9.2")

    def test_archive_traversal_and_symlinks_rejected(self):
        for filename in ["../escape.exe", "/absolute.exe", "C:/file.exe"]:
            with self.subTest(filename=filename):
                blob = io.BytesIO()
                with zipfile.ZipFile(blob, "w") as archive:
                    archive.writestr(filename, "bad")
                blob.seek(0)
                with zipfile.ZipFile(blob) as archive:
                    with self.assertRaises(ValueError):
                        updater._safe_members(archive)

    def test_download_rejects_corruption(self):
        class Response(io.BytesIO):
            def __enter__(self): return self
            def __exit__(self, *args): return False
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "asset.zip"
            with patch("winnat_ui.updater.urllib.request.urlopen", return_value=Response(b"invalid")):
                with self.assertRaisesRegex(ValueError, "SHA256"):
                    updater._download("https://github.com/" + updater.REPOSITORY +
                                      "/releases/download/v1.9.3/" + updater.ASSET_NAME,
                                      target, "a" * 64)

    def test_update_only_packaged_windows_exe(self):
        with patch.object(updater.sys, "platform", "linux"):
            with self.assertRaisesRegex(RuntimeError, "Windows"):
                updater.launch("not-staged")


if __name__ == "__main__":
    unittest.main()
