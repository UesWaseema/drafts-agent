from decimal import Decimal          # new
import pandas as pd
import mysql.connector
import os
from dotenv import load_dotenv
import numpy as np

DEC2 = lambda x: None if pd.isna(x) else round(float(x), 2)

def persist(df: pd.DataFrame) -> None:
    """
    Bulk upserts the fully-scored DataFrame into the interspire_analysis_results MySQL table.
    """
    load_dotenv() # Ensure environment variables are loaded

    DB_HOST = os.getenv("DRAFTS_DB_HOST")
    DB_USER = os.getenv("DRAFTS_DB_USER")
    DB_PASSWORD = os.getenv("DRAFTS_DB_PASS")
    DB_NAME = os.getenv("DRAFTS_DB_NAME")

    conn = None
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        cursor = conn.cursor()

        columns_mapping = {
            # ── primary key ───────────────
            'analysis_id'                  : 'analysis_id',
            'campaign_id'                  : 'campaign_id',

            # ── subject line + heuristics ─
            'subject_line'                 : 'subject_line',
            'subject_length'               : 'subject_length',
            'email_content'                : 'email_content',
            'email_type'                   : 'email_type',
            'subject_length_score'         : 'subject_length_score',
            'subject_caps_percentage'      : 'subject_caps_percentage',
            'subject_spam_risk_score'      : 'subject_spam_risk_score',
            'subject_punctuation_score'    : 'subject_punctuation_score',
            'subject_overall_score'        : 'subject_overall_score',

            # ── body-level features ───────
            'intro_word_count'             : 'intro_word_count',
            'intro_score_contribution'     : 'intro_score_contribution',
            'bullets_position'             : 'bullets_position',
            'bullets_score_contribution'   : 'bullets_score_contribution',
            'cta_count'                    : 'cta_count',
            'cta_score_contribution'       : 'cta_score_contribution',
            'email_content_score'          : 'email_content_score',

            # ── model / agent outputs ─────
            'confidence_score'             : 'confidence_score',
            'confidence_score_justification':'confidence_score_justification',
            'bounce_risk'                  : 'bounce_risk',
            'bounce_risk_explanation'      : 'bounce_risk_explanation',
            'structure_score'              : 'structure_score',
            'structure_justification'      : 'structure_justification',

            'waiver_percentage'            : 'waiver_percentage',
            'waiver_compliance'            : 'waiver_compliance',
            'compliance_details'           : 'compliance_details',
            'waiver_recommendations'       : 'waiver_recommendations',

            'content_quality_score'        : 'content_quality_score',
            'content_recommendations'      : 'content_recommendations',

            # ── super-score ───────────────
            'overall_score'                : 'overall_score'
        }

        # --- build df_to_persist ----------------------------------------------------
        df_to_persist = df[list(columns_mapping.values())].copy()

        # numeric coercions ---------------------------------------------------------
        int_cols = [
            'analysis_id','campaign_id','subject_length','subject_length_score',
            'subject_spam_risk_score','subject_punctuation_score','intro_word_count',
            'intro_score_contribution','cta_count','cta_score_contribution',
            'email_content_score','confidence_score','structure_score',
            'content_quality_score','overall_score'
        ]
        float_cols = [
            'subject_caps_percentage','bullets_score_contribution','bounce_risk'
        ]
        bool_cols  = ['waiver_compliance']

        for c in int_cols:
            df_to_persist[c] = df_to_persist[c].fillna(0).astype(int)

        for c in float_cols:
            df_to_persist[c] = df_to_persist[c].apply(DEC2)

        for c in bool_cols:
            df_to_persist[c] = df_to_persist[c].fillna(False).astype(int)

        text_cols = set(df_to_persist.columns) - set(int_cols) - set(float_cols) - set(bool_cols)
        for c in text_cols:
            df_to_persist[c] = df_to_persist[c].fillna("").astype(str)

        # --- SQL parts --------------------------------------------------------------
        insert_cols       = ', '.join(columns_mapping.keys())
        placeholders      = ', '.join(['%s'] * len(columns_mapping))
        update_clauses    = ', '.join(
            f"{col}=VALUES({col})"
            for col in columns_mapping.keys()
            if col not in ('analysis_id','campaign_id')    # keep PKs stable
        )
        update_clauses   += ', created_at=CURRENT_TIMESTAMP'

        sql = f"""INSERT INTO interspire_analysis_results
                  ({insert_cols})
                  VALUES ({placeholders})
                  ON DUPLICATE KEY UPDATE {update_clauses};"""

        # --- executemany payload ----------------------------------------------------
        data_to_insert = [
            tuple(row[col] for col in columns_mapping.keys())
            for _, row in df_to_persist.iterrows()
        ]

        # Execute the bulk upsert
        cursor.executemany(sql, data_to_insert)
        conn.commit()
        print(f"Successfully persisted {len(data_to_insert)} rows to interspire_analysis_results.")

    except mysql.connector.Error as err:
        print(f"Error persisting data to database: {err}")
        # Optionally re-raise the exception if you want app.py to handle it
        raise
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        raise
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    # This block is for testing the persist function independently
    # You would typically run this from a separate test script or directly in a Python interpreter
    print("Running save_results.py as a standalone script for testing purposes.")
    # Example usage: Create a dummy DataFrame and call persist
    dummy_data = {
        'analysis_id': [1, 2],
        'campaign_id': [101, 102],
        'subject_line': ['Test Subject 1', 'Test Subject 2'],
        'subject_length': [14, 14],
        'email_content': ['Test Content 1', 'Test Content 2'],
        'email_type': ['promotional', 'transactional'],
        'subject_length_score': [80, 75],
        'subject_caps_percentage': [0.5, 0.1],
        'subject_spam_risk_score': [10, 5],
        'subject_punctuation_score': [5, 2],
        'subject_overall_score': [80, 75],
        'intro_word_count': [50, 40],
        'intro_score_contribution': [10, 8],
        'bullets_position': ['middle', 'end'],
        'bullets_score_contribution': [0.8, 0.6],
        'cta_count': [2, 1],
        'cta_score_contribution': [10, 5],
        'email_content_score': [90, 85],
        'confidence_score': [88, 82],
        'confidence_score_justification': ['Good', 'Fair'],
        'bounce_risk': [5.5, 12.3],
        'bounce_risk_explanation': ['Low risk', 'Medium risk'],
        'structure_score': [92, 89],
        'structure_justification': ['Well structured', 'Needs improvement'],
        'waiver_percentage': [50, 0],
        'waiver_compliance': [True, False],
        'compliance_details': ['Compliant', 'Non-compliant'],
        'waiver_recommendations': ['None', 'Add waiver'],
        'content_quality_score': [85, 78],
        'content_recommendations': ['None', 'Improve content'],
        'overall_score': [87, 80]
    }
    dummy_df = pd.DataFrame(dummy_data)
    
    # Ensure environment variables are set for testing, e.g., in a .env file or directly
    # os.environ["DRAFTS_DB_HOST"] = "your_db_host"
    # os.environ["DRAFTS_DB_USER"] = "your_db_user"
    # os.environ["DRAFTS_DB_PASS"] = "your_db_password"
    # os.environ["DRAFTS_DB_NAME"] = "your_db_name"

    try:
        persist(dummy_df)
        print("Dummy data persistence test completed.")
    except Exception as e:
        print(f"Dummy data persistence test failed: {e}")
