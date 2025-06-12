"""
ui.app
======
Streamlit front-end for the 5-agent CFP pipeline.

Order of execution
------------------
1.  Writer (Crew)         – first-pass draft
2.  spam_check.py         – detect hits
3.  Spam-remover (Crew)   – rewrite
4.  qc_rules.py           – deterministic 18-rule checker
5.  qc_tone.py (Crew)     – rate P-1, P-5, P-9   (only if needed)
6.  qc_autofix.py (Crew)  – patch any ❌
7.  htmlizer.py (Crew)    – plain-text → HTML

Each AI step logs tokens & latency via utils.db.log_prompt_output.
"""

from __future__ import annotations
import time, uuid, random
import streamlit as st
from crewai import Crew, Process

# ---------- project imports ------------------------------------------ #
from agents.writer import draft_writer_agent, build_writer_task
from agents.spam_remover import spam_removal_agent, build_remover_task, strip_markers
from agents.qc_tone import qc_tone_agent, build_tone_task
from agents.qc_autofix import qc_autofix_agent, build_autofix_task
from agents.htmlizer import htmlizer_agent, build_html_task
from scripts.spam_check import find_spam, highlight_spam
from scripts.qc_rules import run_qc
from utils.db import log_prompt_output
from utils.tokens import n_tokens

# ------------------- helper stubs you must implement ----------------- #
from utils.helpers import parse_full_date, as_text       #  ← add as_text
# --------------------------------------------------------------------- #

# ───────────────────────────── UI SETUP ─────────────────────────────── #
st.set_page_config(page_title="CFP Draft Generator", layout="wide")
st.title("📧 Call-for-Papers Draft Generator")

# Persistent state
if "step" not in st.session_state:
    st.session_state.step = 0          # 0 = input, 1 = draft, … 6 = html
if "run_id" not in st.session_state:
    st.session_state.run_id = str(uuid.uuid4())

# ═════════════════ 0 · INPUT FORM  (DB-driven) ════════════════════════ #
if st.session_state.step == 0:
    from utils.db import fetch_journals, fetch_domains               # NEW

    # ---- pull DB rows once ---------------------------------------------- #
    journals = fetch_journals() or []
    domains  = fetch_domains()  or []

    if not journals or not domains:
        st.error("🚨 Couldn’t load journals / domains from the database.")
        st.stop()

    j_titles = [j["journal_title"] for j in journals]
    d_names  = [d["domain_name"]   for d in domains]

    st.header("Select Journal & Domain")
    sel_journal_title = st.selectbox("Journal", j_titles)
    sel_domain_name   = st.selectbox("Domain",  d_names)

    journal = next(j for j in journals if j["journal_title"] == sel_journal_title)
    domain  = next(d for d in domains  if d["domain_name"]   == sel_domain_name)

    # -------- auto-populate (but still editable) ------------------------- #
    st.header("Details (editable)")
    journal_name  = st.text_input("Journal name",   journal["journal_title"])
    journal_short = st.text_input("Short name",     journal["short_title"])
    issn          = st.text_input("ISSN",           journal["issn"])
    impact_factor = st.text_input("Impact Factor",  str(journal.get("impact_factor", "")))
    domain_field  = st.text_input("Research field", domain["domain_name"])

    base_url      = domain["domain_url"].rstrip("/")
    submit_url    = st.text_input("Submission URL", f"{base_url}{journal['journal_path']}/submit-paper")

    cred_url_1    = st.text_input("Credibility link 1", f"{base_url}{journal['journal_path']}/about")
    cred_url_2    = st.text_input("Credibility link 2", f"{base_url}{journal['journal_path']}/editorial-board")

    sender_name   = st.text_input("Sender name",   journal.get("sender_full_name", ""))
    sender_email  = st.text_input("Sender e-mail", domain.get("sender_email", ""))

    deadline_raw  = st.text_input("Submission deadline (e.g. 31 July 2025)",
                                  (journal.get("next_deadline") or ""))

    # quick validation
    if deadline_raw and not parse_full_date(deadline_raw):
        st.warning("⚠️ Deadline is not a full date (‘31 July 2025’ or ‘July 31 2025’).")

    # ---------- go! ------------------------------------------------------- #
    if st.button("Generate first draft ✍️", type="primary"):
        ui_dict = dict(
            impact_factor=impact_factor,
            submission_deadline=deadline_raw,
            waiver_available=False, waiver_percentage=0,
            domain=domain_field, special_issue=False,
            submit_url=submit_url, url1=cred_url_1, url2=cred_url_2,
            sender_name=sender_name, sender_email=sender_email,
            template="",                           # you can still add a template later
        )
        waiver_dict = dict(level="❌ Minimal", last=None,
                           recommended_pct=0, waiver_msg="")

        writer_task = build_writer_task(
            journal_meta={
                "journal_title": journal_name,
                "short_title":   journal_short,
                "issn":          issn,
            },
            ui_inputs=ui_dict,
            waiver_info=waiver_dict,
            records=[],                            # recent rows not wired yet
        )

        t0   = time.time()
        crew = Crew(
        agents=[draft_writer_agent],
        tasks=[writer_task],
        process=Process.sequential,
        verbose=False,
        )

        result = crew.kickoff()

        st.session_state.draft_raw = result.raw or str(result)
        log_prompt_output(writer_task.description,
                          st.session_state.draft_raw,
                          draft_type="writer",
                          journal_title=journal_name,
                          model_name=draft_writer_agent.llm.model,
                          latency_ms=int((time.time() - t0) * 1000))
        st.session_state.step = 1
        st.experimental_rerun()


