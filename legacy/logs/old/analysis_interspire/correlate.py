import pandas as pd
import numpy as np
from scipy.stats import spearmanr
import os

def compute_correlations(df_features: pd.DataFrame, df_metrics: pd.DataFrame) -> pd.DataFrame:
    """
    Computes Spearman correlation and p-value for each numeric feature vs each target metric.

    Args:
        df_features (pd.DataFrame): DataFrame containing feature columns.
        df_metrics (pd.DataFrame): DataFrame containing target metrics (open_rate, click_rate, bounce_rate).
                                   Must contain 'id' column for merging.

    Returns:
        pd.DataFrame: A tidy DataFrame with columns: feature, metric, correlation, p_value.
    """
    # Ensure 'id' column is present in both and merge them
    if 'id' not in df_features.columns or 'id' not in df_metrics.columns:
        raise ValueError("Both df_features and df_metrics must contain an 'id' column.")
    
    df_merged = pd.merge(df_features, df_metrics[['id', 'open_rate', 'click_rate', 'bounce_rate']], on='id', how='inner')

    numeric_features = df_merged.select_dtypes(include=np.number).columns.tolist()
    # Remove 'id' and metric columns from features
    numeric_features = [f for f in numeric_features if f not in ['id', 'open_rate', 'click_rate', 'bounce_rate']]

    target_metrics = ['open_rate', 'click_rate', 'bounce_rate']

    correlations_data = []

    for feature in numeric_features:
        for metric in target_metrics:
            # Drop NaN values for correlation calculation
            temp_df = df_merged[[feature, metric]].dropna()
            if len(temp_df) > 1: # Need at least 2 data points for correlation
                if temp_df[feature].nunique(dropna=False) <= 1:
                    continue   # constant -> skip correlation
                correlation, p_value = spearmanr(temp_df[feature], temp_df[metric])
                correlations_data.append({
                    'feature': feature,
                    'metric': metric,
                    'correlation': correlation,
                    'p_value': p_value
                })
            else:
                correlations_data.append({
                    'feature': feature,
                    'metric': metric,
                    'correlation': np.nan,
                    'p_value': np.nan
                })

    return pd.DataFrame(correlations_data)

def save_correlations_to_csv(df_correlations: pd.DataFrame, output_dir: str = "analysis_interspire/outputs"):
    """
    Saves the correlation DataFrame to a CSV file.
    Creates the output directory if it doesn't exist.
    """
    output_path = os.path.join(output_dir, "feature_correlations.csv")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df_correlations.to_csv(output_path, index=False)
    print(f"Correlations saved to {output_path}")

if __name__ == "__main__":
    # Example usage for testing
    # Create dummy feature and metric DataFrames
    features_data = {
        'id': [1, 2, 3, 4, 5],
        'subject_char_count': [10, 25, 8, 30, 15],
        'subject_caps_ratio': [10.0, 50.0, 0.0, 20.0, 30.0],
        'content_intro_word_count': [5, 12, 3, 15, 8],
        'content_external_domain_count': [0, 1, 0, 2, 1]
    }
    metrics_data = {
        'id': [1, 2, 3, 4, 5],
        'open_rate': [0.1, 0.2, 0.05, 0.15, 0.12],
        'click_rate': [0.01, 0.02, 0.005, 0.015, 0.012],
        'bounce_rate': [0.001, 0.002, 0.0005, 0.0015, 0.0012]
    }
    df_features_dummy = pd.DataFrame(features_data)
    df_metrics_dummy = pd.DataFrame(metrics_data)

    print("Dummy Features DataFrame:")
    print(df_features_dummy)
    print("\nDummy Metrics DataFrame:")
    print(df_metrics_dummy)

    # Compute correlations
    correlations_df = compute_correlations(df_features_dummy, df_metrics_dummy)
    print("\nComputed Correlations:")
    print(correlations_df)

    # Save correlations to CSV
    save_correlations_to_csv(correlations_df, output_dir="analysis_interspire/outputs")
