"""Parse each live-show week: show metadata plus every performance row."""
from __future__ import annotations

import re
from dataclasses import dataclass

import pandas as pd
from bs4 import BeautifulSoup, Tag

from xfactor.scraper.cleaning import clean, parse_date, split_song, to_int
from xfactor.scraper.html_tables import read_table, wikitables
from xfactor.scraper.records import LiveShowRecord, PerformanceRecord

_WEEK = re.compile(r"^Week\s+(?P<num>\d+)(?::\s*(?P<stage>[^(]+?))?\s*\((?P<dates>[^)]*)\)")
_ARTIST_COLS = ("artist", "hero", "diva", "band", "musician")
_PARTNER_COLS = ("partner",)
_SHOWDOWN = ("showdown", "sing-off", "sing off")


@dataclass(frozen=True)
class _Segment:
    """One 'Order -> Song [-> artist] [-> partner]' group of columns."""
    order: str
    song: str
    artist: str | None
    partner: str | None


def _segments(columns: list[str]) -> list[_Segment]:
    order_idx = [i for i, c in enumerate(columns) if c.lower().startswith("order")]
    segments = []
    for pos, start in enumerate(order_idx):
        end = order_idx[pos + 1] if pos + 1 < len(order_idx) else len(columns)
        window = [c for c in columns[start + 1:end] if not c.lower().startswith("result")]
        if not window:
            continue
        song = next((c for c in window if re.search(r"song|single", c, re.I)), window[0])
        rest = [c for c in window if c != song]
        artist = next((c for c in rest if any(k in c.lower() for k in _ARTIST_COLS)), None)
        partner = next((c for c in rest if any(k in c.lower() for k in _PARTNER_COLS)), None)
        segments.append(_Segment(order=columns[start], song=song, artist=artist, partner=partner))
    return segments


def _theme(heading: Tag) -> str | None:
    """Read the 'Theme:' bullet that follows a week heading (if any)."""
    container = heading.parent if heading.parent and "mw-heading" in heading.parent.get("class", []) else heading
    for sibling in container.find_next_siblings():
        if sibling.name in ("h2", "h3", "h4", "table") or "mw-heading" in sibling.get("class", []):
            return None
        if sibling.name == "ul":
            for item in sibling.find_all("li"):
                text = clean(item.get_text()) or ""
                if text.lower().startswith("theme"):
                    return clean(text.split(":", 1)[-1])
    return None


def _is_separator(values: list[object]) -> bool:
    texts = {clean(v) for v in values if clean(v)}
    return len(texts) == 1 and any(k in next(iter(texts)).lower() for k in _SHOWDOWN + ("details",))


def _rows(frame: pd.DataFrame, show: LiveShowRecord, night: int) -> list[PerformanceRecord]:
    columns = list(frame.columns)
    act_col = columns[0]
    result_col = next((c for c in columns if c.lower().startswith("result")), None)
    segments = _segments(columns)
    showdown = False
    out: list[PerformanceRecord] = []
    for _, row in frame.iterrows():
        values = [row[c] for c in columns]
        if _is_separator(values):
            showdown = True
            continue
        act = clean(row[act_col])
        if not act or act.lower() in ("act", "contestant") or parse_date(act, show.first_air_date.year if show.first_air_date else 2000):
            continue  # header repeats and "29 October" night-divider rows
        seen_songs: set[str] = set()
        for seg in segments:
            title, paren_artist = split_song(row[seg.song])
            if not title or title in seen_songs or title.lower() in ("n/a", "none"):
                continue
            seen_songs.add(title)
            artist = clean(row[seg.artist]) if seg.artist else None
            if artist and split_song(artist)[0] == title:
                artist = None  # a colspan copied the song cell into the artist column
            out.append(PerformanceRecord(
                series=show.series, week_number=show.week_number, night=night, act=act,
                running_order=to_int(row[seg.order]),
                song_title=title[:200],
                song_artist=(artist or paren_artist),
                duet_partner=clean(row[seg.partner]) if seg.partner else None,
                is_showdown=showdown,
                result=clean(row[result_col]) if result_col else None,
            ))
    return out


def parse_weeks(soup: BeautifulSoup, series: int, year: int) -> tuple[tuple[LiveShowRecord, ...], tuple[PerformanceRecord, ...]]:
    shows: dict[int, LiveShowRecord] = {}
    nights: dict[int, int] = {}
    performances: list[PerformanceRecord] = []
    for table in wikitables(soup):
        heading = table.find_previous(["h3", "h4"])
        match = _WEEK.match(heading.get_text(" ", strip=True)) if heading else None
        if not match:
            continue
        frame = read_table(table)
        if not any(c.lower().startswith("order") for c in frame.columns):
            continue  # "song choices" vote tables carry no performances
        week = int(match.group("num"))
        if week not in shows:
            dates = clean(match.group("dates"))
            first = re.split(r"/", dates or "")[0].strip()
            month = (dates or "").split()[-1] if dates else ""
            first_date = parse_date(first if not first.isdigit() else f"{first} {month}", year)
            stage = clean(match.group("stage")) or f"Week {week}"
            shows[week] = LiveShowRecord(series, week, stage, dates, first_date, _theme(heading))
        nights[week] = nights.get(week, 0) + 1
        performances.extend(_rows(frame, shows[week], nights[week]))
    return tuple(shows.values()), tuple(performances)
