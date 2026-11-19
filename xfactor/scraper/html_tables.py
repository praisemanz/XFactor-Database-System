"""Fetching and table-reading helpers for Wikipedia's rendered HTML."""
from __future__ import annotations

import io
import json
import re
import urllib.parse
import urllib.request
import warnings
from pathlib import Path

import pandas as pd
from bs4 import BeautifulSoup, Tag

from xfactor.scraper.cleaning import clean

RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"
API = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "XFactorDBStudentProject/1.0 (CMSC 4323 coursework)"

PAGES = {
    "main": "The_X_Factor_(British_TV_series)",
    "discography": "The_X_Factor_(British_TV_series)_discography",
    **{f"series_{n}": f"The_X_Factor_(British_TV_series)_series_{n}" for n in range(1, 16)},
}

warnings.filterwarnings("ignore", category=FutureWarning)


def fetch_all(force: bool = False) -> None:
    """Download each page's rendered HTML into data/raw/ (cached)."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for key, title in PAGES.items():
        target = RAW_DIR / f"{key}.json"
        if target.exists() and not force:
            continue
        query = urllib.parse.urlencode({
            "action": "parse", "page": title, "prop": "text",
            "format": "json", "formatversion": 2, "redirects": 1,
        })
        request = urllib.request.Request(f"{API}?{query}", headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=30) as response:
            target.write_bytes(response.read())
        print(f"fetched {title}")


def load_soup(key: str) -> BeautifulSoup:
    payload = json.loads((RAW_DIR / f"{key}.json").read_text(encoding="utf-8"))
    soup = BeautifulSoup(payload["parse"]["text"], "lxml")
    for tag in soup.find_all(attrs={"rowspan": True}):
        tag["rowspan"] = re.match(r"\d*", str(tag["rowspan"])).group() or "1"
    for tag in soup.find_all(attrs={"colspan": True}):
        tag["colspan"] = re.match(r"\d*", str(tag["colspan"])).group() or "1"
    for sup in soup.select("sup.reference, span.sortkey, style"):
        sup.decompose()
    return soup


def read_table(table: Tag) -> pd.DataFrame:
    """Read one <table> into a DataFrame with flat, reference-free column names."""
    frame = pd.read_html(io.StringIO(str(table)))[0]
    columns = []
    for col in frame.columns:
        label = col[-1] if isinstance(col, tuple) else col
        columns.append(clean(label) or "")
    frame.columns = _dedupe(columns)
    return frame


def _dedupe(columns: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    result = []
    for col in columns:
        base = re.sub(r"\.\d+$", "", col)
        count = seen.get(base, 0)
        result.append(base if count == 0 else f"{base}.{count}")
        seen[base] = count + 1
    return result


def heading_text(table: Tag, levels: tuple[str, ...] = ("h2", "h3", "h4")) -> str:
    heading = table.find_previous(list(levels))
    return heading.get_text(" ", strip=True) if heading else ""


def wikitables(soup: BeautifulSoup) -> list[Tag]:
    return soup.select("table.wikitable")
