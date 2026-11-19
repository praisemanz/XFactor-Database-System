"""Live shows, the songs performed on them, TV episodes and commercial releases."""
from __future__ import annotations

from datetime import date

from sqlalchemy import (
    Boolean, CheckConstraint, Date, Enum, ForeignKey, Index, Integer, Numeric, SmallInteger, String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from xfactor.models.acts import Act, SeriesAct
from xfactor.models.base import Base
from xfactor.models.competition import Series


class Artist(Base):
    """A recording artist: original performer of a covered song, or a duet partner."""
    __tablename__ = "artist"

    artist_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)


class Song(Base):
    __tablename__ = "song"
    __table_args__ = (Index("ix_song_title", "title"),)

    song_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    artist_id: Mapped[int | None] = mapped_column(ForeignKey("artist.artist_id", ondelete="SET NULL"))

    artist: Mapped[Artist | None] = relationship()


class LiveShow(Base):
    __tablename__ = "live_show"
    __table_args__ = (
        UniqueConstraint("series_id", "week_number", name="uq_live_show_week"),
        CheckConstraint("week_number BETWEEN 1 AND 20", name="ck_week_number_range"),
    )

    show_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    series_id: Mapped[int] = mapped_column(ForeignKey("series.series_id", ondelete="CASCADE"), nullable=False)
    week_number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    stage: Mapped[str] = mapped_column(String(40), nullable=False)
    air_dates: Mapped[str | None] = mapped_column(String(60))
    first_air_date: Mapped[date | None] = mapped_column(Date)
    theme: Mapped[str | None] = mapped_column(String(255))

    series: Mapped[Series] = relationship()
    performances: Mapped[list[Performance]] = relationship(back_populates="show", cascade="all, delete-orphan")


class Performance(Base):
    __tablename__ = "performance"
    __table_args__ = (
        CheckConstraint("running_order IS NULL OR running_order >= 1", name="ck_running_order_positive"),
        CheckConstraint("night IN (1, 2)", name="ck_night"),
        Index("ix_performance_song", "song_id"),
        Index("ix_performance_entry", "entry_id"),
    )

    performance_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    show_id: Mapped[int] = mapped_column(ForeignKey("live_show.show_id", ondelete="CASCADE"), nullable=False)
    entry_id: Mapped[int] = mapped_column(ForeignKey("series_act.entry_id", ondelete="CASCADE"), nullable=False)
    song_id: Mapped[int] = mapped_column(ForeignKey("song.song_id"), nullable=False)
    duet_partner_id: Mapped[int | None] = mapped_column(ForeignKey("artist.artist_id", ondelete="SET NULL"))
    night: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    running_order: Mapped[int | None] = mapped_column(SmallInteger)
    is_showdown: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    result_text: Mapped[str | None] = mapped_column(String(80))

    show: Mapped[LiveShow] = relationship(back_populates="performances")
    entry: Mapped[SeriesAct] = relationship()
    song: Mapped[Song] = relationship()
    duet_partner: Mapped[Artist | None] = relationship()


class Episode(Base):
    """A broadcast episode with its official BARB viewing figure."""
    __tablename__ = "episode"
    __table_args__ = (
        CheckConstraint("viewers_millions IS NULL OR viewers_millions >= 0", name="ck_viewers_non_negative"),
        Index("ix_episode_air_date", "air_date"),
    )

    episode_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    series_id: Mapped[int] = mapped_column(ForeignKey("series.series_id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    air_date: Mapped[date | None] = mapped_column(Date)
    viewers_millions: Mapped[float | None] = mapped_column(Numeric(5, 2))
    weekly_rank: Mapped[int | None] = mapped_column(SmallInteger)

    series: Mapped[Series] = relationship()


class Release(Base):
    """A single or album released by a former contestant (from the discography article)."""
    __tablename__ = "music_release"  # RELEASE is a reserved word in MySQL
    __table_args__ = (
        UniqueConstraint("act_id", "release_type", "title", name="uq_release_act_title"),
        CheckConstraint("uk_peak IS NULL OR uk_peak BETWEEN 1 AND 200", name="ck_uk_peak_range"),
    )

    release_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    act_id: Mapped[int] = mapped_column(ForeignKey("act.act_id", ondelete="CASCADE"), nullable=False)
    release_type: Mapped[str] = mapped_column(Enum("Single", "Album", name="release_type"), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    release_date: Mapped[date | None] = mapped_column(Date)
    uk_peak: Mapped[int | None] = mapped_column(SmallInteger)
    certification: Mapped[str | None] = mapped_column(String(60))

    act: Mapped[Act] = relationship()
