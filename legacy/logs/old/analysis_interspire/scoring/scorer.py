import pandas as pd
from analysis_interspire.scoring.rules_subject import analyse_subject
from analysis_interspire.scoring.rules_content import calculate_content_scores
from analysis_interspire.scoring.rules_risk import calculate_risk_scores
import numpy as np

# Define the full schema for the output DataFrame
# This should include all possible keys from subject, content, and risk scores,
# plus original columns like campaign_id, subject_line, etc.
FULL_SCHEMA = [
    "campaign_id",
    "subject_line",
    "email_body", # Original HTML body
    "sent_count",
    "opens",
    "clicks",
    "bounces",
    "open_rate",
    "click_rate",
    "bounce_rate",
    "intro_score",
    "bullets_score",
    "cta_score",
    "external_domains_score",
    "structure_score",
    "html_validation_score",
    "mobile_friendly_score",
    "email_content_score",
    "overall_compliance_status",
    "overall_score",
    "confidence_level",
    "optimization_priority_list",
    "feedback_json",
    "optimizer_version",
    # Add individual pass/fail fields from rules_risk.py
    "intro_pass",
    "cta_pass",
    "external_domains_pass",
    "html_validation_pass",
    "mobile_friendly_pass",
]

def score_drafts(df_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Scores email drafts based on subject, content, and risk rules.

    Args:
        df_raw (pd.DataFrame): DataFrame containing raw email campaign data
                                with 'subject_line' and 'email_body' columns.

    Returns:
        pd.DataFrame: DataFrame with all scoring results, conforming to FULL_SCHEMA.
    """
    results = []

    for index, row in df_raw.iterrows():
        subject_line = row.get("subject_line", "")
        email_body = row.get("email_body", "")

        subj_dict = analyse_subject(subject_line)
        row.update(subj_dict)
        content_scores = calculate_content_scores(email_body)
        risk_scores = calculate_risk_scores(subj_dict, content_scores)

        # Combine all scores and original data for the current row
        combined_row_data = {
            "campaign_id": row.get("campaign_id"),
            "subject_line": subject_line,
            "email_body": email_body,
            "sent_count": row.get("sent_count"),
            "opens": row.get("opens"),
            "clicks": row.get("clicks"),
            "bounces": row.get("bounces"),
            "open_rate": row.get("open_rate"),
            "click_rate": row.get("click_rate"),
            "bounce_rate": row.get("bounce_rate"),
            **subj_dict,
            **content_scores,
            **risk_scores
        }
        
        # Flatten per_rule_pass_fail into the main dictionary
        if "per_rule_pass_fail" in combined_row_data:
            for k, v in combined_row_data["per_rule_pass_fail"].items():
                combined_row_data[k] = v
            del combined_row_data["per_rule_pass_fail"]

        results.append(combined_row_data)

    df_scored = pd.DataFrame(results)

    # Ensure all columns from FULL_SCHEMA are present, fill missing with NaN
    for col in FULL_SCHEMA:
        if col not in df_scored.columns:
            df_scored[col] = np.nan
    
    # Reorder columns to match FULL_SCHEMA
    df_scored = df_scored[FULL_SCHEMA]

    return df_scored

if __name__ == "__main__":
    # Example usage for testing
    # Create a dummy DataFrame similar to what data_loader.py would return
    dummy_data = {
        "campaign_id": [1, 2, 3, 4],
        "subject_line": [
            "This is a good subject line for testing purposes.",
            "URGENT: Win a FREE iPhone now!!!",
            "Your Exclusive Update: New Features!",
            "Short"
        ],
        "email_body": [
            "<html><head><meta name='viewport' content='width=device-width'></head><body><h1>Welcome</h1><p>This is an intro. More text.</p><ul><li>Item</li></ul><a href='http://example.com'>CTA</a></body></html>",
            "<html><body><p style='color:red;'>Inline style.</p><a href='http://spam.com'>Spam</a><a href='mailto:a@b.com'>Email</a></body></html>",
            "<html><body><p>Intro text.</p><a href='http://one.com'>1</a></body></html>",
            "<div>No HTML or body tags. Just text.</div>"
        ],
        "sent_count": [1000, 500, 750, 200],
        "opens": [100, 50, 150, 10],
        "clicks": [10, 5, 20, 1],
        "bounces": [50, 20, 30, 5]
    }
    df_test = pd.DataFrame(dummy_data)

    # Manually add rate columns as data_loader would
    df_test["open_rate"] = df_test["opens"] / df_test["sent_count"].replace(0, np.nan)
    df_test["click_rate"] = df_test["clicks"] / df_test["sent_count"].replace(0, np.nan)
    df_test["bounce_rate"] = df_test["bounces"] / df_test["sent_count"].replace(0, np.nan)

    print("--- Raw DataFrame ---")
    print(df_test)

    df_scored_output = score_drafts(df_test)
    print("\n--- Scored DataFrame ---")
    print(df_scored_output)

    # Verify schema
    print("\n--- Schema Check ---")
    print(f"All schema columns present: {all(col in df_scored_output.columns for col in FULL_SCHEMA)}")
    print(f"Number of columns in scored DF: {len(df_scored_output.columns)}")
    print(f"Number of columns in schema: {len(FULL_SCHEMA)}")
