"""The NL service with a stub LLM (the external API is the only thing faked) and real MySQL."""
from dataclasses import dataclass, field

from xfactor.nlq.schema_prompt import schema_description
from xfactor.nlq.service import ask


@dataclass
class StubLlm:
    sql: str
    explanation: str = "test"
    seen_rows: list = field(default_factory=list)

    def write_sql(self, question):
        return {"sql": self.sql, "explanation": self.explanation}

    def write_answer(self, question, sql, columns, rows):
        self.seen_rows = rows
        return f"{len(rows)} rows"


def test_schema_description_lists_tables_and_views():
    text = schema_description()
    assert "TABLE performance(" in text and "song_id INTEGER -> song.song_id" in text
    assert "VIEW v_series_summary" in text


def test_answers_from_database_rows(loaded_db):
    llm = StubLlm("SELECT winner FROM v_series_summary WHERE series_number = 3")
    result = ask("Who won series 3?", llm, engine=loaded_db)
    assert result.error is None
    assert llm.seen_rows == [["Leona Lewis"]]
    assert result.columns == ("winner",)


def test_unsafe_sql_is_never_executed(loaded_db):
    llm = StubLlm("DELETE FROM act")
    result = ask("delete everything", llm, engine=loaded_db)
    assert result.error and "only SELECT" in result.error
    assert llm.seen_rows == []


def test_unanswerable_question_returns_explanation(loaded_db):
    result = ask("What is the weather?", StubLlm("", "Not in the database."), engine=loaded_db)
    assert result.answer == "Not in the database." and result.sql is None


def test_bad_sql_reports_database_error(loaded_db):
    result = ask("x", StubLlm("SELECT no_such_column FROM act"), engine=loaded_db)
    assert result.error and "no_such_column" in result.error


def test_read_only_session_blocks_writes_even_if_guard_bypassed(loaded_db):
    import pymysql
    import pytest

    from xfactor.nlq.service import run_readonly
    with pytest.raises(pymysql.MySQLError, match="READ ONLY"):
        run_readonly(loaded_db, "UPDATE act SET name = name WHERE act_id = 1")


def test_read_only_mode_does_not_leak_into_pooled_connections(loaded_db):
    from sqlalchemy import text

    from xfactor.nlq.service import run_readonly
    run_readonly(loaded_db, "SELECT 1")
    with loaded_db.connect() as conn:  # same pool: must still be writable
        conn.execute(text("UPDATE act SET name = name WHERE act_id = 1"))
        conn.rollback()
