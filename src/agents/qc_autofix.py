from crewai import Agent, Task
from utils.llm import openrouter_llm

qc_autofix_agent = Agent(
    role="CFP Draft Autofixer",
    goal="Patch only what QC marked ❌ while preserving tone, data, and footer.",
    backstory=(
        "You correct compliance issues in CFP drafts without rewriting from scratch. "
        "The footer block must stay exactly as provided."
    ),
    llm=openrouter_llm,
    verbose=False,   # suppress chain-of-thought
)

# --------------------------------------------------------------------
# Footer template you do NOT want the model to touch
FOOTER_BLOCK = """
Warm Regards,
<sender_name>
Editorial Office
<journal_name>
616 Corporate Way, Suite 2-6158
Valley Cottage, NY 10989
United States
Email: <sender_email>
""".strip()

# --------------------------------------------------------------------
TASK_TMPL = f"""
### Original prompt
{{draft_prompt}}

### Draft to fix
{{original_draft}}

### QC checklist
{{quality_checklist}}

### Hard Fix-Rules
* Change **only** what turns every ❌ into ✔.
* Keep headings—add **creative side-headings** if missing.
* **Do NOT touch the footer block below (must remain verbatim):**

{FOOTER_BLOCK}

* Final body word-count must be **> 320**.
* Replace “open access/open-access” → **“openaccess”**.
* Remove indexing, fast-track, double-blind, waiver disclaimer, placeholder text.
* Full journal name appears exactly twice (intro + footer).
* If any ❌ remain that you truly cannot fix, append a short section titled  
  “🛠 Remaining Issues” listing them.

Return **only** the corrected draft (plus the issues list if needed).
"""

def _split_footer(draft: str):
    lines = draft.rstrip().splitlines()
    for i, ln in enumerate(lines):
        if ln.strip().lower().startswith("warm regards"):
            return "\n".join(lines[:i]), "\n".join(lines[i:])
    return draft, ""   # fallback: no footer found

# Factory function ───────────────────────────────────────────────────
def build_autofix_task(draft_prompt: str,
                       original_draft: str,
                       quality_checklist: str) -> tuple[Task, str]:
    """Create a task instance with runtime data injected."""
    body, footer = _split_footer(original_draft)
    task = Task(
        description=TASK_TMPL.format(
            draft_prompt=draft_prompt,
            original_draft=body,          # send body only
            quality_checklist=quality_checklist,
        ),
        agent=qc_autofix_agent,
        expected_output="Corrected body text (plus optional 🛠 Remaining Issues).",
    )
    return task, footer  # return footer so caller can re-attach
