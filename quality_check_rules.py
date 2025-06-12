import re
from typing import Dict, List

# Optional: try importing your global spam list if defined elsewhere
try:
    from common import SPAM_WORDS as BASE_SPAM
except ImportError:
    BASE_SPAM: List[str] = []

# Additional spam/buzz terms and unsafe phrasing
EXTRA_SPAM_WORDS: List[str] = [
    "challenge", "unravel", "discovery", "empower", "paving", "boundaries",
    "cornerstone", "intricacies", "landscape", "pioneering",
    "transformative", "transform", "transformation", "breakthroughs",
    "discoveries", "pivotal", "masterpiece", "empowering", "groundbreaking",
    "landmark", "extraordinary", "intricate", "transforming", "unveil",
    "unveiling", "unveils", "push", "building", "unlocking", "shaping",
    "join us", "join", "beacon", "opportunity", "innovation", "innovators",
    "collaboration", "leader", "chapter", "exciting", "imagine", "narrative",
    "leading", "narration", "narrating", "pushing", "pushes", "narrates",
    "innovating", "joining", "collaborating", "excite", "shape", "shapes",
    "unlock", "unlocked", "unlocks", "build", "builds", "milestone",
    "milestones", "excites", "boundary", "challenges", "cornerstones",
    "discovered", "empowers", "intricate", "landscapes", "pave", "pioneer",
    "unravels", "challenged", "unraveling", "discovering", "empowered",
    "paves", "challenging", "unraveled",
]

REPLACEMENTS: Dict[str, str] = {
    r"\bplatforms?\b": "forum",
    r"\bvenues?\b": "forum",
    r"\bopportunity\b": "window",
    r"\bchance\b": "prospect",
    r"\bplease\b": "",
    r"feel\s+free\s+to": "",
    r"\bvisit\b": "", r"\bexplore\b": "", r"\bdiscover\b": "",
    r"\blimited\b": "confined",
    r"\bdiscount\b": "waiver", r"\breduction\b": "waiver",
    r"\bfinancial\b": "",
    r"\bfield\b": "area", r"\barena\b": "area",
    r"\benable\b": "",
}

ALL_SPAM_WORDS = (
    {w.lower() for w in BASE_SPAM}
    | {w.lower() for w in EXTRA_SPAM_WORDS}
    | {re.sub(r"\b", "", k).lower() for k in REPLACEMENTS}
)

# Footer lines expected at the end of every draft
FOOTER_LINES = [
    "warm regards",
    "editorial office",
    "616 corporate way",
    "suite 2-6158",
    "valley cottage",
    "ny 10989",
    "united states",
    "email:",
]

# Rule labels
CHECKS = {
    "word_count": "Word count > 320",
    "spam_clean": "No spam/buzz words present",
    "no_full_waiver": "Draft does not promise a full waiver",
    "no_indexing": "No indexing-related terms used",
    "review_policy": "Mentions rigorous peer‑review only",
    "blind_policy": "Mentions single‑blind review only",
    "article_type": "Article types unrestricted or all types welcome",
    "full_date": "Deadline includes full date (e.g. 31 July 2025)",
    "openaccess_format": "Only 'openaccess' or 'oa' are allowed; no 'open access' or 'open-access'",
    "no_placeholder": "No “[mention recipient…” placeholder",
    "journal_twice": "Full journal name appears only twice",
    "no_waiver_disclaimer": "No waiver disclaimer when waiver unavailable",
}

# Helper to extract just the draft body
def _extract_body(draft: str) -> str:
    lines = draft.splitlines()
    start = next((i for i, ln in enumerate(lines) if ln.strip().lower().startswith("dear")), 0)
    end = next((i for i in range(len(lines) - 1, -1, -1) if "@" in lines[i]), len(lines) - 1)
    return " ".join(lines[start : end + 1]).strip()

# Main quality check function
def run_quality_check(draft: str, sidebar_info: Dict[str, str]) -> Dict[str, object]:
    report = {"passed": True, "checklist": []}
    body = _extract_body(draft)
    lower = body.lower()

    def mark(cond: bool, key: str, note: str = ""):
        if cond:
            report["checklist"].append(f"✔ {CHECKS[key]}")
        else:
            report["checklist"].append(f"❌ {CHECKS[key]}{f' — {note}' if note else ''}")
            report["passed"] = False

    # 1. word-count ≥ 320
    mark(len(re.findall(r"\b\w+\b", body)) > 320, "word_count")

    # 2. Spam / buzzword residue
    leftover = sorted(w for w in ALL_SPAM_WORDS if re.search(rf"\b{re.escape(w)}\b", lower))
    mark(not leftover, "spam_clean", f"Leftover: {', '.join(leftover)}" if leftover else "")

    # 3. Must NOT mention “full waiver”
    mark("full waiver" not in lower, "no_full_waiver")

    # 4. Must NOT mention indexing (in any form)
    mark("index" not in lower, "no_indexing")

    # 5. Must NOT mention fast-track peer review (use “rigorous”)
    mark("fast-track" not in lower and "fast track" not in lower, "review_policy")

    # 6. Must NOT mention double-blind review (only single-blind is valid)
    mark("double-blind" not in lower, "blind_policy")

    # 7. If article types (review, case study, etc.) are listed the draft must also say “all types welcome”
    article_types = ["original research", "review", "case study", "editorial", "commentary"]
    found_types = [t for t in article_types if re.search(rf"\b{re.escape(t)}\b", lower)]
    mark(
        (not found_types)                         # no mention → pass
        or (len(found_types) == len(article_types))  # all mentioned → pass
        or ("all types" in lower),                  # or explicitly says so
        "article_type",
    )

    # 8. Deadline must contain a full date in either “31 July 2025” or “July 31 2025” style
    date_regex = r"\b(\d{1,2}\s+(january|february|march|april|may|june|july|august|september|october|november|december)|" \
                 r"(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2})\s+\d{4}\b"
    mark(re.search(date_regex, lower), "full_date")

    # 9. The phrase “open access”/“open-access” is forbidden—only “openaccess” or “oa”
    mark(not re.search(r"\bopen\s+access\b|\bopen-access\b", lower), "openaccess_format")

    # 10. Placeholder check
    mark("[mention recipient" not in lower, "no_placeholder")

    # 11. Journal name frequency
    jn = sidebar_info.get("journal_title", "").lower()
    if jn:
        mark(lower.count(jn) <= 2, "journal_twice")

    # 12. Waiver disclaimer when waiver not offered
    if sidebar_info.get("waiver_stance", "").lower().startswith("❌") \
       or sidebar_info.get("waiver_stance") == "❌ Minimal":
        mark("does not offer fee waiver" not in lower, "no_waiver_disclaimer")
    else:
        mark(True, "no_waiver_disclaimer")   # always pass when waiver available

    return report

    return report
