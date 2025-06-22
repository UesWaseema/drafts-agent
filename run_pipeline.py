import os
import streamlit as st, math
import random
import streamlit.components.v1 as components 
import logging, json, textwrap, pandas as pd
from itertools import count
from crewai import Crew, Process, Task
import uuid
from datetime import date, timedelta
import random 
import logging, qc_ai
from qc_models import MODEL_LIST
from statistics import fmean
from db import log_prompt_output, log_agent_run, save_run, save_draft, get_conn, get_unique_scenarios_for_journal
import time
import tiktoken
import json, re
import cache_init   # side-effect: registers Redis cache


st.set_page_config(page_title="Draft Generator", layout="wide")


logging.basicConfig(level=logging.INFO)
logging.getLogger("qc_ai").setLevel(logging.DEBUG)

# Enable verbose logging
DEBUG = os.getenv("LOG_LEVEL", "INFO").upper() == "DEBUG"
logger = logging.getLogger("cfp_debug")
logger.setLevel(logging.DEBUG if DEBUG else logging.INFO)

# ── Token length helper ────────────────────────────────────────────
try:
    enc = tiktoken.get_encoding("cl100k_base")
    def n_tokens(txt: str) -> int:
        return len(enc.encode(txt))
except ImportError:
    def n_tokens(txt: str) -> int: return max(1, len(txt) // 4)

_io_counter = count()

def readonly(label, value):
    st.text_input(label, value, disabled=True)


# ── Build metrics block without breaking context limit ────────────
def make_metrics_block(rows: list[dict],
                       headline: dict[str, str],
                       waiver_md: str,
                       token_budget_left: int,
                       max_col_len: int = 500) -> tuple[str, list[dict]]:
    """Return (markdown_block, maybe_trimmed_rows)."""
    keep = rows.copy()               # start with all rows

    def draft_block(rws: list[dict]) -> str:
        if not rws:
            return "*No recent analytics rows found.*"
        df = pd.DataFrame(rws)
        table = df.to_markdown(index=False)
        latest_json = json.dumps(rws[0], indent=2, default=str)
        return f"""
📊 **Recent metrics** ({len(rws)} emails)

- Avg. Overall Score  : {headline['overall']}
- Avg. Subject Score  : {headline['subject']}
- Avg. Structure Score: {headline['structure']}
- Avg. Content Score  : {headline['content']}

🗒 **Raw analytics**
```text
{table}
{waiver_md}

📌 Newest row

json
Copy
Edit
{latest_json}
```"""

    block = draft_block(keep)

    # 1) Drop rows until fits
    while keep and n_tokens(block) > token_budget_left:
        keep = keep[:-1]
        block = draft_block(keep)

    # 2) If still too big, truncate verbose cols
    if keep and n_tokens(block) > token_budget_left:
        df = pd.DataFrame(keep)
        for col in df.columns[df.dtypes == object]:
            df[col] = df[col].astype(str).str.slice(0, max_col_len)
        keep = df.to_dict("records")
        block = draft_block(keep)

    return block, keep


# ------------------------------------------------------------------
# >>> NEW – multillm_qcresults helper
# ------------------------------------------------------------------

MODEL_SHORT_TO_COL = {
    "gpt-4.1-2025-04-14":       "gpt-4.1-2025-04-14",
    "gpt-4o-2024-08-06":        "gpt-4o-2024-08-06",
    "gemini-2.5-pro-preview-06-05": "gemini-2.5-pro-preview-06-05",
    "deepseek-r1-0528":         "deepseek-r1-0528",
    "o3-2025-04-16":            "o3-2025-04-16",
}

def _short_name(model_id: str) -> str:
    """openai/gpt-4o-2024-08-06 → gpt-4o-2024-08-06"""
    return model_id.split("/")[-1]

def save_multillm_qc(draft_txt: str,
                     qc_prompt: str,
                     model_reports: dict[str, dict]) -> None:
    """
    Insert one consolidated bundle.
    model_reports comes straight from qc_ai.score(..., return_models=True)
    """
    cols  = ["draft", "qc_prompt"]
    vals  = [draft_txt, qc_prompt]

    for mdl, rep in model_reports.items():
        short = _short_name(mdl)
        if short in MODEL_SHORT_TO_COL:
            cols.append(f"`{MODEL_SHORT_TO_COL[short]}`")
            vals.append(json.dumps(rep))
    # any missing JSON columns will default to NULL

    placeholders = ", ".join(["%s"] * len(vals))
    col_list     = ", ".join(cols)

    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            f"INSERT INTO multillm_qcresults ({col_list}) VALUES ({placeholders})",
            tuple(vals)
        )
        conn.commit()
# ------------------------------------------------------------------
# <<< END NEW

def _start_timer():
    if not st.session_state.timer_running:
        st.session_state.timer_running = True
        st.session_state.timer_start_ts = time.time()

def _pause_timer():
    if st.session_state.timer_running:
        now = time.time()
        st.session_state.timer_elapsed_ms += int((now - st.session_state.timer_start_ts) * 1000)
        st.session_state.timer_running = False

# put this just after the other imports
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cfp_debug")

# Import common utilities and agents/tasks
from common import (
    get_highlighted_text,
    get_leftover_spam_words,
    calculate_core_word_count,
    extract_core_content,
    filter_agent_output,
    fetch_journals,
    fetch_domains,
    fetch_cfp_templates,
    fetch_open_templates,
    recommend_waiver,
    SPAM_WORDS,
    calc_spam_metrics,
    get_model_name # NEW
)
from agent_draft_writer import create_draft_writer_agent, create_draft_task
from agent_spam_removal import spam_removal_agent, spam_removal_task, final_output_sanitizer
from agent_gemini_html import (
    gemini_html_agent,
    convert_draft_to_html,
    build_final_plaintext,
)
from agent_reminder_writer import (
    create_reminder_writer_agent,
    create_reminder_task,
)
from agent_scenario import (
    groq_scenario_agent
)

# 👇 NEW
from common import INTERSPIRE_DOMAINS, MAILWIZZ_DOMAINS

from interspire_helpers import (
    get_recent_campaign_raw as _isp_fetch,          # NEW
    rows_to_json,
    get_last_waiver_percentage,
    get_latest_campaign, # NEW
)
from mailwizz_helpers import get_mailwizz_recent_campaigns as _mw_fetch

import datetime as _dt # Added for stopwatch
import re, html, pandas as pd, json

from crewai import LLM # NEW
LLM.provider = 'openrouter' # NEW

def _plain_preview(html_txt: str, max_chars: int = 350) -> str:
    txt = re.sub("<[^>]+>", "", html_txt or "")
    txt = html.unescape(txt).strip()
    return (txt[:max_chars] + " …") if len(txt) > max_chars else txt

def fetch_recent_campaigns(pattern: str,
                           domain: str,
                           limit: int = 10) -> list[dict]:
    """
    Return the N latest campaigns for *pattern* from the correct system,
    plus an extra helper field:
        "draft_type" = "CFP" | "Open" | "Unknown"
        "preview"    = plain-text 350-char snippet of the HTML body
    """
    if domain in INTERSPIRE_DOMAINS:
        rows = _isp_fetch(pattern, domain=domain, limit=limit)
    elif domain in MAILWIZZ_DOMAINS:
        rows = _mw_fetch(pattern, domain=domain, limit=limit)
    else:
        raise ValueError(f"Domain {domain} is in neither system list.")

    for r in rows:
        name = r.get("campaign_name", "") or ""
        if name.startswith("CFP_"):
            r["draft_type"] = "CFP"
        elif name.startswith("OPEN_"):
            r["draft_type"] = "Open"
        else:
            r["draft_type"] = "Unknown"
        body_html = r.get("email_body") or r.get("email", "")   # 🆕 add fallback
        r["preview"] = _plain_preview(body_html)
    return rows

# ────────────────────────────────────────────────────────────────────
# 📌  QUALITY CHECK 2  – deterministic + AI  (after Auto-Fix)
# ────────────────────────────────────────────────────────────────────
# from qc_script import validate as qc_det   # disable
# import qc_ai # NEW


def get_draft_run_pk(run_uuid: str) -> int:
    """Convert draft_runs.run_id (uuid) → draft_runs.id (int)."""
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM draft_runs WHERE run_id = %s LIMIT 1",
            (run_uuid,)
        )
        row = cur.fetchone()
        if not row:
            raise RuntimeError(f"run_id {run_uuid} not found")
        return row["id"] if isinstance(row, dict) else row[0]
    
