"""
utils.db
========
Lightweight DB helper layer that works with:

* **SQLite**  – dev / unit tests (default)
* **MySQL**   – prod if `DB_PORT=3306`
* **Postgres**– prod if `DB_PORT=5432`

Also preserves the original `log_prompt_output()` helper used
throughout the Streamlit app.
"""

from __future__ import annotations
import os, sqlite3, contextlib
from pathlib import Path
from typing import Iterator, Any, Optional

import mysql.connector                # MySQL
import psycopg2, psycopg2.extras      # Postgres

# ── Paths & env vars ------------------------------------------------------- #
ROOT = Path(__file__).resolve().parent.parent
_SQLITE_PATH = ROOT / "journal_data.db"

_DSN = dict(
    host=os.getenv("DRAFTS_DB_HOST", "localhost"),
    port=int(os.getenv("DB_PORT", 0) or 3306),
    user=os.getenv("DRAFTS_DB_USER", "root"),
    password=os.getenv("DRAFTS_DB_PASS", ""),
    dbname=os.getenv("DRAFTS_DB_NAME", "drafts"),
)

# --------------------------------------------------------------------------- #
# Private connection builders                                                 #
# --------------------------------------------------------------------------- #
def _sqlite_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _mysql_conn():
    return mysql.connector.connect(
        host=_DSN["host"],
        port=_DSN["port"],
        user=_DSN["user"],
        password=_DSN["password"],
        database=_DSN["dbname"],
        autocommit=True,

    )


def _pg_conn():
    return psycopg2.connect(
        host=_DSN["host"],
        port=_DSN["port"],
        user=_DSN["user"],
        password=_DSN["password"],
        dbname=_DSN["dbname"],
        cursor_factory=psycopg2.extras.DictCursor,
    )


# --------------------------------------------------------------------------- #
# Public helpers                                                              #
# --------------------------------------------------------------------------- #
def get_conn(flavour: str | None = None):
    """
    Return a live DB connection.  Selection order:

    1. *flavour* param if given ('sqlite' / 'mysql' / 'postgres')
    2. By port env-var → 3306→MySQL, 5432→Postgres, else SQLite
    """
    if flavour == "sqlite":
        return _sqlite_conn()
    if flavour == "mysql":
        return _mysql_conn()
    if flavour == "postgres":
        return _pg_conn()

    if _DSN["port"] == 3306:
        return _mysql_conn()
    if _DSN["port"] == 5432:
        return _pg_conn()
    return _sqlite_conn()


@contextlib.contextmanager
def cursor(flavour: str | None = None):
    """Context-manager → `with cursor() as cur:` returns an open cursor."""
    conn = get_conn(flavour)
    cur  = conn.cursor()
    try:
        yield cur
        conn.commit()
    finally:
        cur.close()
        conn.close()


# --------------------------------------------------------------------------- #
# Prompt-logging helper (lifted from legacy db.py)                            #
# --------------------------------------------------------------------------- #
def log_prompt_output(
    *,
    prompt_text: str,
    output_text: str,
    draft_type: str,
    journal_title: str,
    waiver_pct: int | None = None,
    model_name: str | None = None,
    latency_ms: int | None = None,
    user_id: int | None = None,
) -> None:
    """
    Insert a row into `prompt_logs` table (**schema unchanged**) no matter which
    RDBMS is backing the app.
    """
    sql = """
        INSERT INTO prompt_logs
        (prompt_text, output_text, draft_type, journal_title,
         waiver_pct, model_name, processing_ms, user_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """
    vals = (
        prompt_text,
        output_text,
        draft_type,
        journal_title,
        waiver_pct,
        model_name,
        latency_ms,
        user_id,
    )

    # psycopg2 uses *%s* placeholders too, so the same SQL works.
    with cursor() as cur:
        cur.execute(sql, vals)

# ──────────────────────────────────────────────────────────────────────
#  Smart master-data helpers
#     – Always read from journal_data.db **if the file & table exist**
#     – otherwise fall back to the main RDBMS
# ──────────────────────────────────────────────────────────────────────
def _has_sqlite_table(table: str) -> bool:
    """Return True if the named table exists inside journal_data.db."""
    if not _SQLITE_PATH.exists():
        return False
    with _sqlite_conn() as conn:
        res = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        return bool(res)


def _query_sqlite(table: str) -> list[dict]:
    sql = f"SELECT * FROM {table} ORDER BY 1"
    with _sqlite_conn() as conn:
        rows = conn.execute(sql).fetchall()
        return [dict(r) for r in rows]


def fetch_journals() -> list[dict]:
    if _has_sqlite_table("journal_details"):
        return _query_sqlite("journal_details")

    sql = "SELECT * FROM journal_details ORDER BY journal_title"
    with get_conn() as conn, conn.cursor() as cur:      # ← normal cursor
        cur.execute(sql)
        cols = [c[0] for c in cur.description]          # column names
        return [dict(zip(cols, row)) for row in cur.fetchall()]



def fetch_domains() -> list[dict]:
    if _has_sqlite_table("domains"):
        return _query_sqlite("domains")

    sql = "SELECT * FROM domains ORDER BY domain_name"
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql)
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
