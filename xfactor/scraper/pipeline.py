"""Build a Dataset from the cached Wikipedia pages and save it as JSON.

Usage:  python -m xfactor.scraper.pipeline [--fetch]
"""
from __future__ import annotations

import dataclasses
import json
import sys
from datetime import date
from pathlib import Path

from xfactor.scraper import records as rec
from xfactor.scraper.html_tables import fetch_all, load_soup
from xfactor.scraper.parse_main import parse_discography, parse_overview
from xfactor.scraper.parse_series import (
    parse_acts, parse_judges, parse_mentorships, parse_presenters, parse_ratings,
)
from xfactor.scraper.parse_weeks import parse_weeks

PARSED_PATH = Path(__file__).resolve().parents[2] / "data" / "parsed" / "xfactor.json"
SERIES_COUNT = 15


def build_dataset() -> rec.Dataset:
    overview = parse_overview(load_soup("main"))
    series, mentorships, acts, shows, perfs, episodes = [], [], [], [], [], []
    for number in range(1, SERIES_COUNT + 1):
        soup = load_soup(f"series_{number}")
        info = overview.get(number, {})
        year = info["start_date"].year if info.get("start_date") else 2003 + number
        series.append(rec.SeriesRecord(
            number=number,
            start_date=info.get("start_date"),
            end_date=info.get("end_date"),
            num_episodes=info.get("num_episodes"),
            avg_viewers_millions=info.get("avg_viewers"),
            judges=parse_judges(soup),
            presenters=parse_presenters(soup),
        ))
        mentorships.extend(parse_mentorships(soup, number))
        acts.extend(parse_acts(soup, number))
        week_shows, week_perfs = parse_weeks(soup, number, year)
        shows.extend(week_shows)
        perfs.extend(week_perfs)
        episodes.extend(parse_ratings(soup, number, year))
    return rec.Dataset(
        series=tuple(series), mentorships=tuple(mentorships), acts=tuple(acts),
        live_shows=tuple(shows), performances=tuple(perfs), episodes=tuple(episodes),
        releases=parse_discography(load_soup("discography")),
    )


def _encode(value: object) -> object:
    if isinstance(value, date):
        return value.isoformat()
    raise TypeError(type(value))


def save_dataset(dataset: rec.Dataset, path: Path = PARSED_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dataclasses.asdict(dataset), default=_encode, indent=1), encoding="utf-8")


def _decode(cls: type, data: dict) -> object:
    kwargs = {}
    for f in dataclasses.fields(cls):
        value = data.get(f.name)
        if isinstance(value, str) and f.name.endswith("date"):
            value = date.fromisoformat(value)
        elif isinstance(value, list):
            value = tuple(tuple(v) if isinstance(v, list) else v for v in value)
        kwargs[f.name] = value
    return cls(**kwargs)


def load_dataset(path: Path = PARSED_PATH) -> rec.Dataset:
    raw = json.loads(path.read_text(encoding="utf-8"))
    kinds = {
        "series": rec.SeriesRecord, "mentorships": rec.MentorshipRecord, "acts": rec.ActRecord,
        "live_shows": rec.LiveShowRecord, "performances": rec.PerformanceRecord,
        "episodes": rec.EpisodeRecord, "releases": rec.ReleaseRecord,
    }
    return rec.Dataset(**{k: tuple(_decode(cls, item) for item in raw[k]) for k, cls in kinds.items()})


def main() -> None:
    if "--fetch" in sys.argv:
        fetch_all(force=True)
    dataset = build_dataset()
    save_dataset(dataset)
    for name in ("series", "mentorships", "acts", "live_shows", "performances", "episodes", "releases"):
        print(f"{name:>13}: {len(getattr(dataset, name))}")
    print(f"saved -> {PARSED_PATH}")


if __name__ == "__main__":
    main()
