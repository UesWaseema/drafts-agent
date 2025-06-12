# interspire_helpers.py  ──────────────────────────
import json, datetime
from db import get_conn
from common import get_db_connection

_EXPECTED_COLS = None   # module-level cache

def _expected_cols(conn) -> int:
    global _EXPECTED_COLS
    if _EXPECTED_COLS is None:
        with conn.cursor() as cur:
            cur.execute("DESCRIBE interspire_analysis_results")
            _EXPECTED_COLS = len(cur.fetchall())
    return _EXPECTED_COLS

# --- put this near the other SQL constants -----------------------
SQL_RECENT_RAW = """
SELECT subject, email, sent_date
FROM   interspire_data
WHERE  campaign_name LIKE %s
ORDER BY sent_date DESC
LIMIT  %s;
"""

SQL_RECENT = """
SELECT ar.*
FROM   interspire_analysis_results AS ar
JOIN   interspire_data             AS d
       ON ar.campaign_id = d.id
WHERE  d.campaign_name LIKE %s
ORDER  BY d.sent_date DESC
LIMIT  %s;
"""

def get_recent_campaign_records(journal: str, limit: int = 10) -> list[dict]:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(SQL_RECENT, (journal, limit))
        rows = cur.fetchall()

        if rows and len(rows[0]) != _expected_cols(conn):
            raise RuntimeError(
                f"Schema drift: got {len(rows[0])} cols, "
                f"expected {_expected_cols(conn)}. Update helper."
            )

    return [dict(r) for r in rows]          # ← every column preserved

def get_recent_campaign_raw(pattern: str, limit: int = 10) -> list[dict]:
    """
    Return the most-recent `limit` rows straight from interspire_data
    (no join, no 31-column analysis table).
    """
    conn = get_db_connection("mysql")        # *** use server DB ***
    cur  = conn.cursor(dictionary=True)      # return dict rows
    try:
        cur.execute(SQL_RECENT_RAW, (pattern, limit))
        rows = cur.fetchall()                # list[dict]
    finally:
        cur.close()
        conn.close()
    return rows

def rows_to_json(rows: list[dict]) -> str:
    def dt(o):
        if isinstance(o, (datetime.date, datetime.datetime)):
            return o.isoformat()
        raise TypeError
    return json.dumps(rows, indent=2, default=dt)

def get_latest_campaign(journal: str) -> dict | None:
    # Step 1: Get the latest campaign_id from interspire_data for the given journal
    sql_get_id = """
      SELECT id
      FROM   interspire_data
      WHERE  campaign_name LIKE %s
      ORDER  BY sent_date DESC
      LIMIT  1
    """
    campaign_id = None
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql_get_id, (journal,))
        row = cur.fetchone()

    if not row:                      # no match found
        return None

    # Works for both DictCursor and regular cursor
    campaign_id = row["id"] if isinstance(row, dict) else row[0]

    # Step 2: Use the campaign_id to get the full row from interspire_analysis_results
    sql_get_record = """
      SELECT *
      FROM   interspire_analysis_results
      WHERE  campaign_id = %s
      LIMIT  1
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

def get_last_waiver_percentage(journal: str) -> int | None:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(SQL_LAST_WAIVER, (journal,))
        row = cur.fetchone()
    if not row:
        return None
    # DictCursor → use column name; Plain cursor → use index 0
    return row.get("waiver_percentage") if isinstance(row, dict) else row[0]
