"""Parse the main article (series overview) and the discography article."""
from __future__ import annotations

from bs4 import BeautifulSoup

from xfactor.scraper.cleaning import clean, parse_date, split_song, to_float, to_int
from xfactor.scraper.html_tables import heading_text, read_table, wikitables
from xfactor.scraper.records import ReleaseRecord


def parse_overview(soup: BeautifulSoup) -> dict[int, dict]:
    """Series number -> {start_date, end_date, num_episodes, avg_viewers}."""
    for table in wikitables(soup):
        if not heading_text(table).startswith("Series overview"):
            continue
        frame = read_table(table)
        cols = list(frame.columns)
        avg_col = next(c for c in cols if c.lower().startswith("average"))
        out = {}
        for _, row in frame.iterrows():
            number = to_int(row["Series"])
            if number is None:
                continue
            out[number] = {
                "start_date": parse_date(row["First episode"]),
                "end_date": parse_date(row["Last episode"]),
                "num_episodes": to_int(row["No. of episodes"]),
                "avg_viewers": to_float(row[avg_col]),
            }
        return out
    return {}


def parse_discography(soup: BeautifulSoup) -> tuple[ReleaseRecord, ...]:
    releases: list[ReleaseRecord] = []
    for table in wikitables(soup):
        section = heading_text(table, ("h2",))
        if section not in ("Singles", "Albums"):
            continue
        frame = read_table(table)
        cols = list(frame.columns)
        title_col = next(c for c in cols if c.endswith("title"))
        peak_col = next(c for c in cols if "peak" in c.lower())
        cert_col = next((c for c in cols if "certification" in c.lower()), None)
        for _, row in frame.iterrows():
            artist = clean(row["Artist"])
            raw_title = clean(row[title_col])
            if not artist or not raw_title:
                continue
            title = split_song(raw_title)[0] if section == "Singles" else raw_title
            cert = clean(row[cert_col]) if cert_col else None
            releases.append(ReleaseRecord(
                artist=artist,
                series=to_int(row["Series"]),
                position_in_show=clean(row["Position in show"]),
                release_type="Single" if section == "Singles" else "Album",
                title=(title or raw_title)[:200],
                release_date=parse_date(row["UK release date"]),
                uk_peak=to_int(row[peak_col]),
                certification=None if cert in (None, "N/a", "—N/a") else cert[:60],
            ))
    return tuple(dict.fromkeys(releases))