# ═════════════════ 1 · SPAM DETECTION ═════════════════════════════════ #
elif st.session_state.step == 1:
    st.header("Spam-word scan")
    draft_raw = st.session_state.draft_raw
    spam_hits = find_spam(draft_raw, exceptions={"deadline", "submission"})
    st.markdown(highlight_spam(draft_raw), unsafe_allow_html=True)
    st.info(f"Found {len(spam_hits)} spam hits: {', '.join(sorted(spam_hits))}"
            if spam_hits else "No spam words 🎉")

    if st.button("Clean spam words 🧹"):
        task = build_remover_task(draft_raw, list(spam_hits))
        t0 = time.time()
        crew = Crew(agents=[spam_removal_agent], tasks=[task],
                    process=Process.sequential, verbose=False)
        cleaned = strip_markers(crew.kickoff().raw or "")
        log_prompt_output(task.description, cleaned, "spam_remove",
                          journal_name, spam_removal_agent.llm.model,
                          int((time.time() - t0) * 1000))
        st.session_state.draft_clean = cleaned
        st.session_state.step = 2
        st.experimental_rerun()

# ═════════════════ 2 · QC SCRIPT ( + tone AI ) ════════════════════════ #
elif st.session_state.step == 2:
    draft = st.session_state.draft_clean
    qc = run_qc(draft, submit_url=submit_url)
    checklist = qc["checklist"]
    # ---- optional tone AI pass
    if qc["need_ai"]:
        tone_task = build_tone_task(draft)
        t0 = time.time()
        crew = Crew(agents=[qc_tone_agent], tasks=[tone_task],
                    process=Process.sequential, verbose=False)
        tone_lines = (crew.kickoff().raw or "").splitlines()
        checklist += [ln.strip() for ln in tone_lines if ln.strip()]
        log_prompt_output(tone_task.description, "\n".join(tone_lines),
                          "qc_tone", journal_name, qc_tone_agent.llm.model,
                          int((time.time() - t0) * 1000))

    st.subheader("QC checklist")
    for line in checklist:
        st.markdown(line)

    if all(l.startswith("✔") for l in checklist):
        st.success("All checks passed! → proceed to HTML")
        if st.button("Generate HTML"):
            st.session_state.step = 4
            st.experimental_rerun()
    else:
        st.error("Some ❌ found")
        if st.button("Auto-fix draft 🔧"):
            task, footer = build_autofix_task(
                draft_prompt="",
                original_draft=draft,
                quality_checklist="\n".join(checklist),
            )
            t0 = time.time()
            crew = Crew(agents=[qc_autofix_agent], tasks=[task],
                        process=Process.sequential, verbose=False)
            fixed_body = as_text(crew.kickoff())
            fixed = fixed_body + footer
            log_prompt_output(task.description, fixed, "qc_autofix",
                              journal_name, qc_autofix_agent.llm.model,
                              int((time.time() - t0) * 1000))
            st.session_state.draft_clean = fixed
            st.experimental_rerun()

# ═════════════════ 4 · HTMLIZER ═══════════════════════════════════════ #
elif st.session_state.step == 4:
    draft_final = st.session_state.draft_clean
    st.header("Generate HTML")
    task = build_html_task(draft_final)
    t0 = time.time()
    crew = Crew(agents=[htmlizer_agent], tasks=[task],
                process=Process.sequential, verbose=False)
    html_out = as_text(crew.kickoff())
    log_prompt_output(task.description, html_out, "htmlizer",
                      journal_name, htmlizer_agent.llm.model,
                      int((time.time() - t0) * 1000))

    st.subheader("Plain-text")
    st.text_area("Final draft", draft_final, height=400)
    st.subheader("HTML code")
    st.code(html_out, language="html")
    st.markdown("---")
    st.markdown(html_out, unsafe_allow_html=True)
    st.success("Pipeline complete 🚀")
