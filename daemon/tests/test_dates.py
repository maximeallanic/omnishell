import unittest
from datetime import date, datetime

from babel import Locale

from google_hub.dates import DateReader, session_languages

TODAY = date(2026, 10, 3)  # a Saturday
FR_FR = Locale.parse("fr_FR")
FR = DateReader(["fr"], "DMY", FR_FR)


class TestTrailingDate(unittest.TestCase):
    def check(self, reader, cases):
        for txt, exp in cases.items():
            self.assertEqual(reader.parse_trailing_date(txt, TODAY), exp, txt)

    def test_french(self):
        self.check(FR, {
            "acheter du pain demain": ("acheter du pain", date(2026, 10, 4)),
            "payer loyer aujourd'hui": ("payer loyer", TODAY),
            "dentiste après-demain": ("dentiste", date(2026, 10, 5)),
            "dentiste apres-demain": ("dentiste", date(2026, 10, 5)),
            "rapport vendredi": ("rapport", date(2026, 10, 9)),
            "courses samedi": ("courses", date(2026, 10, 10)),
            "facture le 12": ("facture", date(2026, 10, 12)),
            "facture le 2": ("facture", date(2026, 11, 2)),
            "impôts 12/10": ("impôts", date(2026, 10, 12)),
            "noël 1/1": ("noël", date(2027, 1, 1)),
            "rendez-vous 12 octobre": ("rendez-vous", date(2026, 10, 12)),
            "dentiste 2026-10-12": ("dentiste", date(2026, 10, 12)),
            "sans date": ("sans date", None),
            "demain": ("demain", None),
            "acheter 3": ("acheter 3", None),
            "appeler Paul 14h": ("appeler Paul 14h", None),
            "relire dans 3 heures": ("relire dans 3 heures", None),
            "congés en mai": ("congés en mai", None),
        })

    def test_other_languages(self):
        self.check(DateReader(["fr", "en"], "DMY", FR_FR), {
            "buy bread tomorrow": ("buy bread", date(2026, 10, 4)),
            "report on friday": ("report", date(2026, 10, 9)),
            "acheter du pain demain": ("acheter du pain", date(2026, 10, 4)),
            "buy a car": ("buy a car", None),
        })
        self.check(DateReader(["de"], "DMY", FR_FR), {"Brot kaufen morgen": ("Brot kaufen", date(2026, 10, 4)),
                                                "Steuer 12.10.2026": ("Steuer", date(2026, 10, 12))})
        self.check(DateReader(["es"], "DMY", FR_FR), {"comprar pan mañana": ("comprar pan", date(2026, 10, 4))})
        self.check(DateReader(["ru"], "DMY", FR_FR), {"купить хлеб завтра": ("купить хлеб", date(2026, 10, 4))})
        self.check(DateReader(["zh"], "YMD", FR_FR), {"买面包明天": ("买面包", date(2026, 10, 4))})
        self.check(DateReader(["en"], "MDY", FR_FR), {"taxes 10/12": ("taxes", date(2026, 10, 12))})

    def test_language_not_enabled_is_not_guessed(self):
        self.assertEqual(FR.parse_trailing_date("Brot kaufen morgen", TODAY), ("Brot kaufen morgen", None))
        self.assertEqual(FR.parse_trailing_date("buy bread tomorrow", TODAY), ("buy bread tomorrow", None))

    def test_unsupported_language_is_dropped_loudly(self):
        with self.assertLogs("google_hub.dates", "WARNING"):
            r = DateReader(["fr", "xx"], "DMY", FR_FR)
        self.assertEqual(r.languages, ["fr"])

    def test_session_languages(self):
        env = {"LANGUAGE": "fr:en", "LC_ALL": "", "LC_TIME": "de_DE.UTF-8", "LANG": "fr_FR.UTF-8"}
        self.assertEqual(session_languages(env), ["fr", "en", "de"])
        self.assertEqual(session_languages({"LANG": "C.UTF-8"}), [])


class TestDayQuery(unittest.TestCase):
    def test_day_query(self):
        self.assertEqual(FR.day_query("Demain", TODAY), date(2026, 10, 4))
        self.assertEqual(FR.day_query("lundi", TODAY), date(2026, 10, 5))
        self.assertEqual(FR.day_query("aujourd'hui", TODAY), TODAY)
        self.assertEqual(FR.day_query("12 octobre", TODAY), date(2026, 10, 12))
        self.assertIsNone(FR.day_query("lundi matin", TODAY))
        self.assertIsNone(FR.day_query("reunion", TODAY))
        self.assertIsNone(FR.day_query("3", TODAY))
        en_de = DateReader(["en", "de"], "DMY", FR_FR)
        self.assertEqual(en_de.day_query("tomorrow", TODAY), date(2026, 10, 4))
        self.assertEqual(en_de.day_query("morgen", TODAY), date(2026, 10, 4))


class TestFormat(unittest.TestCase):
    def test_format(self):
        self.assertEqual(FR.format_day(date(2026, 10, 9)), "ven. 9 oct.")
        self.assertEqual(FR.format_when(datetime(2026, 10, 9, 14, 0)), "ven. 9 oct. 14:00")
        self.assertEqual(FR.format_when(date(2026, 10, 9)), "ven. 9 oct.")

    def test_format_follows_locale(self):
        """Names, word order and clock come from CLDR, not from a table written for one language."""
        cases = {"en_US": ("Fri, Oct 9", "Fri, Oct 9, 2:00\u202fPM"),
                 "de_DE": ("Fr., 9. Okt.", "Fr., 9. Okt., 14:00"),
                 "ja_JP": ("10月9日(金)", "10月9日(金) 14:00"),
                 "ar_EG": ("الجمعة، 9 أكتوبر", None)}
        for name, (day, when) in cases.items():
            r = DateReader(["en"], None, Locale.parse(name))
            self.assertEqual(r.format_day(date(2026, 10, 9)), day, name)
            if when:
                self.assertEqual(r.format_when(datetime(2026, 10, 9, 14, 0)), when, name)
