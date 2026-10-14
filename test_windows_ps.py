"""Runs only on Windows (CI runner): real PowerShell round-trip through network.ps."""
import sys
import unittest

import network


@unittest.skipUnless(sys.platform == "win32", "richiede Windows")
class PowerShellTests(unittest.TestCase):
    def test_accented_text_round_trip(self):
        self.assertEqual(network.ps("Write-Output 'Connessione alla rete locale àèìòù'"),
                         "Connessione alla rete locale àèìòù")

    def test_error_keeps_stderr(self):
        with self.assertRaises(RuntimeError) as ctx:
            network.ps("$ErrorActionPreference='Stop'; Get-Item 'C:\\percorso-inesistente-winnat'")
        self.assertIn("STDERR", str(ctx.exception))

    def test_error_line_matches_numbered_script(self):
        with self.assertRaises(RuntimeError) as ctx:
            network.ps("$ErrorActionPreference='Stop'\n$x = 1\nthrow 'errore-di-prova'")
        text = str(ctx.exception)
        self.assertRegex(text, r"(riga|line):\s*3\b")
        self.assertIn("0003 | throw 'errore-di-prova'", text)


if __name__ == "__main__":
    unittest.main()
