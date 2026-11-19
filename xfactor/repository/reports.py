"""Read-side queries: a multi-join ORM query, VIEW access, and STORED PROCEDURE calls."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import MetaData, Table, func, select, text
from sqlalchemy.orm import Session, aliased

from xfactor import models as m


@dataclass(frozen=True)
class ResultTable:
    """Column names + rows, ready to print in a terminal or render as HTML."""
    columns: tuple[str, ...]
    rows: tuple[tuple[Any, ...], ...]


def _table(result: Any) -> ResultTable:
    return ResultTable(tuple(result.keys()), tuple(tuple(r) for r in result.fetchall()))


# --------------------------------------------------------------------------- JOIN

def songs_by_mentor(session: Session, mentor: str, limit: int = 50) -> ResultTable:
    """Multi-join query (7 tables) built with the ORM:

    person -> mentorship -> category, series -> series_act -> act -> performance -> song
    "Which songs did <mentor>'s acts sing, and how did those acts finish?"
    """
    mentor_p = aliased(m.Person)
    stmt = (
        select(
            m.Series.series_number.label("series"),
            m.Category.name.label("category"),
            m.Act.name.label("act"),
            m.LiveShow.week_number.label("week"),
            m.Song.title.label("song"),
            m.SeriesAct.final_position.label("final_position"),
        )
        .join(m.Mentorship, m.Mentorship.mentor_id == mentor_p.person_id)
        .join(m.Category, m.Category.category_id == m.Mentorship.category_id)
        .join(m.Series, m.Series.series_id == m.Mentorship.series_id)
        .join(m.SeriesAct, m.SeriesAct.mentorship_id == m.Mentorship.mentorship_id)
        .join(m.Act, m.Act.act_id == m.SeriesAct.act_id)
        .join(m.Performance, m.Performance.entry_id == m.SeriesAct.entry_id)
        .join(m.LiveShow, m.LiveShow.show_id == m.Performance.show_id)
        .join(m.Song, m.Song.song_id == m.Performance.song_id)
        .select_from(mentor_p)
        .where(mentor_p.full_name.like(f"%{mentor}%"))
        .order_by(m.Series.series_number, m.LiveShow.week_number, m.Performance.running_order)
        .limit(limit)
    )
    return _table(session.execute(stmt))


def most_performed_songs(session: Session, limit: int = 15) -> ResultTable:
    """Aggregate join: songs sung most often across all series."""
    stmt = (
        select(m.Song.title.label("song"), m.Artist.name.label("artist"),
               func.count(m.Performance.performance_id).label("times_performed"))
        .join(m.Performance, m.Performance.song_id == m.Song.song_id)
        .outerjoin(m.Artist, m.Artist.artist_id == m.Song.artist_id)
        .group_by(m.Song.song_id, m.Song.title, m.Artist.name)
        .order_by(func.count(m.Performance.performance_id).desc(), m.Song.title)
        .limit(limit)
    )
    return _table(session.execute(stmt))


# --------------------------------------------------------------------------- VIEWS

VIEW_NAMES = ("v_series_summary", "v_performance_detail", "v_mentor_stats")


def reflect_view(session: Session, name: str) -> Table:
    """Map a database VIEW into SQLAlchemy as a read-only Table (separate MetaData so
    `create_all` never tries to create it as a real table)."""
    if name not in VIEW_NAMES:
        raise ValueError(f"unknown view {name!r}")
    return Table(name, MetaData(), autoload_with=session.get_bind())


def read_view(session: Session, name: str, limit: int = 100, **filters: Any) -> ResultTable:
    view = reflect_view(session, name)
    stmt = select(view)
    for column, value in filters.items():
        if value is not None:
            stmt = stmt.where(view.c[column] == value)
    return _table(session.execute(stmt.limit(limit)))


# --------------------------------------------------------------------------- STORED PROCEDURES

def series_leaderboard(session: Session, series_number: int) -> ResultTable:
    return _table(session.execute(text("CALL sp_series_leaderboard(:n)"), {"n": series_number}))


def act_journey(session: Session, act_name: str) -> ResultTable:
    return _table(session.execute(text("CALL sp_act_journey(:name)"), {"name": act_name}))


def record_showdown_result(session: Session, series: int, week: int, act: str, result: str) -> int:
    """Call the write procedure and read its OUT parameter through a session variable."""
    session.execute(
        text("CALL sp_record_showdown_result(:s, :w, :a, :r, @rows_updated)"),
        {"s": series, "w": week, "a": act, "r": result},
    )
    return int(session.execute(text("SELECT @rows_updated")).scalar() or 0)
