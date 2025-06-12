"""
qc_script.py  –  Deterministic quality checker for CFP e-mails
==============================================================

Checks implemented
------------------
Structure / Formatting
    • Block order         (Hook → Waiver → About → Topics → Links → Close → Signature)
    • Bullet list count   (< 6) / prefix (“● ”) / no nested lists
    • URL rules           (exactly 1 CTA + 2 same-domain credibility links)
    • Visible e-mails     (exactly one)
    • Signature in one <p>
    • “Journal + ISSN” appears once

Guardrails
    • Word-count          330–450 (≥ 320 body words)
    • Spam density        ≤ 2 %
    • Forbidden phrases   (waiver, fast-track, indexing, …)
    • Hype-word cap       ≤ 3
    • Hard-sell verbs     forbidden
    • “open access/open-access” spelling forbidden (use ‘OA’ / ‘openaccess’)

Date & math
    • Deadline date present AND ≤ 60 days in the future

Article-type rule
    • If article types listed ⇒ ends with “All types welcome.”

-------------------------------------------------------------------------------
Return value
    validate(text)  → dict(rule_name -> True / False / detail str)
-------------------------------------------------------------------------------
"""

from __future__ import annotations
import re, html, datetime as dt
from collections import Counter
from urllib.parse import urlparse

##############################################################################
#  🔧  Configuration – tweak as needed
##############################################################################

# Minimal spam word sample.  Replace / extend with your master list.
SPAM_WORDS = {
    "100%", "miracle", "guarantee", "unlock", "exclusive", "winner"
}

# Hype & hard-sell vocabulary
HYPE_WORDS  = {
    "groundbreaking", "revolutionary", "spectacular", "incredible",
    "unbeatable", "seize", "amazing", "once-in-a-lifetime", "bargain",
    "massive", "discount", "unrivalled"
}
HARD_SELL   = {"seize", "grab", "don't miss out", "act now", "hurry"}

# Forbidden phrase patterns (case-insensitive)
FORBIDDEN_PATTERNS = {
    "waiver":      r"\b(full waiver|zero\s+apc|free of charge)\b",
    "fast_review": r"\b(fast[- ]?track|rapid review|quick (?:turnaround|review))\b",
    "indexing":    r"\bindexed in|scopus|web of science|impact on indexing\b",
    "doubleblind": r"double[- ]blind",
    "open_access": r"\bopen[- ]access\b",      # allow 'openaccess' or 'OA'
}

# Article-type keywords that trigger the “All types welcome” rule
ARTICLE_TYPES = {"review", "case study", "case report", "original article",
                 "letter", "meta-analysis", "short communication"}


##############################################################################
#  🧩  Helper functions
##############################################################################

WORD_RE  = re.compile(r"\b[\w'-]+\b", re.I)
DATE_RE  = re.compile(r"\b(\d{1,2}\s+[A-Za-z]+\s+\d{4})\b")  # e.g. 31 July 2025

def _wordcount(text: str) -> int:
    return len(WORD_RE.findall(text))

def _spam_density(text: str) -> float:
    words = [w.lower() for w in WORD_RE.findall(text)]
    spam_hits = sum(w in SPAM_WORDS for w in words)
    return spam_hits / max(1, len(words))

def _first_journal_issn_once(text: str) -> bool:
    """True if pattern 'Journal.*ISSN' appears exactly once."""
    return len(re.findall(r"journal[^.\n]{0,120}?ISSN", text, flags=re.I)) == 1

def _extract_urls(text: str) -> list[str]:
    url_re = re.compile(r"https?://[^\s)>\]]+", re.I)
    return url_re.findall(text)

def _same_domain(u1: str, u2: str) -> bool:
    return urlparse(u1).netloc == urlparse(u2).netloc

def _extract_emails(text: str) -> list[str]:
    email_re = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
    return email_re.findall(text)

def _deadline_within_60(text: str, today: dt.date | None = None) -> bool:
    today = today or dt.date.today()
    m = DATE_RE.search(text)
    if not m:
        return False
    try:
        d = dt.datetime.strptime(m.group(1), "%d %B %Y").date()
    except ValueError:
        return False
    return (d - today).days <= 60

