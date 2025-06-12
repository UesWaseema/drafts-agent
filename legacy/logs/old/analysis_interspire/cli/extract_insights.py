import argparse
import pandas as pd
import os
import sys

# Add the parent directory to the Python path to allow importing analysis_interspire
# This is a common pattern for runnable scripts within a package
script_dir = os.path.dirname(__file__)
package_root = os.path.abspath(os.path.join(script_dir, '..', '..'))
sys.path.insert(0, package_root)

from analysis_interspire.data_loader import load_history
from analysis_interspire.feature_builder import build_features
from analysis_interspire.correlate import compute_correlations, save_correlations_to_csv

def extract_insights(limit: int | None = None):
    """
    Performs Phase 1 Data Analysis & Insight Extraction for Interspire data.
    Steps: load -> build_features -> correlate -> save CSV -> print completion message.
    """
    print("Starting Phase 1 Data Analysis & Insight Extraction for Interspire data...")

    # 1. Load data
    print(f"Loading history data (limit: {limit if limit is not None else 'None'})...")
    df_history = load_history(limit=limit)
    print(f"Loaded {len(df_history)} records.")

    if df_history.empty:
        print("No data loaded. Exiting.")
        return

    # Separate metrics for correlation
    df_metrics = df_history[['id', 'open_rate', 'click_rate', 'bounce_rate']].copy()

    # 2. Build features
    print("Building features...")
    df_features = build_features(df_history)
    print(f"Built {len(df_features.columns) - 1} features.") # -1 for 'id' column

    # 3. Compute correlations
    print("Computing correlations between features and metrics...")
    df_correlations = compute_correlations(df_features, df_metrics)
    print("Correlations computed.")

    # 4. Save CSV
    output_dir = "analysis_interspire/outputs"
    save_correlations_to_csv(df_correlations, output_dir=output_dir)

    # 5. Print completion message
    print(f"\nPhase 1 completed; outputs in {output_dir}")

def main():
    parser = argparse.ArgumentParser(
        description="Perform Phase 1 Data Analysis & Insight Extraction for Interspire email data."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of records to load from the database (e.g., 50000)."
    )
    args = parser.parse_args()

    extract_insights(limit=args.limit)

if __name__ == "__main__":
    main()
