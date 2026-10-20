"""Dates typed by the user (task due dates, day searches) and their short display.

Parsing relies on dateparser (python3-dateparser), which knows about 200 languages. It reads
the session languages plus the ones listed in config.json "date_languages", and only those:
guessing among every language turns ordinary words into dates ("car" is Wednesday in Turkish,
"pan" a weekday in Nuer). The task preview names the languages read, so a date written in
another one is never dropped silently.

Display uses the CLDR patterns of the LC_TIME locale (babel, python3-babel): names, word order
and 12/24-hour clock follow the session ("ven. 9 oct.", "Fri, Oct 9", "10月9日(金)").
"""
import locale
import logging
import os
from datetime import date, datetime, time

from babel import Locale
from babel.dates import format_skeleton, format_time, get_datetime_format
from dateparser.data.languages_info import language_order
from dateparser.date import DateDataParser
from dateparser.search import search_dates

from .session_locale import session_locale

log = logging.getLogger(__name__)

SUPPORTED = frozenset(language_order)
# ISO 8601 first: a forced DATE_ORDER would otherwise read 2026-10-12 as 10 December.
ISO_FORMATS = ["%Y-%m-%d"]
# Longest trailing date expression tried, in whitespace-separated words ("the day after tomorrow").
MAX_WORDS = 4


def session_languages(environ=os.environ) -> list[str]:
    """Languages of the session locale, most specific variable first (LANGUAGE is a list)."""
    names = environ.get("LANGUAGE", "").split(":")
    names += [environ.get(v, "") for v in ("LC_ALL", "LC_TIME", "LC_MESSAGES", "LANG")]
    out = []
    for name in names:
        code = name.split(".")[0].split("@")[0].split("_")[0].lower()
        if code and code not in ("c", "posix") and code not in out:
            out.append(code)
    return out


def session_date_order() -> str | None:
    """Day/month/year order of numeric dates in the LC_TIME locale (DMY for fr_FR, MDY for en_US).

    None while LC_TIME is still the C locale (setlocale not called, or the locale is missing).
    """
    if locale.getlocale(locale.LC_TIME)[0] is None:
        return None
    fmt = locale.nl_langinfo(locale.D_FMT).lower()
    pos = {k: fmt.find("%" + k) for k in "dmy"}
    if -1 in pos.values():
        return None
    return "".join(sorted(pos, key=pos.get)).upper()


def _add_month(d: date, day: int) -> date | None:
    y, m = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    try:
        return date(y, m, day)
    except ValueError:
        return None


class DateReader:
    def __init__(self, languages: list[str], date_order: str | None, display: Locale):
        unknown = [l for l in languages if l not in SUPPORTED]
        if unknown:
            log.warning("Dates: dateparser does not support %s; due dates and day searches written in "
                        "it are not recognised", ", ".join(unknown))
        self.languages = [l for l in languages if l in SUPPORTED]
        if not self.languages:
            log.warning("Dates: no supported language, due dates and day searches are disabled")
        self.date_order = date_order
        self.display = display

    @classmethod
    def from_session(cls, extra: list[str]) -> "DateReader":
        languages = session_languages()
        languages += [l for l in extra if l not in languages]
        return cls(languages, session_date_order(), session_locale("LC_TIME"))

    def _settings(self, today: date, **extra) -> dict:
        s = {"PREFER_DATES_FROM": "future", "RELATIVE_BASE": datetime.combine(today, time()),
             "RETURN_TIME_AS_PERIOD": True, **extra}
        if self.date_order:
            s["DATE_ORDER"] = self.date_order
        return s

    def _day(self, expr: str, today: date) -> date | None:
        """The day named by expr, or None if expr is not a day.

        Bare numbers are quantities ("buy 3"), and expressions carrying a time of day or a
        duration in hours ("14h", "in 3 hours") or naming a week, month or year are not days.
        """
        if not self.languages or expr.isdigit():
            return None
        data = self._parser(today).get_date_data(expr, date_formats=ISO_FORMATS)
        dt = data.date_obj
        if dt is None or data.period != "day" or dt.time() != time():
            return None
        d = dt.date()
        if d == today and self._implied(expr, today, "day"):
            # A lone unit word ("heures", "minutes") falls back on the base date: it names no day.
            return None
        if d < today and self._implied(expr, today, "month"):
            # "le 2" on the 3rd: the day of month already passed, so it means next month.
            d = _add_month(today, d.day)
        return d

    def _parser(self, today: date, **extra) -> DateDataParser:
        return DateDataParser(languages=self.languages, settings=self._settings(today, **extra))

    def _implied(self, expr: str, today: date, part: str) -> bool:
        """True when expr does not state part itself and dateparser filled it from the base date."""
        strict = self._parser(today, REQUIRE_PARTS=[part])
        return strict.get_date_data(expr, date_formats=ISO_FORMATS).date_obj is None

    def _candidates(self, text: str, today: date) -> list[tuple[str, str]]:
        """(title, expression) splits where expression ends text, longest expression first."""
        words = text.split()
        out = [(" ".join(words[:-n]), " ".join(words[-n:]))
               for n in range(min(MAX_WORDS, len(words) - 1), 0, -1)]
        # Scripts written without spaces (Chinese, Japanese, Thai) only split through search.
        found = search_dates(text, languages=self.languages, settings=self._settings(today)) or []
        if found and text.endswith(found[-1][0]) and text[:-len(found[-1][0])].strip():
            out.append((text[:-len(found[-1][0])].strip(), found[-1][0]))
        return out

    def parse_trailing_date(self, text: str, today: date) -> tuple[str, date | None]:
        """Split a task text into its title and the due date that ends it, if any."""
        text = " ".join(text.split())
        if not self.languages:
            return text, None
        for title, expr in self._candidates(text, today):
            d = self._day(expr, today)
            if d:
                return title, d
        return text, None

    def day_query(self, text: str, today: date) -> date | None:
        t = " ".join(text.split())
        return self._day(t, today) if t else None


    def format_day(self, d: date) -> str:
        """Abbreviated weekday, day and month ("ven. 9 oct.")."""
        return format_skeleton("MMMEd", d, locale=self.display)

    def format_time(self, dt: datetime) -> str:
        """Time of day, 12- or 24-hour as the locale writes it ("14:00", "2:00\u202fPM")."""
        return format_time(dt, "short", locale=self.display)

    def format_when(self, dt: datetime | date) -> str:
        """Day, plus the time of day for a datetime, joined the way the locale joins them."""
        if not isinstance(dt, datetime):
            return self.format_day(dt)
        glue = get_datetime_format("short", locale=self.display)
        return glue.replace("{1}", self.format_day(dt.date())).replace(
            "{0}", self.format_time(dt))