# ────────────────────────────────────────────────────────────────────
# 📌  HELPER: Spam-clean a draft
# ────────────────────────────────────────────────────────────────────
def step_spam_clean(draft: str) -> str:
    found = get_leftover_spam_words(draft, SPAM_WORDS)
    logger.debug("Spam detector → %s", found)           # show list even if empty
    if not found:
        return draft

    description_text = f"""
You are a silent processing agent. Do not explain anything.

Replace the following spam words in the draft with context-appropriate synonyms: {', '.join(found)}.

Draft:
{draft}

Only return the updated draft text. Nindo commentary. No metadata.
"""

    spam_task = Task(
        name="Spam Cleanup Task",
        description=description_text,
        agent=spam_removal_agent,
        expected_output="Spam-cleaned draft text with replacements applied",
    )

    crew = Crew(
        agents=[spam_removal_agent],
        tasks=[spam_task],
        process=Process.sequential
    )

    result = crew.kickoff()
    cleaned = final_output_sanitizer(str(result))
    logger.debug("Spam-cleaned length=%d", len(cleaned))

    # ── NEW: compute spam metrics & persist score ────────────────
    metrics = calc_spam_metrics(cleaned)
    st.session_state.spam_metrics = metrics           # for banner display

    save_run(                                          # updates same run_id
        st.session_state.run_id,
        spam_score = metrics["score"]                 # <- new column
    )

   # ── token bookkeeping ───────────────────────────────────────────
    usage = getattr(result, "usage", {})
    ptok  = usage.get("prompt_tokens", n_tokens(description_text))   # fallback
    ctok  = usage.get("completion_tokens", n_tokens(str(result)))    # fallback

    log_agent_run(
       st.session_state.run_id,
       "spam_cleanup",
       spam_removal_agent.llm.model,
       ptok,
       ctok
   )

    push_banner(
       "Spam Remover",
       spam_removal_agent.llm.model,
       getattr(spam_removal_agent.llm, "temperature", "?"),
       ptok,
       ctok
   )
   # ────────────────────────────────────────────────────────────────

    return cleaned

# ────────────────────────────────────────────────────────────────────
# 🔍 Helper – build a LIKE pattern that matches the ESP’s journal column
#     • Interspire stores the SHORT title exactly.      (e.g. IJN)
#     • MailWizz  stores the FULL title, but without a
#       leading “Journal of …”.                        (e.g. International Nutrition)
# --------------------------------------------------------------------
def build_like_pattern(is_interspire: bool,
                       short: str,
                       full: str) -> str:
    """
    Return a SQL-LIKE pattern suitable for the current ESP.
    """
    if is_interspire:                     # Interspire path
        return f"%{short}%"
    clean_full = re.sub(r"^\s*journal\s+of\s+", "", full, flags=re.I).strip()
    return f"%{clean_full}%"

# ────────────────────────────────────────────────────────────────
def step_generate_and_spam():
    """Runs draft-writer ➜ initial spam removal."""

    debug_mode      = st.session_state.get("debug_mode", False)
    show_full_prompt = st.session_state.get("show_full_prompt", False)
    # Access the scenario manually selected or typed by the user
    user_scenario = st.session_state.get("manual_scenario", "").strip()

    
    # --- compute waiver numbers FIRST ---------------------------------
    waiver_level   = selected_journal["waiver_stance"] if selected_journal else "❌ Minimal"
    last_waiver    = get_last_waiver_percentage(f"%{journal_short_name}%")
    recommended_pct, waiver_msg = recommend_waiver(waiver_level, last_waiver)
    # ------------------------------------------------------------------
    start_ts = time.time()
    with st.spinner("Generating your CFP draft... This may take a moment."):
        # Construct the instructions string for the agent
        instructions_content = f"""
        Journal Name: {journal_name}
        Short Name: {journal_short_name}
        ISSN: {issn}
        Impact Factor: {impact_factor}
        Scenario Focus: {user_scenario or 'Not specified by user'}
        Submission Deadline: {submission_deadline}
        Fee Waiver: {'Yes' if waiver_available else 'No'}
        Fee Waiver Percentage: {waiver_percentage if waiver_available else 'N/A'}
        Fee Waiver Details: {fee_waiver_details if waiver_available else 'N/A'}
        Domain: {domain}
        Special Issue: {'Yes' if special_issue else 'No'}
        Submit Paper URL: {submit_paper_url}
        Other URL 1: {other_url_1}
        Other URL 2: {other_url_2}
        Sender Name: {sender_name}
        Sender Email: {sender_email}
        """
        
        if include_acceptance_rate and selected_journal and selected_journal['acceptance_rate'] is not None:
            instructions_content += f"\nAcceptance Rate: {selected_journal['acceptance_rate']}"
        
        if include_volume_issue and selected_journal:
            if selected_journal['volume'] is not None:
                instructions_content += f"\nVolume: {selected_journal['volume']}"
            if selected_journal['issue'] is not None:
                instructions_content += f"\nIssue: {selected_journal['issue']}"

        # Template selection based on draft_type
        template_content = ""
        if draft_type == "CFP":
            templates = fetch_cfp_templates()
        elif draft_type == "Open":
            templates = fetch_open_templates()
        
        if not templates:
            st.error(f"No templates found for {draft_type} type in the database.")
            st.stop()
        
        template_content = random.choice(templates)
        
        instructions_content += f"\n\nUse the following template as a base for the email draft:\n\n{template_content}"

        # Update pattern-building call
        is_isp  = selected_domain_name in INTERSPIRE_DOMAINS
        pattern = build_like_pattern(
            is_interspire = is_isp,
            short         = journal_short_name,
            full          = journal_name
        )
    

        records = fetch_recent_campaigns(
            pattern = pattern,              # wild-card LIKE '%Big Data Research%'
            domain  = selected_domain_name, # sidebar pick (CFP10, NCFP9, etc.)
            limit   = 10
        )


     # ---------- NEW recent-campaign JSON block -----------------
        keep_cols = ["campaign_name", "draft_type",
                    "subject", "sent_date", "preview"]

        df_recent = pd.DataFrame([{k: r.get(k) for k in keep_cols} for r in records])

        if not df_recent.empty:
            recent_table = df_recent.to_markdown(index=False)
            recent_json  = df_recent.to_json(orient="records",
                                            indent=2,
                                            date_format="iso")
            latest_json  = json.dumps(df_recent.iloc[0].to_dict(),
                                    indent=2, default=str)
        else:
            recent_table = "*No recent rows found for this journal.*"
            recent_json  = "[]"
            latest_json  = "{}"
