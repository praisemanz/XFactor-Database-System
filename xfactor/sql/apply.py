"""Create the database, its tables (via the ORM), views and stored procedures."""
from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import text

from xfactor.db import database_url, get_engine, make_engine
from xfactor.models import Base

SQL_DIR = Path(__file__).resolve().parent
SEPARATOR = "-- @@"


def statements(path: Path) -> list[str]:
    """Split a .sql file on '-- @@' lines; drop blank / comment-only chunks."""
    chunks = path.read_text(encoding="utf-8").split(f"\n{SEPARATOR}\n")
    out = []
    for chunk in chunks:
        code = "\n".join(line for line in chunk.splitlines() if not line.strip().startswith("--"))
        if code.strip():
            out.append(chunk.strip())
    return out


def create_database() -> None:
    name = os.getenv("DB_NAME", "xfactor")
    server = make_engine(database_url(include_db=False))
    with server.begin() as conn:
        conn.execute(text(f"CREATE DATABASE IF NOT EXISTS `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci"))
    server.dispose()


def create_schema(drop_first: bool = False) -> None:
    engine = get_engine()
    if drop_first:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    apply_sql_objects()


def apply_sql_objects() -> None:
    """Run views.sql and procedures.sql. A raw DBAPI cursor is used with no parameters so
    PyMySQL does not treat the literal '%' in LIKE patterns as a format placeholder."""
    raw = get_engine().raw_connection()
    try:
        with raw.cursor() as cursor:
            for file_name in ("views.sql", "procedures.sql"):
                for statement in statements(SQL_DIR / file_name):
                    cursor.execute(statement)
        raw.commit()
    finally:
        raw.close()
