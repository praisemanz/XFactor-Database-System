"""Series, the people who ran them, and the category/mentor structure."""
from __future__ import annotations

from datetime import date

from sqlalchemy import (
    Boolean, CheckConstraint, Date, Enum, ForeignKey, Integer, Numeric, String, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from xfactor.models.base import Base


class Series(Base):
    __tablename__ = "series"
    __table_args__ = (
        CheckConstraint("series_number BETWEEN 1 AND 99", name="ck_series_number_range"),
        CheckConstraint("end_date IS NULL OR start_date IS NULL OR end_date >= start_date",
                        name="ck_series_dates_ordered"),
    )

    series_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    series_number: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    num_episodes: Mapped[int | None] = mapped_column(Integer)
    avg_viewers_millions: Mapped[float | None] = mapped_column(Numeric(5, 2))

    judges: Mapped[list[SeriesJudge]] = relationship(back_populates="series", cascade="all, delete-orphan")
    presenters: Mapped[list[SeriesPresenter]] = relationship(back_populates="series", cascade="all, delete-orphan")
    mentorships: Mapped[list[Mentorship]] = relationship(back_populates="series", cascade="all, delete-orphan")


class Person(Base):
    """Judges, presenters and judges'-houses assistants."""
    __tablename__ = "person"

    person_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    full_name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)


class SeriesJudge(Base):
    __tablename__ = "series_judge"

    series_id: Mapped[int] = mapped_column(ForeignKey("series.series_id", ondelete="CASCADE"), primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("person.person_id", ondelete="CASCADE"), primary_key=True)
    is_guest: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    series: Mapped[Series] = relationship(back_populates="judges")
    person: Mapped[Person] = relationship()


class SeriesPresenter(Base):
    __tablename__ = "series_presenter"

    series_id: Mapped[int] = mapped_column(ForeignKey("series.series_id", ondelete="CASCADE"), primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("person.person_id", ondelete="CASCADE"), primary_key=True)
    programme: Mapped[str] = mapped_column(
        Enum("The X Factor", "The Xtra Factor", name="programme"), primary_key=True)

    series: Mapped[Series] = relationship(back_populates="presenters")
    person: Mapped[Person] = relationship()


class Category(Base):
    __tablename__ = "category"

    category_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)


class Mentorship(Base):
    """One judge mentoring one category in one series (the 'judges' houses' stage)."""
    __tablename__ = "mentorship"
    __table_args__ = (UniqueConstraint("series_id", "category_id", name="uq_mentorship_series_category"),)

    mentorship_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    series_id: Mapped[int] = mapped_column(ForeignKey("series.series_id", ondelete="CASCADE"), nullable=False)
    category_id: Mapped[int] = mapped_column(ForeignKey("category.category_id"), nullable=False)
    mentor_id: Mapped[int] = mapped_column(ForeignKey("person.person_id"), nullable=False)
    house_location: Mapped[str | None] = mapped_column(String(120))

    series: Mapped[Series] = relationship(back_populates="mentorships")
    category: Mapped[Category] = relationship()
    mentor: Mapped[Person] = relationship()
    assistants: Mapped[list[MentorshipAssistant]] = relationship(cascade="all, delete-orphan")


class MentorshipAssistant(Base):
    __tablename__ = "mentorship_assistant"

    mentorship_id: Mapped[int] = mapped_column(
        ForeignKey("mentorship.mentorship_id", ondelete="CASCADE"), primary_key=True)
    person_id: Mapped[int] = mapped_column(ForeignKey("person.person_id", ondelete="CASCADE"), primary_key=True)

    person: Mapped[Person] = relationship()
