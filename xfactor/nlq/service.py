"""Natural-language questions over the database: question -> SQL -> rows -> answer.

The model never answers from its own knowledge: it writes SQL, we run it, and the
final answer is written only from the rows the database returned.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Protocol

import pymysql
from sqlalchemy import URL, Engine

from xfactor.db import database_url, make_engine
from xfactor.nlq.schema_prompt import schema_description
from xfactor.nlq.sql_guard import UnsafeSqlError, validate_select

MODEL = "claude-opus-5-5"
ROWS_FOR_ANSWER = 60

SQL_SYSTEM = (
    "You translate questions about The X Factor (UK) into one MySQL 8 SELECT query over the "
    "database below. Write exactly one read-only SELECT (CTEs allowed), no comments, no semicolon. "
    "Select human-readable columns (names, titles) rather than ids, and give every output column "
    "a unique alias. If the question cannot be "
    "answered from this database, set sql to an empty string and explain why.\n\n"
)
ANSWER_SYSTEM = (
    "You answer questions about The X Factor (UK) using ONLY the query results provided. "
    "Do not add facts that are not in the results. If the results are empty or do not answer "
    "the question, say so plainly. Be concise: one short paragraph or a short list."
)
SQL_SCHEMA = {
    "type": "object",
    "properties": {
        "sql": {"type": "string", "description": "A single MySQL SELECT statement, or empty."},
        "explanation": {"type": "string", "description": "One sentence on what the query does."},
    },
    "required": ["sql", "explanation"],
    "additionalProperties": False,
}


class LlmClient(Protocol):
    """The two model calls the service needs. Implemented by ClaudeClient; stubbed in tests."""

    def write_sql(self, question: str) -> dict[str, str]: ...
    def write_answer(self, question: str, sql: str, columns: list[str], rows: list[list[Any]]) -> str: ...


@dataclass(frozen=True)
class Answer:
    question: str
    answer: str
    sql: str | None
    explanation: str
    columns: tuple[str, ...] = ()
    rows: tuple[tuple[Any, ...], ...] = ()
    error: str | None = None


class ClaudeClient:
    """LlmClient backed by the Anthropic API (reads ANTHROPIC_API_KEY from the environment)."""

    def __init__(self) -> None:
        import anthropic
        self._anthropic = anthropic
        self.client = anthropic.Anthropic()

    def _create(self, system: str, content: str, effort: str, **extra: Any) -> Any:
        response = self.client.beta.messages.create(
            model=MODEL,
            max_tokens=16000,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": content}],
            output_config={"effort": effort, **extra},
            # Server-side refusal fallback: if a safety classifier declines, the API
            # re-runs the request on a fallback model inside the same call.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        if response.stop_reason == "refusal":
            raise RuntimeError("The model declined to answer this question.")
        return "".join(block.text for block in response.content if block.type == "text")

    def write_sql(self, question: str) -> dict[str, str]:
        raw = self._create(SQL_SYSTEM + schema_description(), question, "medium",
                           format={"type": "json_schema", "schema": SQL_SCHEMA})
        return json.loads(raw)

    def write_answer(self, question: str, sql: str, columns: list[str], rows: list[list[Any]]) -> str:
        payload = json.dumps({"columns": columns, "rows": rows[:ROWS_FOR_ANSWER],
                              "total_rows": len(rows)}, default=str)
        content = f"Question: {question}\n\nSQL that was run:\n{sql}\n\nResults (JSON):\n{payload}"
        return self._create(ANSWER_SYSTEM, content, "low").strip()


def readonly_url() -> URL:
    """Use the SELECT-only account when configured; otherwise the app account (still guarded)."""
    base = database_url()
    user = os.getenv("DB_READONLY_USER")
    if not user:
        return base
    return base.set(username=user, password=os.getenv("DB_READONLY_PASSWORD") or None)


@lru_cache(maxsize=1)
def readonly_engine() -> Engine:
    return make_engine(readonly_url())


def run_readonly(engine: Engine, sql: str) -> tuple[list[str], list[list[Any]]]:
    """Run one query inside its own READ ONLY transaction, then roll back.

    Nothing is set at session level, so pooled connections are never left read-only.
    A raw DBAPI cursor with no parameters is used so ':' or '%' in the SQL are not
    mistaken for bind placeholders.
    """
    raw = engine.raw_connection()
    try:
        with raw.cursor() as cursor:
            cursor.execute("START TRANSACTION READ ONLY")
            try:
                cursor.execute(sql)
                columns = [d[0] for d in cursor.description or ()]
                return columns, [list(row) for row in cursor.fetchall()]
            finally:
                raw.rollback()
    finally:
        raw.close()


def ask(question: str, llm: LlmClient, engine: Engine | None = None) -> Answer:
    question = question.strip()[:500]
    if not question:
        return Answer(question, "Please type a question.", None, "", error="empty question")
    plan = llm.write_sql(question)
    raw_sql = (plan.get("sql") or "").strip()
    explanation = plan.get("explanation", "")
    if not raw_sql:
        return Answer(question, explanation or "That can't be answered from this database.", None, explanation)
    try:
        safe_sql = validate_select(raw_sql)
    except UnsafeSqlError as exc:
        return Answer(question, "The generated query was rejected for safety.", raw_sql, explanation, error=str(exc))
    try:
        columns, rows = run_readonly(engine or readonly_engine(), safe_sql)
    except pymysql.MySQLError as exc:  # surfaced to the user; DB errors are expected for bad SQL
        message = str(exc)
        return Answer(question, "The generated query failed to run.", raw_sql, explanation, error=message)
    answer = llm.write_answer(question, raw_sql, columns, rows)
    return Answer(question, answer, raw_sql, explanation, tuple(columns), tuple(tuple(r) for r in rows))
