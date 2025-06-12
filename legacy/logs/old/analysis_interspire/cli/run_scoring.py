import argparse
import pandas as pd
from analysis_interspire.data_loader import load_history
from analysis_interspire.scoring.scorer import score_drafts
import os

def main():
    parser = argparse.ArgumentParser(description="Run Interspire email draft scoring.")
    parser.add_argument("--limit", type=int, default=None,
                        help="Maximum number of records to load from the database.")
    args = parser.parse_args()

    output_dir = "analysis_interspire/outputs"
    output_file = os.path.join(output_dir, "draft_analysis.csv")

    print("Loading historical data...")
    df_raw = load_history(limit=args.limit)
    print(f"Loaded {len(df_raw)} rows.")

    print("Scoring drafts...")
    df_scored = score_drafts(df_raw)
    print("Draft scoring complete.")

    print(f"Writing results to {output_file}...")
    os.makedirs(output_dir, exist_ok=True)
    df_scored.to_csv(output_file, index=False)
    print(f"Scoring complete, rows={len(df_scored)}, file={output_file}")

if __name__ == "__main__":
    main()
