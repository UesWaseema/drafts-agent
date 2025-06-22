"""
qc_ai.py  –  Heuristic (LLM) checks for CFP e-mails
===================================================

What it checks
--------------
P-1  Hook quality      – First ≤ 40 words contain: *field + journal + benefit*
P-9  Balanced benefit  – Exactly 1 author-centric perk  &  1 concrete metric
P-5  Collegial tone    – No hard-sell language (seize, grab, hurry, …)

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
• Requires litellm and your **CustomLiteLLM** wrapper.
• Set environment variable **OPENROUTER_API_KEY**.
"""

from __future__ import annotations
import os, re, json, logging, concurrent.futures
from typing import Dict, Any, List, Mapping, Tuple, overload

# ── Bring in the LiteLLM wrapper you defined elsewhere ──────────────
from common import CustomLiteLLM   # ← adjust path
from qc_helper import save_qc                 # ← NEW IMPORT
from datetime import datetime

TODAY_STR = datetime.today().strftime("%B %d, %Y")  # e.g., "June 16, 2025"


logger = logging.getLogger(__name__)
 
# ── Configuration ───────────────────────────────────────────────────
from qc_models import MODEL_LIST              # ← NEW IMPORT

TEMPERATURE = 0.0
TIMEOUT     = 30              # seconds

# ── Helper: run one model and parse its JSON ───────────────────────
# ── Helper: run one model and parse its JSON ───────────────────────
def _run_one_model(model_name: str, provider: str, prompt: str) -> dict:
    """
    provider = "openai"      -> call direct (prefix model with 'openai/')
    provider = "openrouter"  -> call via OpenRouter
    """
    if provider == "openai":
        full_name = (
            model_name if model_name.startswith("openai/")
            else f"openai/{model_name}"          # ensures vendor prefix
        )
        llm = CustomLiteLLM(
            model=full_name,                    # e.g. "openai/o3"
            temperature=TEMPERATURE,
            # No base_url override needed; LiteLLM picks it from prefix
        )
    else:                                       # provider == "openrouter"
        llm = CustomLiteLLM(
            model=f"openrouter/{model_name}",
            temperature=TEMPERATURE,
        )

    try:
        res = llm._generate([prompt], stop=None, timeout=TIMEOUT)
        raw = res.generations[0][0].text
        # ───── DEBUG: log first 500 chars of every reply ─────
        print(f"\n=== DEBUG {model_name} raw reply ↓↓↓ ===\n"
              f"{raw[:500]}\n"
              f"=== DEBUG {model_name} raw end ↑↑↑ ===\n")
        
    except Exception as e:
        logger.warning("LLM %s (%s) failed: %s", model_name, provider, e)
        return {}

    try:
        return json.loads(raw.strip())
    except json.JSONDecodeError:
        return _extract_first_json(raw)

TEMPLATE_KEYS = [
    "hook_ok", "balanced_ok", "tone_ok", "headings_ok", "bullets_ok",
    "journal_issn_ok", "cta_ok", "same_domain_ok",
    "single_email_ok", "deadlines_ok", "waiver_rule_ok", "name_usage_ok",
    "word_count_ok", "spam_density_ok", "forbidden_ok", "hype_cap_ok",
    "vocab_ok", "formatting_ok", "domain_ok"
]

def _blank_report() -> Dict[str, bool]:
    return {k: False for k in TEMPLATE_KEYS}

# Hard-sell verbs reused from qc_script for consistency
HARD_SELL = {"seize", "grab", "don't miss out", "act now", "hurry"}

# Author-centric perk keywords
AUTHOR_PERKS = {
    "visibility", "reach", "discoverability", "impact", "citation",
    "readership", "author rights", "copyright retention"
}

