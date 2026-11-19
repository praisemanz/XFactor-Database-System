"""Contestants (acts), where they come from, and their run in a series."""
from __future__ import annotations

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from xfactor.models.base import Base
from xfactor.models.competition import Mentorship, Series


class Hometown(Base):
    __tablename__ = "hometown"

    hometown_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)


class Act(Base):
    """A solo artist or group. The same act can enter more than one series."""
    __tablename__ = "act"

    act_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    is_group: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    entries: Mapped[list[SeriesAct]] = relationship(back_populates="act", cascade="all, delete-orphan")


class SeriesAct(Base):
    """An act's participation in one series as a live-show finalist."""
    __tablename__ = "series_act"
    __table_args__ = (
        UniqueConstraint("series_id", "act_id", name="uq_series_act"),
        CheckConstraint("final_position IS NULL OR final_position >= 1", name="ck_final_position_positive"),
        Index("ix_series_act_position", "series_id", "final_position"),
    )

    entry_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    series_id: Mapped[int] = mapped_column(ForeignKey("series.series_id", ondelete="CASCADE"), nullable=False)
    act_id: Mapped[int] = mapped_column(ForeignKey("act.act_id", ondelete="CASCADE"), nullable=False)
    mentorship_id: Mapped[int | None] = mapped_column(ForeignKey("mentorship.mentorship_id", ondelete="SET NULL"))
    hometown_id: Mapped[int | None] = mapped_column(ForeignKey("hometown.hometown_id", ondelete="SET NULL"))
    age_text: Mapped[str | None] = mapped_column(String(20))
    final_position: Mapped[int | None] = mapped_column(Integer)
    result_text: Mapped[str | None] = mapped_column(String(60))

    series: Mapped[Series] = relationship()
    act: Mapped[Act] = relationship(back_populates="entries")
    mentorship: Mapped[Mentorship | None] = relationship()
    hometown: Mapped[Hometown | None] = relationship()
