"""Safety and integrity tests for the privileged GitHub CI preview publisher."""
import hashlib
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import zipfile

from tools import publish_ci_preview as publisher


SHA = "a" * 40
MERGE = "c" * 40


def run(event="push"):
    return {"name": "Build Windows executable",
            "path": ".github/workflows/build.yml",
            "conclusion": "success", "status": "completed",
            "event": event, "head_sha": SHA, "head_branch": "main",
            "id": 100, "run_number": 55,
            "repository": {"full_name": publisher.REPO},
            "head_repository": {"full_name": publisher.REPO}}


def artifact(sha=SHA):
    return {"id": 987, "name": f"WinNAT-UI-Windows-55-{sha}",
            "size_in_bytes": 1000, "expired": False,
            "archive_download_url": publisher.API + "/actions/artifacts/987/zip",
            "digest": "sha256:" + "b" * 64,
            "workflow_run": {"id": 100, "head_sha": SHA}}


def make_zip(path, run_meta=None, *, defender=True, exe=b"example"):
    info = run_meta or run()
    meta = (f"Functional version: 1.16.0\n"
            f"Build identifier: 1.16.0+ci.55.{info['head_sha'][:8]}\n"
            f"Git commit: {info['head_sha']}\n"
            f"Workflow: {info['id']}\n")
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("BUILD_INFO.txt", meta)
        archive.writestr("WinNAT-UI.exe", exe)
        archive.writestr("SHA256.txt", hashlib.sha256(exe).hexdigest())
        archive.writestr("DEFENDER_SCAN.txt", "Scanned" if defender else "")


class PreviewPublisherTests(unittest.TestCase):
    def test_ignores_untrusted_or_failed_workflow(self):
        for bad in (dict(run(), conclusion="failure"),
                    dict(run(), head_repository={"full_name": "malicious/fork"}),
                    dict(run(), path=".github/workflows/other.yml"),
                    dict(run(), status="in_progress")):
            with self.subTest(bad=bad), patch.object(publisher, "_api") as api:
                self.assertIsNone(publisher._get_run_artifact(bad))
                api.assert_not_called()

    def test_accepts_valid_original_repo_build(self):
        with patch.object(publisher, "_api",
                          return_value={"artifacts": [artifact()]}):
            asset, sha = publisher._get_run_artifact(run())
        self.assertEqual(asset["id"], 987)
        self.assertEqual(sha, SHA)

    def test_pr_synthetic_merge_sha_accepted_but_push_rejected(self):
        with patch.object(publisher, "_api",
                          return_value={"artifacts": [artifact(MERGE)]}):
            self.assertEqual(publisher._get_run_artifact(run("pull_request"))[1], MERGE)
            with self.assertRaisesRegex(ValueError, "Exactly one"):
                publisher._get_run_artifact(run("push"))

    def test_validate_zip_and_build_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "payload.zip"
            make_zip(path)
            self.assertEqual(publisher._validate_zip(path, run(), SHA), "1.16.0")
            with self.assertRaisesRegex(ValueError, "BUILD_INFO"):
                publisher._validate_zip(path, run(), MERGE)

    def test_missing_defender_manifest_content_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "payload.zip"
            make_zip(path, defender=False)
            with self.assertRaisesRegex(ValueError, "Defender"):
                publisher._validate_zip(path, run(), SHA)

    def test_zip_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "payload.zip"
            make_zip(path)
            with zipfile.ZipFile(path, "a") as archive:
                archive.writestr("../outside.exe", b"bad")
            with self.assertRaisesRegex(ValueError, "Unsafe ZIP"):
                publisher._validate_zip(path, run(), SHA)

    def test_catalog_record_has_canonical_release_url(self):
        entry = publisher._record(run(), "ci-run-100", SHA, "b" * 64, 120, "1.16.0")
        self.assertEqual(entry["run_id"], 100)
        self.assertEqual(entry["version"], "1.16.0")
        self.assertEqual(entry["url"],
                         "https://github.com/matiz311/WinNAT-UI/releases/download/ci-run-100/WinNAT-UI-Windows.zip")

    def test_catalog_stores_only_metadata_and_creates_orphan_root(self):
        requests = []
        def api(path, method="GET", body=None, allow_404=False):
            requests.append((path, method, body))
            if path.endswith("/git/ref/heads/ci-builds"):
                return None
            if path == "/git/blobs":
                return {"sha": "b" * 40}
            if path == "/git/trees":
                return {"sha": "c" * 40}
            if path == "/git/commits":
                return {"sha": "d" * 40}
            if path == "/git/refs":
                return {"ref": "refs/heads/ci-builds"}
            raise AssertionError(path)
        entry = publisher._record(run(), "ci-run-100", SHA, "b" * 64, 120, "1.16.0")
        with patch.object(publisher, "_api", side_effect=api):
            self.assertEqual(publisher._update_index(entry), "d" * 40)
        blobs = [body for path, _, body in requests if path == "/git/blobs"]
        self.assertEqual(len(blobs), 1)
        self.assertIn("ci-run-100", blobs[0]["content"])
        self.assertNotIn("WinNAT-UI.exe", blobs[0]["content"])
        commits = [body for path, _, body in requests if path == "/git/commits"]
        self.assertEqual(commits[0]["parents"], [])


if __name__ == "__main__":
    unittest.main()