# Concrete metric regexes (IF, review days, waiver %)
METRIC_PAT = re.compile(
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

# ── STRONG INVIGILATOR PROMPT ───────────────────────────────────────
PROMPT_TEMPLATE = """
You are a senior professor with rigorous academic-editorial discipline.
Act like a *super-strict, no non-sense invigilator*: audit the draft against EVERY rule below.
Return a single JSON object – **no explanations outside the JSON**.

Today's date is **{today}**.

### RULES TO CHECK  (all must be TRUE)

HOOK & BALANCE  
• hook_ok            – First ≤ 80 words mention the journal name.  
• balanced_ok        – Body contains author-centric perks (visibility, citation, readership…) **and** **exactly one** concrete metric (IF, waiver %, review days).

TONE  
• tone_ok            – No clichés (“I hope this finds you well”), no formulaic praise, no hard-sell verbs (seize/grab/act now/hurry), no ALL-CAPS words (acronyms allowed), no exclamation marks.

STRUCTURE & FORMAT (CONTENT-FOCUSED)  
• headings_ok        – ≥ 3 bold headings or colon headings; none contains a question mark.  
• bullets_ok         – Bullets use “● ” or “* ” or “- ”.  
{issn_note}

URL & EMAIL  
• cta_ok             – Exactly one “/submit-paper” URL **and/or** one “mailto:” CTA.  
• same_domain_ok     – All URLs share the same domain.  
• single_email_ok    – Exactly one visible email address in the body.

CONTENT GUARD-RAILS  
• deadlines_ok       – At least one explicit date (format “August 06, 2025” or “06 August 2025”) and that date is ≤ 60 days from today (**{TODAY_STR}**).
• waiver_rule_ok     – If a waiver exists it is mentioned **once**; if not, no waiver mention.  
• name_usage_ok      – Full journal name appears once in intro **and** once in signature only.  
• word_count_ok      – 300 ≤ core body words ≤ 350 (exclude greeting & signature).  
• spam_density_ok    – Spam-word density ≤ 2 %.  
• forbidden_ok       – No mentions of indexing services, fast-track, double-blind, placeholder text, emojis, hidden links, informal styling.  
• hype_cap_ok        – ≤ 3 hype words (groundbreaking, revolutionary, spectacular, incredible, unbeatable, massive, unrivalled).  
• vocab_ok           – None of the FORBIDDEN VOCABULARY list appears.  
• formatting_ok      – Plain text only; no “<” or “>”; short paragraphs (≤ 4 sentences); no urgency metaphors (“last chance”, “clock is ticking”).  
• domain_ok          – Literal domain string “<DOMAIN_PLACEHOLDER>” does **NOT** appear in body.

### OUTPUT  
Return **one** JSON object with all Boolean flags **plus** a "comments" object:  
* For every flag that is **false**, add a key-value pair explaining (≤ 15 words) why it failed.  
* If the flag is true, omit it from "comments".

Example  
json
{
  "hook_ok": true,
  "balanced_ok": false,
  …
  "domain_ok": true,
  "__PASS__": false,
  "comments": {
    "balanced_ok": "found two perk words, zero concrete metrics",
    "tone_ok": "contains cliché 'hope you are well'"
  }
}

Draft to audit:
----------------
{email}
----------------
JSON:
""".replace("{", "{{").replace("}", "}}").replace("{{email}}", "{email}")

# ── Local pre-checks to reduce LLM calls (optional) ─────────────────
def _precheck_balanced(text: str) -> bool:
    perks   = sum(pk in text.lower() for pk in AUTHOR_PERKS)
    metrics = len(METRIC_PAT.findall(text))
    return perks == 1 and metrics == 1

def _precheck_tone(text: str) -> bool:
    low = text.lower()
    return not any(v in low for v in HARD_SELL) and "!" not in text and text.upper() != text

# ---- robust JSON extraction ----------------------------------------
def _extract_first_json(blob: str) -> dict:
    """
    Grab the first full JSON object in 'blob' and return it.
    Preserves nested keys like the 'comments' object.
    """
    try:
        start = blob.index("{")
        end   = blob.rindex("}") + 1
        return json.loads(blob[start:end])
    except Exception:
        return {}

# ── Public scoring function ─────────────────────────────────────────
@overload
def score(                                     # default call – old behaviour
    text: str,
    domain: str,
    timeout: int = TIMEOUT,
    prompt_override: str | None = None,
    has_issn: bool = True,
    return_prompt: bool = False,
    return_models: bool = False,
) -> Dict[str, bool]: ...

@overload
def score(                                     # when return_prompt=True
    text: str,
    domain: str,
    timeout: int = TIMEOUT,
    prompt_override: str | None = None,
    has_issn: bool = True,
    return_prompt: bool = True,
    return_models: bool = False,
) -> Tuple[Dict[str, bool], str]: ...

@overload
def score(                                     # when return_models=True
    text: str,
    domain: str,
    timeout: int = TIMEOUT,
    prompt_override: str | None = None,
    has_issn: bool = True,
    return_prompt: bool = False,
    return_models: bool = True,
) -> Tuple[Dict[str, bool], str, Dict[str, Dict]]: ...

def score(
    text: str,
    domain: str,
    timeout: int = TIMEOUT,
    prompt_override: str | None = None,
    has_issn: bool = True,
    return_prompt: bool = False,               # ← CLI / optional
    return_models: bool = False,               # ← Streamlit expects this
):
    """
    Heuristic LLM validation using CustomLiteLLM.
    Falls back to deterministic rejects if blatant violations are found.
    """
    fast_fail = {
        "balanced_ok": _precheck_balanced(text),
        "tone_ok": _precheck_tone(text)
    }

    # Set ISSN rule dynamically
    issn_note = (
        "• journal_issn_ok    – Pattern “ISSN:” must appear exactly once."
        if has_issn else
        "• journal_issn_ok    – This journal does not use ISSNs; this rule is not applicable."
    )

    # Build prompt dynamically
    prompt = (prompt_override if prompt_override is not None else PROMPT_TEMPLATE)
    prompt = (prompt
              .replace("{email}", text)
              .replace("{today}", TODAY_STR)
              .replace("{issn_note}", issn_note)
              .replace("<DOMAIN_PLACEHOLDER>", domain))

    # ── Parallel calls to every model ──────────────────────────────
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(MODEL_LIST)) as ex:
        futures = {
            ex.submit(_run_one_model, name, provider, prompt): name
            for name, provider in MODEL_LIST
        }
        model_reports = {name: fut.result() for fut, name in futures.items()}

    votes = list(model_reports.values())

    # ── Majority vote fusion ───────────────────────────────────────
    final = _blank_report()
    needed = (len(MODEL_LIST) + 1) // 2          # ceil(N/2)
    for k in TEMPLATE_KEYS:
        final[k] = sum(v.get(k) for v in votes if k in v) >= needed
    final["__PASS__"] = all(final.values())

    # decide which tuple size the caller wants
    if return_models:
        return final, prompt, model_reports
    if return_prompt:
        return final, prompt
    return final


# ── CLI entrypoint ────────────────────────────────────────────────
if __name__ == "__main__":
    from pathlib import Path
    import json, sys

    if len(sys.argv) < 3:
        print("Usage: python qc_ai.py <draft_file.txt> <run_id>")
        sys.exit(1)

    email_txt = Path(sys.argv[1]).read_text(encoding="utf-8")
    run_id    = int(sys.argv[2])
    result, used_prompt = score(
        email_txt,
        domain="example.com",
        return_prompt=True,         # ← ask for prompt
    )

    # plain JSON output for CI logs
    print(json.dumps(result, ensure_ascii=False, indent=2))

    # persist to DB
    save_qc(run_id, used_prompt, result)

    # exit-code 0 = PASS, 2 = any fail
    sys.exit(0 if result.get("__PASS__") else 2)