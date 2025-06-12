import pandas as pd
from . import features_subject as fs
from . import features_content as fc

def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Applies all feature extraction functions from features_subject and features_content
    to the input DataFrame.

    Args:
        df (pd.DataFrame): The input DataFrame containing 'subject' and 'email' columns.

    Returns:
        pd.DataFrame: A new DataFrame with original 'id' and all computed feature columns.
    """
    if 'subject' not in df.columns or 'email' not in df.columns or 'id' not in df.columns:
        raise ValueError("Input DataFrame must contain 'id', 'subject', and 'email' columns.")

    # Initialize a new DataFrame for features with the 'id' column
    df_features = pd.DataFrame({'id': df['id']})

    # Apply subject features
    df_features['subject_char_count'] = fs.char_count(df['subject'])
    df_features['subject_caps_ratio'] = fs.caps_ratio(df['subject'])
    df_features['subject_has_call_for_papers'] = fs.has_call_for_papers(df['subject'])
    df_features['subject_excess_exclaim'] = fs.excess_exclaim(df['subject'])
    df_features['subject_length_bucket'] = fs.length_bucket(df['subject'])

    # Apply content features
    df_features['content_intro_word_count'] = fc.intro_word_count(df['email'])
    df_features['content_has_html_bullets'] = fc.has_html_bullets(df['email'])
    df_features['content_external_domain_count'] = fc.external_domain_count(df['email'])
    df_features['content_single_cta'] = fc.single_cta(df['email'])

    return df_features

if __name__ == "__main__":
    # Example usage for testing
    # Create a dummy DataFrame
    data = {
        'id': [1, 2, 3, 4],
        'subject': [
            "Hello World!",
            "CALL FOR PAPERS: Important Announcement",
            "Short subject",
            "Another subject with a question?"
        ],
        'email': [
            "<p>Email body 1.</p><br>More text. <a href='http://example.com'>Link</a>",
            "<p>Email body 2.</p><ul><li>Item</li></ul> <a href='http://anothersite.org'>Link</a>",
            "Plain text email.\nLine break. <a href='http://test.com'>Test</a>",
            "No breaks. Just text. <a href='http://domain1.com'>D1</a> <a href='http://domain2.com'>D2</a>"
        ],
        'opens': [100, 200, 50, 150],
        'clicks': [10, 20, 5, 15],
        'bounces': [1, 2, 0, 1],
        'sent_count': [1000, 1000, 500, 1000],
        'domain': ['cfp7', 'journalsinfo', 'cfp7', 'journalsinfo'],
        'created_at': ['2023-01-01', '2023-01-02', '2023-01-03', '2023-01-04']
    }
    dummy_df = pd.DataFrame(data)

    print("Original DataFrame:")
    print(dummy_df)

    # Build features
    features_df = build_features(dummy_df)
    print("\nFeatures DataFrame:")
    print(features_df)
    features_df.info()
