from datetime import date

import pytest

from xfactor.scraper.cleaning import (
    canonical_person, clean, finishing_position, norm_key, parse_date, resolve_mentor, split_names,
    split_song, to_float, to_int,
)


@pytest.mark.parametrize("raw, expected", [
    ("Joe McElderry[12]", "Joe McElderry"),
    ("  Over 25s  (Cowell)* ", "Over 25s (Cowell)"),
    (float("nan"), None),
    ("—", None),
    ("Result[citation needed]", "Result"),
])
def test_clean(raw, expected):
    assert clean(raw) == expected


def test_split_song_with_original_artist():
    assert split_song('"Hero" (Mariah Carey)') == ("Hero", "Mariah Carey")


def test_split_song_mashup_and_no_artist():
    assert split_song('"Bad Romance" / "Poker Face"') == ("Bad Romance / Poker Face", None)
    assert split_song('"Hallelujah"') == ("Hallelujah", None)
    assert split_song(None) == (None, None)


@pytest.mark.parametrize("result, position", [
    ("Winner", 1), ("Runner-Up", 2), ("3rd Place", 3), ("12th Place", 12), ("Withdrew", None), (None, None),
])
def test_finishing_position(result, position):
    assert finishing_position(result) == position


def test_parse_date_with_and_without_year():
    assert parse_date("22 August 2009") == date(2009, 8, 22)
    assert parse_date("10/11 October", 2009) is None  # needs pre-splitting by the caller
    assert parse_date("10 October", 2009) == date(2009, 10, 10)
    assert parse_date("garbage") is None


def test_numbers():
    assert to_int("12th") == 12
    assert to_int("DNC") is None
    assert to_float("11.00[3]") == 11.0
    assert to_float("1,234.5") == 1234.5


def test_norm_key_ignores_case_punctuation_and_wildcard_suffix():
    assert norm_key("John & Edward") == norm_key("john and edward")
    assert norm_key("Lola Saunders (Wildcard Girls)") == norm_key("Lola Saunders")
    assert norm_key("Rhythmix") == norm_key("Little Mix")


def test_canonical_person_merges_aliases():
    assert canonical_person("Cheryl (singer)") == "Cheryl"
    assert canonical_person("Cheryl Fernandez-Versini") == "Cheryl"
    assert canonical_person("Simon Cowell") == "Simon Cowell"


def test_resolve_mentor_by_surname():
    judges = ("Simon Cowell", "Cheryl", "Louis Walsh", "Mel B")
    assert resolve_mentor("Cowell", judges) == "Simon Cowell"
    assert resolve_mentor("Cole", judges) == "Cheryl"
    assert resolve_mentor("Mel B", judges) == "Mel B"
    assert resolve_mentor(None, judges) is None


def test_split_names():
    assert split_names("Sinitta, Annie Skates and Jack Osbourne") == ("Sinitta", "Annie Skates", "Jack Osbourne")
    assert split_names(None) == ()
