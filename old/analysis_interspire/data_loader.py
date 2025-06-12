import pandas as pd
import sqlalchemy
import os
import numpy as np # Import numpy for np.nan

def load_history(limit: int | None = None) -> pd.DataFrame:
    """
    Loads historical Interspire email campaign data from the database into a pandas DataFrame.
    Computes 'open_rate', 'click_rate', and 'bounce_rate' columns.
    Replaces division by zero with np.nan.

    Args:
        limit (int, optional): Maximum number of records to load. Defaults to None (no limit).

    Returns:
        pandas.DataFrame: DataFrame containing Interspire data with rate columns.
    """
    # Database connection details - using environment variables prefixed with "DRAFTS_"
    db_user = os.getenv("DRAFTS_DB_USER")
    db_password = os.getenv("DRAFTS_DB_PASS")
    db_host = os.getenv("DRAFTS_DB_HOST")
    db_name = os.getenv("DRAFTS_DB_NAME")

    if not all([db_user, db_password, db_host, db_name]):
        raise ValueError("Database credentials (DRAFTS_DB_USER, DRAFTS_DB_PASSWORD, DRAFTS_DB_HOST, DRAFTS_DB_NAME) must be set as environment variables.")

    db_connection_str = f"mysql+mysqlconnector://{db_user}:{db_password}@{db_host}/{db_name}"
    engine = sqlalchemy.create_engine(db_connection_str)

    query = "SELECT * FROM interspire_data"
    if limit is not None:
        query += f" LIMIT {limit}"

    try:
        df = pd.read_sql(query, engine)
    except Exception as e:
        raise RuntimeError(f"Error loading data from database: {e}")

    # Ensure 'email' and 'subject' columns have no NaN values
    df['email'] = df['email'].fillna('')
    df['subject'] = df['subject'].fillna('')

    # Compute additional rate columns, handling division by zero
    df["open_rate"] = df["opens"] / df["sent_count"].replace(0, np.nan)
    df["click_rate"] = df["clicks"] / df["sent_count"].replace(0, np.nan)
    df["bounce_rate"] = df["bounces"] / df["sent_count"].replace(0, np.nan)

    return df
