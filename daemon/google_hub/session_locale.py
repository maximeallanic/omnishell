"""Locale of the session: CLDR locale (babel) for dates, language tags for Google and Wikipedia.

Names come from GLib (LANGUAGE, LC_ALL, the category, LANG, in that order), the same list
GTK and GNOME Shell use, so the daemon speaks the language the desktop speaks.
"""
import logging

from babel import Locale, UnknownLocaleError
from gi.repository import GLib

log = logging.getLogger(__name__)

# What babel and glibc mean by the C/POSIX locale: untranslated messages, US-style formats.
POSIX = "en_US_POSIX"
# glibc locale modifiers that name a script (sr_RS@latin, uz_UZ@cyrillic, sd_IN@devanagari).
SCRIPT_MODIFIERS = {"latin": "Latn", "cyrillic": "Cyrl", "devanagari": "Deva"}


def _posix_name(name: str) -> str:
    """'fr_FR.UTF-8@euro' -> 'fr_FR', 'sr_RS@latin' -> 'sr_Latn_RS'."""
    base, _, modifier = name.partition("@")
    base = base.split(".")[0]
    script = SCRIPT_MODIFIERS.get(modifier)
    if script and base:
        lang, _, territory = base.partition("_")
        return "_".join(filter(None, (lang, script, territory)))
    return base


def session_locale(category: str, names: list[str] | None = None) -> Locale:
    """First session locale babel knows for category ("LC_TIME", "LC_MESSAGES")."""
    if names is None:
        names = GLib.get_language_names_with_category(category)
    unknown = []
    for name in names:
        posix = _posix_name(name)
        if posix in ("C", "POSIX"):
            return Locale.parse(POSIX)
        try:
            return Locale.parse(posix)
        except (UnknownLocaleError, ValueError):
            unknown.append(name)
    log.warning("%s: no CLDR data for %s, formats fall back to the C locale",
                category, ", ".join(unknown) or "an empty locale")
    return Locale.parse(POSIX)


def google_hl(loc: Locale) -> str:
    """Interface language for Google (hl=): BCP 47 tag, region kept (pt-BR, zh-TW)."""
    return loc.language + (f"-{loc.territory}" if loc.territory else "")


def wikipedia_language(loc: Locale) -> str:
    """Wikipedia edition (subdomain) of the session language."""
    return loc.language
