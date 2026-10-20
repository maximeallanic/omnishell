"""gettext lookup for the ``omnishell`` domain in the session's message language; falls back to the English msgid.

Languages come from GLib (LANGUAGE, LC_ALL, LC_MESSAGES, LANG), the list GTK and GNOME Shell use, as in
session_locale.py. Catalogues are compiled from po/ by install.sh into
~/.local/share/omnishell/locale, next to the installed panel/ directory.
"""
import gettext
from pathlib import Path

from gi.repository import GLib

DOMAIN = "omnishell"
LOCALE_DIR = Path(__file__).resolve().parent.parent.parent / "locale"

_translation = gettext.translation(DOMAIN, localedir=str(LOCALE_DIR), fallback=True,
                                   languages=GLib.get_language_names_with_category("LC_MESSAGES"))
_ = _translation.gettext
ngettext = _translation.ngettext
