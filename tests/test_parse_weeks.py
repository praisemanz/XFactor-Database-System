from bs4 import BeautifulSoup

from xfactor.scraper.parse_weeks import _segments, parse_weeks

WEEK_HTML = """
<div class="mw-heading mw-heading4"><h4>Week 1 (10/11 October)</h4></div>
<ul><li>Theme: Musical heroes</li><li>Guest mentor: Robbie Williams</li></ul>
<table class="wikitable">
<tr><th>Act</th><th>Category (mentor)</th><th>Order</th><th>Song</th><th>Musical Hero</th><th>Result</th></tr>
<tr><th>Rachel Adedeji</th><td>Girls (Minogue)</td><td>1</td><td>"Let Me Entertain You"</td><td>Robbie Williams</td><td>Bottom Two</td></tr>
<tr><th>Olly Murs</th><td>Over 25s (Cowell)</td><td>2</td><td>"She's the One"</td><td>Robbie Williams</td><td>Safe</td></tr>
<tr><th colspan="6">Final showdown details</th></tr>
<tr><th>Rachel Adedeji</th><td>Girls (Minogue)</td><td>1</td><td colspan="2">"Nobody Knows"</td><td>Saved</td></tr>
</table>
<div class="mw-heading mw-heading4"><h4>Week 10: Final (12/13 December)</h4></div>
<table class="wikitable">
<tr><th>Act</th><th>Category (mentor)</th><th>Order</th><th>First song</th><th>Order</th><th>Second song</th><th>Duet Partner</th><th>Result</th></tr>
<tr><th>Joe McElderry</th><td>Boys (Cole)</td><td>1</td><td>"Dance with My Father"</td><td>4</td><td>"Don't Let the Sun Go Down on Me"</td><td>George Michael</td><td>Winner</td></tr>
</table>
"""


def _parse():
    return parse_weeks(BeautifulSoup(WEEK_HTML, "lxml"), series=6, year=2009)


def test_live_show_metadata():
    shows, _ = _parse()
    first, final = shows
    assert (first.week_number, first.stage, first.theme) == (1, "Week 1", "Musical heroes")
    assert str(first.first_air_date) == "2009-10-10"
    assert (final.week_number, final.stage) == (10, "Final")


def test_performances_include_showdown_and_artist():
    _, perfs = _parse()
    week1 = [p for p in perfs if p.week_number == 1]
    assert len(week1) == 3
    assert week1[0].song_title == "Let Me Entertain You" and week1[0].song_artist == "Robbie Williams"
    showdown = week1[2]
    assert showdown.is_showdown and showdown.song_title == "Nobody Knows"
    assert showdown.song_artist is None  # colspan copy must not be treated as an artist


def test_multi_song_week_yields_one_row_per_song_with_duet_partner():
    _, perfs = _parse()
    final = [p for p in perfs if p.week_number == 10]
    assert [(p.running_order, p.song_title) for p in final] == [
        (1, "Dance with My Father"), (4, "Don't Let the Sun Go Down on Me")]
    assert final[1].duet_partner == "George Michael"
    assert final[0].duet_partner is None


def test_segments_pick_song_column_after_order():
    segs = _segments(["Act", "Category (mentor)", "Order", "Year", "Song", "Result"])
    assert len(segs) == 1 and segs[0].song == "Song"
