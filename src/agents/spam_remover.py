"""
agents.spam_remover
===================
Crew-style agent + task builder that:
1. Receives a draft and explicit spam-word list (already detected by the
   pure-Python checker).
2. Rewrites the draft, replacing / removing every hit.
3. Outputs ONLY the cleaned draft between bracket markers.

Usage
-----
    from agents.spam_remover import spam_removal_agent, build_remover_task
    task  = build_remover_task(draft_text, spam_hits)
    crew  = Crew(agents=[spam_removal_agent], tasks=[task],
                 process=Process.sequential, verbose=False)
    result = crew.kickoff()

    clean_text = strip_markers(result.raw)   # helper provided below
"""

from __future__ import annotations
import re
from typing import List, Tuple, Dict, Any

from crewai import Agent, Task
from utils.llm import openrouter_llm

# ── 1. Agent definition ───────────────────────────────────────────────── #
spam_removal_agent = Agent(
    role="Spam-word replacement and draft-refinement specialist",
    goal="Eliminate every supplied spam word while preserving ALL formatting.",
    backstory=(
        "You are an expert in text sanitisation and lexical substitution. "
        "You never leak your chain-of-thought."
    ),
    allow_delegation=False,
    verbose=False,
    llm=openrouter_llm,
    max_iter=2,
    generation_config={
        "stop_sequences": ["\nThought:", "\nPlan:", "\nReasoning:"],
        "temperature": 0.0,
        "max_output_tokens": 4096,
    },
)

# ── 2. Task-builder helper ────────────────────────────────────────────── #
def build_remover_task(draft: str, spam_hits: List[str]) -> Task:
    """
    Return a CrewAI Task that instructs the agent to clean the draft.

    Parameters
    ----------
    draft :
        The raw email draft (string).
    spam_hits :
        List of lower-cased spam words already detected.

    Returns
    -------
    Task – ready to pass to Crew().
    """
    hits_csv = ", ".join(sorted(spam_hits)) or "«none»"

    prompt = f"""
**IRONCLAD PROCESSING RULES**
1. ABSOLUTELY NO INTERNAL MONOLOGUE.
2. THINKING MUST BE INTERNALISED.

**YOUR MANDATORY PROTOCOL**
1. Replace each spam word with a context-appropriate synonym.
2. Output ONLY the modified text.

**ABSOLUTE CONSTRAINTS**
- Preserve journal metadata, URLs, headings, signature block EXACTLY.
- Do NOT add commentary or JSON.
- If replacement truly impossible, leave the word unchanged.

[INPUT DRAFT]
{draft}

[SPAM WORDS]
{hits_csv}

[OUTPUT FORMAT]
[BEGIN REFINED DRAFT]
(Your cleaned draft here)
[END REFINED DRAFT]
""".strip()

    return Task(
        description=prompt,
        agent=spam_removal_agent,
        expected_output=(
            "Same draft with all spam words replaced and NOTHING else. "
            "Must be wrapped between the two bracket markers."
        ),
    )

# ── 3. Helper to strip bracket markers after Crew run ────────────────── #
_DRAFT_RE = re.compile(
    r"\[BEGIN(?: REFINED)? DRAFT\](?P<body>.*?)\[END(?: REFINED)? DRAFT\]",
    re.DOTALL | re.IGNORECASE,
)

def strip_markers(text: str) -> str:
    """Return the cleaned draft without the wrapper lines."""
    m = _DRAFT_RE.search(text)
    return m.group("body").strip() if m else text.strip()
