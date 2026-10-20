import unittest
from datetime import date, datetime

from google_hub.notify import next_summary_time, summary_due, summary_text


def dt(*a):
    return datetime(*a)


def t(bucket):
    return {"bucket": bucket}


class TestNotify(unittest.TestCase):
    def test_next_summary(self):
        self.assertEqual(next_summary_time(dt(2026, 10, 3, 7, 0), None, 9), dt(2026, 10, 3, 9, 0))
        self.assertEqual(next_summary_time(dt(2026, 10, 3, 11, 0), None, 9), dt(2026, 10, 3, 11, 0))
        self.assertEqual(next_summary_time(dt(2026, 10, 3, 11, 0), date(2026, 10, 3), 9), dt(2026, 10, 4, 9, 0))
        self.assertEqual(next_summary_time(dt(2026, 10, 3, 7, 0), date(2026, 10, 2), 9), dt(2026, 10, 3, 9, 0))

    def test_summary_due_wall_clock(self):
        self.assertFalse(summary_due(dt(2026, 10, 3, 8, 59), None, 9))
        self.assertTrue(summary_due(dt(2026, 10, 3, 9, 0), None, 9))
        self.assertTrue(summary_due(dt(2026, 10, 4, 19, 0), date(2026, 10, 3), 9))   # wake-up after a suspend
        self.assertFalse(summary_due(dt(2026, 10, 4, 19, 0), date(2026, 10, 4), 9))

    def test_summary_text(self):
        self.assertEqual(summary_text([t("today")] * 3 + [t("overdue")]), "3 tasks today, 1 overdue")
        self.assertEqual(summary_text([t("today")]), "1 task today")
        self.assertEqual(summary_text([t("overdue")] * 2), "2 tasks overdue")
        self.assertIsNone(summary_text([t("week"), t("undated")]))
