import streamlit as st
import pandas as pd

from db import (
    fetch_distinct_draft_types,
    fetch_distinct_journals,
    fetch_campaigns,
    fetch_draft,
    fetch_distinct_scenarios,   # ⬅️  new helper in db.py
    save_analysis,
)
from agent import analyse        # analyse() now accepts preset_scenario

st.set_page_config(page_title="Scenario Checker", layout="wide")
st.title("📧 Newsletter Scenario-Checker")

# ── 1️⃣ draft-type filter ─────────────────────────────────────────
draft_types  = ["All"] + fetch_distinct_draft_types()
draft_choice = st.sidebar.selectbox("Draft type", draft_types)
dt_filter    = None if draft_choice == "All" else draft_choice

# ── 2️⃣ journal filter ────────────────────────────────────────────
journal_list = fetch_distinct_journals(dt_filter)
journal      = st.sidebar.selectbox("Journal", journal_list)

# ── 2️⃣ ½ scenario pre-select / new ───────────────────────────────
if journal:
    known_scenarios = fetch_distinct_scenarios(journal)
    scenario_key    = f"scenario_{journal}"
    scenario_pick   = st.sidebar.selectbox(
        "Scenario (pick or type new)",
        ["<type new>"] + known_scenarios,
        key=scenario_key,
    )
    if scenario_pick == "<type new>":
        scenario_pick = st.sidebar.text_input("Enter new scenario").strip()

# ── 3️⃣ show campaigns table ─────────────────────────────────────
if journal:
    rows = fetch_campaigns(journal, dt_filter)
    if not rows:
        st.warning("No campaigns match this journal / draft-type.")
        st.stop()

    st.subheader(f"Campaigns for **{journal}** ({draft_choice})")

    df = (pd.DataFrame(rows)
            .sort_values("created_at", ascending=False)
            .reset_index(drop=True))
    st.dataframe(df, height=380, use_container_width=True)

    # ── build TODO list (Not analysed only) ──────────────────────
    df_todo = df[df["status"] == "Not analysed"]
    if df_todo.empty:
        st.info("All drafts in this filter are already analysed ✅")
        st.stop()

    labels = (
        df_todo["newsletterid"].astype(str)
        + " | " + df_todo["subject"].str.slice(0, 60)
    )
    selected_labels = st.multiselect(
        "Pick up to 10 drafts to analyse",
        options=labels.tolist(),
        max_selections=10,
        key=f"todo_{journal}_{draft_choice}",
    )
    selected_ids = [int(lbl.split(" | ")[0]) for lbl in selected_labels]

    # ── 4️⃣ analyse button ───────────────────────────────────────
    if st.button(f"Analyse {len(selected_ids)} selected draft(s)"):
        if not selected_ids:
            st.info("Select at least one draft.")
            st.stop()
        if not scenario_pick:
            st.info("Please choose or type a scenario first.")
            st.stop()

        analysed, panels = 0, []
        with st.spinner("Calling Llama 4 …"):
            for nid in selected_ids:
                draft = fetch_draft(nid)
                if not draft:
                    st.warning(f"id {nid}: draft not found / stale")
                    continue
                try:
                    result = analyse(draft, scenario_pick)   #  ⬅️  pass hint
                    save_analysis(
                        draft["newsletterid"],
                        result,
                        draft["htmlbody"],
                        journal,
                        draft_choice if draft_choice != "All" else draft["draft_type"],
                    )
                    analysed += 1
                    panels.append({
                        "nid": nid,
                        "subject": draft["subject"],
                        "html": draft["htmlbody"],
                        "text": draft["textbody"],
                        "output": result,
                    })
                except Exception as exc:
                    st.error(f"id {nid}: {exc}")

        st.success(f"Finished. {analysed} draft(s) analysed ✅")

        # ── 5️⃣ show each draft + JSON output ───────────────────
        for p in panels:
            with st.expander(f'📧 {p["nid"]} — {p["subject"]}', expanded=False):
                st.markdown("#### HTML body", unsafe_allow_html=True)
                st.markdown(p["html"], unsafe_allow_html=True)

                st.markdown("#### Plain-text body")
                st.code(p["text"] or "(empty)", language="markdown")

                st.markdown("#### Analysis JSON")
                st.json(p["output"])
