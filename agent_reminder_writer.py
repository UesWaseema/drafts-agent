# agent_reminder_writer.py
# ─────────────────────────────────────────────────────────────────────
from crewai import Agent, Task
from common import get_llm_for_stance               # your router
# Any DB helper that returns a list[dict] identical to CFP path
from interspire_helpers     import get_recent_campaign_raw          # already in your code

# ── Model-specific SYSTEM blocks (same as CFP writer) ───────────────
from agent_draft_writer import SYSTEM_BLOCKS, _clean_stance, BASE_RULES


# ────────────────────────────────────────────────────────────────────
#  EXTRA RULES specific to reminder e-mails
# ────────────────────────────────────────────────────────────────────
REMINDER_RULES = """
### ADDITIONAL HOUSE RULES — REMINDER CONTEXT  (MUST obey **in addition** to BASE_RULES)

• PURPOSE  – This message is a *gentle follow-up* (“open reminder”) that nudges the author
  about the **same Call-for-Papers** announced previously.

• TONE     – Warm, collegial, appreciative; avoid any high-pressure phrases
  (“last chance”, “hurry”, etc.). Convey genuine courtesy: the editors simply wish
  to ensure the scholar saw the invitation.

• REFERENCE – Explicitly acknowledge the *prior invitation* in the **opening line**, but
  **do NOT** recycle the exact wording “Following our earlier call…”. Use fresh,
  varied phrasing each time (e.g. “Picking up from our recent announcement…”, 
  “Building on the invitation we sent last month…”, “Circling back to our previous note…”).

• STRUCTURE – Do **not** use a rigid template.  Aim for **3–5 natural paragraphs**:
    1. Engaging acknowledgment of the earlier invitation (40–70 words)
    2. Brief journal credentials + Impact Factor (40–70 words)
    3. Value proposition (fee waiver, fit, benefits) (90–130 words)
    4. Optional bulleted or sub-headed section (“Why Publish with <JOURNAL_SHORT>”) (60–100 words)
    5. Warm closing & submission link (40–70 words)

• SUBJECTS – Output **exactly 10** `Subject: …` lines (≤ 65 chars each) that
  clearly signal a friendly reminder *and* vary stylistically:
    “Subject: Still considering <JOURNAL_SHORT>?”
    “Subject: Gentle nudge—submit to <JOURNAL_SHORT>”
    …(eight more)

• BODY  – Re-state any fee-waiver **once**; omit if none exists.

• STYLE VARIETY – Vary sentence length and rhetorical devices
  (question, data point, micro-story, or concise quote) to keep the tone lively.

• WORD-COUNT – **Total body must be ≥ 370 words** (target 370-450)—
  count *only* the email body, not the subject lines or footer.

"""


# ────────────────────────────────────────────────────────────────────
#  AGENT maker (same pattern as CFP writer)
# ────────────────────────────────────────────────────────────────────
def create_reminder_writer_agent(selected_waiver_stance: str) -> Agent:
    return Agent(
        role   = ("Specialized assistant that drafts warm, collegial reminder e-mails "
                  "for previously sent CFP invitations."),
        goal   = ("Produce a concise, engaging reminder that references the earlier CFP, "
                  "respects all HOUSE RULES, and includes ten reminder-flavoured "
                  "subject lines."),
        backstory = ("You are an expert academic copy-writer who excels at follow-up "
                     "communications that maintain goodwill while prompting action."),
        verbose=False,
        allow_delegation=False,
        llm=get_llm_for_stance(selected_waiver_stance),
    )


# ────────────────────────────────────────────────────────────────────
#  TASK maker — pulls the last CFP draft and embeds it for context
# ────────────────────────────────────────────────────────────────────
def create_reminder_task(
    agent: Agent,
    waiver_stance: str,
    journal_meta: dict,   # must include journal_meta["domain"]
) -> Task:
    stance_key   = _clean_stance(waiver_stance)
    system_block = SYSTEM_BLOCKS[stance_key]

    # ---- 1. latest CFP for this journal *and* domain -----------------
    pattern = f"%{journal_meta['short_title']}%"
    domain  = journal_meta["domain"]

    records = get_recent_campaign_raw(pattern, domain, limit=1)
    last_cfp = records[0]["email"]   if records else ""
    last_sub = records[0]["subject"] if records else ""

    last_draft_block = (
        "\n\n### Previous CFP draft (for reference – **do NOT copy verbatim**)\n"
        f"**Subject line used:** {last_sub}\n\n"
        "```text\n"
        f"{last_cfp.strip()}\n"
        "```\n"
    )

    # ---- 2. journal meta block ---------------------------------------
    journal_block = (
        f"Journal Name: {journal_meta['full_title']}\n"
        f"Short Name: {journal_meta['short_title']}\n"
        f"Impact Factor: {journal_meta['impact_factor']}\n"
        f"Submission Deadline: {journal_meta['deadline']}\n"
        f"Fee Waiver: {journal_meta['waiver_flag']}\n"
        f"Waiver Percentage: {journal_meta.get('waiver_pct', 'N/A')}\n"
        f"Submit Paper URL: {journal_meta['submit_url']}\n"
        f"Other URL 1: {journal_meta['url1']}\n"
        f"Other URL 2: {journal_meta['url2']}\n"
        f"Sender Name: {journal_meta['sender_name']}\n"
        f"Sender Email: {journal_meta['sender_email']}\n"
    )

    full_prompt = (
        system_block +
        BASE_RULES +
        REMINDER_RULES +
        "\n\n" +
        journal_block +
        last_draft_block
    )

    return Task(
        name="Reminder Draft Generation",
        description=full_prompt,
        agent=agent,
        expected_output="A reminder e-mail draft that satisfies every HOUSE RULE.",
    )
