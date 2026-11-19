"""Engine/session factory. Connection settings come from environment variables (.env)."""
from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from typing import Any

from dotenv import load_dotenv
from sqlalchemy import URL, Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

load_dotenv()


def database_url(include_db: bool = True) -> URL:
    return URL.create(
        "mysql+pymysql",
        username=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD") or None,
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "3306")),
        database=os.getenv("DB_NAME", "xfactor") if include_db else None,
        query={"charset": "utf8mb4"},
    )


def connect_args() -> dict[str, Any]:
    """TLS options for hosted MySQL.

    DB_SSL_CA=/path/to/ca.pem  -> verify the server against that CA (e.g. Aiven's ca.pem)
    DB_SSL=1                    -> TLS verified against the system CA store
    """
    ca = os.getenv("DB_SSL_CA")
    if ca:
        return {"ssl_ca": ca}
    if os.getenv("DB_SSL"):
        return {"ssl_verify_cert": True}
    return {}


def make_engine(url: URL) -> Engine:
    return create_engine(url, connect_args=connect_args(), pool_pre_ping=True, pool_recycle=280)


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    return make_engine(database_url())


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional scope: commit on success, roll back on any error."""
    session = sessionmaker(bind=get_engine(), expire_on_commit=False)()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