# -----------------------------------------------------------

        waiver_md = f"""
        🧾 **Waiver Analysis**

        Last waiver offered : {last_waiver or 'N/A'} %  
        Journal stance      : {waiver_level}  
        Suggested now       : {recommended_pct}% ({waiver_msg})
        """

        if draft_type == "CFP":
            json_block = (
                "\n📈 **JSON export of the same 10 rows**  \n```json\n"
                f"{recent_json}\n```\n\n"
                "📌 **Most-recent row only**\n```json\n"
                f"{latest_json}\n```"
            )
        else:
            # --- reminder / “Open” branch (single previous draft) -------------
            json_block = (
                "\n📌 **Previous CFP JSON (1 row)**\n```json\n"
                f"{latest_json}\n```"
            )
        metrics_block = waiver_md + json_block

        # ─── Prompt-level debug (runs only after metrics_block exists) -----
        #if debug_mode:
        #    with st.expander("📝 Debug: full prompt sent to LLM"):
        #        st.code(metrics_block + instructions_content, language="markdown")

        #    logger.info("[PROMPT] first row = %s", records[0] if records else None)
        #    logger.info("[PROMPT] waiver=%s rec_pct=%s", last_waiver, recommended_pct)
        #    logger.info("[PROMPT] prompt length = %s chars",
        #                len(metrics_block + instructions_content))

        # ─── 6. splice it into full_instructions  ────────────────────────
        full_instructions = (
            f"Generate a CFP email for the {journal_name} ({journal_short_name}) "
            f"using {domain}. Highlight the journal's Impact Factor of {impact_factor} "
            "and mention any fee-waiver details. Use a **creative, unique scenario and structure**, "
            "and craft an **eye-catching, memorable opening paragraph** that immediately grabs attention. "
            "Ensure all required URLs and sender details are included exactly as specified in the system instructions.\n\n"

            + instructions_content           # key-value list

            + metrics_block                  # contains the JSON with 10 rows

            + "\n\n"                         # <── NEW directive starts here
            "### How to use the JSON above\n"
            "1. Parse the `JSON export of the same 10 rows` section.\n"
            "2. Notice the **subject**, **email** body, and **sent_date** for each entry.\n"
            "3. Infer tone, length, and structure from those examples.\n"
            "4. Write the new CFP draft in a **similar style**, but with fresh content.\n"
            "5. Do **not** copy the old subjects verbatim—create new ones.\n"
            + "\n\n"
            + "\n\n"
            "### Scenario Intent\nUse the following as the user's intended purpose or theme for the draft:\n**{user_scenario}**\n"
              "### Layout requirement – side-headings - HARD RULE.\n"
              "Structure the email with clear **side-headings** so the reader can scan quickly. "
              "Use bold formatting for each heading and keep each section concise.\n"
            + "\n\n### Additional hard rules\n"
              "- Use bold **creative side-headings**.\n"
              "- Final draft must exceed **320 words**.\n"
              "- Never output the placeholder text "
              "\"[mention recipient's specific research area if known, otherwise keep general]\".\n"
              "- Mention the full journal name only once in the intro and once in the signature.\n"
              "- If waiver_available is No, do NOT add a sentence about fee waivers.\n"
        )

        # Build waiver popup
        waiver_popup = ""
        if waiver_available:
            waiver_popup = (
                "\n\n---\n"
                "**📋 Waiver Review**\n"
                f"Last waiver offered : {last_waiver or 'N/A'} %\n"
                f"Journal stance      : {waiver_level}\n"
                f"Suggested now      : {recommended_pct}% ({waiver_msg})\n"
            )

        # 5) Now, when you build your Task.description, just append `waiver_popup`:
        task_description = f"""
        {full_instructions}

        {waiver_popup}
        """

        try:
            # ── Choose writer + task based on Draft Type ───────────────────
            if draft_type == "Open":          # ⬅ radio button from sidebar
                # 1) build a tiny meta-dict for the helper
                journal_meta = {
                    "full_title":  journal_name,
                    "short_title": journal_short_name,
                    "impact_factor": impact_factor,
                    "deadline": submission_deadline,
                    "waiver_flag": "Yes" if waiver_available else "No",
                    "waiver_pct": waiver_percentage,
                    "submit_url": submit_paper_url,
                    "url1":  other_url_1,
                    "url2":  other_url_2,
                    "sender_name":  sender_name,
                    "sender_email": sender_email,
                    "domain": selected_domain_name,
                }

                # 2) writer & task for *reminder*
                writer_agent = create_reminder_writer_agent(waiver_level)
                dynamic_draft_task = create_reminder_task(
                    agent         = writer_agent,
                    waiver_stance = waiver_level,
                    journal_meta  = journal_meta,
                )

            else:                            # regular CFP flow
                writer_agent = create_draft_writer_agent(waiver_level)
                dynamic_draft_task = create_draft_task(
                    agent             = writer_agent,
                    waiver_stance     = waiver_level,
                    instructions_block= task_description,
                )

            final_prompt = dynamic_draft_task.description # NEW LINE

            # ── OPTIONAL: inspect full prompt ──────────────────────────────
            if show_full_prompt:
                with st.expander("📝 Final prompt to LLM", expanded=False):
                    st.code(final_prompt, language="markdown")

                # Offer a download
                st.download_button(
                    label="💾 Download prompt.txt",
                    data=task_description,
                    file_name="prompt.txt",
                    mime="text/plain"
                )

            # Always log first 10k chars to console for quick grepping
            logger.info("[FINAL PROMPT first 1k]\n%s", final_prompt[:1000])

            total_tokens = n_tokens(final_prompt)
            logger.info("[PROMPT tokens] %s", total_tokens)
            #if debug_mode:
            #    st.caption(f"🧮 Prompt length: **{total_tokens:,} tokens**")

            # ─── DEBUG guard rail ────────────────────────────────────────────
            logger.info("[DEBUG] waiver_popup len=%s", len(waiver_popup))
            logger.info("[DEBUG] full prompt tokens=%s", n_tokens(final_prompt))

            #if debug_mode:
            #    st.caption(f"⚙️ Prompt tokens: {n_tokens(final_prompt):,}")
            #    st.code(final_prompt[:1000] + "\n...\n", language="markdown")

            # Bail early if prompt is clearly empty
            if not waiver_popup.strip():
                logger.warning("No waiver popup attached.")

            crew = Crew(
                agents=[writer_agent],
                tasks=[dynamic_draft_task],
                verbose=False,
                process=Process.sequential
            )
            result = crew.kickoff()
            logger.debug("Draft-writer returned type=%s chars=%d",
                         type(result).__name__,
                         len(str(result)))

            # ---------- token bookkeeping ----------
            usage = getattr(result, "usage", {})
            ptok  = usage.get("prompt_tokens", n_tokens(final_prompt)) # CHANGED
            ctok  = usage.get("completion_tokens", n_tokens(str(result)))
            log_agent_run(st.session_state.run_id, "draft_writer",
                          writer_agent.llm.model, ptok, ctok)
            push_banner("Draft Writer", writer_agent.llm.model,
            writer_agent.llm.temperature, ptok, ctok)

        
            # ---------------------------------------
            
            # Process initial draft output
            raw_output = result.raw if hasattr(result, 'raw') else str(result)
            subject_lines, email_body_text = filter_agent_output(raw_output, include_subjects=True)
            st.session_state.email_body_txt = email_body_text.strip()   # ← NEW

            # ▸ Join the 10 subjects under a clear header
            subjects_block = "Subject Lines:\n" + "\n".join(subject_lines)

            # ▸ Combine with the email body
            merged_draft_text = f"{subjects_block}\n\n{email_body_text}"

            st.session_state.draft_prompt = final_prompt # CHANGED
            st.session_state.draft_output = merged_draft_text.strip()

            # Reset downstream state whenever a new draft is generated
            for key in ("qc_prompt", "qc_output", "fix_prompt", "fix_output"):
                st.session_state.pop(key, None)

            save_run(
                st.session_state.run_id,
                journal_shortname=selected_journal["short_title"],
                domain=selected_domain_name,
                campaign_name=campaign_name,
                draft_prompt=st.session_state.draft_prompt,
                draft_output=st.session_state.draft_output,
                waiver_percentage  = waiver_percentage,          # ← NEW
                waiver_deadline    = waiver_deadline,            # if you added this col
                submission_deadline= final_deadline,             # if you added this col
                draft_type        = draft_type,      # ← NEW
            )
            # Set draft_pk after saving the run
            st.session_state.draft_pk = get_draft_run_pk(st.session_state.run_id)

            # ▸ Keep both in session state
            st.session_state.subject_lines = subject_lines
            st.session_state.generated_draft = merged_draft_text.strip()

            # Creative enhancement prompts
            creative_prompts = [
                "use a creative structure to the email, eye catching",
                "use an appealing and creative structure that will keep the interest of the reader till the end",
                "Craft a compelling piece with a unique structure that holds the reader's attention from start to finish.",
                "Compose content that is eye-catching, creatively structured, and maintains momentum throughout.",
                "Write with an inventive layout that is both aesthetically appealing and deeply engaging.",
                "Design promotional material with an eye-grabbing layout and a storyline that holds attention."
            ]

            # Randomly select one creative prompt
            selected_creative_prompt = random.choice(creative_prompts)

            # Extract core content for rewriting (excluding subjects and signature)
            # Use the newly parsed email_body_text as the original_draft_text for rewriting
            original_draft_text = email_body_text
            
            rewrite_instructions = (
                f"Rewrite the following email draft to be more stylistically compelling, "
                f"maintaining the original tone and data. Focus on the following creative enhancement: "
                f"'{selected_creative_prompt}'.\n\n"
                f"All original House Rules remain fully in force (ABSOLUTE OUTPUT restriction, URL format, word-count, replacement dictionary, forbidden vocabulary, etc.)."
                f"Original Draft:\n{original_draft_text}"
            )
            
            # Create a temporary task for rewriting
            rewrite_task = create_draft_task(
                agent               = writer_agent,   # same agent
                waiver_stance       = waiver_level,   # "❌ Minimal", etc.
                instructions_block = rewrite_instructions
            )

            
            rewrite_crew = Crew(
                agents  = [writer_agent],
                tasks   = [rewrite_task],
                process = Process.sequential,
                verbose = False
            )

            enhanced_raw   = rewrite_crew.kickoff()

            clean_rewrite  = final_output_sanitizer(
            enhanced_raw.raw if hasattr(enhanced_raw, "raw") else str(enhanced_raw)
            )
            subject_lines, enhanced_draft_text = filter_agent_output(
            clean_rewrite, include_subjects=True
            )

            # Removed st.spinner("Enhancing draft...")
            # Inputs are passed via task description, so no explicit inputs needed for kickoff here
            enhanced_result = enhanced_raw 

            rewrite_prompt = rewrite_task.description # NEW LINE
            rewrite_output = enhanced_result.raw if hasattr(enhanced_result, "raw") else str(enhanced_result) # NEW LINE
            st.session_state.rewrite_output = rewrite_output          # >>> NEW

            # ---------- token bookkeeping ----------
            usage = getattr(enhanced_result, "usage", {})
            ptok  = usage.get("prompt_tokens", n_tokens(rewrite_prompt)) # CHANGED
            ctok  = usage.get("completion_tokens", n_tokens(rewrite_output)) # CHANGED
            log_agent_run(st.session_state.run_id, "rewrite_restyle",
                          writer_agent.llm.model, ptok, ctok)
            push_banner("Re-writer", writer_agent.llm.model,
            writer_agent.llm.temperature, ptok, ctok)

        
            # ---------------------------------------
            
            #show_io(rewrite_prompt, rewrite_output, "Rewrite-Agent") # NEW LINE
            save_run( # NEW BLOCK
                st.session_state.run_id,
                rewrite_prompt = rewrite_prompt,
                rewrite_output = rewrite_output,
            ) # END NEW BLOCK

            enhanced_draft_text = enhanced_result.raw if hasattr(enhanced_result, 'raw') else str(enhanced_result)
            # Filter enhanced draft output to remove thoughts
            _, enhanced_draft_text = filter_agent_output(enhanced_draft_text)

            # Store generated draft and subject lines in session state
            st.session_state.generated_draft = enhanced_draft_text.strip()
            st.session_state.subject_lines = subject_lines
            st.session_state.spam_checked_output = "" # Clear previous spam check output
            st.session_state.replaced_spam_words = [] # New: Clear previous replaced spam words

            with st.spinner("Performing initial spam check and replacement..."):
                try:
                    filtered_spam_output = step_spam_clean(enhanced_draft_text.strip())
                    st.session_state.spam_checked_output = filtered_spam_output
                    
                    # Clear any QC leftovers
                    for k in ("qc_prompt", "qc_output", "qc_passed",
                            "fix_prompt", "fix_output",
                            "qc2_report", "qc2_failed", "qc2_passed",
                            "re_qc_done"):
                        st.session_state.pop(k, None)
                    
                    # Store sidebar info for later QC use
                    st.session_state.sidebar_info = {
                        "journal_title": journal_name,
                        "short_title": journal_short_name,
                        "issn": issn,
                        "impact_factor": impact_factor,
                        "acceptance_rate": selected_journal.get("acceptance_rate", "") if selected_journal else "",
                        "total_articles": selected_journal.get("total_articles", "")  if selected_journal else "",
                        "apc_usd": selected_journal.get("apc_usd", "")               if selected_journal else "",
                        "volume": selected_journal.get("volume", "")                 if selected_journal else "",
                        "issue": selected_journal.get("issue", "")                  if selected_journal else "",
                        "tier_classification": selected_journal.get("tier_classification", "") if selected_journal else "",
                        "waiver_stance": waiver_stance,
                        "journal_path": journal_path_suffix,
                        "sender_full_name": sender_name,
                    }
                    
                    # NEW ↓↓↓
                    try:
                        log_prompt_output(
                            prompt_text=full_instructions,          # the master prompt you built
                            output_text=filtered_spam_output,       # final cleaned draft
                            draft_type=draft_type,                  # 'CFP' or 'Open'
                            journal_title=journal_name,
                            waiver_pct=waiver_percentage if waiver_available else None,
                            model_name=writer_agent.llm.model,
                            latency_ms=int((time.time() - start_ts) * 1000),
                            user_id=None                            # fill if you track logins
                        )
                    except Exception as db_err:
                        st.error("⚠️ Could not write to prompt_logs table.")
                        st.exception(db_err)
                    # Initialize editable_draft_content with the spam-cleaned output
                    st.session_state.editable_draft_content = st.session_state.spam_checked_output
                except Exception as e:
                    st.error(f"An error occurred during initial spam checking: {e}")
                    st.info("Please check your API key, model name, and network connection.")
                    st.exception(e)

            # Display the final spam-checked draft directly (this will be replaced by components.html)
            # st.markdown(st.session_state.spam_checked_output)
            
            # Calculate and display word count for the enhanced version
            enhanced_core_word_count = calculate_core_word_count(st.session_state.generated_draft)
            # The user's strict instruction "STRICTLY SHOW ONLY THE FINAL DRAFT" implies no word count or warnings.
            # Removing these as well to adhere strictly to the instruction.
            # st.write(f"**Content Word Count (excluding salutation and signature): {enhanced_core_word_count} words**")
            # if enhanced_core_word_count < 400:
            #     st.warning("Warning: The enhanced draft's core word count is below 400 words. Consider expanding the content.")
            # elif enhanced_core_word_count > 600:
            #     st.warning("Warning: The enhanced draft's core word count exceeds 600 words. Consider condensing the content.")
            
            # Add a guard so you never pass an empty string to the downstream steps:
            if not email_body_text.strip():
                st.error("⚠️ Draft came back empty. Enable debug_mode for details.")
                st.stop()

        except Exception as e:
            st.error(f"An error occurred during draft generation: {e}")
            st.info("Please check your API key, model name, and network connection.")
            st.exception(e) # Added to show full traceback
    if "draft_prompt" in st.session_state and "draft_output" in st.session_state:
        st.session_state.generated = True
        #show_io(st.session_state.draft_prompt, st.session_state.draft_output, "Draft-Writer")
