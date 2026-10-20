import unittest

from google_hub.text import matches, normalize


class TestText(unittest.TestCase):
    def test_normalize(self):
        self.assertEqual(normalize("  Réunion   d'Équipe "), "reunion d'equipe")

    def test_matches_all_words_any_field(self):
        self.assertTrue(matches("reunion lyon", "Réunion d'équipe", "Lyon 3e"))
        self.assertFalse(matches("reunion paris", "Réunion", "Lyon"))

    def test_matches_ignores_none_fields(self):
        self.assertTrue(matches("lyon", None, "Lyon"))
