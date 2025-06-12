import streamlit as st
import pandas as pd
import json
import os

# Define the path to the CSV file
output_file = "analysis_interspire/outputs/draft_analysis.csv"

st.set_page_config(layout="wide")

st.title("Interspire Draft Analysis")

if os.path.exists(output_file):
    df = pd.read_csv(output_file)

    st.dataframe(
        df[["campaign_id","subject_line","overall_score","overall_compliance_status",
            "subject_overall_score","email_content_score","bounce_rate"]]
        .sort_values("overall_score", ascending=False),
        use_container_width=True
    )

    idx = st.selectbox("Inspect row #", df.index)
    row = df.loc[idx].to_dict()
    st.subheader("Full Details")
    for k,v in row.items():
        if k=="feedback_json":
            st.json(json.loads(v) if isinstance(v,str) else v)
        else:
            st.write(f"**{k}**: {v}")
else:
    st.warning(f"No analysis data found. Please run the scoring script first: `python -m analysis_interspire.cli.run_scoring`")
