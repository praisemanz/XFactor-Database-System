"""Integration tests run against a real MySQL database named `xfactor_test`.

They are skipped automatically when no MySQL server is reachable.
"""
import os

os.environ["DB_NAME"] = "xfactor_test"  # must be set before xfactor.db builds its engine

import pytest
from sqlalchemy.exc import OperationalError

from xfactor.db import get_engine, session_scope


@pytest.fixture(scope="session")
def loaded_db():
    from xfactor.loader import populate
    from xfactor.scraper.pipeline import PARSED_PATH, load_dataset
    from xfactor.sql.apply import create_database, create_schema

    if not PARSED_PATH.exists():
        pytest.skip("parsed dataset missing; run python -m xfactor.scraper.pipeline")
    try:
        create_database()
        create_schema(drop_first=True)
    except OperationalError as exc:
        pytest.skip(f"MySQL not reachable: {exc.orig}")
    with session_scope() as session:
        populate(session, load_dataset())
    yield get_engine()


@pytest.fixture()
def session(loaded_db):
    """A session whose changes are rolled back after each test."""
    from sqlalchemy.orm import Session

    connection = loaded_db.connect()
    transaction = connection.begin()
    sess = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield sess
    finally:
        sess.close()
        transaction.rollback()
        connection.close()
