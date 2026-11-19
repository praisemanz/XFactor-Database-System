"""ORM models. Import from here so every table is registered on Base.metadata."""
from xfactor.models.acts import Act, Hometown, SeriesAct
from xfactor.models.base import Base
from xfactor.models.competition import (
    Category, Mentorship, MentorshipAssistant, Person, Series, SeriesJudge, SeriesPresenter,
)
from xfactor.models.shows import Artist, Episode, LiveShow, Performance, Release, Song

__all__ = [
    "Base", "Series", "Person", "SeriesJudge", "SeriesPresenter", "Category", "Mentorship",
    "MentorshipAssistant", "Hometown", "Act", "SeriesAct", "Artist", "Song", "LiveShow",
    "Performance", "Episode", "Release",
]
