from database_sync_pipeline import DatabaseSyncPipeline
from datetime import datetime
import pymysql, os
from dotenv import load_dotenv

load_dotenv()
DB = {
    'host': os.getenv('DRAFTS_DB_HOST'),
    'user': os.getenv('DRAFTS_DB_USER'),
    'password': os.getenv('DRAFTS_DB_PASS'),
    'database': os.getenv('DRAFTS_DB_NAME'),
    'cursorclass': pymysql.cursors.DictCursor
}
conn = pymysql.connect(**DB)
with conn.cursor() as cur:
    cur.execute("""
        UPDATE interspire_data
           SET sent_date = DATE(created_at)
         WHERE sent_date IS NULL
    """)
    print(f"{cur.rowcount} rows back-filled in interspire_data")
    # Repeat for mailwizz_data if needed
conn.commit()
conn.close()
