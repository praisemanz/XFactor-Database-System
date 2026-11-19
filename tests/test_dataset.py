"""Sanity checks over the full parsed snapshot (data/parsed/xfactor.json)."""
from collections import Counter

import pytest

from xfactor.scraper.cleaning import norm_key
from xfactor.scraper.pipeline import PARSED_PATH, load_dataset

pytestmark = pytest.mark.skipif(not PARSED_PATH.exists(), reason="run the scraper pipeline first")


@pytest.fixture(scope="module")
def data():
    return load_dataset()


def test_every_series_has_one_winner(data):
    winners = Counter(a.series for a in data.acts if a.final_position == 1)
    assert sorted(winners) == list(range(1, 16))
    assert set(winners.values()) == {1}


def test_known_winners(data):
    winners = {a.series: a.name for a in data.acts if a.final_position == 1}
    assert winners[3] == "Leona Lewis"
    assert winners[6] == "Joe McElderry"
    assert winners[8] == "Little Mix"


def test_large_dataset(data):
    total = sum(len(getattr(data, f)) for f in ("series", "mentorships", "acts", "live_shows",
                                                "performances", "episodes", "releases"))
    assert total >= 2000


def test_nearly_all_performances_match_a_finalist(data):
    finalists = {(a.series, norm_key(a.name)) for a in data.acts}
    unmatched = [p for p in data.performances if (p.series, norm_key(p.act)) not in finalists]
    assert len(unmatched) / len(data.performances) < 0.01


def test_each_series_has_four_mentors(data):
    per_series = Counter(mt.series for mt in data.mentorships)
    assert all(count >= 3 for count in per_series.values())
