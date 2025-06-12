import streamlit as st
import random
import streamlit.components.v1 as components  # Import components
import logging, json, textwrap, pandas as pd # NEW
from crewai import Crew, Process, Task

# ── Token length helper ────────────────────────────────────────────
try:
    import tiktoken
    enc = tiktoken.get_encoding("cl100k_base")
    def n_tokens(txt: str) -> int:
        return len(enc.encode(txt))
except ImportError:                                  # coarse fallback
    def n_tokens(txt: str) -> int: return max(1, len(txt) // 4)

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
from langchain_core.agents import AgentFinish # Added for AgentFinish handling
from statistics import fmean # Added
from db import log_prompt_output
import time

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
    SPAM_WORDS
)
from agent_draft_writer import draft_writer_agent, draft_task
from agent_spam_removal import spam_removal_agent, spam_removal_task, final_output_sanitizer
from agent_html_converter import html_converter_agent, html_conversion_task, html_output_sanitizer
from interspire_helpers import (
    get_recent_campaign_records,
    rows_to_json,
    get_last_waiver_percentage,
    get_latest_campaign, # NEW
)
import datetime # Added for rows_to_json
import json # NEW

# --- Streamlit UI ---
st.set_page_config(page_title="CFP Email Draft Generator", layout="wide")

