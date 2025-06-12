"""
agents.qc_tone
==============
Mini-agent that rates three ‘soft’ pillars:

P-1  Fast value hook in first 40 words  
P-5  Collegial (no hard-sell) tone  
P-9  Balanced benefit (author vs reader, no indexing / big-waiver hype)

It always returns exactly three lines:

✔ P-1 hook — ok  
❌ P-5 tone — contains “Seize the chance!”  
✔ P-9 benefit — ok
"""

from __future__ import annotations
from typing import List
from crewai import Agent, Task
from utils.llm import openrouter_llm

# ── Agent ---------------------------------------------------------------- #
qc_tone_agent = Agent(
    role="Tone-coach for CFP drafts",
    goal="Label P-1, P-5, P-9 as ✔/❌ with one-line reason—no extra text.",
    backstory="You judge hook clarity, salesy tone, and benefit balance.",
    llm=openrouter_llm,
    verbose=False,
    allow_delegation=False,
    generation_config={"temperature": 0.0, "max_output_tokens": 256},
)

_TONE_PROMPT = """
You are given a CFP email draft.

Rate only these pillars:

P-1 **Fast hook** – first ≤40 words state field + journal + benefit.  
P-5 **Collegial tone** – no hard-sell phrases (“seize”, “grab this chance”).  
P-9 **Balanced benefit** – at least one author-perk (visibility/OA) and
     no indexing / big-waiver hype.

Return exactly three lines:

✔/❌ P-1 hook — <reason>  
✔/❌ P-5 tone — <reason>  
✔/❌ P-9 benefit — <reason>

No extra commentary.

[DRAFT]
===
{draft}
===
""".strip()


def build_tone_task(draft: str) -> Task:
    """Return CrewAI Task asking for the 3-line verdict."""
    return Task(
        description=_TONE_PROMPT.format(draft=draft),
        agent=qc_tone_agent,
        expected_output="Three lines (one per pillar) with ✔/❌ and reason.",
    )