def _block_order_ok(text: str) -> bool:
    """Quick heuristic: check that markers appear in the right order."""
    markers = [
        r"dear\b",                        # Hook starts after greeting
        r"\b\d{1,2}%|\b(?:\d{1,2}\s?%|\d{1,2}\s?percent).*?(?:\d{1,2}\s+[A-Za-z]+\s+\d{4})", # Waiver line
        r"about the journal",
        r"(topics|scope)",
        r"https?://",                     # first CTA URL
        r"happy to assist|feel free to contact",
        r"warm regards|sincerely|kind regards"
    ]
    pos = []
    for pat in markers:
        m = re.search(pat, text, flags=re.I | re.S)
        pos.append(m.start() if m else -1)
    # all markers must be found (-1 absent) and strictly increasing
    return all(p > -1 for p in pos) and all(earlier < later for earlier, later in zip(pos, pos[1:]))

def _bullet_checks(text: str) -> bool:
    """Ensure bullets start with '● ' and no nested bullets."""
    lines = text.splitlines()
    bullet_lines = [ln for ln in lines if ln.strip().startswith("●")]
    if len(bullet_lines) > 6:
        return False
    # nested check: there must be no bullet line that is indented relative to previous bullet
    for i, ln in enumerate(bullet_lines[1:], start=1):
        if ln.startswith("    ") or ln.startswith("\t"):
            return False
    # all bullet prefixes must be '● '
    return all(ln.lstrip().startswith("● ") for ln in bullet_lines)

def _article_type_rule(text: str) -> bool:
    lower = text.lower()
    types_present = sum(kw in lower for kw in ARTICLE_TYPES)
    if types_present >= 3:
        return "all types welcome" in lower
    return True

##############################################################################
#  ✅  Master validator
##############################################################################

def validate(text: str) -> dict[str, bool | str]:
    """
    Return {"RULE_ID": bool, ...}.
    A False value means the draft violates that rule.
    """
    results: dict[str, bool | str] = {}

    # Strip HTML entities for regex clarity (emails often wrapped with &lt;)
    text = html.unescape(text)

    # ── Structure / formatting ──────────────────────────────────────────────
    results["struct_block_order"]  = _block_order_ok(text)
    results["struct_bullets"]      = _bullet_checks(text)
    results["struct_journal_issn"] = _first_journal_issn_once(text)

    urls  = _extract_urls(text)
    emails = _extract_emails(text)
    results["links_cta_count"]     = len(urls) == 3    # 1 CTA + 2 credibility
    results["links_same_domain"]   = (
        len(urls) == 3 and _same_domain(urls[0], urls[1]) and _same_domain(urls[0], urls[2])
    )
    results["emails_single"]       = len(emails) == 1

    # Signature line check: one <p> containing <br>
    sig_ok = bool(re.search(r"<p>.*?<br>.*?</p>", text, flags=re.S | re.I))
    results["signature_block"] = sig_ok

    # ── Guardrails ───────────────────────────────────────────────────────────
    wc = _wordcount(text)
    results["word_count"]          = 330 <= wc <= 450
    results["spam_density"]        = _spam_density(text) <= 0.02

    for tag, pat in FORBIDDEN_PATTERNS.items():
        results[f"forbidden_{tag}"] = not re.search(pat, text, flags=re.I)

    hype_hits = sum(w in HYPE_WORDS for w in WORD_RE.findall(text.lower()))
    results["hype_cap"]            = hype_hits <= 3

    hs_hits  = any(hv in text.lower() for hv in HARD_SELL)
    results["hard_sell_verbs"]     = not hs_hits

    # ── Date maths ───────────────────────────────────────────────────────────
    results["deadline_≤60d"]       = _deadline_within_60(text)

    # ── Article-type rule ────────────────────────────────────────────────────
    results["article_type_clause"] = _article_type_rule(text)

    # ── Overall verdict convenience key ─────────────────────────────────────
    results["__PASS__"] = all(v is True for k, v in results.items() if not k.startswith("__"))

    return results


##############################################################################
#  🏃  CLI usage
##############################################################################

if __name__ == "__main__":
    import sys, json, textwrap
    if len(sys.argv) < 2:
        print("Usage: python qc_script.py <draft_file.txt>")
        sys.exit(1)

    with open(sys.argv[1], encoding="utf-8") as f:
        draft = f.read()

    report = validate(draft)
    # Pretty print failing rules
    fails = [k for k, v in report.items() if v is False]
    print(json.dumps(report, indent=2))
    if fails:
        print("\n❌  FAILED rules:", ", ".join(fails))
        sys.exit(2)
    print("\n✅  Draft passes all deterministic checks.")
