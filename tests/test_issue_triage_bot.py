"""Regression tests for the conservative GitHub Issue triage bot."""
import unittest
from unittest.mock import Mock

from tools.issue_triage_bot import MARKER, assess, candidate_fingerprints, make_comment, triage


class AssessmentTests(unittest.TestCase):
    def test_vpn_report_preserves_unknown_cause_and_priority(self):
        result = assess("VPN FullTunnel non funziona",
                        "Malwarebytes VPN non si collega quando WinNAT è presente.", 76)
        self.assertEqual(result.component, "VPN Full Tunnel")
        self.assertEqual(result.state, "triage:informazioni-richieste")
        self.assertIsNone(result.suggested_title)
        self.assertIn("non è ancora verificata", result.hypothesis)
        text = make_comment({"number": 76, "body": ""}, result, [])
        self.assertIn(MARKER, text)
        self.assertIn("priorità:** da valutare", text)
        self.assertIn("Collaudo:** non eseguito", text)
        self.assertNotIn("fixed-in/v", text)

    def test_generic_issue_has_distinct_title_without_asserting_cause(self):
        result = assess("[Bug] Altra operazione - Errore operativo non classificato",
                        "Versione: 0.0.0", 39)
        self.assertIn("(#39)", result.suggested_title)
        self.assertIn("Diagnostica da approfondire", result.suggested_title)
        self.assertEqual(result.state, "triage:informazioni-richieste")

    def test_detailed_evidence_only_transitions_to_in_analysis(self):
        body = ("**Versione:** 1.16.0\n**Eccezione:** HTTPError\n"
                "Traceback Python: request failure while checking releases; "
                "detailed report and complete reproduction were attached " * 3)
        result = assess("Errore durante verifica aggiornamenti", body, 80)
        self.assertEqual(result.state, "triage:in-analisi")
        self.assertIn("endpoint", result.hypothesis)
        self.assertIsNone(result.suggested_title)

    def test_real_gateway_version_is_recognized_but_placeholder_is_not(self):
        base = ("**Versione WinNAT-UI:** {version}\n"
                "**Eccezione:** HTTPError\n### Errore principale\n"
                + "Diagnostics with an explicit stack and context. " * 6)
        good = assess("[Bug] Aggiornamenti", base.format(version="1.16.0"), 91)
        missing = assess("[Bug] Aggiornamenti", base.format(version="0.0.0"), 92)
        self.assertEqual(good.state, "triage:in-analisi")
        self.assertEqual(missing.state, "triage:informazioni-richieste")

    def test_smoke_test_release_reference_does_not_become_updater_issue(self):
        body = (
            "## Test automatico controllato\n"
            "Apertura Issue per verificare la PR e la futura release correttiva.\n"
            "Risultato atteso: label iniziale, nessuna priority o fixed-in e commento."
        )
        actual = assess("[Test CI] Verifica automatica triage delle nuove Issue", body, 78)
        self.assertEqual(actual.component, "Generale")
        self.assertEqual(actual.state, "triage:informazioni-richieste")

    def test_structured_operation_identifies_real_updater_issue(self):
        body = (
            "**Versione WinNAT-UI:** 1.16.0\n"
            "**Operazione:** Aggiornamenti\n"
            "**Moduli:** app.py, updater.py\n"
            "**Eccezione:** HTTPError\n"
        )
        actual = assess("[Bug] Errore operativo non classificato", body, 81)
        self.assertEqual(actual.component, "Aggiornamenti")

    def test_generic_issue_uses_opening_description_for_vpn(self):
        body = "Il client Malwarebytes VPN non si connette con WinNAT attivo."
        actual = assess("[Bug] Errore operativo non classificato", body, 82)
        self.assertEqual(actual.component, "VPN Full Tunnel")

    def test_feature_has_feature_prefix(self):
        result = assess("[Feature] bug report", "aggiungere filtri per l'interfaccia", 90)
        self.assertIn("[Feature]", result.suggested_title)
        self.assertEqual(result.kind, "Miglioramento")


class GithubInteractionTests(unittest.TestCase):
    def test_skip_if_human_triage_already_in_progress(self):
        api = Mock()
        api.api.return_value = {"number": 76, "state": "open",
                                "title": "Test", "body": "", "labels": [
                                    {"name": "triage:confermato"}]}
        self.assertIn("skipped", triage(api, 76))
        self.assertEqual(api.api.call_count, 1)

    def test_skip_if_marker_already_present(self):
        api = Mock()
        api.api.side_effect = [
            {"number": 41, "state": "open", "title": "Test", "body": "", "labels": []},
            [{"body": "previous auto-triage " + MARKER}],
        ]
        self.assertIn("skipped", triage(api, 41))
        self.assertEqual(api.api.call_count, 2)

    def test_apply_preserves_unrelated_labels(self):
        api = Mock()
        original = {"number": 90, "state": "open", "title": "Error",
                    "body": "Unexpected issue", "labels": [
                        {"name": "bug-report"}, {"name": "triage:ricevuto"}]}
        updated = dict(original, labels=[
            {"name": "bug-report"}, {"name": "triage:informazioni-richieste"}])
        api.api.side_effect = [original, [], {}, {}, updated]
        self.assertEqual(triage(api, 90), "Triage completed.")
        patch = api.api.call_args_list[2]
        self.assertEqual(patch.args[1], "PATCH")
        self.assertIn("bug-report", patch.args[2]["labels"])
        self.assertNotIn("triage:ricevuto", patch.args[2]["labels"])

    def test_fingerprint_only_creates_possible_correlation(self):
        fingerprint = "a" * 24
        api = Mock()
        api.api.return_value = [
            {"number": 1, "body": "<!-- winnat-fingerprint:" + fingerprint + " -->"},
            {"number": 2, "body": "<!-- winnat-fingerprint:" + fingerprint + " -->"},
            {"number": 3, "body": "<!-- winnat-fingerprint:" + "b" * 24 + " -->"},
        ]
        issue = {"number": 1, "body": "<!-- winnat-fingerprint:" + fingerprint + " -->"}
        self.assertEqual(candidate_fingerprints(api, issue), [2])
        assessment = assess("Unknown error", "", 1)
        comment = make_comment(issue, assessment, [2])
        self.assertIn("non duplicati confermati", comment)


if __name__ == "__main__":
    unittest.main()