# >>> NEW AI-ONLY QC ROUTINE (paste here) <<<
# ---------------------------------------------------------------
# def step_qc_draft():
#     """Run one-shot AI QC on the current editable draft."""
#     if not st.session_state.get("draft_output"):
#         st.warning("Generate a draft first.")
#         return
#
#     email_txt = st.session_state.get(
#         "editable_draft_content",
#         st.session_state.get("draft_output", "")
#     ).strip()
#     prompt = build_qc_prompt(email_txt, domain)
#
#     # 1) Show prompt immediately; response will be filled in later
#     show_io(prompt, "(waiting…)", "QC-Agent")
#
#     # ▸ 2) call the checker LLM
#     report = qc_ai.score(email_txt, domain=domain, prompt_override=prompt)
#
#     # ▸ 3) front-end: show raw JSON
#     out_json = json.dumps(report, indent=2)
#     show_io(prompt, out_json, "QC-Agent")
#
#     # ▸ 4) cache for later UI
#     st.session_state.qc_prompt  = prompt
#     st.session_state.qc_output  = out_json
#     st.session_state.qc_passed  = report["__PASS__"]
#
#     # ▸ 5) persist in draft_runs
#     save_run(
#         st.session_state.run_id,
#         qc_prompt = prompt,
#         qc_output = out_json
#     )
#
#     # ▸ 6) metric logging (optional but nice)
#     prompt_tok = n_tokens(prompt)
#     comp_tok   = n_tokens(out_json)
#     log_agent_run(
#         st.session_state.run_id,
#         "qc_ai",
#         qc_ai.MODEL,
#         prompt_tok,
#         comp_tok
#     )
#
# # ▸ 7) quick banner feedback – now with reasons
#     if report["__PASS__"]:
#         st.success("🎉 Draft PASSED all QC checks!")
#     else:
#         comments = report.get("comments", {})
#         if not comments:                     # fallback if model forgot comments
#             comments = {k: "failed (no details)"
#                         for k, ok in report.items()
#                         if k != "__PASS__" and not ok}
#
#         lines = [f"**{rule}** — {comments.get(rule, 'failed')}"
#                  for rule, ok in report.items()
#                  if rule != "__PASS__" and not ok]
#
#         st.error("❌ QC failed:\n\n" + "\n".join(lines))
# ---------------------------------------------------------------
# def step_auto_fix():
#     """Runs auto-fix agent on last QC result."""
#     # build task + get untouched footer
#     autofix_task, frozen_footer = build_autofix_task(
#         draft_prompt        = st.session_state.draft_prompt,
#         original_draft        = st.session_state.draft_output,
#         quality_checklist  = st.session_state.qc_output,
#     )
#
#     autofix_crew = Crew(
#         agents=[qc_autofix_agent],
#         tasks=[autofix_task],
#         verbose=False,
#         process=Process.sequential,
#     )
#     autofix_body_raw = autofix_crew.kickoff()
#
#     # ---------- token bookkeeping ----------
#     usage = getattr(autofix_body_raw, "usage", {})
#     ptok  = usage.get("prompt_tokens", n_tokens(autofix_task.description))
#     ctok  = usage.get("completion_tokens", n_tokens(str(autofix_body_raw)))
#     log_agent_run(st.session_state.run_id, "autofix",
#                   qc_autofix_agent.llm.model, ptok, ctok)
#    
#     # ---------------------------------------
#
#     raw_text = (
#         autofix_body_raw.output if hasattr(autofix_body_raw, "output")
#         else str(autofix_body_raw)
#     )
#
#     clean_text = final_output_sanitizer(raw_text)
#     fixed_text = step_spam_clean(clean_text) + frozen_footer
#
#     st.session_state.fix_prompt = autofix_task.description
#     st.session_state.fix_output = fixed_text
#     st.session_state.editable_draft_content = fixed_text
#
#     save_run(
#         st.session_state.run_id,
#         fix_prompt=st.session_state.fix_prompt,
#         fix_output=st.session_state.fix_output,
#     )
#
#     st.success("✅ Autofix complete. Review below.")
#
#     if 'fix_output' in st.session_state:
#         st.session_state.history.append(
#             ("Original", st.session_state.draft_output,
#              "Corrected", st.session_state.fix_output)
#         )
#     st.session_state.fix_done = True
#     show_io(st.session_state.fix_prompt, st.session_state.fix_output, "Auto-Fix")
# ---------------------------------------------------------------
# def step_qc_after_fix():
#     """Runs QC again on fixed draft; writes pass/fail report."""
# # ⛔  old
# # fixed_text = st.session_state.fix_output  # Access the fixed text from session state
#
# # ✅  new
#     fixed_text = st.session_state.editable_draft_content.strip()
#
#     # ────────────────────────────────────────────────────────────────────
#     # 📌  QUALITY CHECK 2  – deterministic + AI  (after Auto-Fix)
#     # ────────────────────────────────────────────────────────────────────
#     def run_full_qc(text: str) -> dict:
#         ai = qc_ai.score(text, domain=domain)      # single-layer QC
#
#         # approximate token bookkeeping (optional)
#         prompt_tok = n_tokens(qc_ai.PROMPT_TEMPLATE.format(email=text))
#         comp_tok   = prompt_tok
#         log_agent_run(
#             st.session_state.run_id, "qc_ai",
#             os.getenv("QC_AI_MODEL", "gpt-4o-2024-08-06"),
#             prompt_tok, comp_tok
#         )
#         return ai
#     qc2 = run_full_qc(fixed_text)   # ← run on the final Auto-Fixed draft
#
#     # Format for UI
#     failed_rules = [k for k, v in qc2.items() if k not in ("__PASS__",) and v is False]
#
#     # ── save to session state so we can show later
#     st.session_state.qc2_report = qc2
#     st.session_state.qc2_failed = failed_rules
#     st.session_state.qc2_passed = qc2["__PASS__"]
#
#     # ── Log + immediate feedback ───────────────────────────────────────
#     if qc2["__PASS__"]:
#         st.success("🎉 Draft PASSED all deterministic + AI checks!")
#     else:
#         pass
#     st.session_state.re_qc_done = True
#
#     save_run(
#         st.session_state.run_id,
#         qc2_prompt="Full QC after auto-fix",
#         qc2_output=str(qc2)
#     )
#
#     show_io(str(st.session_state.qc2_report), str(st.session_state.qc2_failed), "QC-After-Fix")
# ────────────────────────────────────────────────────────────────

