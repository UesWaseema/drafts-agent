"""
qc_helper.py – single routine that stores QC results in MySQL
"""
import os, json, mysql.connector

CFG = dict(
    host     = os.getenv("DRAFTS_DB_HOST", "127.0.0.1"),
    user     = os.getenv("DRAFTS_DB_USER", "admin_waseema"),
    password = os.getenv("DRAFTS_DB_PASS", "YgGAtafH4ypW488Ud3bV"),
    database = os.getenv("DRAFTS_DB_NAME", "admin_drafts_agent_data"),
    port     = int(os.getenv("DRAFTS_DB_PORT", 3306)),
    charset  = "utf8mb4",
)

def save_qc(run_id: int, prompt: str, result: dict):
    """
    Inserts one row into qc_results2.
    """
    cnx = mysql.connector.connect(**CFG)
    cur = cnx.cursor()
    cur.execute(
        "INSERT INTO qc_results2 (run_id, prompt, result_json, passed) "
        "VALUES (%s, %s, %s, %s)",
        (run_id, prompt, json.dumps(result, ensure_ascii=False), int(result["__PASS__"]))
    )
    cnx.commit()
    cur.close()
    cnx.close()