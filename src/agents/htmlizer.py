"""
src/agents/htmlizer.py
────────────────────────────────────────────────────────
Gemini-powered HTML formatter for CFP drafts.

✔ Converts a plain-text email body→production-ready HTML
✔ Keeps every word; only adds semantic tags / links
✔ Obeys “Template-One headings” & signature rules
"""

from __future__ import annotations

import re
from crewai import Agent, Task
from utils.llm import openrouter_llm   # ← our OpenRouter Gemini wrapper

# ---------------------------------------------------------------------
# 1)  System prompt (back-story) – contains ALL hard rules
# ---------------------------------------------------------------------
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
   • Wrap that line **and every following line** in ONE <p> element and place
     <br> tags between the lines, e.g.:

     <p>Warm Regards,<br>
        Jane Doe<br>
        Editorial Office<br>
        Journal of XYZ (ISSN 1234-5678)<br>
        616 Corporate Way, Suite 2-6158<br>
        Valley Cottage, NY 10989<br>
        United States<br>
        Email: <a href="mailto:jane@xyz.org">jane@xyz.org</a></p>

   • Do not alter the text—just wrap and preserve it.
7. Output **pure HTML only** — no <html>, <head>, <body> wrappers, no markdown
   fences, no commentary.
""".strip()

# ---------------------------------------------------------------------
# 2)  Agent
# ---------------------------------------------------------------------
htmlizer_agent: Agent = Agent(
    role="HTML Formatter",
    goal="Return pure, production-ready HTML e-mail bodies.",
    backstory=HTML_SYSTEM_PROMPT,
    llm=openrouter_llm,       # Gemini 2.5-flash routed via OpenRouter
    verbose=False,
    allow_delegation=False,
)

# ---------------------------------------------------------------------
# 3)  Task builder – injects the draft text at runtime
# ---------------------------------------------------------------------
_HTML_TASK_TMPL = """
Convert the following plain-text draft into HTML obeying all rules in the
system prompt above.

----
{draft_to_convert}
----
""".strip()


def build_html_task(draft_to_convert: str) -> Task:
    """Return a CrewAI Task that will emit the HTML string."""
    return Task(
        description=_HTML_TASK_TMPL.format(draft_to_convert=draft_to_convert),
        agent=htmlizer_agent,
        expected_output="Pure HTML string – no prose, no code-block fences.",
        llm_options={"temperature": 0.3},
    )


# ---------------------------------------------------------------------
# 4)  Post-processing helper – strips any leading Gemini chatter
# ---------------------------------------------------------------------
def strip_html_noise(raw_html: str) -> str:
    """
    Keep everything from the first real <p> onward.

    Gemini sometimes prepends explanation bullets like
    “<p>`<ul>` is used…”.  We drop anything before the first <p>
    whose NEXT non-space char is **not** a back-tick (`).
    """
    match = re.search(r"<p\b[^>]*>(?!`)", raw_html)
    if match:
        return raw_html[match.start():].strip()

    # Fallback: return from first '<' or the whole string
    first_tag = raw_html.find("<")
    return raw_html[first_tag:].strip() if first_tag != -1 else raw_html.strip()
