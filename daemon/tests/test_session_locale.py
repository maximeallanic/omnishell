import unittest

from omnishell.session_locale import google_hl, session_locale, wikipedia_language


class TestSessionLocale(unittest.TestCase):
    def test_first_known_name(self):
        loc = session_locale("LC_MESSAGES", ["pt_BR.UTF-8", "pt_BR", "pt", "C"])
        self.assertEqual((google_hl(loc), wikipedia_language(loc)), ("pt-BR", "pt"))
        loc = session_locale("LC_MESSAGES", ["zh_TW.UTF-8", "zh_TW", "zh", "C"])
        self.assertEqual((google_hl(loc), wikipedia_language(loc)), ("zh-TW", "zh"))
        self.assertEqual(google_hl(session_locale("LC_MESSAGES", ["ja", "C"])), "ja")

    def test_modifier_and_unknown(self):
        self.assertEqual(str(session_locale("LC_TIME", ["sr_RS@latin", "C"])), "sr_Latn_RS")
        self.assertEqual(str(session_locale("LC_TIME", ["sr_RS.UTF-8", "C"])), "sr_Cyrl_RS")
        self.assertEqual(str(session_locale("LC_TIME", ["ca_ES.UTF-8@valencia", "C"])), "ca_ES")
        with self.assertLogs("omnishell.session_locale", "WARNING"):
            loc = session_locale("LC_TIME", ["xx_YY.UTF-8", "xx"])
        self.assertEqual(loc.language, "en")
        self.assertEqual(session_locale("LC_TIME", ["xx", "fr_FR", "C"]).language, "fr")

    def test_c_locale(self):
        self.assertEqual(session_locale("LC_TIME", ["C"]).language, "en")
