import streamlit as st
import mysql.connector
import pandas as pd
import json
from interspire_composite_scorer import InterspireCompositeScorer
import os
from dotenv import load_dotenv

def get_sample_campaigns(limit=10):
    """Get sample campaigns from database for testing"""
    load_dotenv()
    config = {
        'host': os.getenv('DRAFTS_DB_HOST'),
        'user': os.getenv('DRAFTS_DB_USER'),
        'password': os.getenv('DRAFTS_DB_PASS'),
        'database': os.getenv('DRAFTS_DB_NAME'),
        'charset': 'utf8mb4'
    }
    
    conn = mysql.connector.connect(**config)
    query = """
    SELECT d.id, d.campaign_name, d.subject, d.email, d.journal, d.domain
    FROM interspire_data d
    LEFT JOIN interspire_analysis a ON d.id = a.campaign_id
    WHERE a.campaign_id IS NULL AND d.subject IS NOT NULL AND d.subject != ''
    LIMIT %s
    """
    
    df = pd.read_sql(query, conn, params=[limit])
    conn.close()
    return df

def analyze_campaign_preview(campaign_row):
    """Analyze a single campaign and return detailed results"""
    scorer = InterspireCompositeScorer()
    
    try:
        analysis_result = scorer.score_single_draft(
            campaign_row['id'],
            campaign_row['subject'],
            campaign_row['email'] or ''
        )
        return analysis_result
    except Exception as e:
        return {'error': str(e)}

