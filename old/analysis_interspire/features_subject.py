
import pandas as pd
import re

def char_count(s: pd.Series) -> pd.Series:
    """
    Calculates the character count of each string in a pandas Series.
    """
    return s.apply(len)

def caps_ratio(s: pd.Series) -> pd.Series:
    """
    Calculates the ratio of uppercase characters to total characters (as a percentage)
    for each string in a pandas Series. Returns 0 if the string is empty.
    """
    def _caps_ratio(text):
        if not text:
            return 0.0
        total_chars = len(text)
        if total_chars == 0:
            return 0.0
        uppercase_chars = sum(1 for char in text if char.isupper())
        caps = uppercase_chars
        total = total_chars
        return (100 * caps / total).round(2)
    return s.apply(_caps_ratio)

def has_call_for_papers(s: pd.Series) -> pd.Series:
    """
    Checks if the string contains the phrase "call for papers" (case-insensitive).
    Returns 1 if present, 0 otherwise.
    """
    return s.apply(lambda x: 1 if re.search(r"call\s+for\s+papers", str(x), re.IGNORECASE) else 0)

def excess_exclaim(s: pd.Series) -> pd.Series:
    """
    Counts the total number of exclamation marks and question marks in each string.
    """
    return s.apply(lambda x: str(x).count('!') + str(x).count('?'))

def length_bucket(s: pd.Series) -> pd.Series:
    """
    Categorizes the length of each string into "<35", "35-55", or ">55".
    """
    def _length_bucket(text):
        length = len(str(text))
        if length < 35:
            return "<35"
        elif 35 <= length <= 55:
            return "35-55"
        else:
            return ">55"
    return s.apply(_length_bucket)

if __name__ == "__main__":
    # Example usage for testing
    test_subjects = pd.Series([
        "Hello World!",
        "CALL FOR PAPERS: Important Announcement",
        "Short",
        "This is a moderately long subject line between 30 and 60 characters.",
        "This subject line is definitely longer than sixty characters, which is quite excessive for an email subject."])
