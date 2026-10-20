"""Web search group (id "google"): direct URL, web search, Gemini, suggestions, keywords."""
import json
import logging
import re
from pathlib import Path
from urllib.parse import quote_plus

from .i18n import _

log = logging.getLogger(__name__)

# A query is worth searching once it is MIN_BYTES long in UTF-8. Counting bytes rather than characters scales with
# the script: three Latin letters, two Cyrillic, Greek, Hebrew or Arabic ones, a single Han, kana or Hangul
# character (one ideograph is already a word). The extension applies the same rule (logic.js, longEnough).
MIN_BYTES = 3


def long_enough(q: str) -> bool:
    return len(q.encode("utf-8")) >= MIN_BYTES


MAX_SUGGESTIONS = 4
DEFAULTS = Path(__file__).with_name("defaults") / "keywords.json"
ICON_URL = "web-browser-symbolic"
ICON_SEARCH = "system-search-symbolic"
ICON_GEMINI = "omnishell-gemini-symbolic"

# Top-level domain: letters of any script (.org, .рф, .中国) or its punycode form (xn--p1ai).
_DOMAIN = re.compile(r"^[\w-]+(\.[\w-]+)*\.([^\W\d_]{2,}|xn--[\w-]+)(:\d+)?(/\S*)?$", re.I)
_LOCAL = re.compile(r"^localhost(:\d+)?(/\S*)?$", re.I)


def looks_like_url(text: str) -> str | None:
    t = text.strip()
    if not t or any(c.isspace() for c in t):
        return None
    if re.match(r"^https?://\S+$", t, re.I):
        return t
    if _LOCAL.match(t):
        return "http://" + t
    if _DOMAIN.match(t):
        return "https://" + t
    return None


def load_keywords(path: Path | None, lang: str) -> dict[str, tuple[str, str]]:
    """Search keywords; "{lang}" in a URL template is the session language (Wikipedia edition)."""
    kw = {k: tuple(v) for k, v in json.loads(DEFAULTS.read_text()).items()}
    if path and path.exists():
        try:
            kw.update({k: (v[0], v[1]) for k, v in json.loads(path.read_text()).items()})
        except (ValueError, TypeError, IndexError, KeyError) as e:
            log.warning("keywords.json ignored (%s): %s", path, e)
    return {k: (label, tpl.replace("{lang}", lang)) for k, (label, tpl) in kw.items()}


def parse_suggest(body: bytes, content_type: str) -> list[str]:
    m = re.search(r"charset=([\w-]+)", content_type or "", re.I)
    try:
        data = json.loads(body.decode(m.group(1) if m else "utf-8"))
        return [s for s in data[1] if isinstance(s, str)]
    except (ValueError, LookupError, IndexError, TypeError):
        return []


def _item(id_, name, kind, icon, url="", description=""):
    return {"group": "google", "id": id_, "name": name, "description": description,
            "icon": icon, "kind": kind, "url": url}


def search_url(q: str) -> str:
    return "https://www.google.com/search?q=" + quote_plus(q)


def google_items(query: str, suggestions: list[str], keywords: dict) -> list[dict]:
    q = " ".join(query.split())
    if not long_enough(q):
        return []
    items = []
    head, _sep, rest = q.partition(" ")
    if rest and head in keywords:
        label, tpl = keywords[head]
        # Translators: search keyword result: "YouTube: cat videos".
        items.append(_item(f"google:kw:{head}", _("{label}: {query}").format(label=label, query=rest), "url", ICON_SEARCH,
                           tpl.replace("{q}", quote_plus(rest))))
    elif (url := looks_like_url(q)):
        items.append(_item("google:url", _("Open {url}").format(url=q), "url", ICON_URL, url))
    items.append(_item("google:search", _("Search “{query}” on Google").format(query=q), "search", ICON_SEARCH, search_url(q)))
    items.append(_item("google:gemini", _("Ask Gemini: “{query}”").format(query=q), "gemini", ICON_GEMINI))
    seen = {q.lower()}
    for s in suggestions:
        if s.lower() in seen:
            continue
        seen.add(s.lower())
        items.append(_item(f"google:sugg:{s}", s, "search", ICON_SEARCH, search_url(s)))
    n_fixed = sum(1 for i in items if not i["id"].startswith("google:sugg:"))
    return items[:n_fixed + MAX_SUGGESTIONS]