def main():
    st.set_page_config(page_title="Analysis Preview", layout="wide")
    st.title("🔍 Campaign Analysis Preview")
    st.write("Test your analyzers before pushing to database")
    
    # Get sample campaigns
    if st.button("🔄 Load Sample Campaigns"):
        with st.spinner("Loading campaigns..."):
            campaigns_df = get_sample_campaigns(20)
            st.session_state.campaigns = campaigns_df
    
    if 'campaigns' in st.session_state and not st.session_state.campaigns.empty:
        st.subheader("📊 Sample Campaigns")
        
        # Display campaigns table
        st.dataframe(st.session_state.campaigns[['id', 'campaign_name', 'subject', 'journal']], 
                    use_container_width=True)
        
        # Select campaign to analyze
        campaign_ids = st.session_state.campaigns['id'].tolist()
        selected_id = st.selectbox("Select Campaign to Analyze", campaign_ids)
        
        if st.button("🧪 Analyze Selected Campaign"):
            selected_campaign = st.session_state.campaigns[
                st.session_state.campaigns['id'] == selected_id
            ].iloc[0]
            
            with st.spinner("Analyzing campaign..."):
                analysis_result = analyze_campaign_preview(selected_campaign)
            
            if 'error' in analysis_result:
                st.error(f"Analysis failed: {analysis_result['error']}")
            else:
                # Display analysis results
                st.subheader("📋 Analysis Results")
                
                # Campaign Info
                col1, col2 = st.columns(2)
                with col1:
                    st.write("**Campaign Details:**")
                    st.write(f"ID: {selected_campaign['id']}")
                    st.write(f"Subject: {selected_campaign['subject']}")
                    st.write(f"Journal: {selected_campaign['journal']}")
                
                with col2:
                    st.write("**Composite Scores:**")
                    composite = analysis_result.get('composite_scoring', {})
                    st.metric("Overall Score", f"{composite.get('weighted_composite', 0):.1f}/100")
                    st.metric("Subject Score", f"{composite.get('subject_score', 0):.1f}/100")
                    st.metric("Content Score", f"{composite.get('content_score', 0):.1f}/100")
                    st.metric("Confidence", composite.get('confidence_level', 'Unknown'))
                
                # Detailed Analysis Tabs
                tab1, tab2, tab3, tab4 = st.tabs(["Subject Analysis", "Content Analysis", "Feedback", "Raw Data"])
                
                with tab1:
                    subject_data = analysis_result.get('subject_analysis', {})
                    if subject_data:
                        st.write("**Length Analysis:**")
                        length_data = subject_data.get('length_analysis', {})
                        st.json(length_data)
                        
                        st.write("**Caps Analysis:**")
                        caps_data = subject_data.get('caps_analysis', {})
                        st.json(caps_data)
                        
                        st.write("**Spam Risk:**")
                        spam_data = subject_data.get('spam_risk', {})
                        st.json(spam_data)
                
                with tab2:
                    content_data = analysis_result.get('content_analysis', {})
                    if content_data:
                        st.write("**Intro Analysis:**")
                        intro_data = content_data.get('intro_analysis', {})
                        st.json(intro_data)
                        
                        st.write("**CTA Analysis:**")
                        cta_data = content_data.get('cta_analysis', {})
                        st.json(cta_data)
                        
                        st.write("**Domain Analysis:**")
                        domain_data = content_data.get('domain_analysis', {})
                        st.json(domain_data)
                
                with tab3:
                    feedback = analysis_result.get('overall_feedback', [])
                    if feedback:
                        st.write("**Recommendations:**")
                        for item in feedback:
                            st.write(f"• {item}")
                    
                    priority = analysis_result.get('improvement_priority', [])
                    if priority:
                        st.write("**Priority Improvements:**")
                        for i, item in enumerate(priority, 1):
                            st.write(f"{i}. {item}")
                
                with tab4:
                    st.write("**Complete Analysis Result:**")
                    st.json(analysis_result)
                
                # Database Preview
                st.subheader("🗄️ Database Mapping Preview")
                
                if st.button("🔍 Show Database Mapping"):
                    from batch_interspire_analysis import BatchInterspireAnalyzer
                    analyzer = BatchInterspireAnalyzer()
                    
                    db_mapping = analyzer.map_analysis_to_schema(selected_campaign['id'], analysis_result)
                    
                    st.write("**Data that would be inserted into database:**")
                    
                    # Display in a more readable format
                    for key, value in db_mapping.items():
                        if isinstance(value, (list, dict)):
                            st.write(f"**{key}:** {json.dumps(value, indent=2)}")
                        else:
                            st.write(f"**{key}:** {value}")
        
        # Batch Analysis Preview
        st.subheader("🚀 Batch Analysis Preview")
        
        if st.button("🧪 Analyze All Sample Campaigns"):
            progress_bar = st.progress(0)
            results = []
            
            for i, (_, campaign) in enumerate(st.session_state.campaigns.iterrows()):
                progress_bar.progress((i + 1) / len(st.session_state.campaigns))
                
                analysis_result = analyze_campaign_preview(campaign)
                
                if 'error' not in analysis_result:
                    composite = analysis_result.get('composite_scoring', {})
                    results.append({
                        'id': campaign['id'],
                        'subject': campaign['subject'][:50] + '...' if len(campaign['subject']) > 50 else campaign['subject'],
                        'overall_score': composite.get('weighted_composite', 0),
                        'subject_score': composite.get('subject_score', 0),
                        'content_score': composite.get('content_score', 0),
                        'confidence': composite.get('confidence_level', 'Unknown')
                    })
            
            if results:
                results_df = pd.DataFrame(results)
                st.write("**Batch Analysis Results:**")
                st.dataframe(results_df, use_container_width=True)
                
                # Summary statistics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Average Overall Score", f"{results_df['overall_score'].mean():.1f}")
                with col2:
                    st.metric("Average Subject Score", f"{results_df['subject_score'].mean():.1f}")
                with col3:
                    st.metric("Average Content Score", f"{results_df['content_score'].mean():.1f}")
                
                # Approval for database insertion
                st.subheader("✅ Ready for Database?")
                if st.button("🚀 Approve and Run Full Batch Analysis"):
                    st.success("Ready to run batch analysis! Use run_initial_analysis.py")
                    st.code("python run_initial_analysis.py")
    
    else:
        st.info("Click 'Load Sample Campaigns' to start testing")

if __name__ == "__main__":
    main()