# ───────────────────────────────────────────────────────────────
# 💾 SAVE & HTML CONVERSION
# ───────────────────────────────────────────────────────────────
def step_save_and_html() -> None:
    """
    Uses the CURRENT editor text (editable_draft_content) as the
    single source of truth, converts it to HTML, and saves both
    plain-text and HTML to the database.
    """

    # ------------------------------------------------------------------
    # 1. Get the up-to-date body text (user may have edited it)
    # ------------------------------------------------------------------
    draft_txt = st.session_state.get("editable_draft_content", "").strip()

    if not draft_txt:
        st.warning("Nothing to save/convert – draft is empty.")
        return

    # Keep legacy key in-sync for any other code that still reads it
    st.session_state.email_body_txt = draft_txt

    # ------------------------------------------------------------------
    # 2. Wrap / clean for plain-text storage
    # ------------------------------------------------------------------
    final_plain_txt = build_final_plaintext(
        body_txt    = draft_txt,
        domain_code = st.session_state.domain_code,
    )

    # ------------------------------------------------------------------
    # 3. Upsert into draft_runs (plain-text version)
    # ------------------------------------------------------------------
    save_run(
        st.session_state.run_id,
        final_draft = final_plain_txt,
    )

    # ------------------------------------------------------------------
    # 4. Send to **HTML agent**
    # ------------------------------------------------------------------
    html_code, usage = convert_draft_to_html(
        plain_email       = draft_txt,                         # ← NEW
        domain_code       = st.session_state.domain_code,
        journal_shortname = st.session_state.journal_shortname,
        domain_term       = st.session_state.domain_term,
    )

    # ------------------------------------------------------------------
    # 5. Insert / update row in drafts table
    # ------------------------------------------------------------------
    if "draft_id" not in st.session_state:
        draft_id = save_draft(
            draft_run_id  = st.session_state.draft_pk,
            subject_lines = st.session_state.subject_lines,
            html_body     = html_code,
            text_body     = final_plain_txt,
        )
        st.session_state.draft_id = draft_id
    else:
        save_draft(
            draft_id      = st.session_state.draft_id,
            draft_run_id  = st.session_state.draft_pk,
            subject_lines = st.session_state.subject_lines,
            html_body     = html_code,
            text_body     = final_plain_txt,
            update=True,
        )

    # ------------------------------------------------------------------
    # 6. Logging / banners
    # ------------------------------------------------------------------
    ptok = usage.get("prompt_tokens", n_tokens(draft_txt))
    ctok = usage.get("completion_tokens", n_tokens(html_code))

    log_agent_run(
        st.session_state.run_id, "html_convert",
        gemini_html_agent.llm.model, ptok, ctok
    )
    push_banner(
        "HTML Converter", gemini_html_agent.llm.model,
        gemini_html_agent.llm.temperature, ptok, ctok
    )

    save_run(st.session_state.run_id, html_code=html_code)

    # ------------------------------------------------------------------
    # 7. Preview in UI
    # ------------------------------------------------------------------
    st.session_state.generated_html_code  = html_code
    st.session_state.rendered_html_output = html_code
    st.success("✅ Draft saved and converted to HTML (latest edits included).")

def show_io(prompt_text: str, output_text: str, label: str):
    """Side-by-side prompt / output viewer with unique widget keys."""
    idx = next(_io_counter) # 0, 1, 2, …

    with st.expander(f"🗂 {label} – prompt / output", expanded=False):
        col_p, col_o = st.columns(2)

        with col_p:
            st.selectbox(
                "Prompt",
                [prompt_text],
                index=0,
                label_visibility="collapsed",
                key=f"{label}_prompt_{idx}" # ← unique
            )

        with col_o:
            st.selectbox(
                "Output",
                [output_text],
                index=0,
                label_visibility="collapsed",
                key=f"{label}_output_{idx}" # ← unique
        )

# ─────────────────────────────────────────────────────────────
# QC 2.0  – lean wrapper around qc_ai.score()
# ─────────────────────────────────────────────────────────────
import qc_ai, json                           # NEW
import qc_helper            # 👈 make sure helper is imported
# from common import n_tokens                  # already present
from db import save_run, log_agent_run       # already present

def _build_qc_prompt(email_txt: str) -> str:
    """Fill qc_ai's template and return the final mega-prompt."""
    return (
        qc_ai.PROMPT_TEMPLATE
             .replace("<DOMAIN_PLACEHOLDER>", domain)   # global `domain`
             .format(email=email_txt)
    )

def _render_cached_qc() -> None:
    """Show the last QC result if present in session_state."""
    if not st.session_state.get("qc_output"):
        return

    summary = json.loads(st.session_state.qc_output)
    with st.expander("🔍 QC summary", expanded=False):
        if summary["__PASS__"]:
            st.success("✅ Passed all checks")
        else:
            st.error("❌ Failed checks")
        st.json(summary, expanded=True)

def _render_cached_qc2() -> None:
    if not st.session_state.get("qc2_output"):
        return
    summary = json.loads(st.session_state.qc2_output)
    with st.expander("🔍 2nd QC summary", expanded=False):
        if summary.get("__PASS__"):
            st.success("✅ Passed all checks")
        else:
            st.error("❌ Failed checks")
        st.json(summary, expanded=True)

