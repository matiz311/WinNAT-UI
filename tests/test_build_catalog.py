"""Regression tests for official releases and non-release Actions builds."""
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from winnat_ui import build_catalog


SHA = "a" * 40
DIGEST = "b" * 64


def official(version, digest=True):
    tag = "v" + version
    return {"tag_name": tag, "draft": False, "prerelease": False,
            "assets": [{"name": "WinNAT-UI-Windows.zip",
                        "size": 120,
                        "digest": "sha256:" + DIGEST if digest else "",
                        "browser_download_url":
                        "https://github.com/matiz311/WinNAT-UI/releases/download/"
                        + tag + "/WinNAT-UI-Windows.zip"}]}


def successful_run(run_id=100, number=55):
    return {"id": run_id, "run_number": number,
            "path": ".github/workflows/build.yml", "event": "pull_request",
            "conclusion": "success", "status": "completed", "head_sha": SHA,
            "head_branch": "feat/unfinished", "created_at": "2026-10-17T20:00:00Z",
            "head_repository": {"full_name": "matiz311/WinNAT-UI"},
            "html_url": "https://github.com/matiz311/WinNAT-UI/actions/runs/" + str(run_id)}


def artifact(run_id=100, number=55):
    return {"id": 999, "name": f"WinNAT-UI-Windows-{number}-{SHA}",
            "size_in_bytes": 123, "digest": "sha256:" + DIGEST,
            "archive_download_url":
                "https://api.github.com/repos/matiz311/WinNAT-UI/actions/artifacts/999/zip",
            "expired": False, "workflow_run": {"id": run_id, "head_sha": SHA}}


class CatalogTests(unittest.TestCase):
    def test_official_release_supports_old_versions_not_only_latest(self):
        with patch.object(build_catalog, "_api_json", return_value=[
            official("1.16.0"), official("1.15.1"), official("1.14.0", digest=False),
            dict(official("1.13.0"), prerelease=True)]):
            rows = build_catalog.release_catalog()
        self.assertEqual([r["version"] for r in rows], ["1.16.0", "1.15.1"])
        self.assertTrue(all(r["kind"] == "release" and r["available"] for r in rows))

    def test_only_successful_original_repo_build_and_exact_asset(self):
        good = successful_run()
        bad_fork = dict(successful_run(101), head_repository={"full_name": "fork/WinNAT-UI"})
        wrong_workflow = dict(successful_run(102), path=".github/workflows/issue-triage.yml")
        def fake_api(path, token=None):
            if path.startswith("/actions/runs?"):
                return {"workflow_runs": [good, bad_fork, wrong_workflow]}
            if path.startswith("/actions/runs/100/"):
                return {"artifacts": [artifact()]}
            raise AssertionError("Unexpected API request: " + path)
        with patch.object(build_catalog, "_api_json", side_effect=fake_api):
            rows = build_catalog.build_catalog()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["commit"], SHA)
        self.assertEqual(rows[0]["label"], "Build #55 · aaaaaaaa · Test")

    def test_pr_build_uses_merge_sha_not_source_sha(self):
        merge = "c" * 40
        run = successful_run()
        art = dict(artifact(), name=f"WinNAT-UI-Windows-55-{merge}")
        with patch.object(build_catalog, "_api_json", side_effect=[
                {"workflow_runs": [run]}, {"artifacts": [art]}]):
            rows = build_catalog.build_catalog()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["commit"], merge)
        self.assertEqual(rows[0]["source_commit"], SHA)

    def test_push_rejects_unrelated_artifact_commit(self):
        run = dict(successful_run(), event="push")
        art = dict(artifact(), name="WinNAT-UI-Windows-55-" + "c" * 40)
        with patch.object(build_catalog, "_api_json", side_effect=[
                {"workflow_runs": [run]}, {"artifacts": [art]}]):
            self.assertEqual(build_catalog.build_catalog(), [])

    def test_expired_missing_digest_or_incomplete_build_omitted(self):
        run = successful_run()
        bad = [dict(artifact(), expired=True)]
        with patch.object(build_catalog, "_api_json", side_effect=[
                {"workflow_runs": [run]}, {"artifacts": bad}]):
            self.assertEqual(build_catalog.build_catalog(), [])

    def test_untrusted_redirect_rejected(self):
        for url in ("http://objects.githubusercontent.com/x",
                    "https://example.com/x", "https://objects.githubusercontent.com.evil.test/x",
                    "https://user:pass@objects.githubusercontent.com/x"):
            with self.subTest(url=url):
                self.assertFalse(build_catalog._trusted_artifact_location(url))

    def test_token_missing_rejected_before_network(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "GitHub"):
                build_catalog._download_build({"id": "999",
                                                "url": "https://api.github.com/repos/matiz311/WinNAT-UI/actions/artifacts/999/zip"},
                                               Path(directory) / "x.zip", "")

    def test_verifies_build_manifest_and_stages(self):
        content = io.BytesIO()
        exe = b"mock-exe"
        exe_sha = hashlib.sha256(exe).hexdigest()
        meta = ("Functional version: 1.16.0\nBuild identifier: 1.16.0+ci.55.aaaaaaaa\n"
                "Git commit: " + SHA + "\nWorkflow: 100\n")
        with zipfile.ZipFile(content, "w") as archive:
            archive.writestr("WinNAT-UI.exe", exe)
            archive.writestr("BUILD_INFO.txt", meta)
            archive.writestr("SHA256.txt", "SHA256: " + exe_sha)
            archive.writestr("DEFENDER_SCAN.txt", "Defender scan completed")
        zipped = content.getvalue()
        info = {"kind": "build", "commit": SHA, "run_id": 100,
                "run_number": 55, "id": "999"}
        def mock_download(_record, path, _token):
            Path(path).write_bytes(zipped)
        with patch.object(build_catalog, "_download_build", side_effect=mock_download):
            stage, build_id = build_catalog.prepare_build(info, "token")
        try:
            self.assertEqual(build_id, "1.16.0+ci.55.aaaaaaaa")
            self.assertEqual((stage / "new" / "WinNAT-UI.exe").read_bytes(), exe)
        finally:
            import shutil
            shutil.rmtree(stage)

    def test_rejects_forged_build_metadata(self):
        content = io.BytesIO()
        with zipfile.ZipFile(content, "w") as archive:
            archive.writestr("WinNAT-UI.exe", b"exe")
            archive.writestr("BUILD_INFO.txt",
                             "Functional version: 1.16.0\nBuild identifier: 1.16.0+ci.55.aaaaaaaa\n"
                             "Git commit: " + SHA + "\nWorkflow: 999\n")
            archive.writestr("SHA256.txt", "SHA256: " + hashlib.sha256(b"exe").hexdigest())
            archive.writestr("DEFENDER_SCAN.txt", "scanned")
        info = {"kind": "build", "commit": SHA, "run_id": 100, "run_number": 55, "id": "999"}
        with patch.object(build_catalog, "_download_build",
                          side_effect=lambda info, path, token: Path(path).write_bytes(content.getvalue())):
            with self.assertRaisesRegex(ValueError, "incoerenti"):
                build_catalog.prepare_build(info, "token")


if __name__ == "__main__":
    unittest.main()
