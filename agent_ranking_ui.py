import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from agent_ranking import AgentRanking

st.set_page_config(layout="wide")

st.title("Email Campaign Ranking Agent")

# Initialize AgentRanking (data loading and analysis happens here)
@st.cache_resource
def get_agent_ranker():
    return AgentRanking()

agent_ranker = get_agent_ranker()

st.header("1. Historical Data Ingestion")
historical_df = agent_ranker.get_campaign_data()

if historical_df.empty:
    st.warning("No historical data ingested. Please ensure data sources are available and .env is configured.")
else:
    st.write(f"Successfully ingested {len(historical_df)} historical records.")
    st.dataframe(historical_df.head())

# Display Interspire and MailWizz data separately as requested in the initial prompt
st.subheader("Interspire Data")
interspire_df = agent_ranker.get_campaign_data(source='Interspire')
if not interspire_df.empty:
    st.dataframe(interspire_df)
else:
    st.info("No Interspire data available.")

st.subheader("MailWizz Data")
mailwizz_df = agent_ranker.get_campaign_data(source='MailWizz')
if not mailwizz_df.empty:
    st.dataframe(mailwizz_df)
else:
    st.info("No MailWizz data available.")

st.header("2. Draft Scoring & Analysis")

# Single draft input form
with st.form("single_draft_analysis"):
    st.subheader("📧 Analyze Email Draft")
    
    col1, col2 = st.columns([1, 2])
    with col1:
        draft_subject = st.text_input(
            "Subject Line", 
            placeholder="Call for Papers: AI Conference 2025"
        )
    
    with col2:
        draft_content = st.text_area(
            "Email Content (HTML or Plain Text)",
            placeholder="<p>Dear Researcher...</p>",
            height=200
        )
    
    analyze_button = st.form_submit_button("🔍 Analyze Draft", use_container_width=True)

if analyze_button and draft_subject and draft_content:
    # Use your composite scorer
    from interspire_composite_scorer import InterspireCompositeScorer
    
    scorer = InterspireCompositeScorer()
    analysis = scorer.score_single_draft(draft_subject, draft_content)
    
    # Display composite score prominently
    st.subheader("📊 Overall Performance Score")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(
            "Composite Score", 
            f"{analysis['composite_scoring']['weighted_composite']:.1f}/100",
            help="Combined subject (40%) + content (30%) + baseline (30%)"
        )
    with col2:
        st.metric(
            "Confidence Level", 
            analysis['composite_scoring']['confidence_level']
        )
    with col3:
        performance = analysis['performance_prediction']
        st.metric(
            "Risk Level", 
            performance['risk_assessment']
        )

    # Detailed scoring breakdown
    st.subheader("📋 Detailed Analysis")
    
    tab1, tab2, tab3 = st.tabs(["Subject Analysis", "Content Analysis", "Recommendations"])
    
    with tab1:
        subject_data = analysis['subject_analysis']
        
        # Subject score components
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Subject Score", f"{analysis['composite_scoring']['subject_score']:.1f}/100")
            st.write(f"**Length:** {subject_data['length_analysis']['character_count']} chars")
            st.write(f"**Caps Ratio:** {subject_data['caps_analysis']['caps_percentage']:.1f}%")
        
        with col2:
            st.write("**Compliance Status:**")
            compliance = subject_data.get('compliance_report', {})
            for rule, status in compliance.items():
                icon = "✅" if status.get('status') == 'Pass' else "❌"
                st.write(f"{icon} {rule.replace('_', ' ').title()}")
    
    with tab2:
        content_data = analysis['content_analysis']
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Content Score", f"{analysis['composite_scoring']['content_score']:.1f}/100")
            st.write(f"**Intro Length:** {content_data['intro_analysis']['word_count']} words")
            st.write(f"**CTA Count:** {content_data['cta_analysis']['cta_count']}")
        
        with col2:
            st.write(f"**External Domains:** {content_data['domain_analysis']['external_domain_count']}")
            st.write(f"**Bullets Found:** {'Yes' if content_data['bullet_analysis']['bullets_found'] else 'No'}")
    
    with tab3:
        st.write("**Priority Improvements:**")
        for i, suggestion in enumerate(analysis['improvement_priority'], 1):
            st.write(f"{i}. {suggestion}")
        
        st.write("**Detailed Feedback:**")
        for feedback in analysis['overall_feedback']:
            st.info(feedback)

st.header("3. Multi-Draft Comparison")

# Multiple draft input
num_drafts = st.slider("Number of drafts to compare", 2, 5, 3)

drafts_to_compare = []
for i in range(num_drafts):
    with st.expander(f"📝 Draft {i+1}", expanded=(i==0)):
        col1, col2 = st.columns([1, 2])
        with col1:
            subject = st.text_input(f"Subject {i+1}", key=f"multi_subject_{i}")
        with col2:
            content = st.text_area(f"Content {i+1}", key=f"multi_content_{i}", height=100)
        
        if subject and content:
            drafts_to_compare.append({
                'id': f"Draft {i+1}",
                'subject': subject,
                'content': content
            })

if st.button("🏆 Compare Drafts") and len(drafts_to_compare) >= 2:
    # Score all drafts
    scorer = InterspireCompositeScorer()
    scored_drafts = []
    
    for draft in drafts_to_compare:
        analysis = scorer.score_single_draft(draft['subject'], draft['content'])
        analysis['draft_info'] = draft
        scored_drafts.append(analysis)
    
    # Sort by composite score
    scored_drafts.sort(key=lambda x: x['composite_scoring']['weighted_composite'], reverse=True)
    
    # Display ranking
    st.subheader("🏅 Draft Rankings")
    
    for rank, draft in enumerate(scored_drafts, 1):
        with st.container():
            col1, col2, col3, col4 = st.columns([1, 3, 1, 1])
            
            with col1:
                if rank == 1:
                    st.write("🥇")
                elif rank == 2:
                    st.write("🥈")
                elif rank == 3:
                    st.write("🥉")
                else:
                    st.write(f"#{rank}")
            
            with col2:
                st.write(f"**{draft['draft_info']['id']}**")
                st.write(f"Subject: {draft['draft_info']['subject'][:50]}...")
            
            with col3:
                st.metric("Score", f"{draft['composite_scoring']['weighted_composite']:.1f}")
            
            with col4:
                st.write(draft['composite_scoring']['confidence_level'])
            
            st.divider()

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
