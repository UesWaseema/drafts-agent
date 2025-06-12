"""
qc_ai.py  –  Heuristic (LLM) checks for CFP e-mails
===================================================

What it checks
--------------
P-1  Hook quality     – First ≤ 40 words contain:   *field + journal + benefit*
P-9  Balanced benefit – Exactly 1 author-centric perk  &  1 concrete metric
P-5  Collegial tone   – No hard-sell language (seize, grab, hurry, …)

Return
------
score(text) → dict{
    hook_ok:       bool,
    balanced_ok:   bool,
    tone_ok:       bool,
    __PASS__:      bool          # convenience flag (all True)
}

Setup
-----
• Requires python-openai ≥ 1.0 (`pip install openai`)
• Set environment variable **OPENAI_API_KEY**

"""

from __future__ import annotations
import os, re, json
from typing import Dict

import openai

# ── Configuration ───────────────────────────────────────────────────────────
MODEL   = os.getenv("QC_AI_MODEL", "o3")       # default to OpenAI o3
TIMEOUT = 30                                   # seconds

# Hard-sell verbs reused from qc_script for consistency
HARD_SELL = {"seize", "grab", "don't miss out", "act now", "hurry"}

# Author-centric perk keywords
AUTHOR_PERKS = {
    "visibility", "reach", "discoverability", "impact", "citation",
    "readership", "author rights", "copyright retention"
}

# Concrete metric regexes (IF, review days, waiver %)
METRIC_PAT  = re.compile(
    r"""
    (?:
        impact\s+factor\s*\d+(?:\.\d+)?   |   # IF 6.044
        \b\d+\s*%\b                       |   # waiver %
        \b\d+\s*(?:days|hours)\b          |   # review days
        \b\d+\s*(?:day|hour)\s*review\b   |
        \bmedian\s+time\s+to\s+decision   |
        \b(?:h\s*-?index|snip)\s*\d+(?:\.\d+)?
    )
    """,
    re.X | re.I,
)

# ── LLM prompt template ─────────────────────────────────────────────────────
PROMPT_TEMPLATE = """
You are an academic email auditor. For the draft below:
1. Does the first **≤40 words** clearly state the research field, the journal name, AND one tangible benefit (e.g., waiver %, visibility)?  Answer "hook_ok: yes/no".
2. Does the entire body mention **exactly one** author-centric perk AND **exactly one** concrete metric (IF, waiver %, review days)?  Answer "balanced_ok: yes/no".
3. Is the overall tone collegial (avoid commands like "seize", "grab", "act now"; no ALL-CAPS, no exclamation marks)?  Answer "tone_ok: yes/no".
Return a valid JSON object with those three boolean keys.

DRAFT:
------
{email}
------
JSON:
"""

##############################################################################
#  🔍  Local pre-checks to reduce LLM calls (optional but cheap)
##############################################################################

def _precheck_balanced(text: str) -> bool:
    """Early exit if >1 metrics or >1 perks => definitely fail."""
    perks   = sum(pk in text.lower() for pk in AUTHOR_PERKS)
    metrics = len(METRIC_PAT.findall(text))
    return perks == 1 and metrics == 1

def _precheck_tone(text: str) -> bool:
    low = text.lower()
    return not any(v in low for v in HARD_SELL) and "!" not in text and text.upper() != text

##############################################################################
#  🎯  Public scoring function
##############################################################################

def score(text: str,
          model: str = MODEL,
          timeout: int = TIMEOUT) -> Dict[str, bool]:
    """
    Heuristic LLM validation.  Falls back to deterministic rejects
    if blatant violations are found locally to save tokens.
    """
    # Cheap heuristic knockout
    fast_fail = {}
    fast_fail["balanced_ok"] = _precheck_balanced(text)
    fast_fail["tone_ok"]     = _precheck_tone(text)

    if not all(fast_fail.values()):
        fast_fail["hook_ok"] = False     # unknown without LLM, mark fail
        fast_fail["__PASS__"] = False
        return fast_fail

    # ------------------- LLM call (only if cheap tests pass) --------------
    client = openai.OpenAI()
    chat = client.chat.completions.create(
        model=model,
        messages=[{"role": "user",
                   "content": PROMPT_TEMPLATE.format(email=text)}],
        timeout=timeout
    )

    try:
        data = json.loads(chat.choices[0].message.content.strip())
    except json.JSONDecodeError:
        # Fallback: treat as fail safe
        return {"hook_ok": False,
                "balanced_ok": False,
                "tone_ok": False,
                "__PASS__": False}

    # Ensure booleans
    final = {
        "hook_ok":     bool(data.get("hook_ok", False)),
        "balanced_ok": bool(data.get("balanced_ok", False)),
        "tone_ok":     bool(data.get("tone_ok", False))
    }
    final["__PASS__"] = all(final.values())
    return final

##############################################################################
#  🏃  CLI helper  – run: python qc_ai.py draft.txt
##############################################################################

if __name__ == "__main__":
    import sys, textwrap, pprint
    if len(sys.argv) < 2:
        print("Usage: python qc_ai.py <draft_file.txt>")
        sys.exit(1)

    with open(sys.argv[1], encoding="utf-8") as f:
        email_txt = f.read()

    result = score(email_txt)
    pprint.pp(result)
    if result["__PASS__"]:
        print("\n✅  Draft passes AI heuristics.")
    else:
        fails = [k for k, v in result.items() if k != "__PASS__" and not v]
        print("\n❌  AI checks failed:", ", ".join(fails))
        sys.exit(2)
