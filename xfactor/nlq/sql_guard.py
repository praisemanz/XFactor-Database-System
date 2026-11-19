"""Validate LLM-generated SQL before it touches the database.

Defence in depth: this guard is the first layer. The query also runs as a SELECT-only
MySQL user inside a READ ONLY transaction with a time limit (see service.py).
"""
from __future__ import annotations

import re

MAX_ROWS = 200

_FORBIDDEN = re.compile(
    r"\b(insert|update|delete|replace|merge|drop|alter|create|truncate|rename|grant|revoke|"
    r"call|do|handler|load|lock|unlock|set|use|kill|shutdown|flush|install|uninstall|"
    r"outfile|dumpfile|load_file|sleep|benchmark|get_lock|into)\b",
    re.IGNORECASE,
)
_SYSTEM_SCHEMAS = re.compile(r"\b(mysql|information_schema|performance_schema|sys)\s*\.", re.IGNORECASE)


class UnsafeSqlError(ValueError):
    """Raised when generated SQL is not a single read-only SELECT."""


def _strip_strings(sql: str) -> str:
    """Blank out string literals so keyword checks only see real SQL."""
    sql = re.sub(r"'(?:[^'\\]|\\.|'')*'", "''", sql)
    return re.sub(r'"(?:[^"\\]|\\.)*"', '""', sql)


def validate_select(sql: str) -> str:
    """Return a cleaned single SELECT statement with a row limit, or raise UnsafeSqlError."""
    cleaned = sql.strip().rstrip(";").strip()
    if not cleaned:
        raise UnsafeSqlError("empty query")
    bare = _strip_strings(cleaned)
    if ";" in bare:
        raise UnsafeSqlError("only one statement is allowed")
    if "/*" in bare or "--" in bare or "#" in bare:
        raise UnsafeSqlError("comments are not allowed")
    if not re.match(r"^\s*(select|with)\b", bare, re.IGNORECASE):
        raise UnsafeSqlError("only SELECT queries are allowed")
    match = _FORBIDDEN.search(bare)
    if match:
        raise UnsafeSqlError(f"keyword not allowed: {match.group(1).upper()}")
    if _SYSTEM_SCHEMAS.search(bare):
        raise UnsafeSqlError("system schemas are not allowed")
    # The optimizer hint caps run time per query (ms) without touching session state.
    return f"SELECT /*+ MAX_EXECUTION_TIME(5000) */ * FROM ({cleaned}) AS llm_query LIMIT {MAX_ROWS}"
