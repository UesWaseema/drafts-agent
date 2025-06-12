"""
Rule-based scoring for subject lines.
All functions return *numbers* so scorer.py can sum them.
"""

import re, math, pandas as pd
from analysis_interspire.scoring.utils_text import spam_word_hit

############################################################
# shared helpers
############################################################
def _clean(text: str) -> str:
    if not isinstance(text, str):
        return ""
    # collapse whitespace & HTML entities
    text = re.sub(r"&nbsp;|\\s+", " ", text, flags=re.I).strip()
    return text

def char_count(text: str) -> int:
    return len(_clean(text))

def caps_percentage(text: str) -> float:
    t = _clean(text)
    if not t:
        return 0.0
    caps = sum(1 for ch in t if ch.isupper())
    return round(100 * caps / len(t), 2)

############################################################
# individual rule scores (positive good, negative bad)
############################################################
def length_score(text: str) -> int:
    n = char_count(text)
    if 35 <= n <= 55:
        return 30
    return -25

def caps_score(text: str) -> int:
    pct = caps_percentage(text)
    if 10 <= pct <= 20:
        return 15
    if pct > 30:
        return -20
    if pct < 10:
        return -5
    return 0

_SPAM_RE = re.compile(r"\\b[A-Z]{2,}\\b")

def spam_risk_score(text: str) -> int:
    """Negative ⇒ higher risk"""
    score = 0
    # ALL-CAPS words
    caps_hits = _SPAM_RE.findall(text)
    score -= 5 * len(caps_hits)
    # common spam words
    words = re.findall(r"[A-Za-z']+", text)
    spam_hits = sum(spam_word_hit(w) for w in words)
    score -= 3 * spam_hits
    return max(-25, score)  # cap penalty

def keyword_score(text: str) -> int:
    return 8 if re.search(r"call\\s+for\\s+papers", text, flags=re.I) else 0

def punctuation_penalty(text: str) -> (bool, int):
    bad = len(re.findall(r"[!?]", text)) > 1
    return (not bad, 0 if not bad else -10)

############################################################
# high-level wrapper (dict per subject)
############################################################
def analyse_subject(text: str) -> dict:
    length_sc     = length_score(text)
    caps_sc       = caps_score(text)
    spam_sc       = spam_risk_score(text)
    kw_sc         = keyword_score(text)
    punct_ok, pp  = punctuation_penalty(text)

    overall = length_sc + caps_sc + spam_sc + kw_sc + pp

    return {
        # metrics you asked about
        "subject_length_score":           length_sc,
        "subject_caps_score":             caps_sc,
        "subject_spam_risk_score":        spam_sc,
        "subject_keyword_score":          kw_sc,
        "subject_punctuation_ok":         punct_ok,
        "subject_overall_score":          overall,
        # extra fields reused elsewhere
        "subject_length":                 char_count(text),
        "subject_caps_percentage":        caps_percentage(text),
        "subject_length_ok":              35 <= char_count(text) <= 55,
        "subject_caps_status":            "Pass" if 10 <= caps_percentage(text) <= 20 else "Fail",
    }
