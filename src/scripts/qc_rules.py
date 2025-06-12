"""
scripts.qc_rules
================
Deterministic checker that enforces:

• 9 Compliance rules (C-1 … C-9)  
• 6 Pillar rules (P-2, P-3, P-4, P-6, P-7, P-10)

The three “tone / semantic” pillars (P-1, P-5, P-9) are *flagged* for a
follow-up AI pass.  `run_qc()` therefore returns:

    {
        "passed": bool,               # True if every scriptable rule ✔
        "checklist": list[str],       # human-readable ✔ / ❌ lines
        "need_ai": ["P-1", "P-5", …]  # pillars that require AI review
    }
"""

from __future__ import annotations
import re, datetime
from typing import List, Dict
from urllib.parse import urlparse

from utils.spam_words import SPAM_WORDS        # master list

# ---------------------------- helpers --------------------------------- #
_DATE_RE = re.compile(
    r"\b(\d{1,2}\s+[A-Z][a-z]+\s+20\d{2}|[A-Z][a-z]+\s+\d{1,2}\s+20\d{2})\b"
)

ART_TYPES = {"review", "case study", "case report", "original article",
             "short communication", "editorial"}

HYPE_WORDS = {
    "groundbreaking", "revolutionary", "spectacular", "incredible",
    "unbeatable", "seize", "amazing", "once-in-a-lifetime",
    "bargain", "massive discount", "unrivalled",
}

FEE_PHRASES = [
    "full waiver", "complete waiver", "no apc", "zero apc",
    "free of charge", "waived fee", "entire waiver",
]

FAST_PHRASES = [
    "fast-track", "rapid review", "quick review", "expedited review",
    "quick turnaround", "rapid turnaround",
]

INDEX_PHRASES = [
    "indexed", "indexing", "scopus", "web of science", "wos",
    "abstracting and indexing",
]

OPEN_ACCESS_NEG = re.compile(r"\bopen[- ]access\b", re.I)

EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
URL_RE   = re.compile(r"https?://\S+", re.I)

ALLOWED_SPAM_EXCEPTIONS = {"deadline", "submission"}   # ≈ “harmless” tokens


def _words(text: str) -> List[str]:
    return re.findall(r"[A-Za-z']+", text)


