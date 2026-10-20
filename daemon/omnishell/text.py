"""Text normalisation for searches (case and combining marks ignored, any script)."""
import unicodedata


def normalize(s: str) -> str:
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return " ".join(s.casefold().split())


def matches(query: str, *fields: str | None) -> bool:
    words = normalize(query).split()
    hay = [normalize(f) for f in fields if f]
    return bool(words) and all(any(w in h for h in hay) for w in words)
