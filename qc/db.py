"""
db.py – Scenario-Checker data helpers
====================================

Reads:  admin_cfp.is_newsletters
Writes: admin_drafts_agent_data.newsletter_analysis
"""

from typing import List, Dict, Optional
from contextlib import contextmanager
from mysql.connector.pooling import MySQLConnectionPool
from config import DB_CFG


# ────────────────────────── connection pools ──────────────────────────
_POOL_CFP = MySQLConnectionPool(
    pool_name="cfp_pool",
    pool_size=4,
    host=DB_CFG["host"],
    port=DB_CFG["port"],
    user=DB_CFG["user"],
    password=DB_CFG["password"],
    database=DB_CFG["db_cfp"],
    charset="utf8",
)

_POOL_ADA = MySQLConnectionPool(
    pool_name="ada_pool",
    pool_size=4,
    host=DB_CFG["host"],
    port=DB_CFG["port"],
    user=DB_CFG["user"],
    password=DB_CFG["password"],
    database=DB_CFG["db_agent"],
    charset="utf8",
)


@contextmanager
def conn_cfp():
    cnx = _POOL_CFP.get_connection()
    try:
        yield cnx
    finally:
        cnx.close()


@contextmanager
def conn_ada():
    cnx = _POOL_ADA.get_connection()
    try:
        yield cnx
    finally:
        cnx.close()


# ───────────────────────── pattern helpers ────────────────────────────
_DRAFT_WH = "('cfp','ope','unopen','reminder','openrem','editorial')"

# whitelist of official journal slugs (2–6 chars, exact match)
_JOUR_LIST = (
    'IJN','JPHI','JAR','JARH','IJCV','JCRHAP','JHOR','JNRT','JNDC','JHC',
    'JPMC','JWRH','JOS','JVHC','IJHA','JBBS','JAPST','JCCI','JDOI','JAA',
    'JPGR','IPJ','JOA','JBTM','JDDD','JHP','IJGH','JCSR','JCGB','JHHR',
    'JSDR','JMBR','IJPR','JBD','JMID','JCDP','JEC','JPAE','JNA','JSLR',
    'JDRT','JDT','JAN','JOM','JFM','JVAT','JECT','JCRC','JES','JTC','JPHN',
    'JAPB','JRD','IJIP','IJOE','JAFS','IJAR','JFB','JESR','JGM','IJCM',
    'JEN','JW','IJGP','JPAR','IMSJ','IJP','JBR','JDRR','JOT','JSN','JZR',
    'JPCD','JCAP','JI','IJNR','JTRR','JRNM','IJSTD','IJL','JSEM','IJNE',
    'JBSC','JFS','JBFB','JCC','JFSH','JN','JSM','JALR','JAC','JMPT',
    'J3DPA','JGRC','JLR','JD','JPA','IJLI','IJEN','JFD','JGE','IJHS','JWL',
    'JCPN','JEH','IJT','IJIR','JBCS','JE','JSDT','JKSP','JPCH','JPD',
    'IJCP','IJBA','JMSU','JSB','JPCS','JH','JWC','IJWD','IJST','JHAI',
    'IJMP','JF','JOP','IJBM','JATS','JTMH','JARS','JSC','JDRPR','IJTR',
    'JRAI','JADR','JBI','IJANR','JCBT','JIO','IIIJ','JAWD','IJBT','IJNN',
    'JSCE','JED','IJCO','JLCE','IJV','JWMH','IEJ','JIG','JBMB','IJPC',
    'IJPM','JART','JM','JTR','JP','IJE','JBSR','JCY','JCH','IJG','JBF',
    'JPR','JPOR','JPAN','IJNI','JHD','JC','JBP','JNPP','JOD','JS','JMM',
    'IJA','JICES','IJAN','JAMMBP','JAL','JOC','JCD','JMR','IJC','JARB',
    'JNMB','JA','IJS','IJAA','JTT','IJCY','JDMS','JIS','JU','IJSB','JVB',
    'IJH','IJO'
)

# tokens split helpers
T1        = "LOWER(SUBSTRING_INDEX(nl.name, '_', 1))"
T2        = "SUBSTRING_INDEX(SUBSTRING_INDEX(nl.name, '_', 2), '_', -1)"
TOK_BEFR  = "SUBSTRING_INDEX(SUBSTRING_INDEX(nl.name, '_', -1), '-', 1)"
DT_DASH   = "LOWER(SUBSTRING_INDEX(SUBSTRING_INDEX(nl.name, '-', -2), '-', 1))"

SQL_DRAFT = f"""
CASE
  WHEN {T1} IN {_DRAFT_WH} THEN {T1}
  WHEN {DT_DASH} IN {_DRAFT_WH} THEN {DT_DASH}
  ELSE 'unknown'
END
""".strip()

_SQL_JOUR_RAW = f"""
CASE
  WHEN {T1} IN {_DRAFT_WH} THEN {T2}
  WHEN {DT_DASH} IN {_DRAFT_WH} THEN {TOK_BEFR}
  ELSE SUBSTRING_INDEX(nl.name, '_', 1)
END
""".strip()