st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Baskerville&display=swap" rel="stylesheet">
<style>
/* Global Baskerville font */
* {
    font-family: 'Baskerville', serif !important;
}
/* Textarea styling */
[data-testid="stTextArea"] textarea {
    color: #FFFFFF !important;
    border: 1px solid #4A4A4A !important;
    background-color: transparent !important; /* Make background transparent */
}
/* Spam word highlighting */
.highlight-spam {
    color: #FF0000 !important;
    background-color: #330000;
    font-weight: bold;
}
</style>
""", unsafe_allow_html=True)

st.title("📧 CFP Email Draft Generator")
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

# Fetch data from database
journals_data = fetch_journals()
assert journals_data, "DB connection failed – journals table is empty"
domains_data = fetch_domains()

# Create dictionaries for easy lookup
journals_dict = {journal['journal_title']: journal for journal in journals_data}
domains_dict = {domain['domain_name']: domain for domain in domains_data}

# Sidebar for inputs
with st.sidebar:
    st.header("Select Journal and Domain")

    # Journal Selection
    journal_titles = [j['journal_title'] for j in journals_data]
    selected_journal_title = st.selectbox("Choose a Journal", journal_titles)
    selected_journal = journals_dict.get(selected_journal_title)

    # Domain Selection
    domain_names = [d['domain_name'] for d in domains_data]
    selected_domain_name = st.selectbox("Choose a Domain", domain_names)
    selected_domain = domains_dict.get(selected_domain_name)

    st.header("Manual Overrides / Additional Details")
    # Populate fields with selected journal/domain data, allow override
    journal_name = st.text_input("Journal Name", selected_journal['journal_title'] if selected_journal else "")
    journal_short_name = st.text_input("Journal Short Name", selected_journal['short_title'] if selected_journal else "")
    
    pattern = f"%{journal_short_name.strip()}%"   # wildcard for SQL LIKE

    issn = st.text_input("ISSN Number", selected_journal['issn'] if selected_journal else "")
    domain = st.text_input("Domain (e.g., Artificial Intelligence and Machine Learning)", selected_domain['domain_name'] if selected_domain else "")
    
    st.header("Submission Details")
    special_issue = st.checkbox("Is this for a Special Issue?")
    
    # Waiver details
    waiver_stance = selected_journal['waiver_stance'] if selected_journal else "❌ Minimal"
    waiver_available = st.checkbox(f"Fee Waiver Available? (Journal Stance: {waiver_stance})", value="✅ Aggressive" in waiver_stance or "⚠️ Targeted" in waiver_stance)
    fee_waiver_details = ""
    # ─── fetch journal-level facts ───────────────────────────────────
    recent_records = get_recent_campaign_records(pattern, limit=10)

    def first_recent_waiver(rows):
        for r in rows:                         # newest → oldest
            wp = r.get("waiver_percentage")
            if wp is not None:
                return wp
        return None

    last_waiver = get_last_waiver_percentage(pattern)
    latest_row = get_latest_campaign(pattern) # NEW
    waiver_display = "—" if last_waiver is None else f"{last_waiver}"
    waiver_level = selected_journal["waiver_stance"] if selected_journal else "❌ Minimal"

    recommended_pct, waiver_msg = recommend_waiver(waiver_level, last_waiver)

    # UI – show stance + last + recommendation in a helpful note
    st.caption(
        f"📑 Last campaign waiver: {waiver_display} % · "
        f"Journal stance: {waiver_level} → suggested **{recommended_pct}%**"
    )

    waiver_percentage = st.number_input(
        "Waiver Percentage",
        min_value=0, max_value=100,
        value=recommended_pct if waiver_available else 0,
        step=1,
    )
    if waiver_available:
        fee_waiver_details = st.text_input("Fee Waiver Details (e.g., for submissions before July 15, 2025)", "Yes, for submissions before July 15, 2025")

    # ─── sanity check before we build the prompt ─────────────────────
    def waiver_needs_attention() -> str | None:
        if not waiver_available and waiver_level != "❌ Minimal":
            return "The journal allows selective waivers, but you chose none."
        if waiver_available and waiver_level == "❌ Minimal":
            return "This journal rarely grants waivers – please confirm."
        if waiver_available and abs(waiver_percentage - recommended_pct) > 10:
            return f"Entered {waiver_percentage}% differs a lot from the "\
                   f"recommended {recommended_pct}%."
        return None

    warn_msg = waiver_needs_attention()
    if warn_msg:
        with st.popover("⚠️ Waiver check"):
            st.write(warn_msg)
            st.write("👉 Adjust the waiver or click **Proceed anyway**.")
            if st.button("Proceed anyway"):
                warn_msg = None   # user overrides

    if warn_msg:
        st.stop()   # prevent running the pipeline with questionable waiver
    
    st.header("Sender Information")
    sender_name = st.text_input("Sender Name", selected_journal['sender_full_name'] if selected_journal else "")
    sender_email = st.text_input("Sender Email", selected_domain['sender_email'] if selected_domain else "")

    st.header("Additional Information")
    impact_factor = st.text_input("Impact Factor", str(selected_journal['impact_factor']) if selected_journal and selected_journal['impact_factor'] is not None else "")
    submission_deadline = st.text_input("Submission Deadline", "August 31, 2025") # This is a generic placeholder, could be added to DB
    
    # Checkboxes for additional journal details
    include_acceptance_rate = st.checkbox("Include Acceptance Rate?")
    include_volume_issue = st.checkbox("Include Volume and Issue?")

    # ─── Debug toggle ────────────────────────────────────────────────
    debug_mode        = st.checkbox("🔍 Show debug info", value=False)
    show_full_prompt  = st.checkbox("📄 Show full prompt before send", value=False)

    # ─── Sidebar debug (no metrics_block here) ───────────────
    if debug_mode:
        with st.expander("📊 Debug: recent rows"):
            if recent_records:
                st.markdown(f"```text\n{recent_table}\n```")
            else:
                st.write("No recent rows.")
            st.write("First non-null waiver →", last_waiver)
            st.write("Recommended % →", recommended_pct)

        # Always log to console even if UI box is closed
        logger.info("[SIDEBAR] rows=%s waiver=%s rec_pct=%s",
                    len(recent_records), last_waiver, recommended_pct)

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
    
    # Use random.sample to pick 2 unique URLs from the combined list
    # Ensure there are at least 2 unique URLs available
    if len(possible_first_urls) >= 2:
        selected_other_urls = random.sample(possible_first_urls, 2)
        
        # Check for the exclusion rule: current-issue, previous-issue, archives
        # If both selected URLs are from the issue_archive_suffixes group, re-sample
        while all(url in issue_archive_suffixes for url in selected_other_urls):
            selected_other_urls = random.sample(possible_first_urls, 2)
    elif len(possible_first_urls) == 1:
        selected_other_urls = [possible_first_urls[0], ""] # Only one URL available
    else:
        selected_other_urls = ["", ""] # No URLs available


    other_url_1 = st.text_input("Other URL 1", f"{full_journal_url}{selected_other_urls[0]}")
    other_url_2 = st.text_input("Other URL 2", f"{full_journal_url}{selected_other_urls[1]}")

    # Radio button for Draft Type
    draft_type = st.radio("Draft Type", ("CFP", "Open"))


if st.button("Generate Draft", type="primary"):
    start_ts = time.time()
    with st.spinner("Generating your CFP draft... This may take a moment."):
        # Construct the instructions string for the agent
        instructions_content = f"""
        Journal Name: {journal_name}
        Short Name: {journal_short_name}
        ISSN: {issn}
        Impact Factor: {impact_factor}
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

        # ─── 1. fetch the last 10 campaigns ──────────────────────────────
        pattern = f"%{journal_short_name}%"          # e.g. "%IJN%"
        records  = get_recent_campaign_records(pattern, limit=10)

        # ─── 2. headline averages (None-aware) ───────────────────────────
        def avg(field: str) -> str:
            vals = [r[field] for r in records if r[field] is not None]
            return f"{sum(vals)/len(vals):.2f}" if vals else "N/A"

        headline = {
            "overall"  : avg("overall_score"),
            "subject"  : avg("subject_overall_score"),
            "structure": avg("structure_score"),
            "content"  : avg("email_content_score"),
        }

        # ─── 3. waiver analysis message  (unchanged) ─────────────────────
        # waiver_level = selected_journal["waiver_stance"] if selected_journal else "❌ Minimal" # Moved up
        # last_waiver  = get_last_waiver_percentage(journal_name) # Moved up
        # _, waiver_text = recommend_waiver(waiver_level, last_waiver) # Moved up

        # ─── 4. full JSON dump of the rows ───────────────────────────────
        # ─── Convert to DataFrame for nice tabular prompt ────────────────
        df_recent = pd.DataFrame(records)

        # A pretty table for the model (and humans). If the list is empty,
        # we’ll pass a placeholder so the LLM doesn’t choke on “[]”.
        if not df_recent.empty:
            recent_table = df_recent.to_markdown(index=False)      # pipe-table
            recent_json  = df_recent.to_json(orient="records", date_format="iso", indent=2)
        else:
            recent_table = "*No analysed rows found for this journal yet.*"
            recent_json  = "[]"

        latest_json = json.dumps(records[0] if records else {}, indent=2, default=str)

        metrics_block = f"""
📊 **Recent Email-Campaign Metrics** (last {len(records)} emails)

- Avg. Overall Score  : {headline['overall']}
- Avg. Subject Score  : {headline['subject']}
- Avg. Structure Score: {headline['structure']}
- Avg. Content Score  : {headline['content']}

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
```"""

        # ─── Prompt-level debug (runs only after metrics_block exists) -----
        if debug_mode:
            with st.expander("📝 Debug: full prompt sent to LLM"):
                st.code(metrics_block + instructions_content, language="markdown")

            logger.info("[PROMPT] first row = %s", records[0] if records else None)
            logger.info("[PROMPT] waiver=%s rec_pct=%s", last_waiver, recommended_pct)
            logger.info("[PROMPT] prompt length = %s chars",
                        len(metrics_block + instructions_content))

        # ─── 6. splice it into full_instructions  ────────────────────────
        full_instructions = (
            f"Generate a CFP email for the {journal_name} ({journal_short_name}) focusing on {domain}. "
            f"Highlight the journal's Impact Factor of {impact_factor} and mention the fee waiver details. "
            "Ensure all required URLs and sender details are included as specified in the system instructions. "
            "Use the following details:\n\n" + instructions_content + metrics_block
        )

        # 1) Fetch latest campaign record
        latest = get_latest_campaign(pattern)          # returns a dict or None
        last_pct = latest.get("waiver_percentage") if latest else None

        # 2) Fetch journal stance
        stance = selected_journal["waiver_stance"] if selected_journal else "❌ Minimal" # Ensure selected_journal is not None

        # 3) Compute a recommended waiver
        recommended_pct, waive_msg = recommend_waiver(stance, last_pct)

        # 4) Build the waiver-popup questions only when appropriate
        waiver_popup = ""
        if last_pct is not None or waiver_available:
            # Determine which branch we're in:
            if stance == "❌ Minimal":
                if last_pct is not None:
                    prompt = (
                      f"The last campaign offered a {last_pct}% waiver, "
                      "but this journal has a **Minimal** waiver stance (0–10%).\n"
                      "I recommend offering **no waiver** this time. Do you still want to proceed with a waiver?\n"
                      "1) Yes, offer a waiver anyway\n"
                      "2) No waiver\n"
                    )
                else:
                    prompt = (
                      "This is a tier-3 journal with a **Minimal** waiver stance (0–10%) and no waiver was given last time.\n"
                      "I recommend **no waiver**. Do you still want to proceed with a waiver?\n"
                      "1) Yes, specify a waiver\n"
                      "2) No waiver\n"
                    )
            else:
                # For Targeted or Aggressive
                if last_pct is not None:
                    prompt = (
                      f"The last campaign offered a {last_pct}% waiver. Based on the **{stance}** stance, "
                      f"I recommend **{recommended_pct}%** this time. Would you like to:\n"
                      "1) Use the recommended waiver\n"
                      f"2) Specify a different waiver percentage (other than {recommended_pct}%)\n"
                    )
                else:
                    prompt = (
                      f"No waiver was given last time. Based on the **{stance}** stance, "
                      f"I recommend **{recommended_pct}%** this time. Would you like to:\n"
                      "1) Use the recommended waiver\n"
                      "2) Specify a different waiver percentage\n"
                    )

            waiver_popup = (
              "\n\n---\n"
              "**📋 Waiver Review**\n" +
              prompt +
              "3) Add deadline/conditions for this waiver (if any): __%\n"
            )

        # 5) Now, when you build your Task.description, just append `waiver_popup`:
        task_description = f"""
        {full_instructions}

        {waiver_popup}
        """

        # ── OPTIONAL: inspect full prompt ──────────────────────────────
        if show_full_prompt:
            with st.expander("📝 Full prompt being sent to the LLM", expanded=False):
                st.code(task_description, language="markdown")

            # Offer a download
            st.download_button(
                label="💾 Download prompt.txt",
                data=task_description,
                file_name="prompt.txt",
                mime="text/plain"
            )

        # Always log first 10k chars to console for quick grepping
        logger.info("[PROMPT first 10k] %s …", task_description[:10_000])

        total_tokens = n_tokens(task_description)
        logger.info("[PROMPT tokens] %s", total_tokens)
        if debug_mode:
            st.caption(f"🧮 Prompt length: **{total_tokens:,} tokens**")

        try:
            dynamic_draft_task = Task(
                description=task_description,
                agent=draft_writer_agent,
                expected_output="A polished CFP draft with 10 subject lines, structured sections, clear tone, and full signature block.",
                llm_options={"transform": "middle-out"}
            )

            crew = Crew(
                agents=[draft_writer_agent],
                tasks=[dynamic_draft_task],
                verbose=False,
                process=Process.sequential
            )
            result = crew.kickoff()
            
            # Process initial draft output
            raw_output = result.raw if hasattr(result, 'raw') else str(result)
            subject_lines, email_body_text = filter_agent_output(raw_output, include_subjects=True)

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
                f"Ensure the signature at the end of the draft follows this exact structure:\n"
                f"    Warm Regards,\n"
                f"    {sender_name}\n"
                f"    Editorial Office\n"
                f"    {journal_name}\n"
                f"    616 Corporate Way, Suite 2-6158\n"
                f"    Valley Cottage, NY 10989\n"
                f"    United States\n"
                f"    Email: {sender_email}\n\n"
                f"Original Draft:\n{original_draft_text}"
            )
            
            # Create a temporary task for rewriting
            rewrite_task = Task(
                description=(
                    f"Rewrite the following email draft to be more stylistically compelling, "
                    f"maintaining the original tone and data. Focus on the following creative enhancement: "
                    f"'{selected_creative_prompt}'.\n\n"
                    f"Adhere strictly to the following rules:\n"
                    f"- The rewritten draft MUST NOT include any subject lines. Only rewrite the provided 'Original Draft' content.\n"
                    f"- Signature at the end of the draft must always follow this exact structure, ensuring each line is separated by a double newline (`\n\n`) for proper formatting:\n"
                    f"    Warm Regards,\n\n"
                    f"    {sender_name}\n\n"
                    f"    Editorial Office\n\n"
                    f"    {journal_name}\n\n"
                    f"    616 Corporate Way, Suite 2-6158\n\n"
                    f"    Valley Cottage, NY 10989\n\n"
                    f"    United States\n\n"
                    f"    Email: {sender_email}\n\n"
                    f"Ensure all other paragraphs in the draft are also separated by double newlines (`\n\n`) for clear readability.\n\n"
                    f"Original Draft:\n{original_draft_text}"
                ),
                agent=draft_writer_agent,
                expected_output="A rewritten version of the provided email draft, adhering to the creative enhancement prompt, maintaining original tone and data, and including the specified signature structure.",
                llm_options={"transform": "middle-out"}
            )
            
            # Create a temporary crew for rewriting
            rewrite_crew = Crew(
                agents=[draft_writer_agent],
                tasks=[rewrite_task],
                verbose=False,
                process=Process.sequential
            )
            
            # Removed st.spinner("Enhancing draft...")
            # Inputs are passed via task description, so no explicit inputs needed for kickoff here
            enhanced_result = rewrite_crew.kickoff()
            enhanced_draft_text = enhanced_result.raw if hasattr(enhanced_result, 'raw') else str(enhanced_result)
            # Filter enhanced draft output to remove thoughts
            _, enhanced_draft_text = filter_agent_output(enhanced_draft_text)

            # Store generated draft and subject lines in session state
            st.session_state.generated_draft = enhanced_draft_text.strip()
            st.session_state.subject_lines = subject_lines
            st.session_state.spam_checked_output = "" # Clear previous spam check output
            st.session_state.replaced_spam_words = [] # New: Clear previous replaced spam words

            # Perform initial spam check automatically
            # First, identify spam words in the generated draft
            # Call get_highlighted_text for highlighting (it returns only the text)
            # The SPAM_WORDS list is now in common.py, so it needs to be imported or passed.
            # For now, I'll assume it's imported.
            from common import SPAM_WORDS
            highlighted_text_for_initial_spam_check = get_highlighted_text(enhanced_draft_text.strip(), SPAM_WORDS)
            
            # Then, get the leftover spam words separately
            found_spam_words_in_draft = get_leftover_spam_words(enhanced_draft_text.strip(), SPAM_WORDS)
            st.session_state.replaced_spam_words = found_spam_words_in_draft # Store the words that will be replaced

            # Create a dynamic spam removal task
            dynamic_spam_removal_task = Task(
                description=(
                    f"Refine the following draft by removing or replacing spam words. "
                    f"Draft to refine: {enhanced_draft_text.strip()}\n"
                    f"Spam words to replace: {', '.join(found_spam_words_in_draft)}"
                ),
                agent=spam_removal_agent,
                expected_output="A cleaned version of the email draft with all specified spam words removed or replaced.",
                llm_options={"transform": "middle-out"}
            )

            spam_crew = Crew(
                agents=[spam_removal_agent],
                tasks=[dynamic_spam_removal_task],
                verbose=False,
                process=Process.sequential
            )
            
            with st.spinner("Performing initial spam check and replacement..."):
                try:
                    spam_cleaned_result = spam_crew.kickoff()
                    # Sanitize the agent's output to ensure only the refined draft is kept
                    # Always convert the result to a string and then sanitize it
                    raw_output = spam_cleaned_result.return_values['output'] if isinstance(spam_cleaned_result, AgentFinish) and 'output' in spam_cleaned_result.return_values else str(spam_cleaned_result)
                    filtered_spam_output = final_output_sanitizer(raw_output)
                    st.session_state.spam_checked_output = filtered_spam_output
                    # NEW ↓↓↓
                    try:
                        log_prompt_output(
                            prompt_text=full_instructions,          # the master prompt you built
                            output_text=filtered_spam_output,       # final cleaned draft
                            draft_type=draft_type,                  # 'CFP' or 'Open'
                            journal_title=journal_name,
                            waiver_pct=waiver_percentage if waiver_available else None,
                            model_name="gpt-4o-mini",               # or read from env
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
            
        except Exception as e:
            st.error(f"An error occurred during draft generation: {e}")
            st.info("Please check your API key, model name, and network connection.")
            st.exception(e) # Added to show full traceback

# Display Subject Lines
if st.session_state.subject_lines:
    st.subheader("Generated Subject Lines")
    for line in st.session_state.subject_lines:
        st.markdown(f"- {line}")

# Create two columns for side-by-side layout
col1, col2 = st.columns(2)

with col1:
    st.subheader("Final Draft (Editable)")
    edited_draft_text = st.text_area(
        "Edit your draft here:", # Added the label argument
        value=st.session_state.editable_draft_content,
        height=600,
        key="final_draft",
        help="Edit directly - remaining spam words highlighted in red"
    )
    # Update session state with the content from the text area
    st.session_state.editable_draft_content = edited_draft_text

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

# Buttons for actions
col_buttons_1, col_buttons_2 = st.columns(2)

with col_buttons_1:
    if st.button("♻️ Re-run Spam Removal", type="secondary"):
        # This will trigger a re-run of the script, and the components.html will re-render with updated highlighting
        # based on the latest st.session_state.editable_draft_content
        from common import SPAM_WORDS # Re-import SPAM_WORDS for this section
        re_highlighted_text = get_highlighted_text(st.session_state.editable_draft_content, SPAM_WORDS)
        st.session_state.highlighted_editable_draft = re_highlighted_text
        st.session_state.leftover_spam_words_list = get_leftover_spam_words(st.session_state.editable_draft_content, SPAM_WORDS)
        st.session_state.word_count = calculate_core_word_count(st.session_state.editable_draft_content)
        st.rerun()

with col_buttons_2:
    if st.button("✅ Save Draft and Proceed to HTML", type="primary"):
        with st.spinner("Converting draft to HTML..."):
            html_conversion_inputs = {
                'draft_to_convert': st.session_state.editable_draft_content
            }
            # Create a dynamic HTML conversion task
            dynamic_html_conversion_task = Task(
                description=(
                    f"Convert the following draft to HTML: {st.session_state.editable_draft_content}"
                ),
                agent=html_converter_agent,
                expected_output="The HTML representation of the provided email draft.",
                llm_options={"transform": "middle-out"}
            )

            html_crew = Crew(
                agents=[html_converter_agent],
                tasks=[dynamic_html_conversion_task],
                verbose=False,
                process=Process.sequential
            )
            html_result = html_crew.kickoff()

        # Get raw output from agent
        raw_output = html_result.raw if hasattr(html_result, 'raw') else str(html_result)

        # Apply existing filter
        _, temp_filtered = filter_agent_output(raw_output)

        # Apply HTML-specific sanitizer
        cleaned_html = html_output_sanitizer(temp_filtered)

        # Store in session state
        st.session_state.generated_html_code = cleaned_html
        st.session_state.rendered_html_output = cleaned_html  # For initial display


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

st.markdown("---")
st.info("To run this application, save it as `streamlit_app.py` and execute `streamlit run streamlit_app.py` in your terminal.")
