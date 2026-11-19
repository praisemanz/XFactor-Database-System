"""Populate the database from the parsed Wikipedia dataset through the ORM.

Usage:  python -m xfactor.loader [--reset]
"""
from __future__ import annotations

import sys
from collections import Counter
from collections.abc import Callable
from typing import TypeVar

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from xfactor import models as m
from xfactor.db import session_scope
from xfactor.scraper.cleaning import canonical_person, norm_key, resolve_mentor
from xfactor.scraper.pipeline import load_dataset
from xfactor.scraper.records import Dataset
from xfactor.sql.apply import create_database, create_schema

T = TypeVar("T")


class _Cache:
    """Get-or-create helper so each lookup row (person, artist, ...) is inserted once."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.store: dict[tuple, object] = {}

    def get(self, key: tuple, factory: Callable[[], T]) -> T:
        if key not in self.store:
            obj = factory()
            self.session.add(obj)
            self.store[key] = obj
        return self.store[key]  # type: ignore[return-value]


def _load_series(session: Session, data: Dataset, cache: _Cache) -> dict[int, m.Series]:
    series_by_number: dict[int, m.Series] = {}
    for rec in data.series:
        series = m.Series(series_number=rec.number, start_date=rec.start_date, end_date=rec.end_date,
                          num_episodes=rec.num_episodes, avg_viewers_millions=rec.avg_viewers_millions)
        session.add(series)
        for name, is_guest in rec.judges:
            person = cache.get(("person", name), lambda n=name: m.Person(full_name=n))
            series.judges.append(m.SeriesJudge(person=person, is_guest=is_guest))
        for name, programme in rec.presenters:
            person = cache.get(("person", name), lambda n=name: m.Person(full_name=n))
            series.presenters.append(m.SeriesPresenter(person=person, programme=programme))
        series_by_number[rec.number] = series
    return series_by_number


def _load_mentorships(data: Dataset, series: dict[int, m.Series], cache: _Cache) -> dict[tuple, m.Mentorship]:
    judges = {r.number: tuple(name for name, _ in r.judges) for r in data.series}
    out: dict[tuple, m.Mentorship] = {}
    for rec in data.mentorships:
        mentor = resolve_mentor(rec.mentor, judges[rec.series])
        category = cache.get(("category", rec.category), lambda c=rec.category: m.Category(name=c))
        mentorship = m.Mentorship(
            category=category, house_location=rec.house_location,
            mentor=cache.get(("person", mentor), lambda n=mentor: m.Person(full_name=n)),
        )
        for assistant in dict.fromkeys(canonical_person(a) for a in rec.assistants):
            person = cache.get(("person", assistant), lambda n=assistant: m.Person(full_name=n))
            mentorship.assistants.append(m.MentorshipAssistant(person=person))
        series[rec.series].mentorships.append(mentorship)
        out[(rec.series, norm_key(rec.category))] = mentorship
    return out


def _load_acts(data: Dataset, series: dict[int, m.Series], mentorships: dict[tuple, m.Mentorship],
               cache: _Cache) -> dict[tuple, m.SeriesAct]:
    entries: dict[tuple, m.SeriesAct] = {}
    for rec in data.acts:
        act = cache.get(("act", norm_key(rec.name)), lambda r=rec: m.Act(name=r.name, is_group=r.is_group))
        hometown = (cache.get(("hometown", rec.hometown), lambda h=rec.hometown: m.Hometown(name=h))
                    if rec.hometown else None)
        entry = m.SeriesAct(
            series=series[rec.series], act=act, hometown=hometown, age_text=rec.age_text,
            final_position=rec.final_position, result_text=rec.result,
            mentorship=mentorships.get((rec.series, norm_key(rec.category))),
        )
        entries[(rec.series, norm_key(rec.name))] = entry
    return entries


def _load_shows(data: Dataset, series: dict[int, m.Series], entries: dict[tuple, m.SeriesAct],
                cache: _Cache, session: Session) -> Counter:
    shows: dict[tuple, m.LiveShow] = {}
    for rec in data.live_shows:
        show = m.LiveShow(series=series[rec.series], week_number=rec.week_number, stage=rec.stage,
                          air_dates=rec.air_dates, first_air_date=rec.first_air_date,
                          theme=rec.theme[:255] if rec.theme else None)
        session.add(show)
        shows[(rec.series, rec.week_number)] = show
    skipped: Counter = Counter()
    for rec in data.performances:
        entry = entries.get((rec.series, norm_key(rec.act)))
        if entry is None:
            skipped[(rec.series, rec.act)] += 1
            continue
        artist = (cache.get(("artist", rec.song_artist.lower()), lambda a=rec.song_artist: m.Artist(name=a[:160]))
                  if rec.song_artist else None)
        song_key = ("song", rec.song_title.lower(), (rec.song_artist or "").lower())
        song = cache.get(song_key, lambda r=rec, a=artist: m.Song(title=r.song_title, artist=a))
        partner = (cache.get(("artist", rec.duet_partner.lower()), lambda p=rec.duet_partner: m.Artist(name=p[:160]))
                   if rec.duet_partner else None)
        session.add(m.Performance(
            show=shows[(rec.series, rec.week_number)], entry=entry, song=song, duet_partner=partner,
            night=min(rec.night, 2), running_order=rec.running_order, is_showdown=rec.is_showdown,
            result_text=rec.result[:80] if rec.result else None,
        ))
    return skipped


def _load_episodes_and_releases(data: Dataset, series: dict[int, m.Series], cache: _Cache,
                                session: Session) -> None:
    for rec in data.episodes:
        session.add(m.Episode(series=series[rec.series], title=rec.title[:120], air_date=rec.air_date,
                              viewers_millions=rec.viewers_millions, weekly_rank=rec.weekly_rank))
    seen: set[tuple] = set()
    for rec in data.releases:
        key = (norm_key(rec.artist), rec.release_type, rec.title.lower())
        if key in seen:
            continue
        seen.add(key)
        act = cache.get(("act", norm_key(rec.artist)), lambda r=rec: m.Act(name=r.artist, is_group=False))
        peak = rec.uk_peak if rec.uk_peak and 1 <= rec.uk_peak <= 200 else None
        session.add(m.Release(act=act, release_type=rec.release_type, title=rec.title,
                              release_date=rec.release_date, uk_peak=peak, certification=rec.certification))


def populate(session: Session, data: Dataset) -> Counter:
    cache = _Cache(session)
    series = _load_series(session, data, cache)
    mentorships = _load_mentorships(data, series, cache)
    entries = _load_acts(data, series, mentorships, cache)
    skipped = _load_shows(data, series, entries, cache, session)
    _load_episodes_and_releases(data, series, cache, session)
    return skipped


def table_counts(session: Session) -> dict[str, int]:
    return {model.__tablename__: session.scalar(select(func.count()).select_from(model))
            for model in m.Base.__subclasses__() if hasattr(model, "__tablename__")}


def main() -> None:
    create_database()
    create_schema(drop_first="--reset" in sys.argv)
    with session_scope() as session:
        if session.scalar(select(func.count()).select_from(m.Series)):
            print("Database already populated. Use --reset to rebuild it.")
            return
        skipped = populate(session, load_dataset())
    with session_scope() as session:
        counts = table_counts(session)
    for table, count in sorted(counts.items()):
        print(f"{table:>22}: {count}")
    print(f"{'TOTAL':>22}: {sum(counts.values())}")
    if skipped:
        print(f"skipped {sum(skipped.values())} performance rows with no matching finalist: {dict(skipped)}")


if __name__ == "__main__":
    main()
