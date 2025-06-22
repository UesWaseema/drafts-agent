# mailwizz_helpers.py
import os, json, datetime, pymysql

# ------------------------------------------------------------------
# 1️⃣  Connection factory local to this module
# ------------------------------------------------------------------
def _connect_mailwizz() -> pymysql.connections.Connection:
    """
    Connect to the MailWizz MySQL database using the env-vars supplied
    by the deployment (DRAFTS_DB_HOST, DRAFTS_DB_USER, etc.).
    """
    return pymysql.connect(
        host        = os.getenv("DRAFTS_DB_HOST", "127.0.0.1"),
        user        = os.getenv("DRAFTS_DB_USER", "root"),
        password    = os.getenv("DRAFTS_DB_PASS", ""),
        database    = os.getenv("MAILWIZZ_DB_NAME", "admin_mailwiz"),
        cursorclass = pymysql.cursors.DictCursor,
        autocommit  = True
    )
# ------------------------------------------------------------------
# 2️⃣  SQL (MySQL placeholders %s are fine)
# ------------------------------------------------------------------
SQL_RECENT_RAW = """
SELECT
  c.name        AS campaign_name,
  c.subject,
  c.from_name   AS journal,
  c.from_email,
  c.send_at     AS sent_date,
  t.content     AS email_body
FROM   mw_campaign c
LEFT JOIN mw_campaign_template t
       ON t.campaign_id = c.campaign_id
WHERE  c.status = 'sent'
  AND  c.from_name LIKE %s          -- 🔄 was c.name LIKE %s
ORDER BY c.send_at DESC
LIMIT  %s;
"""

# ------------------------------------------------------------------
# 3️⃣  Public helper
# ------------------------------------------------------------------
def get_mailwizz_recent_campaigns(
        pattern: str,
        domain: str | None = None,   # accepted for API symmetry, unused
        limit: int = 10
) -> list[dict]:
    """
    Fetch the latest *limit* sent MailWizz campaigns whose
    mw_campaign.name matches `pattern` (SQL LIKE wildcards allowed).
    Returns a list[dict] with HTML body included.
    """
    conn = _connect_mailwizz()
    cur  = conn.cursor()
    try:
        cur.execute(SQL_RECENT_RAW, (pattern, limit))
        rows = cur.fetchall()               # already dicts
    finally:
        cur.close()
        conn.close()
    return rows


# ------------------------------------------------------------------
# 4️⃣  JSON pretty-printer (unchanged)
# ------------------------------------------------------------------
def rows_to_json(rows: list[dict]) -> str:
    def _dt(o):
        if isinstance(o, (datetime.date, datetime.datetime)):
            return o.isoformat()
        raise TypeError
    return json.dumps(rows, indent=2, default=_dt)
