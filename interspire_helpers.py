# interspire_helpers.py  ──────────────────────────────────────────
import os
import json, datetime
import pymysql                           # ← NEW
from db import get_conn                  # analytics DB (already exists)
# ── no longer import get_db_connection from common ──────────────

# ------------------------------------------------------------------
#  PRIVATE: Interspire “raw” DB connection
# ------------------------------------------------------------------
def _interspire_conn():
    """
    Dedicated connector for the *operational* Interspire DB
    (holds `interspire_data`).  Uses env-vars; falls back to localhost.
    """
    return pymysql.connect(
        host        = os.getenv("DRAFTS_DB_HOST", "127.0.0.1"),
        user        = os.getenv("DRAFTS_DB_USER", "admin_waseema"),
        password    = os.getenv("DRAFTS_DB_PASS", "changeme"),
        database    = os.getenv("DRAFTS_DB_NAME", "interspire_db"),
        cursorclass = pymysql.cursors.DictCursor,
        autocommit  = True,
    )

# ------------------------------------------------------------------
_EXPECTED_COLS = None   # module-level cache for schema width
# ------------------------------------------------------------------
def _expected_cols(conn) -> int:
    global _EXPECTED_COLS
    if _EXPECTED_COLS is None:
        with conn.cursor() as cur:
            cur.execute("DESCRIBE interspire_analysis_results")
            _EXPECTED_COLS = len(cur.fetchall())
    return _EXPECTED_COLS

# ------------------------------------------------------------------
#  SQL snippets
# ------------------------------------------------------------------
SQL_RECENT_RAW = """
SELECT
  campaign_name,          -- 🆕 now included
  subject,
  email,
  sent_date,
  journal
FROM   interspire_data
WHERE  journal LIKE %s               -- 🔄 was campaign_name
ORDER  BY sent_date DESC
LIMIT  %s;
"""

SQL_RECENT = """
SELECT ar.*
FROM   interspire_analysis_results AS ar
JOIN   interspire_data             AS d
       ON ar.campaign_id = d.id
WHERE  d.journal LIKE %s            -- 🔄 was d.campaign_name
ORDER  BY d.sent_date DESC
LIMIT  %s;
"""

# ------------------------------------------------------------------
#  Public helpers
# ------------------------------------------------------------------
def get_recent_campaign_records(pattern: str,
                                limit: int = 10) -> list[dict]:
    """
    Full joined record (31-col analysis table) — uses analytics DB.
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(SQL_RECENT, (pattern, limit))
        rows = cur.fetchall()

        if rows and len(rows[0]) != _expected_cols(conn):
            raise RuntimeError(
                f"Schema drift: got {len(rows[0])} cols, "
                f"expected {_expected_cols(conn)}. Update helper."
            )
    return [dict(r) for r in rows]

def get_recent_campaign_raw(pattern: str,
                            domain: str,       # kept for signature parity
                            limit: int = 10) -> list[dict]:
    """
    Last *limit* rows from **interspire_data** only (no join).
    Independent connection via `_interspire_conn()`.
    """
    conn = _interspire_conn()
    cur  = conn.cursor()
    try:
        cur.execute(SQL_RECENT_RAW, (pattern, limit))
        rows = cur.fetchall()
    finally:
        cur.close()
        conn.close()
    return rows

def rows_to_json(rows: list[dict]) -> str:
    def _dt(o):
        if isinstance(o, (datetime.date, datetime.datetime)):
            return o.isoformat()
        raise TypeError
    return json.dumps(rows, indent=2, default=_dt)

# ------------------------------------------------------------------
#  “Latest campaign” + waiver helpers (analytics DB → get_conn)
# ------------------------------------------------------------------
def get_latest_campaign(pattern: str) -> dict | None:
    # 1) latest campaign_id
    sql_get_id = """
      SELECT id
      FROM   interspire_data
      WHERE  campaign_name LIKE %s
      ORDER  BY sent_date DESC
      LIMIT  1;
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql_get_id, (pattern,))
        row = cur.fetchone()
    if not row:
        return None
    campaign_id = row["id"] if isinstance(row, dict) else row[0]

    # 2) pull full analysis record
    sql_get_record = """
      SELECT *
      FROM   interspire_analysis_results
      WHERE  campaign_id = %s
      LIMIT  1;
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql_get_record, (campaign_id,))
        row = cur.fetchone()
    return dict(row) if row else None

SQL_LAST_WAIVER = """
SELECT   ar.waiver_percentage
FROM     interspire_analysis_results AS ar
JOIN     interspire_data             AS d
       ON ar.campaign_id = d.id
WHERE    d.campaign_name LIKE %s
  AND    ar.waiver_percentage IS NOT NULL
ORDER BY d.sent_date DESC
LIMIT    1;
"""

def get_last_waiver_percentage(pattern: str) -> int | None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(SQL_LAST_WAIVER, (pattern,))
        row = cur.fetchone()
    if not row:
        return None
    return row.get("waiver_percentage") if isinstance(row, dict) else row[0]
