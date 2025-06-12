import streamlit as st
import pandas as pd
import mysql.connector
import os
from datetime import datetime, timedelta
from agent_ranking import AgentRanking
from database_sync_pipeline import get_campaign_count, get_last_sync_time # New import

st.set_page_config(layout="wide")

st.title("Email Campaign Ranking Agent")

# ADD: Database sync status at the top
st.header("📊 Campaign Database Status")

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Total Interspire Campaigns", get_campaign_count('interspire_data'))
with col2:
    st.metric("Total MailWizz Campaigns", get_campaign_count('mailwizz_data'))
with col3:
    st.metric("Last Sync", get_last_sync_time())

# Initialize AgentRanking (data loading and analysis happens here)
@st.cache_resource
def get_agent_ranker():
    return AgentRanking()

agent_ranker = get_agent_ranker()

def get_analysis_data():
    """Fetch analysis results from database"""
    config = {
        'host': os.getenv('DRAFTS_DB_HOST'),
        'user': os.getenv('DRAFTS_DB_USER'),
        'password': os.getenv('DRAFTS_DB_PASS'),
        'database': os.getenv('DRAFTS_DB_NAME'),
        'charset': 'utf8mb4'
    }
    
    conn = mysql.connector.connect(**config)
    
    query = """
    SELECT 
        d.id, d.campaign_name, d.subject, d.journal, d.domain,
        a.overall_score, a.confidence_level, a.subject_overall_score, 
        a.email_content_score, a.overall_compliance_status,
        a.analysis_date
    FROM interspire_data d
    JOIN interspire_analysis a ON d.id = a.campaign_id
    ORDER BY a.analysis_date DESC
    LIMIT 1000
    """
    
    df = pd.read_sql(query, conn)
    conn.close()
    return df

# Replace the manual draft sections with:
st.header("📊 Campaign Analysis Results (from Database)")

analysis_df = get_analysis_data()

if not analysis_df.empty:
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total Analyzed", len(analysis_df))
    with col2:
        st.metric("Avg Score", f"{analysis_df['overall_score'].mean():.1f}")
    with col3:
        st.metric("Pass Rate", f"{(analysis_df['overall_compliance_status'] == 'Pass').mean()*100:.1f}%")
    with col4:
        st.metric("High Confidence", f"{(analysis_df['confidence_level'] == 'High').sum()}")
    
    st.dataframe(analysis_df, use_container_width=True)
else:
    st.warning("No analysis data found. Run batch analysis first.")

st.header("4. Export & Next Steps")

col1, col2, col3 = st.columns(3)

with col1:
    if st.button("📊 Generate Report"):
        st.success("Report generation feature coming soon!")

with col2:
    if st.button("🧪 Suggest A/B Test"):
        st.info("A/B testing suggestions coming soon!")

with col3:
    if st.button("📤 Export to MailWizz"):
        st.info("MailWizz integration coming soon!")