def _step_qc_once(pass_id: int = 1) -> None:
    """
    Run qc_ai, persist, banner, and cache.

    pass_id = 1  ➜  qc_prompt  / qc_output   (auto after draft-gen)
    pass_id = 2  ➜  qc2_prompt / qc2_output  (manual "Run QC" button)
    """
    # 0) guard – make sure there is text
    if not st.session_state.get("editable_draft_content"):
        st.warning("Generate a draft first.")
        return

    email_txt = st.session_state.editable_draft_content.strip()
    logger.debug("QC pass=%d — text_len=%d", pass_id, len(email_txt))
    prompt    = _build_qc_prompt(email_txt)

    # 1) call the QC LLM
    try:
        logger.debug("Calling qc_ai.score()  return_models=True")
        summary, prompt_used, model_reports = qc_ai.score(
            email_txt,
            domain=domain,
            prompt_override=prompt,
            return_models=True
        )
        logger.debug("qc_ai returned keys=%s", list(summary.keys()))
        logger.debug("qc_ai model_reports for %d models: %s",
                     len(model_reports), ', '.join(model_reports.keys()))
    except Exception as err:
        st.error(f"QC crashed: {err}")
        logger.exception("QC step failed")
        return

    # 2) choose DB column names + UI label
    if pass_id == 1:
        col_prompt, col_output = "qc_prompt",  "qc_output"
        ui_label = "🔍 QC summary"
    else:
        col_prompt, col_output = "qc2_prompt", "qc2_output"
        ui_label = "🔍 2nd QC summary"

    # 3) optional: store in multillm_qcresults only for first pass
    if pass_id == 1:
        try:
            save_multillm_qc(
                draft_txt     = st.session_state.get("rewrite_output", ""),
                qc_prompt     = prompt,
                model_reports = model_reports
            )
        except Exception as e:
            logger.exception("multillm_qcresults insert failed")

    # 4) UI – collapsible block
    with st.expander(ui_label, expanded=False):
        if summary["__PASS__"]:
            _ = st.success("✅ Passed all checks")
        else:
            _ = st.error("❌ Failed checks")

        _ = st.json(summary, expanded=True)

    # 5) toast + bullet list
    if summary["__PASS__"]:
        st.success("🎉 Draft PASSED all QC checks!")
    else:
        comments = summary.get("comments", {})
        if not comments:  # fallback if model forgot to add comments
            comments = {k: "failed (no details)"
                        for k, ok in summary.items()
                        if k != "__PASS__" and not ok}
        bullet_lines = [f"**{rule}** — {comments.get(rule, 'failed')}"
                        for rule, ok in summary.items()
                        if rule != "__PASS__" and not ok]
        st.error("❌ QC failed:\n\n" + "\n".join(bullet_lines))

    # 6) cache in session_state
    st.session_state[col_prompt] = prompt
    st.session_state[col_output] = json.dumps(summary, indent=2)

    # 7) guarantee we know the draft_pk before DB writes
    if st.session_state.get("draft_pk") is None:
        try:
            st.session_state.draft_pk = get_draft_run_pk(st.session_state.run_id)
        except Exception:
            st.error("Draft not saved – click **Generate Draft** first.")
            logger.exception("Cannot resolve draft_pk")
            return  # abort save

    # 8) write to draft_runs
    save_run(
        st.session_state.run_id,
        **{col_prompt: prompt,
           col_output: json.dumps(summary, indent=2)}
    )

    # 9) telemetry + banner (only real models that ran)
    prompt_tok = n_tokens(prompt)
    comp_tok   = n_tokens(json.dumps(summary))

    for mdl, rep in model_reports.items():
        ptok = rep.get("prompt_tokens", prompt_tok)
        ctok = rep.get("completion_tokens", comp_tok)
        log_agent_run(st.session_state.run_id, "qc_ai", mdl, ptok, ctok)
        push_banner("QC", mdl, rep.get("temperature", "?"), ptok, ctok)

# --------------------------------------------------------------
# Scenario-ranking step  (runs after QC-1)
# --------------------------------------------------------------
def step_scenario_rank() -> None:
    """
    Reads the current editable draft & 10 subjects from session_state,
    calls Groq Llama-4 Maverick, saves scenario + top-3 subject lines.
    """
    if not st.session_state.get("editable_draft_content"):
        st.warning("Draft text missing – generate first.")
        return
    if not st.session_state.get("subject_lines"):
        st.warning("Subject list missing.")
        return

    draft_txt   = st.session_state.editable_draft_content.strip()
    subjects_10 = st.session_state.subject_lines

    with st.spinner("Detecting scenario & ranking subjects…"):
        data = groq_scenario_agent(draft_txt, subjects_10)

    scenario     = data.get("scenario", "").strip()
    top_subjects = data.get("top_subjects", [])[:3]

    # cache for UI
    st.session_state.scenario     = scenario
    st.session_state.top_subjects = top_subjects

    # persist
    save_run(
        st.session_state.run_id,
        scenario  = scenario or None,
        top_subj1 = top_subjects[0] if len(top_subjects) > 0 else None,
        top_subj2 = top_subjects[1] if len(top_subjects) > 1 else None,
        top_subj3 = top_subjects[2] if len(top_subjects) > 2 else None,
    )

    # light banner
    push_banner("Scenario Agent", "llama-4-maverick→Groq", 0.2, 0, 0)

# ######################################################################################################
# ----------------------------------------- Streamlit UI -----------------------------------------------
# ######################################################################################################



# ------------------------------------------------------------------
# 🔝  LIVE BANNER STRIP
# ------------------------------------------------------------------

if "banner_rows" not in st.session_state:
    st.session_state.banner_rows = []           # list of dicts

# Create a placeholder at the very top so it doesn’t scroll away
_banner_box = st.empty()

def _render_banners() -> None:
    """Draw/update the banner strip."""
    rows = st.session_state.banner_rows
    if not rows:
        _banner_box.empty()
        return
    with _banner_box.container():
        st.markdown("### 🧠 Run summary")
        for r in rows:
            st.caption(
                f"🧠 **{r['agent']}**  |  "
                f"Model **{r['model']}**  |  "
                f"T={r['temp']}  |  "
                f"Prompt = {r['ptok']:,} |   "
                f"Comp =  {r['ctok']:,} |  "
                f"Total = {r['ptok']+r['ctok']:,} tokens  "
            )

def push_banner(agent: str, model: str, temp: float,
                ptok: int, ctok: int) -> None:
    """Append one row then re-render."""
    logger.debug("Banner: %s | %s %s", agent, model, ptok+ctok)
    st.session_state.banner_rows.append(
        dict(agent=agent, model=model, temp=temp,
             ptok=ptok, ctok=ctok)
    )
    _render_banners()

# ------------------------------------------------------------------

