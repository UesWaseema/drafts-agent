"""
Gemini-powered HTML formatter for CFP drafts.
Put this file next to your other `agent_*.py` helpers.
"""

import re
from crewai import Agent, Task
from common import openrouter_llm          # ← your CustomLiteLLM (Gemini 2.5 flash)

# ── 1. System / back-story prompt ───────────────────────────────────
HTML_SYSTEM_PROMPT = """
You are an expert HTML formatter.

HARD RULES
1. Never add or rewrite content—re-format exactly what the user gives you.
2. If the draft already has headings, keep them. Otherwise apply the
   Template-One headings (Introduction, Scope, Types of Articles, Metrics,
   Bibliography, Closing Note, signature block).
3. Use only these tags: <p>, <ul>, <li>, <strong>, <em>, <u>, <a>.
4. Convert every full URL (http / https) and every e-mail address into a
   clickable link; do NOT shorten or rename.
5. Bold the journal name + ISSN the first time they appear. Bold the words
   “Fee Waiver” and the waiver date if present.
6. Signature / Closing block:  
   • Detect the final greeting line (e.g. “Warm Regards,” “Kind regards,”  
     “Sincerely,” etc.).  
   • Wrap that line and every following line in **one <p>** element and
     separate each printed line with <br> tags, e.g.:

     <p>Warm Regards,<br>
        {{sender_name}}<br>
        Editorial Office<br>
        {{journal_name}}<br>
        616 Corporate Way, Suite 2-6158<br>
        Valley Cottage, NY 10989<br>
        United States<br>
        Email: <a href="mailto:sender@journal.org">sender@journal.org</a></p>

   • Do not alter the text—just wrap and preserve it.
7. Output **pure HTML, nothing else** – no <html>, <head>, <body>, no “Sure,
   here is the HTML:” prose, no markdown fences.
"""

# ── 2. Agent definition ─────────────────────────────────────────────
gemini_html_agent = Agent(
    role="HTML Formatter",
    goal="Return pure, production-ready HTML e-mail bodies.",
    backstory=HTML_SYSTEM_PROMPT,
    llm=openrouter_llm,              # Gemini 2.5 flash via OpenRouter
    verbose=False,
    allow_delegation=False,
)

# ── 3. Task template (we fill the {draft_to_convert} placeholder later) ──
html_task_template = Task(
    description=(
        "Convert the following plain-text draft into HTML obeying all rules in "
        "the system prompt above.\n\n"
        "----\n"
        "{draft_to_convert}\n"
        "----"
    ),
    agent=gemini_html_agent,
    expected_output="Pure HTML string – no prose, no code block fences."
)

# ── 4. Minimal sanitizer: keep everything from the first '<' onward ─────
def html_output_sanitizer(raw_html: str) -> str:
    """
    Keep everything from the *first* real <p> tag onward.

    • Gemini sometimes prepends bullet points like "<p>`, `<ul>`…" or prose that
      includes tags inside back-ticks.  Those lines are NOT part of the final
      HTML body.

    • Strategy:
        1. Scan for the first <p> tag *whose next non-space character is NOT a
           back-tick (`).  That reliably skips the bullet-list lines.
        2. Return the remainder of the string trimmed.
    """
    m = re.search(r"<p\b[^>]*>(?!`)", raw_html)   # <p> … but not <p>``
    if m:
        return raw_html[m.start():].strip()
    # Fallback – no <p> found, do the old behaviour
    first = raw_html.find("<")
    return raw_html[first:].strip() if first != -1 else raw_html.strip()
