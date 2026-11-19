"""Parse one series page: infobox people, judges' houses, finalists and ratings."""
from __future__ import annotations

import re

from bs4 import BeautifulSoup, Tag

from xfactor.scraper.cleaning import (
    canonical_person, clean, clean_category, finishing_position, parse_date, split_names, to_float, to_int,
)
from xfactor.scraper.html_tables import heading_text, read_table, wikitables
from xfactor.scraper.records import ActRecord, EpisodeRecord, MentorshipRecord

_CATEGORY = re.compile(r"^(?P<cat>.+?)\s*\((?P<mentor>[^()]+)\)\s*$")
_NETWORK_HINT = re.compile(r"ITV2|ITV\b|Xtra", re.IGNORECASE)


def _infobox_cell(soup: BeautifulSoup, labels: tuple[str, ...]) -> Tag | None:
    box = soup.select_one("table.infobox")
    if box is None:
        return None
    for row in box.find_all("tr"):
        header = row.find("th")
        if header and header.get_text(strip=True) in labels:
            return row.find("td")
    return None


def parse_judges(soup: BeautifulSoup) -> tuple[tuple[str, bool], ...]:
    cell = _infobox_cell(soup, ("Judges",))
    if cell is None:
        return ()
    judges = []
    for item in cell.find_all("li") or [cell]:
        text = item.get_text(" ", strip=True)
        link = item.find("a")
        name = link.get("title") if link and link.get("title") else link.get_text() if link else text
        name = canonical_person(re.sub(r"\(guest\)", "", name).strip())
        note = text[len(link.get_text()):] if link else ""
        # "(Glasgow auditions)" marks a guest; "(… permanent from …)" does not.
        is_guest = "(" in note and "permanent" not in note.lower()
        judges.append((name, is_guest))
    return tuple(dict.fromkeys(judges))


def parse_presenters(soup: BeautifulSoup) -> tuple[tuple[str, str], ...]:
    """Return (presenter, programme). ITV2 hosts present spin-off 'The Xtra Factor'."""
    cell = _infobox_cell(soup, ("Presented by", "Hosted by", "Host", "Hosts"))
    if cell is None:
        return ()
    people: list[tuple[str, str]] = []
    for link in cell.find_all("a"):
        title = link.get("title") or link.get_text()
        if _NETWORK_HINT.search(title):
            continue
        tail = ""
        for sibling in link.next_siblings:
            if isinstance(sibling, Tag) and sibling.name == "br":
                break
            tail += sibling.get_text() if isinstance(sibling, Tag) else str(sibling)
            if ")" in tail:
                break
        programme = "The Xtra Factor" if "ITV2" in tail else "The X Factor"
        people.append((canonical_person(title), programme))
    return tuple(dict.fromkeys(people))


def parse_mentorships(soup: BeautifulSoup, series: int) -> tuple[MentorshipRecord, ...]:
    for table in wikitables(soup):
        frame = read_table(table)
        cols = list(frame.columns)
        if not cols or cols[0] != "Judge" or not any(c.startswith("Category") for c in cols):
            continue
        cat_col = next(c for c in cols if c.startswith("Category"))
        loc_col = next((c for c in cols if c.startswith("Location")), None)
        asst_col = next((c for c in cols if c.startswith(("Assistant", "Guest Mentor"))), None)
        records = []
        for _, row in frame.iterrows():
            judge, category = clean(row["Judge"]), clean_category(row[cat_col])
            if not judge or not category:
                continue
            records.append(MentorshipRecord(
                series=series,
                category=category,
                mentor=judge,
                house_location=clean(row[loc_col]) if loc_col else None,
                assistants=split_names(clean(row[asst_col])) if asst_col else (),
            ))
        return tuple(records)
    return ()


def _is_group(name: str, age: str | None, category: str | None, hometown: str | None) -> bool:
    if category and "group" in category.lower():
        return True
    return bool(age and re.search(r"\d\s*[–-]\s*\d", age)) or hometown == "Various"


def parse_acts(soup: BeautifulSoup, series: int) -> tuple[ActRecord, ...]:
    for table in wikitables(soup):
        if not heading_text(table, ("h2",)).startswith("Acts") and "Finalists" not in heading_text(table, ("h2", "h3")):
            continue
        frame = read_table(table)
        if "Act" not in frame.columns:
            continue
        cat_col = next(c for c in frame.columns if c.startswith("Category"))
        records = []
        for index, row in enumerate(frame.itertuples(index=False), start=1):
            values = dict(zip(frame.columns, row))
            name = clean(values["Act"])
            if not name:
                continue
            match = _CATEGORY.match(clean(values[cat_col]) or "")
            category = clean_category(match.group("cat") if match else values[cat_col])
            mentor = match.group("mentor") if match else None
            result = clean(values.get("Result"))
            age = clean(values.get("Age(s)"))
            hometown = clean(values.get("Hometown"))
            records.append(ActRecord(
                series=series, name=name, age_text=age, hometown=hometown,
                category=category, mentor=mentor, result=result,
                final_position=finishing_position(result) or index,
                is_group=_is_group(name, age, category, hometown),
            ))
        return tuple(records)
    return ()


def parse_ratings(soup: BeautifulSoup, series: int, year: int) -> tuple[EpisodeRecord, ...]:
    for table in wikitables(soup):
        if not heading_text(table).startswith(("Ratings", "Viewing")):
            continue
        frame = read_table(table)
        cols = list(frame.columns)
        if "Episode" not in cols:
            continue
        date_col = next((c for c in cols if "date" in c.lower() or c == "Date"), None)
        rating_col = next((c for c in cols if "rating" in c.lower()), None)
        rank_col = next((c for c in cols if "rank" in c.lower()), None)
        records = []
        for _, row in frame.iterrows():
            title = clean(row["Episode"])
            if not title or title.lower().startswith(("average", "series average")):
                continue
            records.append(EpisodeRecord(
                series=series,
                title=title,
                air_date=parse_date(row[date_col], year) if date_col else None,
                viewers_millions=to_float(row[rating_col]) if rating_col else None,
                weekly_rank=to_int(row[rank_col]) if rank_col else None,
            ))
        return tuple(records)
    return ()
