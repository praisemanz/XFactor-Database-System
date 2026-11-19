"""Immutable records produced by the parsers and consumed by the loader.

These are the module boundary between scraping and database loading:
the loader never touches HTML, and the parsers never touch the database.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class SeriesRecord:
    number: int
    start_date: date | None
    end_date: date | None
    num_episodes: int | None
    avg_viewers_millions: float | None
    judges: tuple[tuple[str, bool], ...] = ()          # (name, is_guest)
    presenters: tuple[tuple[str, str], ...] = ()       # (name, programme)


@dataclass(frozen=True)
class MentorshipRecord:
    series: int
    category: str
    mentor: str               # surname or full name as written on the page
    house_location: str | None
    assistants: tuple[str, ...] = ()


@dataclass(frozen=True)
class ActRecord:
    series: int
    name: str
    age_text: str | None
    hometown: str | None
    category: str | None
    mentor: str | None
    result: str | None
    final_position: int | None
    is_group: bool


@dataclass(frozen=True)
class LiveShowRecord:
    series: int
    week_number: int
    stage: str                # "Week 3", "Quarter-Final", "Final" ...
    air_dates: str | None
    first_air_date: date | None
    theme: str | None


@dataclass(frozen=True)
class PerformanceRecord:
    series: int
    week_number: int
    night: int
    act: str
    running_order: int | None
    song_title: str
    song_artist: str | None
    duet_partner: str | None
    is_showdown: bool
    result: str | None


@dataclass(frozen=True)
class EpisodeRecord:
    series: int
    title: str
    air_date: date | None
    viewers_millions: float | None
    weekly_rank: int | None


@dataclass(frozen=True)
class ReleaseRecord:
    artist: str
    series: int | None
    position_in_show: str | None
    release_type: str         # "Single" | "Album"
    title: str
    release_date: date | None
    uk_peak: int | None
    certification: str | None


@dataclass(frozen=True)
class Dataset:
    series: tuple[SeriesRecord, ...] = ()
    mentorships: tuple[MentorshipRecord, ...] = ()
    acts: tuple[ActRecord, ...] = ()
    live_shows: tuple[LiveShowRecord, ...] = ()
    performances: tuple[PerformanceRecord, ...] = ()
    episodes: tuple[EpisodeRecord, ...] = ()
    releases: tuple[ReleaseRecord, ...] = field(default_factory=tuple)