SQL_JOUR = f"""
CASE
  WHEN {_SQL_JOUR_RAW} IN {_JOUR_LIST} THEN {_SQL_JOUR_RAW}
  ELSE 'UNKNOWN'
END
""".strip()


# ───────────────────────── dropdown helpers ──────────────────────
def fetch_distinct_draft_types() -> List[str]:
    sql = f"""
    SELECT DISTINCT {SQL_DRAFT} AS draft_type
    FROM   is_newsletters AS nl
    ORDER  BY draft_type
    """
    with conn_cfp() as c, c.cursor() as cur:
        cur.execute(sql)
        return [r[0] for r in cur.fetchall()]


def fetch_distinct_journals(draft_type: str | None = None) -> List[str]:
    where = f"WHERE {SQL_DRAFT} = %s" if draft_type else ""
    params = (draft_type,) if draft_type else ()
    sql = f"""
    SELECT DISTINCT {SQL_JOUR} AS journal
    FROM   is_newsletters AS nl
    {where}
    ORDER  BY journal
    """
    with conn_cfp() as c, c.cursor() as cur:
        cur.execute(sql, params)
        return [r[0] for r in cur.fetchall()]


# ───────────────────────── scenario helper ───────────────────────
def fetch_distinct_scenarios(journal: str) -> List[str]:
    sql = """
    SELECT DISTINCT scenario
    FROM   admin_drafts_agent_data.newsletter_analysis
    WHERE  journal = %s
    ORDER  BY scenario
    """
    with conn_ada() as c, c.cursor() as cur:
        cur.execute(sql, (journal,))
        return [r[0] for r in cur.fetchall()]


# ───────────────────────── campaign list (+status) ───────────────
def fetch_campaigns(journal: str, draft_type: str | None = None) -> List[Dict]:
    where_j  = f"WHERE {SQL_JOUR} = %s"
    where_dt = f"AND {SQL_DRAFT} = %s" if draft_type else ""
    params   = (journal, draft_type) if draft_type else (journal,)

    sql = f"""
    SELECT
        nl.newsletterid,
        nl.name                      AS campaign_name,
        {SQL_DRAFT}                  AS draft_type,
        {SQL_JOUR}                   AS journal,
        nl.subject,
        FROM_UNIXTIME(nl.createdate) AS created_at,
        CASE WHEN na.newsletterid IS NULL
             THEN 'Not analysed' ELSE 'Analysed' END AS status
    FROM   is_newsletters AS nl
    LEFT JOIN admin_drafts_agent_data.newsletter_analysis AS na
           ON na.newsletterid = nl.newsletterid
    {where_j}
    {where_dt}
    ORDER  BY nl.createdate DESC
    """
    with conn_cfp() as c, c.cursor(dictionary=True) as cur:
        cur.execute(sql, params)
        return cur.fetchall()


# ───────────────────────── single draft fetch ────────────────────
def fetch_draft(newsletterid: int) -> Optional[Dict]:
    sql = f"""
    SELECT
        nl.newsletterid,
        nl.name              AS campaign_name,
        {SQL_DRAFT}          AS draft_type,
        {SQL_JOUR}           AS journal,
        nl.subject,
        nl.textbody,
        nl.htmlbody,
        FROM_UNIXTIME(nl.createdate) AS created_at
    FROM   is_newsletters nl
    WHERE  nl.newsletterid = %s
    LIMIT  1
    """
    with conn_cfp() as c, c.cursor(dictionary=True) as cur:
        cur.execute(sql, (newsletterid,))
        return cur.fetchone()


# ───────────────────────── save analysis row ─────────────────────
def save_analysis(
    newsletterid: int,
    res: Dict,
    body_html: str,
    journal: str,
    draft_type: str,
) -> None:
    sql = """
    INSERT INTO admin_drafts_agent_data.newsletter_analysis
      (newsletterid, analysed_at, journal, draft_type, scenario,
       subject_fit, subject_reasoning, improvement, body_html)
    VALUES
      (%(newsletterid)s, NOW(), %(journal)s, %(draft_type)s, %(scenario)s,
       %(subject_fit)s, %(subject_reasoning)s, %(improvement)s, %(body_html)s)
    ON DUPLICATE KEY UPDATE
       analysed_at       = NOW(),
       journal           = VALUES(journal),
       draft_type        = VALUES(draft_type),
       scenario          = VALUES(scenario),
       subject_fit       = VALUES(subject_fit),
       subject_reasoning = VALUES(subject_reasoning),
       improvement       = VALUES(improvement),
       body_html         = VALUES(body_html);
    """
    payload = {
        "newsletterid":       newsletterid,
        "journal":            journal,
        "draft_type":         draft_type,
        "scenario":           res.get("scenario"),
        "subject_fit":        int(bool(res.get("subject_fit"))),
        "subject_reasoning":  res.get("subject_reasoning"),
        "improvement":        res.get("improvement"),
        "body_html":          body_html,
    }
    with conn_ada() as c, c.cursor() as cur:
        cur.execute(sql, payload)
        c.commit()