st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600&display=swap" rel="stylesheet">
<style>
* { font-family: 'Inter', sans-serif !important; }
[data-testid="stTextArea"] textarea {
    color: #eaeaea;  background: transparent; border: 1px solid #444;
}
.highlight-spam { color:#ff5c5c; background:#2d0000; font-weight:600; }
</style>
""", unsafe_allow_html=True)

st.title("📧 Email Draft Generator")
st.markdown("Generate professional Call-for-Papers (CFP) email drafts for academic journals.")

# Initialize session state variables
if 'generated_draft' not in st.session_state:
    st.session_state.generated_draft = ""
if 'subject_lines' not in st.session_state:
    st.session_state.subject_lines = []
if 'spam_checked_output' not in st.session_state:
    st.session_state.spam_checked_output = ""
if 'editable_draft_content' not in st.session_state:
    st.session_state.editable_draft_content = ""
if 'highlighted_editable_draft' not in st.session_state: # New session state for highlighted HTML
    st.session_state.highlighted_editable_draft = ""
if 'generated_html_code' not in st.session_state:
    st.session_state.generated_html_code = ""
if 'rendered_html_output' not in st.session_state:
    st.session_state.rendered_html_output = ""
if 'history' not in st.session_state: # Added for history
    st.session_state.history = []
if "user_id" not in st.session_state:
    st.session_state.user_id = None   # or pull from your auth system
if "timer_running" not in st.session_state:
    st.session_state.timer_running = False
if "timer_start_ts" not in st.session_state:   # epoch seconds when running
    st.session_state.timer_start_ts = 0.0
if "timer_elapsed_ms" not in st.session_state: # accumulated millis
    st.session_state.timer_elapsed_ms = 0

# Fetch data from database
journals_data = fetch_journals()
assert journals_data, "DB connection failed – journals table is empty"
domains_data = fetch_domains()

# Create dictionaries for easy lookup
journals_dict = {journal['journal_title']: dict(journal) for journal in journals_data}
domains_dict = {domain['domain_name']: dict(domain) for domain in domains_data}

# --- PREP --------------------------------------------------------
if "run_id" not in st.session_state:
    st.session_state.run_id = str(uuid.uuid4())
    # stamp the run’s creation date exactly once
    st.session_state.creation_date = date.today()
    st.session_state.banner_rows = []
    _render_banners()

base_day = st.session_state.creation_date
submission_deadline_default = base_day + timedelta(days=random.randint(45, 60))
waiver_deadline_default     = base_day + timedelta(days=random.randint(25, 35))

short_names = [j["short_title"] for j in journals_data]
default_short = short_names[0]         # or pull from st.session_state

# Sidebar for inputs
with st.sidebar:
    import datetime as _dt

    def _fmt(ms: int) -> str:
        return str(_dt.timedelta(milliseconds=ms))

    elapsed_ms = st.session_state.timer_elapsed_ms
    if st.session_state.timer_running:
        elapsed_ms += int((time.time() - st.session_state.timer_start_ts) * 1000)

    label = "⏱️ Active Time"
    if st.session_state.timer_running:      # while a long task is underway
        label += " (running…)"

    st.sidebar.markdown(f"### {label}: `{_fmt(elapsed_ms)}`")
    # New Campaign subsection
    st.header("Campaign Details")
    campaign_name      = st.text_input("Campaign Name (internal)", "")

    st.header("Journal Details")

    selected_short = st.selectbox(
        "Short Name",
        short_names,
        index=short_names.index(default_short)
    )
    selected_journal = next(
        dict(j) for j in journals_data if j["short_title"] == selected_short
    )
    
    # read-only facts
    readonly("Full Title",  selected_journal["journal_title"])
    readonly("ISSN",        selected_journal["issn"])
    readonly("Sender Name", selected_journal["sender_full_name"])

    st.session_state.journal_shortname = selected_journal["short_title"]   # or ["abbr"] if you store it there
    # ──────────────────────────────────────────────────────────────
    # ✏️ Scenario Picker – based on newsletter_analysis table
    # ──────────────────────────────────────────────────────────────
    st.header("Scenario Focus")

    scenario_list = get_unique_scenarios_for_journal(selected_short)

    # Allow typing a new one too
    if scenario_list:
        scenario_options = scenario_list + ["✍️ Enter a new scenario..."]
    else:
        scenario_options = ["✍️ Enter a new scenario..."]

    selected_scenario = st.selectbox("Pick or type a scenario", scenario_options)

    if selected_scenario == "✍️ Enter a new scenario...":
        manual_scenario = st.text_input("Enter new scenario manually")
    else:
        manual_scenario = selected_scenario

    # Store for use later
    st.session_state.manual_scenario = manual_scenario

    # Radio button for Draft Type
    st.header("Draft Type")
    
    draft_type = st.radio("Choose the draft type", ("CFP", "Open", "Unopen"), horizontal=True)

    st.header("Domain Details")
    # Domain Selection - Reintroduced as per user feedback
    domain_names = [d['domain_name'] for d in domains_data]
    selected_domain_name = st.selectbox("Choose a Domain", domain_names)
    selected_domain = domains_dict.get(selected_domain_name)
    st.session_state.domain_code  = selected_domain["domain_name"]
    st.session_state.domain_term  = (
        selected_domain["domain_name"]
        .split("://", 1)[-1]        # strip http(s)://
        .rstrip("/")                # strip trailing slash
        .lower()
    )

    readonly("Domain",      selected_domain_name)
    readonly("Sender Email",selected_domain["sender_email"])
    st.session_state.domain_code = selected_domain["domain_name"]


    st.header("Waiver Details")

    waiver_deadline    = st.date_input("Waiver Deadline", value=waiver_deadline_default)
    final_deadline     = st.date_input("Final Submission Deadline", value=submission_deadline_default)



    # ------------------------------------------------------------------
    # 🏷️  WAIVER DETAILS  – drop this right inside the sidebar
    # ------------------------------------------------------------------
    st.header("Waiver Details")

    # Pattern for SQL LIKE queries (e.g., "%IJN%")
    pattern = f"%{selected_short}%"

    waiver_stance = selected_journal.get("waiver_stance", "❌ Minimal")
    waiver_available = st.checkbox(
        f"Fee Waiver Available? (Journal stance: {waiver_stance})",
        value=("✅ Aggressive" in waiver_stance or "⚠️ Targeted" in waiver_stance),
    )

    # ── journal-level history ----------------------------------------
    last_waiver    = get_last_waiver_percentage(pattern)
    waiver_display = "—" if last_waiver is None else f"{last_waiver}"
    recommended_pct, waiver_msg = recommend_waiver(waiver_stance, last_waiver)

    st.caption(
        f"📑 Last campaign waiver: {waiver_display}% · "
        f"Journal stance: {waiver_stance} → suggested **{recommended_pct}%**"
    )

    waiver_percentage = st.number_input(
        "Waiver Percentage",
        min_value=0, max_value=100,
        value=recommended_pct if waiver_available else 0,
        step=1,
    )

    fee_waiver_details = ""
    if waiver_available:
        fee_waiver_details = st.text_input(
            "Fee Waiver Details",
            "Yes, for submissions before " + waiver_deadline.strftime("%B %d, %Y")
        )

    # ── sanity guard --------------------------------------------------
    def waiver_needs_attention() -> str | None:
        if not waiver_available and waiver_stance != "❌ Minimal":
            return "The journal allows selective waivers, but you chose none."
        if waiver_available and waiver_stance == "❌ Minimal":
            return "This journal rarely grants waivers – please confirm."
        if waiver_available and abs(waiver_percentage - recommended_pct) > 10:
            return (
                f"Entered {waiver_percentage}% differs a lot from the "
                f"recommended {recommended_pct}%."
            )
        return None

    warn_msg = waiver_needs_attention()
    if "waiver_override" not in st.session_state:
        st.session_state.waiver_override = False

    if warn_msg:
        with st.popover("⚠️ Waiver check"):
            st.write(warn_msg)
            st.write("👉 Adjust the waiver or click **Proceed anyway**.")
            if st.button("Proceed anyway"):
                st.session_state.waiver_override = True
                warn_msg = None   # user overrides

    if warn_msg and not st.session_state.waiver_override:
        st.stop()   # halt build when waiver mismatch is unresolved
    # ------------------------------------------------------------------

    # Submission Stats
    st.header("Submission Stats")
    def _to_float(value, default=0.0):
        try:
            return float(str(value).replace('%', '').strip() or default)
        except ValueError:
            return default

    acceptance_rate = st.number_input(
        "Acceptance Rate (%)", 0.0, 100.0,
        value=_to_float(selected_journal.get("acceptance_rate", 0.0))
        )
    vol_issue       = st.text_input("Volume & Issue", f"{selected_journal.get('volume', '')}/{selected_journal.get('issue', '')}" if selected_journal.get('volume') else "")

    # ─── Debug toggle ────────────────────────────────────────────────
    #debug_mode        = st.checkbox("🔍 Show debug info", value=False)
    #show_full_prompt  = st.checkbox("📄 Show full prompt before send", value=False)

    # ─── Sidebar debug (no metrics_block here) ───────────────
    # Note: recent_records, recent_table, last_waiver, recommended_pct are now defined outside this block
    # and should be accessible.
    #if debug_mode:
        #with st.expander("📊 Debug: recent rows"):
            # Assuming recent_records and recent_table are still available from a broader scope
            # or need to be re-fetched if their scope was limited.
            # For now, keeping as is, assuming they are accessible.
            #if 'recent_records' in locals() and recent_records: # Check if defined and not empty
                #st.markdown(f"```text\n{recent_table}\n```")
            #else:
                #st.write("No recent rows.")
            #st.write("First non-null waiver →", last_waiver)
            #st.write("Recommended % →", recommended_pct)

        # Always log to console even if UI box is closed
        #logger.info("[SIDEBAR] rows=%s waiver=%s rec_pct=%s",
                    #len(recent_records) if 'recent_records' in locals() else 0, last_waiver, recommended_pct)

    # Dynamic URL construction
    base_journal_url = selected_domain['domain_url'] if selected_domain else "https://example.com"
    journal_path_suffix = selected_journal['journal_path'] if selected_journal else ""
    full_journal_url = f"{base_journal_url}{journal_path_suffix}"
    
    submit_paper_url = f"{full_journal_url}/submit-paper"

    # Other URLs logic
    other_url_suffixes = [
        "/about", "/editorial-board", "/aim-and-scope", "/instructions-for-author",
        "/article-processing-charges", "/membership"
    ]
    # Group for exclusion
    issue_archive_suffixes = ["/current-issue", "/previous-issue", "/archives"]

    # Randomly select two unique URLs, ensuring no conflict with issue/archive
    selected_other_urls = []
    
    # First URL: can be any from other_url_suffixes or one from issue_archive_suffixes
    possible_first_urls = other_url_suffixes + issue_archive_suffixes

    # These were removed from the sidebar in previous steps.
    special_issue = st.checkbox("Is this for a Special Issue?", key="special_issue_global_compat")
    include_acceptance_rate = st.checkbox("Include Acceptance Rate?", key="include_acceptance_rate_global_compat")
    include_volume_issue = st.checkbox("Include Volume and Issue?", key="include_volume_issue_global_compat")
    # Use random.sample to pick 2 unique URLs from the combined list
    # Ensure there are at least 2 unique URLs available
    if len(possible_first_urls) >= 2:
        selected_other_urls = random.sample(possible_first_urls, 2)
        
        # Check for the exclusion rule: current-issue, previous-issue, archives
        # If both selected URLs are from the issue_archive_suffixes group, re-sample
        while all(url in issue_archive_suffixes for url in selected_other_urls):
            selected_other_urls = random.sample(possible_first_urls, 2)
    elif len(possible_first_urls) == 1:
        selected_other_urls = [possible_first_urls[0], ""]
    else:
        selected_other_urls = ["", ""]

    other_url_1 = st.text_input("Other URL 1", f"{full_journal_url}{selected_other_urls[0]}")
    other_url_2 = st.text_input("Other URL 2", f"{full_journal_url}{selected_other_urls[1]}")

    

# ── Legacy var aliases for downstream functions ───────────────────
journal_short_name  = selected_short                               # was global before
journal_name        = selected_journal["journal_title"]
issn                = selected_journal["issn"]
domain              = selected_domain_name
impact_factor       = selected_journal.get("impact_factor", "")
sender_name         = selected_journal["sender_full_name"]
sender_email        = selected_domain["sender_email"]
submission_deadline = final_deadline.strftime("%B %d, %Y")   # NEW
special_issue       = st.session_state.get("special_issue", False) # NEW

# Re-declare variables that were previously in the sidebar and are needed globally
include_acceptance_rate = st.session_state.get("include_acceptance_rate", False) # NEW
include_volume_issue = st.session_state.get("include_volume_issue", False) # NEW

# Re-derive URLs as they were part of the sidebar logic
base_journal_url = selected_domain['domain_url'] if selected_domain else "https://example.com"
journal_path_suffix = selected_journal['journal_path'] if selected_journal else ""
full_journal_url = f"{base_journal_url}{journal_path_suffix}"

other_url_suffixes = [
    "/about", "/editorial-board", "/aim-and-scope", "/instructions-for-author",
    "/article-processing-charges", "/membership"
]
issue_archive_suffixes = ["/current-issue", "/previous-issue", "/archives"]
possible_first_urls = other_url_suffixes + issue_archive_suffixes
selected_other_urls = []
if len(possible_first_urls) >= 2:
    selected_other_urls = random.sample(possible_first_urls, 2)
    while all(url in issue_archive_suffixes for url in selected_other_urls):
        selected_other_urls = random.sample(possible_first_urls, 2)
elif len(possible_first_urls) == 1:
    selected_other_urls = [possible_first_urls[0], ""]
else:
    selected_other_urls = ["", ""]

submit_paper_url = f"{full_journal_url}/submit-paper"
other_url_1 = f"{full_journal_url}{selected_other_urls[0]}"
other_url_2 = f"{full_journal_url}{selected_other_urls[1]}"

# waiver_available, waiver_percentage, fee_waiver_details are handled in the Waiver Details block
# ---------------------------------------------------------------

# ──────────────────────────────  TOOLBAR  ──────────────────────────
btn_cols = st.columns(3)

with btn_cols[0]:
    gen_qc_clicked = st.button(
        "▶ Generate Draft + QC",
        key="btn_generate_qc",
        type="primary",
        disabled=not campaign_name.strip()
    )
    if gen_qc_clicked:
        logger.debug("▶ button clicked – new run_id=%s", st.session_state.run_id)

with btn_cols[1]:
    qc_clicked = st.button(
        "🕵️ Run QC",
        key="btn_qc",
        disabled=not st.session_state.get('editable_draft_content')
    )

with btn_cols[2]:
    html_clicked = st.button(
        "💾 Save & ➡️ HTML",
        key="btn_html",
        disabled=not st.session_state.get('editable_draft_content')
    )
# -------------------------------------------------------------------

_render_cached_qc()          # still shows qc_prompt / qc_output
_render_cached_qc2()         # new helper (below)


# ── Spam score banner ─────────────────────────────────────────
m = st.session_state.get("spam_metrics")
if m:
    st.markdown(
        f"""### 🛑 Spam Score&nbsp;&nbsp;**{m['score']}/5 (greater the score, lower the spam)**
<sub>{m['pct']} % spam words  
{m['spam_words']} / {m['words']} words  
{', '.join(m['spam_list']) or '—'}</sub>
""",
        unsafe_allow_html=True
    )
    # Extract values from spam_metrics
    spam_pct = round(m.get("pct", 0.0), 2)
    spamwordcount_str = f"{m.get('spam_words', 0)} / {m.get('words', 0)} words"

    # Save into draft_runs table
    save_run(
        st.session_state.run_id,
        spam_percentage = spam_pct,
        spamwordcount   = spamwordcount_str
    )

# ── Scenario banner ───────────────────────────────────────────
if st.session_state.get("scenario"):
    st.markdown(f"### 🧭 Scenario: **{st.session_state.scenario}**")

if st.session_state.get("top_subjects"):
    st.markdown("**Top-3 Suggested Subjects:**")
    st.markdown("\n".join(f"{i+1}. {s}"
                          for i, s in enumerate(st.session_state.top_subjects)))


if st.session_state.subject_lines:
    st.subheader("🎯 Subject Lines")
    st.markdown("\n".join(f"- {s}" for s in st.session_state.subject_lines))

# ------------------------------------------------------------------
# Final Draft editor & highlight preview
# ------------------------------------------------------------------
def _sync_editor_state() -> None:
    txt = st.session_state.final_draft
    st.session_state.editable_draft_content = txt
    st.session_state.email_body_txt        = txt   # legacy key kept alive

col1, col2 = st.columns(2)

with col1:
    st.subheader("Final Draft (Editable)")
    st.text_area(
        "Edit your draft here:",          # label
        value=st.session_state.editable_draft_content,
        height=600,
        key="final_draft",
        on_change=_sync_editor_state,     # ← NEW
        help="Press Ctrl + Enter to apply edits."
    )

with col2:
    st.subheader("Spam Highlights Preview")
    # Highlight the content from the text area for display
    from common import SPAM_WORDS # Re-import SPAM_WORDS for this section
    highlighted_display_text = get_highlighted_text(st.session_state.editable_draft_content, SPAM_WORDS)
    
    # Display the highlighted content using st.markdown (read-only display)
    st.markdown(
        f"""
        <div style="border: 1px solid #ccc; padding: 10px; min-height: 600px; overflow-y: auto; white-space: pre-wrap;">
            {highlighted_display_text}
        </div>
        """,
        unsafe_allow_html=True
    )

# --- call the steps *after* we know which button was pressed --------
# ---------------------------------------------------------------
if gen_qc_clicked:
    # brand-new run UUID each time
    st.session_state.run_id = str(uuid.uuid4())
    st.session_state.pop("draft_id", None)

    # stopwatch ⏱️
    st.session_state.timer_running    = False
    st.session_state.timer_elapsed_ms = 0
    _start_timer()

    # ① generate first draft (incl. spam clean)
    step_generate_and_spam()

    # ② immediate QC on that fresh draft
    _step_qc_once(pass_id=1)

    # ③ scenario + top-3 subjects
    step_scenario_rank()

    _pause_timer()
    st.rerun()          # refresh UI with QC result & enable “Run QC” button
# ---------------------------------------------------------------

if qc_clicked:          # manual re-check after edits
    _start_timer()
    _step_qc_once(pass_id=2)
    _pause_timer()
# ---------------------------------------------------------------

if html_clicked:
    _start_timer()
    step_save_and_html()
    _pause_timer()

    # final write to draft_runs
    save_run(
        st.session_state.run_id,
        active_ms = st.session_state.timer_elapsed_ms
    )
            
# ---------------------------------------------------------------


# Leftover Spam Words
if 'leftover_spam_words_list' in st.session_state and st.session_state.leftover_spam_words_list:
    st.write("The spam words in this draft are: " + ", ".join(st.session_state.leftover_spam_words_list))
elif 'leftover_spam_words_list' in st.session_state:
            st.write("No spam words found in the draft.")

# Word Counter
core_text = extract_core_content(st.session_state.editable_draft_content)
word_count = len(core_text.split())
warn = ""
if word_count < 400:
    warn = "⚠️ Too short!"
elif word_count > 600:
    warn = "⚠️ Too long!"
st.caption(f"📝 Core content: {word_count} words {warn}")

# if "qc2_report" in st.session_state:
#     with st.expander("🔍 Full QC results", expanded=False):
#         df_qc = (pd.DataFrame(
#                     [{"Rule": k, "Pass": "✅" if v else "❌"}
#                      for k, v in st.session_state.qc2_report.items()
#                      if not k.startswith("__")]
#                  ) .sort_values("Rule"))
#         st.table(df_qc)

# if st.session_state.get("re_qc_done"):
#     passed = st.session_state.qc2_passed
#     st.markdown("---")
#     st.header("🏁 Final QC Result")
#     if passed:
#         st.success("🎉 **All QC checks passed after auto-fix!**")
#     else:
#         pass

# if "qc_report" in st.session_state and st.session_state.qc_report:
#     with st.expander("📝 QC report", expanded=False):
#         if st.session_state.qc_report["passed"]:
#             st.markdown("**All checks passed ✅**")
#         else:
#             for item in st.session_state.qc_report["checklist"]:
#                 st.write(item)

# # Display remaining issues after autofix, if any
# if "editable_draft_content" in st.session_state and "🛠 Remaining Issues" in st.session_state.editable_draft_content:
#     st.markdown("### 🛠 Remaining Issues")
#     remaining = st.session_state.editable_draft_content.split("🛠 Remaining Issues", 1)[-1].strip()
#     st.markdown(remaining)

# HTML Output Section
if st.session_state.generated_html_code:
    st.markdown("---")
    st.subheader("Generated HTML Output")
    
    html_col1, html_col2 = st.columns(2)
    
    with html_col1:
        st.text_area(
            "HTML Code (Editable)",
            value=st.session_state.generated_html_code,
            height=600,
            key="generated_html_code_editor",
            help="Edit the generated HTML code directly."
        )
    
    with html_col2:
        st.markdown("### Rendered HTML Preview:")
        st.markdown(
            st.session_state.rendered_html_output,
            unsafe_allow_html=True
        )
