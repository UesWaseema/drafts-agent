"""Integration helpers for feeding rich Interspire analytics into the CFP-Draft pipeline.

This patch adds two public helpers:

* ``get_recent_campaign_records(journal_name, limit=10)`` -- returns a list of *dicts* containing the **latest ``limit`` rows** from ``interspire_analysis_results`` for the given journal. All columns (31+) are preserved.
* ``format_campaign_records(records, style="json")`` -- converts that list into a prompt-ready string. Supports
  * ``json`` (default) -> a compact JSON array; easy for the LLM to parse.
  * ``markdown`` -> a readable markdown table (handy for debugging in Streamlit).

Both functions work directly with **your existing PostgreSQL connection pool** via ``db.get_conn()``.

If the journal has *no* rows yet, the functions return an empty list / ``"[]"`` so the prompt remains valid.
"""
from __future__ import annotations

import json
import logging
from typing import List, Dict, Any

from db import get_conn  # existing utility that yields a psycopg/pg8000 connection

logger = logging.getLogger(__name__)

__all__ = [
    "get_recent_campaign_records",
    "format_campaign_records",
]


# ---------------------------------------------------------------------------
# Data access helpers
# ---------------------------------------------------------------------------

def get_recent_campaign_records(journal_name: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Fetch the *latest* ``limit`` rows for *journal_name* from
    **interspire_analysis_results**.

    Returns a list of dicts (one per row) or an empty list if none exist.
    The column order is preserved as declared in the table for deterministic
    JSON output.
    """
    sql = (
        "SELECT *\n"
        "  FROM interspire_analysis_results\n"
        " WHERE journal_name = %s\n"
        " ORDER BY sent_at DESC\n"
        " LIMIT %s;"
    )

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (journal_name, limit))
                col_names = [c.name for c in cur.description]  # type: ignore[attr-defined]
                return [dict(zip(col_names, row)) for row in cur.fetchall()]
    except Exception as exc:
        logger.error("Failed to fetch campaign records for %s – %s", journal_name, exc)
        return []


# ---------------------------------------------------------------------------
# Formatting helper
# ---------------------------------------------------------------------------

def format_campaign_records(records: List[Dict[str, Any]], *, style: str = "json") -> str:
    """Convert *records* to a prompt-ready string.

    Parameters
    ----------
    records : list of dict
        The rows returned by :func:`get_recent_campaign_records`.
    style : {"json", "markdown"}
        * ``json`` -- returns a compact JSON array (default).
        * ``markdown`` -- returns a readable markdown table (1st row = headers).
    """
    if not records:
        return "[]" if style == "json" else "No campaign records found."

    if style == "json":
        # Use compact separators to minimise tokens but keep keys readable.
        return json.dumps(records, separators=(",", ":"))

    # --- Markdown table ---
    headers = records[0].keys()
    rows = [" | ".join(map(str, headers))]  # header row
    rows.append(" | ".join(["---"] * len(headers)))  # separator
    for r in records:
        rows.append(" | ".join(map(lambda v: str(v) if v is not None else "", r.values())))
    return "\n".join(rows)
