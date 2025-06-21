# db.py  ── supports either MySQL (3306) or Postgres (5432) automatically
import os
import pymysql            # ← MySQL
import psycopg2, psycopg2.extras
import mysql.connector, os
from contextlib import contextmanager
from dotenv import load_dotenv
load_dotenv()

@contextmanager
def draft_db_cursor():
    conn = mysql.connector.connect(
        host=os.getenv("DRAFTS_DB_HOST"),
        user=os.getenv("DRAFTS_DB_USER"),
        password=os.getenv("DRAFTS_DB_PASS"),
        database=os.getenv("DRAFTS_DB_NAME"),
    )
    cur = conn.cursor()
    try:
        yield cur
        conn.commit()
    finally:
        cur.close()
        conn.close()

def save_run(run_id: str, **cols) -> None:
    """
    Upsert into draft_runs (adds/updates only the columns supplied in **cols).
    """
    if not cols:
        return
    keys, vals        = zip(*cols.items())
    placeholders       = ", ".join(["%s"] * len(vals))
    columns            = ", ".join(keys)
    update_cols        = ", ".join(f"{k}=VALUES({k})" for k in keys)
    sql = f"""
        INSERT INTO draft_runs (run_id, {columns})
        VALUES (%s, {placeholders})
        ON DUPLICATE KEY UPDATE {update_cols};
    """
    with draft_db_cursor() as cur:
        cur.execute(sql, (run_id, *vals))

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

def log_agent_run(run_id: str, step: str,
                  model,          # ← accept “anything”
                  prompt_tok: int,
                  completion_tok: int) -> None:
    """
    Persist one LLM call in agent_runs.
    """

    # ── convert model object → str safely ───────────────────────────
    if not isinstance(model, str):
        # langchain / CrewAI LLMs expose .model_name or .id; fall back to repr
        model = getattr(model, "model_name",
                getattr(model, "id", repr(model)))

    total_tok = prompt_tok + completion_tok
    sql = """
      INSERT INTO agent_runs
      (run_id, step_name, model_name, prompt_tok, completion_tok, total_tok)
      VALUES (%s, %s, %s, %s, %s, %s)
    """
    with draft_db_cursor() as cur:
        cur.execute(sql,
                    (run_id, step, model, prompt_tok, completion_tok, total_tok))


# ──────────────────────────────────────────────────────────────────────────────
#  DRAFT STORAGE HELPERS  (for Interspire workflow)
# ──────────────────────────────────────────────────────────────────────────────

# ─── DRAFT STORAGE HELPERS ─────────────────────────────────────────
def save_draft(
    *,                       # keyword-only args
    draft_run_id: int,       # NEW  ← integer FK to draft_runs.id
    subject_lines: list[str],
    html_body: str,
    text_body: str,
) -> int:
    with get_conn() as conn, conn.cursor() as cur:
        # 1) main row
        if _DSN["port"] == 5432:                              # Postgres
            cur.execute(
                """
                INSERT INTO drafts (draft_run_id, html_body, text_body)
                VALUES (%s, %s, %s)
                RETURNING id
                """,
                (draft_run_id, html_body, text_body),
            )
            draft_id = cur.fetchone()[0]
        else:                                                 # MySQL
            cur.execute(
                """
                INSERT INTO drafts (draft_run_id, html_body, text_body)
                VALUES (%s, %s, %s)
                """,
                (draft_run_id, html_body, text_body),
            )
            draft_id = cur.lastrowid

        # 2) subjects (unchanged)
        subj_sql = """
            INSERT INTO draft_subjects
            (draft_id, subject_line, sort_order, is_final)
            VALUES (%s, %s, %s, 0)
        """
        cur.executemany(
            subj_sql,
            [(draft_id, subj, idx + 1)
             for idx, subj in enumerate(subject_lines)],
        )
        conn.commit()
    return draft_id



def finalize_subject(draft_id: int, subject_id: int) -> None:
    """Mark exactly one subject as the winner for this draft."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE draft_subjects
            SET is_final = CASE WHEN id = %s THEN 1 ELSE 0 END
            WHERE draft_id = %s
            """,
            (subject_id, draft_id),
        )
        conn.commit()


def get_payload_for_api(draft_id: int) -> dict:
    """
    Return {'html': ..., 'text': ..., 'subject': ...} for Interspire API.
    """
    sql = """
        SELECT d.html_body, d.text_body, s.subject_line
        FROM drafts d
        JOIN draft_subjects s ON s.draft_id = d.id AND s.is_final = 1
        WHERE d.id = %s
        LIMIT 1
    """
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(sql, (draft_id,))
        row = cur.fetchone()
    if not row:
        raise RuntimeError(f"No final subject found for draft {draft_id}")

    return {
        "html": row["html_body"],
        "text": row["text_body"],
        "subject": row["subject_line"],
    }


def get_unique_scenarios_for_journal(journal):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT scenario
                FROM newsletter_analysis
                WHERE journal = %s
                  AND scenario IS NOT NULL
                  AND scenario != ''
            """, (journal,))
            results = cur.fetchall()
    return [row["scenario"] for row in results]

