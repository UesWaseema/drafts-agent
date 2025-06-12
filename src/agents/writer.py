"""
src/agents/writer.py
--------------------
ALL logic for the first-pass CFP draft lives here:

    from agents.writer import draft_writer_agent, build_writer_task
    task  = build_writer_task(
                journal_meta = selected_journal,   # dict from DB
                ui_inputs    = ui_dict,            # raw Streamlit fields
                waiver_info  = waiver_dict,        # level/last/recommended/…
                records      = recent_records,     # last 10 campaign rows
            )
    crew  = Crew(agents=[draft_writer_agent], tasks=[task],
                 process=Process.sequential, verbose=False)
    result = crew.kickoff()

No other prompt-assembly code is needed in the UI.
"""

from __future__ import annotations
from typing import Dict, Any, List
import json, pandas as pd, textwrap

from crewai import Agent, Task
from utils.llm import openrouter_llm        # ← same wrapper you use elsewhere
from utils.tokens import n_tokens           # tiny helper for token budgeting


# ════════════════════════════════════════════════════════════════════════
# 1) CrewAI Agent  (verbatim wording)
# ════════════════════════════════════════════════════════════════════════
draft_writer_agent = Agent(
    role=(
        "Specialized writing assistant focused exclusively on creating formal, "
        "warm, and highly personalized call-for-papers email drafts for "
        "academic journals."
    ),
    goal=(
        "Produce a call-for-papers draft that is personal, authentic, engaging, "
        "aligned with the recipient’s academic expertise, anchored in the "
        "journal’s mission and submission context, clear, professionally "
        "formatted, emotionally intelligent, and structured as a cohesive, "
        "warm, and effective letter, **and** includes 10 unique and relevant "
        "subject lines."
    ),
    backstory=(
        "You are an expert academic email copy-writer.  You have years of "
        "experience crafting compelling journal invitations that drive "
        "submissions while respecting scholarly tone."
    ),
    allow_delegation=False,
    verbose=False,
    llm=openrouter_llm,
)


# ════════════════════════════════════════════════════════════════════════
# 2) Helper – build waiver / metrics block
# ════════════════════════════════════════════════════════════════════════
def _build_metrics_block(records: List[dict],
                         waiver_level: str,
                         last_waiver: int | None,
                         recommended_pct: int,
                         waiver_msg: str,
                         budget: int = 6_000) -> str:
    keep_cols = ["subject", "email", "sent_date"]
    trimmed   = [{k: r.get(k) for k in keep_cols} for r in records]
    df        = pd.DataFrame(trimmed)

    recent_json = df.to_json(orient="records", indent=2, date_format="iso") \
                   if not df.empty else "[]"
    latest_json = json.dumps(trimmed[0] if trimmed else {}, indent=2, default=str)

    block = textwrap.dedent(f"""
        🧾 **Waiver Analysis**

        Last waiver offered : {last_waiver or 'N/A'} %
        Journal stance      : {waiver_level}
        Suggested now       : {recommended_pct}% ({waiver_msg})

        📈 **JSON export of the same 10 rows**
        ```json
        {recent_json}
        ```

        📌 **Most-recent row only**
        ```json
        {latest_json}
        ```
    """).strip()

    return block if n_tokens(block) < budget else "📈 Metrics omitted to fit context limit."


# ════════════════════════════════════════════════════════════════════════
# 3) Public helper – build the Task
# ════════════════════════════════════════════════════════════════════════
def build_writer_task(*,
                      journal_meta: Dict[str, Any],
                      ui_inputs   : Dict[str, Any],
                      waiver_info : Dict[str, Any],
                      records     : List[dict]) -> Task:
    """
    Parameters
    ----------
    journal_meta : row from `journal_details` table (dict-like)
    ui_inputs    : dict of Streamlit inputs (impact_factor, sender_name, …)
    waiver_info  : dict {level, last, recommended_pct, waiver_msg}
    records      : last 10 campaign rows for this journal
    """

    jm, ui, w = journal_meta, ui_inputs, waiver_info

    # ── key-value section --------------------------------------------------
    instr = f"""
    Journal Name: {jm['journal_title']}
    Short Name : {jm['short_title']}
    ISSN       : {jm['issn']}
    Impact Factor      : {ui['impact_factor']}
    Submission Deadline: {ui['submission_deadline']}
    Fee Waiver         : {'Yes' if ui['waiver_available'] else 'No'}
    Waiver Percentage  : {ui['waiver_percentage'] if ui['waiver_available'] else 'N/A'}
    Waiver Details     : {ui.get('waiver_details','N/A')}
    Domain             : {ui['domain']}
    Special Issue      : {'Yes' if ui['special_issue'] else 'No'}
    Submit Paper URL   : {ui['submit_url']}
    Other URL 1        : {ui['url1']}
    Other URL 2        : {ui['url2']}
    Sender Name        : {ui['sender_name']}
    Sender Email       : {ui['sender_email']}

    Use the following template as a base for the email draft:

    {ui['template']}
    """.rstrip()

    # ── waiver / metrics JSON block ---------------------------------------
    metrics_block = _build_metrics_block(
        records, w["level"], w["last"], w["recommended_pct"], w["waiver_msg"]
    )

    # ── hard rules (verbatim) ---------------------------------------------
    hard_rules = """
    ### Layout requirement – side-headings - HARD RULE.
    Structure the email with clear **side-headings** so the reader can scan quickly.
    Use bold formatting for each heading and keep each section concise.

    ### Additional hard rules
    - Use bold **creative side-headings**.
    - Final draft must exceed **320 words**.
    - Never output the placeholder text "[mention recipient's specific research area if known, otherwise keep general]".
    - Mention the full journal name only once in the intro and once in the signature.
    - If waiver_available is No, do NOT add a sentence about fee waivers.
    """.strip()

    # ── final prompt -------------------------------------------------------
    prompt = f"""
**Absolute Output Restriction:**
YOUR OUTPUT MUST BE:
1. 10 subject lines starting with 'Subject: '
2. The full email draft
NO OTHER TEXT IS PERMITTED

Generate a complete, professional Call-for-Papers email for
{jm['journal_title']} ({jm['short_title']}) focusing on {ui['domain']}.
Highlight the Impact Factor and mention fee-waiver details if any.
Ensure all required URLs and sender details are included.

{instr}

{metrics_block}

### How to use the JSON above
1. Parse the `JSON export of the same 10 rows` section.
2. Notice the subject, email body, and sent_date for each entry.
3. Infer tone, length, structure from those examples.
4. Write a new CFP draft in a **similar style**, but with fresh content.
5. Do **not** copy the old subjects verbatim—create new ones.

{hard_rules}
""".strip()

    # ── CrewAI Task --------------------------------------------------------
    return Task(
        description=prompt,
        agent=draft_writer_agent,
        expected_output=(
            "A well-formatted CFP email draft obeying every rule, starting with "
            "10 'Subject:' lines and containing no extra commentary."
        ),
        output_file="cfp_draft.txt",
        llm_options={"transform": "middle-out"},
    )
