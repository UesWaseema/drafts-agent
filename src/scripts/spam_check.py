"""
scripts.spam_check
==================
Fast helper to *detect* – not fix – spam / buzz words in a draft.

Functions
---------
find_spam(text, exceptions=None) -> set[str]
    Return the *unique* spam words (lower-cased) present in `text`.

highlight_spam(text, css_class="spam", exceptions=None) -> str
    Return HTML string where each spam hit is wrapped in
    <span class="{css_class}">…</span>  (for Streamlit preview).

Usage example
-------------
>>> from scripts.spam_check import find_spam
>>> hits = find_spam("Amazing discount on groundbreaking research!")
>>> print(hits)
{'amazing', 'discount', 'groundbreaking'}
"""

from __future__ import annotations
import html
import re
from typing import Iterable, List, Set

from utils.spam_words import SPAM_WORDS  # master list (lower-case!)

# -------------------------------------------------------------------- #
# Public API                                                           #
# -------------------------------------------------------------------- #
def find_spam(
    text: str,
    *,
    exceptions: Iterable[str] | None = None,
) -> Set[str]:
    """
    Return a *set* of lower-case spam words found in `text`.

    Parameters
    ----------
    text : str
        Raw input draft (plain text).
    exceptions : Iterable[str] | None
        Words that should be ignored even if they appear in SPAM_WORDS.

    Notes
    -----
    • Word boundaries ⇒ only whole-word matches (case-insensitive).  
    • Punctuation is ignored (`research!` still matches “research”).
    """
    exc = {w.lower() for w in (exceptions or [])}

    hits: Set[str] = set()
    for w in SPAM_WORDS:
        if w in exc:
            continue
        # compile once per word keeps it readable; list is static anyway
        if re.search(rf"\b{re.escape(w)}\b", text, flags=re.IGNORECASE):
            hits.add(w)
    return hits


def highlight_spam(
    text: str,
    *,
    css_class: str = "spam",
    exceptions: Iterable[str] | None = None,
) -> str:
    """
    Wrap every spam hit with a span so you can `.unsafe_allow_html` in Streamlit.

    Example
    -------
    >>> st.markdown(highlight_spam(draft), unsafe_allow_html=True)
    """
    def repl(match: re.Match) -> str:
        word = match.group(0)
        if word.lower() in exc:
            return word  # don’t highlight exceptions
        return f'<span class="{css_class}">{html.escape(word)}</span>'

    exc = {w.lower() for w in (exceptions or [])}
    # Build one big regex that OR-joins every spam word
    spam_regex = re.compile(
        r"\b(" + "|".join(re.escape(w) for w in SPAM_WORDS if w not in exc) + r")\b",
        flags=re.IGNORECASE,
    )
    return spam_regex.sub(repl, html.escape(text))


# -------------------------------------------------------------------- #
# Quick CLI test                                                       #
# -------------------------------------------------------------------- #
if __name__ == "__main__":  # python -m scripts.spam_check "your text"
    import sys, textwrap
    sample = sys.argv[1] if len(sys.argv) > 1 else (
        "Amazing discount on groundbreaking research! "
        "Submit today for massive visibility."
    )
    found = find_spam(sample)
    print("Hits:", ", ".join(sorted(found)) or "— none —")
    print("\nHighlighted ↓\n")
    print(textwrap.fill(highlight_spam(sample), width=80))