# -------------------------- check engine ------------------------------ #
def run_qc(text: str, *, submit_url: str) -> Dict[str, object]:
    body_words = _words(text)
    word_count = len(body_words)

    checklist: List[str] = []
    fails = 0
    need_ai = []                         # P-1, P-5, P-9

    def check(tag: str, ok: bool, reason: str = ""):
        nonlocal fails
        mark = "✔" if ok else "❌"
        checklist.append(f"{mark} {tag}{'' if ok else ' — ' + reason}")
        if not ok:
            fails += 1

    # ---------- C-1  word-count --------------------------------------- #
    check("C-1 word-count", word_count > 320,
          f"{word_count} words")

    # ---------- C-2  spam density < 2 % ------------------------------- #
    spam_hits = [w for w in body_words
                 if w.lower() in SPAM_WORDS
                 and w.lower() not in ALLOWED_SPAM_EXCEPTIONS]
    ok = len(spam_hits) <= 0.02 * word_count
    check("C-2 spam density", ok,
          f"{len(spam_hits)} hits / {word_count} words")

    # ---------- C-3 waiver promises ----------------------------------- #
    waiver_hit = any(p in text.lower() for p in FEE_PHRASES)
    check("C-3 waiver promise", not waiver_hit, "fee waiver phrase found")

    # ---------- C-4 indexing claims ----------------------------------- #
    idx_hit = any(p in text.lower() for p in INDEX_PHRASES)
    check("C-4 indexing claim", not idx_hit, "indexing phrase found")

    # ---------- C-5 fast review promises ------------------------------ #
    fast_hit = any(p in text.lower() for p in FAST_PHRASES)
    check("C-5 fast review", not fast_hit, "fast-review phrase found")

    # ---------- C-6 double-blind mention ------------------------------ #
    db_hit = "double-blind" in text.lower()
    check("C-6 double-blind", not db_hit, "double-blind mentioned")

    # ---------- C-7 article types → must say 'all types welcome' ------ #
    types_listed = any(t in text.lower() for t in ART_TYPES)
    all_types = "all types welcome" in text.lower()
    ok = (not types_listed) or all_types
    reason = "types listed without “all types welcome”" if not ok else ""
    check("C-7 article-types phrase", ok, reason)

    # ---------- C-8 concrete deadline line ---------------------------- #
    date_match = _DATE_RE.search(text)
    deadline_ok = False
    delta_msg = "no full date"
    if date_match:
        try:
            dt = datetime.datetime.strptime(
                date_match.group(0), "%d %B %Y"
            )
        except ValueError:
            dt = datetime.datetime.strptime(
                date_match.group(0), "%B %d %Y"
            )
        days = (dt.date() - datetime.date.today()).days
        deadline_ok = 0 < days <= 60
        delta_msg = f"{days} d ahead"
    kw_hit = re.search(r"(deadline|last date)", date_match.string, re.I) if date_match else None
    ok = deadline_ok and kw_hit
    check("C-8 full deadline", ok, delta_msg)

    # ---------- C-9 open-access spelling ------------------------------ #
    check("C-9 openaccess spelling",
          not OPEN_ACCESS_NEG.search(text), "open access/open-access found")

    # ----------------- P-2 evidence over adjectives ------------------- #
    hype_hits = [w for w in HYPE_WORDS if w in text.lower()]
    metrics   = re.findall(r"\b\d+(\.\d+)?\b", text)
    ok = (len(metrics) >= 1) and (len(hype_hits) <= 3)
    check("P-2 evidence over adjectives", ok,
          f"hype={len(hype_hits)} metrics={len(metrics)}")

    # ----------------- P-3 topic-centric list ------------------------- #
    # (script-only part: ensure 'all types welcome' when article types present)
    check("P-3 topic-centric", ok := (not types_listed or all_types),
          "needs phrase 'all types welcome'" if not ok else "")

    # ----------------- P-4 single CTA (+ 1 email) --------------------- #
    urls = list({u.rstrip('.,)') for u in URL_RE.findall(text)})
    emails = EMAIL_RE.findall(text)
    ok = (len(urls) == 1) and (len(emails) == 1)
    check("P-4 single CTA + email", ok,
          f"urls={len(urls)} emails={len(emails)}")

    # ----------------- P-6 near-term deadline already in C-8 ---------- #
    # Here we just re-use the date check result.
    check("P-6 deadline ≤ 60 d", deadline_ok, delta_msg)

    # ----------------- P-7 exactly two credibility links -------------- #
    root = urlparse(submit_url).netloc
    cred_links = [u for u in urls if urlparse(u).netloc == root and
                  re.search(r"/(about|editorial-board|current-issue)", u)]
    ok = len(cred_links) == 2
    check("P-7 credibility links", ok,
          f"found={len(cred_links)}")

    # ----------------- P-10 soft rapport close ------------------------ #
    close_hit = re.search(
        r"(happy (?:to|for).*assist|available for any questions)",
        text.lower()
    )
    # ensure hit appears before signature
    sig_idx = text.lower().find("warm regards")
    ok = bool(close_hit) and (close_hit.start() < sig_idx if sig_idx != -1 else True)
    check("P-10 soft rapport close", ok, "closing line missing")

    # ----------------- AI-needed pillars ------------------------------ #
    need_ai.extend([p for p in ("P-1", "P-5", "P-9")
                    if p not in (line.split()[1] for line in checklist)])

    return {
        "passed": fails == 0,
        "checklist": checklist,
        "need_ai": need_ai,
    }
