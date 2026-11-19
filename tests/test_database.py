"""Integration tests: CRUD, constraints, index, join, views and stored procedures on MySQL."""
import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError, OperationalError

from xfactor import models as m
from xfactor.repository import reports
from xfactor.repository.crud import MODELS, ActRepository, TableRepository


def test_every_table_has_at_least_three_rows(session):
    for name, model in MODELS.items():
        count = session.scalar(select(func.count()).select_from(model))
        assert count >= 3, name


def test_total_rows_exceed_2000(session):
    total = sum(session.scalar(select(func.count()).select_from(model)) for model in MODELS.values())
    assert total > 2000


def test_act_crud_round_trip(session):
    repo = ActRepository(session)
    act = repo.create("Test Act 123", is_group=True)
    assert repo.get(act.act_id).name == "Test Act 123"
    assert [a.act_id for a in repo.search("Test Act 1")] == [act.act_id]
    assert repo.rename(act.act_id, "Renamed Act").name == "Renamed Act"
    assert repo.delete(act.act_id) is True
    assert repo.get(act.act_id) is None
    assert repo.delete(act.act_id) is False


def test_unique_constraint_rejects_duplicate_act(session):
    with pytest.raises(IntegrityError):
        ActRepository(session).create("Little Mix", is_group=True)


def test_check_constraint_rejects_bad_series_number(session):
    with pytest.raises((IntegrityError, OperationalError)):
        session.execute(text("INSERT INTO series (series_number) VALUES (150)"))


def test_check_constraint_rejects_negative_viewers(session):
    series = session.scalar(select(m.Series).limit(1))
    session.add(m.Episode(series=series, title="Bad", viewers_millions=-1))
    with pytest.raises((IntegrityError, OperationalError)):
        session.flush()


def test_secondary_indexes_exist(session):
    names = {row.Key_name for row in session.execute(text("SHOW INDEX FROM performance"))}
    assert {"ix_performance_song", "ix_performance_entry"} <= names
    plan = session.execute(text("EXPLAIN SELECT * FROM song WHERE title = 'Hallelujah'")).mappings().one()
    assert plan["key"] == "ix_song_title"


def test_multi_join_query(session):
    table = reports.songs_by_mentor(session, "Tulisa", limit=500)
    acts = {row[table.columns.index("act")] for row in table.rows}
    assert "Little Mix" in acts


def test_views(session):
    summary = reports.read_view(session, "v_series_summary", series_number=6)
    row = dict(zip(summary.columns, summary.rows[0]))
    assert row["winner"] == "Joe McElderry" and row["runner_up"] == "Olly Murs"
    mentors = reports.read_view(session, "v_mentor_stats")
    assert "Simon Cowell" in {r[0] for r in mentors.rows}
    with pytest.raises(ValueError):
        reports.reflect_view(session, "series")  # only whitelisted views


def test_leaderboard_procedure(session):
    board = reports.series_leaderboard(session, 7)
    assert board.rows[0][1] == "Matt Cardle"
    assert len(board.rows) == 16


def test_act_journey_procedure(session):
    journey = reports.act_journey(session, "One Direction")
    assert len(journey.rows) > 10
    assert all(row[0] == 7 for row in journey.rows)


def test_write_procedure_returns_out_parameter(session):
    updated = reports.record_showdown_result(session, 6, 1, "Kandy Rain", "Eliminated (test)")
    assert updated >= 1
    result = session.execute(text(
        "SELECT DISTINCT result_text FROM v_performance_detail "
        "WHERE series_number=6 AND week_number=1 AND act='Kandy Rain'")).scalars().all()
    assert result == ["Eliminated (test)"]


def test_generic_table_repository_crud(session):
    repo = TableRepository(session, "category")
    created = repo.create({"name": "Under 16s"})
    rows, total = repo.list(search="Under 16")
    assert total == 1 and rows[0].category_id == created.category_id
    repo.update((created.category_id,), {"name": "Under 15s"})
    assert repo.get((created.category_id,)).name == "Under 15s"
    assert repo.delete((created.category_id,))


def test_generic_repository_validates_input(session):
    repo = TableRepository(session, "series")
    with pytest.raises(ValueError):
        repo.create({"series_number": "not a number"})
    with pytest.raises(ValueError):
        TableRepository(session, "music_release").create(
            {"act_id": "1", "release_type": "Cassette", "title": "x"})
    with pytest.raises(KeyError):
        TableRepository(session, "mysql.user")


def test_composite_primary_key_crud(session):
    repo = TableRepository(session, "series_judge")
    person = m.Person(full_name="Guest Judge Test")
    session.add(person)
    session.flush()
    repo.create({"series_id": "1", "person_id": str(person.person_id), "is_guest": "on"})
    assert repo.get((1, person.person_id)).is_guest is True
    assert repo.delete((1, person.person_id))
