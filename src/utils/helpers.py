"""
utils/helpers.py
────────────────────────────────────────────────────────
Shared helpers for Streamlit UI, agents and QC scripts.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, List, Optional, Tuple

# ════════════════════════════════════════════════════════════════════════
# 0) Date-handling utilities
# ════════════════════════════════════════════════════════════════════════
# Accept “31 July 2025”  or  “July 31 2025/July 31, 2025”
_FULL_DATE_RX = re.compile(
    r"""
    ^\s*
    (?:
        (?P<d1>\d{1,2})\s+                       # 31 July 2025
        (?P<m1>Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|
                Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|
                Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+
        (?P<y1>\d{4})
      |
        (?P<m2>Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|
                Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|
                Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+
        (?P<d2>\d{1,2})\s*,?\s+                 # July 31 2025 / July 31, 2025
        (?P<y2>\d{4})
    )
    \s*$
    """,
    re.IGNORECASE | re.VERBOSE,
)


def parse_full_date(text: str) -> Optional[datetime]:
    """
    Validate and parse a “full date” string into `datetime`, or return **None**.

    Examples accepted:
        • 31 July 2025
        • July 31 2025
        • July 31, 2025
        • 7 Aug 2026
    """
    if not text:
        return None

    m = _FULL_DATE_RX.match(text)
    if not m:
        return None

    if m.group("d1"):  # style-1
        day, mon, yr = m.group("d1"), m.group("m1"), m.group("y1")
    else:  # style-2
        day, mon, yr = m.group("d2"), m.group("m2"), m.group("y2")

    # Try long then short month names
    for fmt in ("%d %B %Y", "%d %b %Y"):
        try:
            return datetime.strptime(f"{day} {mon} {yr}", fmt)
        except ValueError:
            continue
    return None


def today_str() -> str:
    """UTC ‘today’ in YYYY-MM-DD."""
    return datetime.utcnow().strftime("%Y-%m-%d")


# ════════════════════════════════════════════════════════════════════════
# 1) Generic text helpers
# ════════════════════════════════════════════════════════════════════════
def word_count(text: str) -> int:
    """Return number of word-tokens in *text*."""
    return len(re.findall(r"\b\w+\b", text))


def slugify(text: str, max_len: int = 60) -> str:
    """Lower-case slug suitable for filenames / IDs."""
    slug = re.sub(r"[^\w\s-]", "", text.lower())
    slug = re.sub(r"[\s_-]+", "-", slug).strip("-")
    return slug[:max_len]


# ════════════════════════════════════════════════════════════════════════
# 2) Draft-specific helpers (ported from common.py)
# ════════════════════════════════════════════════════════════════════════
def calculate_core_word_count(draft_text: str) -> int:
    """Word-count between salutation and signature."""
    lines = draft_text.strip().splitlines()

    # salutation end
    start, seen_sal = 0, False
    for i, ln in enumerate(lines):
        if ln.startswith("Subject: "):
            continue
        if not seen_sal and ln.strip():
            seen_sal, start = True, i + 1
            break

    # signature start
    end = next((i for i, ln in enumerate(lines) if "Warm Regards," in ln), len(lines))
    content = " ".join(l for l in lines[start:end] if l.strip())
    return len(content.split())


def extract_core_content(draft_text: str) -> str:
    """Body without subjects / salutation / signature."""
    lines = draft_text.strip().splitlines()
    start, seen_sal = 0, False
    for i, ln in enumerate(lines):
        if ln.startswith("Subject: "):
            continue
        if not seen_sal and ln.strip():
            seen_sal, start = True, i + 1
            break
    end = next((i for i, ln in enumerate(lines) if "Warm Regards," in ln), len(lines))
    return "\n".join(lines[start:end]).strip()


# ════════════════════════════════════════════════════════════════════════
# 3) Crew-output JSON parser  (unchanged)
# ════════════════════════════════════════════════════════════════════════
def parse_crew(raw_out: Any) -> dict:
    """Return first valid JSON obj from CrewAI output (never raises)."""
    raw = raw_out.strip() if isinstance(raw_out, str) else str(getattr(raw_out, "raw", "")).strip()
    raw = re.sub(r"```(?:json)?|```", "", raw, flags=re.I).strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    brace = raw.find("{")
    if brace == -1:
        return {"error": "No JSON found", "raw_output": raw}

    depth = 0
    for i, ch in enumerate(raw[brace:], brace):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(raw[brace : i + 1])
                except json.JSONDecodeError:
                    break
    return {"error": "Invalid JSON", "raw_output": raw}


def filter_agent_output(output_text: str, *, include_subjects: bool = False) -> Tuple[List[str], str]:
    """Remove chain-of-thought noise, optionally return subject lines."""
    lines = output_text.strip().splitlines()
    subjects, body = [], []

    SPAM_PREFIXES = (
        "Thought:", "I will", "Here's my plan:", "Let's ",
        "Analyze the spam word list", "Go through the draft",
        "For each instance of a spam word", "Choose a synonym",
        "Replace the spam word", "Ensure formatting", "Do a final review",
        "Example replacements", "Brainstorm inventive layout elements",
        "Improve introduction", "Reframe sections", "Highlight key data",
        "Refine language", "Structure the prompt", "Introduction:",
        "Introduction of", "Mission & Scope:", "Why Publish:",
        "Submission Process:", "Prompt to undertaking:", "Closing:",
        "Signature:", "Drafting approach:",
    )

    for ln in lines:
        if include_subjects and ln.startswith("Subject: "):
            subjects.append(ln.replace("Subject: ", "").strip())
            continue
        if not ln.startswith(SPAM_PREFIXES):
            body.append(ln)

    return subjects, "\n".join(body).strip()

# ------------------------------------------------------------------
# CrewAI output helper
# ------------------------------------------------------------------
def as_text(result) -> str:
    """
    Crew.kickoff() sometimes returns a plain str, sometimes an object
    exposing `.raw`.  This helper always gives you the final text.
    """
    return result if isinstance(result, str) else getattr(result, "raw", str(result))

