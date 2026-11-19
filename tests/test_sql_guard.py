import pytest

from xfactor.nlq.sql_guard import MAX_ROWS, UnsafeSqlError, validate_select


@pytest.mark.parametrize("sql", [
    "SELECT name FROM act",
    "select a.name, count(*) AS n from act a join series_act sa using (act_id) group by a.name;",
    "WITH w AS (SELECT * FROM v_series_summary) SELECT winner FROM w",
    "SELECT name FROM act WHERE name = 'Drop Dead Gorgeous'",  # keyword inside a string is fine
])
def test_allows_read_only_selects(sql):
    wrapped = validate_select(sql)
    assert wrapped.startswith("SELECT /*+ MAX_EXECUTION_TIME(5000) */ * FROM (")
    assert wrapped.endswith(f"LIMIT {MAX_ROWS}")


@pytest.mark.parametrize("sql, reason", [
    ("", "empty"),
    ("DELETE FROM act", "only SELECT"),
    ("SELECT 1; DROP TABLE act", "one statement"),
    ("SELECT * FROM act INTO OUTFILE '/tmp/x'", "INTO"),
    ("SELECT SLEEP(10)", "SLEEP"),
    ("SELECT user, authentication_string FROM mysql.user", "system schemas"),
    ("SELECT 1 /* sneaky */", "comments"),
    ("SELECT 1 -- trailing", "comments"),
    ("WITH x AS (SELECT 1) UPDATE act SET name='x'", "UPDATE"),
    ("CALL sp_series_leaderboard(1)", "only SELECT"),
])
def test_rejects_unsafe_sql(sql, reason):
    with pytest.raises(UnsafeSqlError, match=reason):
        validate_select(sql)
