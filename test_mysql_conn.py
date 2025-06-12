# streamlit_app/test_mysql_conn.py

import pymysql
import os
from dotenv import load_dotenv

load_dotenv()

# Shared credentials
HOST = os.getenv("DRAFTS_DB_HOST")
USER = os.getenv("DRAFTS_DB_USER")
PASS = os.getenv("DRAFTS_DB_PASS")
MAILWIZZ_DB = os.getenv("MAILWIZZ_DB_NAME")
INTERSPIRE_DB = os.getenv("INTERSPIRE_DB_NAME")
DRAFTS_DB = os.getenv("DRAFTS_DB_NAME")


def test_connection(db_name):
    try:
        conn = pymysql.connect(
            host=HOST,
            user=USER,
            password=PASS,
            database=db_name,
            cursorclass=pymysql.cursors.DictCursor
        )
        print(f"✅ Connected to {db_name}")
        with conn.cursor() as cursor:
            cursor.execute("SHOW TABLES;")
            tables = cursor.fetchall()
            print(f"📋 Tables in {db_name}:")
            for row in tables:
                print(" -", list(row.values())[0])
        conn.close()
    except Exception as e:
        print(f"❌ Failed to connect to {db_name}: {e}")

if __name__ == "__main__":
    test_connection(MAILWIZZ_DB)
    test_connection(INTERSPIRE_DB)
    test_connection(DRAFTS_DB)
