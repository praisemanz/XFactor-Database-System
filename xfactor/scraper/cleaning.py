"""Text-cleaning helpers shared by every Wikipedia parser."""
from __future__ import annotations

import math
import re
from datetime import date, datetime

_REF = re.compile(r"\[[^\]]*\]")  # [12], [citation needed], [a]
_SPACE = re.compile(r"\s+")
_QUOTED = re.compile(r"[\"“”]([^\"“”]+)[\"“”]")
_TRAILING_PAREN = re.compile(r"\(([^()]+)\)\s*$")
_ORDINAL = re.compile(r"(\d+)(?:st|nd|rd|th)", re.IGNORECASE)

ALIASES = {
    "cheryl cole": "Cheryl",
    "cheryl fernandez-versini": "Cheryl",
    "cheryl (singer)": "Cheryl",
    "tulisa contostavlos": "Tulisa",
    "mel b": "Mel B",
}


def is_blank(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    return str(value).strip() in ("", "nan", "—", "–", "-", "N/A", "—N/a")


def clean(value: object) -> str | None:
    """Strip reference markers, footnote symbols and extra whitespace."""
    if is_blank(value):
        return None
    text = _REF.sub("", str(value))
    text = text.replace(" ", " ").replace("*", "").replace("†", "").replace("‡", "")
    text = _SPACE.sub(" ", text)
    text = re.sub(r"\s+([,;.)])", r"\1", text).replace("( ", "(").strip(" ,;")
    return text or None


def clean_category(value: object) -> str | None:
    """'16–24s' and '16-24s' are the same category: normalise dashes."""
    text = clean(value)
    return text.replace("–", "-").replace("—", "-") if text else None


def canonical_person(name: str) -> str:
    """Map alternate spellings of the same person to one canonical name."""
    stripped = re.sub(r"\s*\((singer|presenter|entertainer|musician)\)$", "", name.strip())
    return ALIASES.get(stripped.lower(), ALIASES.get(name.strip().lower(), stripped))


MENTOR_ALIASES = {"cole": "Cheryl", "fernandez-versini": "Cheryl", "cheryl": "Cheryl"}

# Acts that were renamed mid-series: name used in week tables -> name in the finalists table.
ACT_ALIASES = {"rhythmix": "littlemix"}


def norm_key(name: str | None) -> str:
    """Comparison key: lowercase alphanumerics only ("John & Edward" -> "johnandedward").

    A trailing parenthetical such as "(Wildcard Girls)" is ignored.
    """
    if not name:
        return ""
    base = re.sub(r"\s*\([^)]*\)\s*$", "", name)
    key = re.sub(r"[^a-z0-9]", "", base.lower().replace("&", "and"))
    return ACT_ALIASES.get(key, key)


def resolve_mentor(mentor: str | None, judges: tuple[str, ...]) -> str | None:
    """Match a surname as written in a table ("Cowell", "Cole") to a judge's full name."""
    if not mentor:
        return None
    alias = MENTOR_ALIASES.get(mentor.strip().lower())
    if alias:
        return alias
    wanted = norm_key(mentor)
    for judge in judges:
        if norm_key(judge) == wanted or norm_key(judge.split()[-1]) == wanted:
            return judge
    return canonical_person(mentor)


def split_song(cell: object) -> tuple[str | None, str | None]:
    """Return (title, artist-in-parentheses) from a song cell like '"Hero" (Mariah Carey)'."""
    text = clean(cell)
    if not text:
        return None, None
    quoted = _QUOTED.findall(text)
    title = " / ".join(q.strip() for q in quoted) if quoted else text.strip('"')
    artist = None
    paren = _TRAILING_PAREN.search(text)
    if quoted and paren:
        artist = paren.group(1).strip()
    return (title.strip() or None), artist


def to_int(value: object) -> int | None:
    text = clean(value)
    if not text:
        return None
    match = re.search(r"\d+", text.replace(",", ""))
    return int(match.group()) if match else None


def to_float(value: object) -> float | None:
    text = clean(value)
    if not text:
        return None
    match = re.search(r"\d+(?:\.\d+)?", text.replace(",", ""))
    return float(match.group()) if match else None


def parse_date(text: object, default_year: int | None = None) -> date | None:
    """Parse '22 August 2009', or '22 August' using default_year."""
    cleaned = clean(text)
    if not cleaned:
        return None
    cleaned = cleaned.split("/")[0].strip()
    for fmt in ("%d %B %Y", "%d %b %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            pass
    if default_year:
        for fmt in ("%d %B", "%d %b"):
            try:
                return datetime.strptime(f"{cleaned} {default_year}", f"{fmt} %Y").date()
            except ValueError:
                pass
    return None


def finishing_position(result: str | None) -> int | None:
    """'Winner' -> 1, 'Runner-Up' -> 2, '3rd Place' -> 3."""
    if not result:
        return None
    lowered = result.lower()
    if lowered.startswith("winner"):
        return 1
    if lowered.startswith("runner"):
        return 2
    match = _ORDINAL.search(lowered)
    return int(match.group(1)) if match else None


def split_names(text: str | None) -> tuple[str, ...]:
    """Split 'A, B and C' / 'A & B' into individual names."""
    if not text:
        return ()
    parts = re.split(r",|\band\b|&|/", text)
    return tuple(p.strip() for p in parts if p.strip())
