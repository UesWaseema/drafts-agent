# db.py  ── supports either MySQL (3306) or Postgres (5432) automatically
import os
import pymysql            # ← MySQL
import psycopg2, psycopg2.extras
from contextlib import contextmanager
from dotenv import load_dotenv
load_dotenv()

_DSN = dict(
    host=os.getenv("DRAFTS_DB_HOST"),
    port=int(os.getenv("DB_PORT", 3306)),
    user=os.getenv("DRAFTS_DB_USER"),
    password=os.getenv("DRAFTS_DB_PASS"),
    db   = os.getenv("DRAFTS_DB_NAME"),   # MySQL arg
    dbname=os.getenv("DRAFTS_DB_NAME"),   # Postgres arg
)

@contextmanager
def get_conn():
    """Open DB connection chosen by port: 3306 → MySQL, 5432 → Postgres."""
    port = _DSN["port"]
    if port == 3306:                         # ---------- MySQL ----------
        conn = pymysql.connect(
            host=_DSN["host"],
            port=port,
            user=_DSN["user"],
            password=_DSN["password"],
            database=_DSN["db"],
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=True,
        )
    else:                                    # ---------- Postgres ----------
        conn = psycopg2.connect(
            host=_DSN["host"],
            port=port,
            user=_DSN["user"],
            password=_DSN["password"],
            dbname=_DSN["dbname"],
            cursor_factory=psycopg2.extras.DictCursor,
        )
    try:
        yield conn
    finally:
        conn.close()

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
):
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

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, vals)
