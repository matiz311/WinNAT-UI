"""Version governance: build IDs never imply a release number increase."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent / "tools"))
import release


class ReleasePolicyTests(unittest.TestCase):
    def test_patch_only_for_fixes(self):
        self.assertEqual(release.release_kind("1.9.1", "1.9.2"), "patch")
        self.assertTrue(release.publication_gate("1.9.1", "1.9.2")[0])

    def test_four_digit_hotfix(self):
        self.assertEqual(release.release_kind("1.9.15", "1.9.15.1"), "hotfix")
        self.assertEqual(release.release_kind("1.9.15.1", "1.9.15.2"), "hotfix")
        self.assertEqual(release.release_kind("1.9.15", "1.9.15.0"), "same")
        self.assertTrue(release.publication_gate("1.9.15", "1.9.15.1")[0])
        with self.assertRaises(ValueError):
            release.release_kind("1.9.15", "1.9.15.3")

    def test_one_build_does_not_require_new_version(self):
        self.assertEqual(release.release_kind("1.9.2", "1.9.2"), "same")
        self.assertFalse(release.publication_gate("1.9.2", "1.9.2")[0])

    def test_minor_requires_summary_and_explicit_approval(self):
        summary = ("### Sintesi\n" + "Riepilogo significativo dei miglioramenti per il rilascio. " * 5
                   + "\n### Funzionalità\n- Funzione nuova con valore operativo, test e compatibilità.\n"
                   + "### Correzioni\n- Correzione verificata e relativa regressione.\n")
        self.assertEqual(release.release_kind("1.9.4", "1.10.0"), "minor")
        self.assertFalse(release.publication_gate("1.9.4", "1.10.0", content=summary)[0])
        self.assertFalse(release.publication_gate("1.9.4", "1.10.0",
                                                 manual=True, content=summary)[0])
        self.assertTrue(release.publication_gate("1.9.4", "1.10.0",
                                                manual=True, minor_approved=True,
                                                content=summary)[0])

    def test_empty_minor_notes_refused_even_if_approved(self):
        with self.assertRaisesRegex(ValueError, "riepilogo"):
            release.publication_gate("1.9.4", "1.10.0",
                                     manual=True, minor_approved=True,
                                     content="### Sintesi\nNuova interfaccia.")

    def test_unjustified_version_jumps_rejected(self):
        for a, b in [("1.9.0", "1.11.0"), ("1.9.0", "1.10.2"),
                     ("1.9.0", "1.9.4"), ("1.10.1", "1.9.2")]:
            with self.subTest(a=a, b=b), self.assertRaises(ValueError):
                release.release_kind(a, b)


if __name__ == "__main__":
    unittest.main()
