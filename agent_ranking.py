# agent_ranking.py

import pandas as pd
import re
import sqlite3 # Added for database access
from campaign_stats import get_interspire_campaign_stats, get_mailwizz_campaign_stats

class AgentRanking:
    def __init__(self):
        self.interspire_data = None
        self.mailwizz_data = None
        self.combined_data = None
        self.analysis_insights = {}
        self.journal_mapping = self._load_journal_mapping() # Load journal mapping
        self.load_data()

    def _load_journal_mapping(self):
        """
        Loads the mapping from full journal names to short names from journal_data.db.
        """
        db_path = 'journal_data.db' # Assuming this path
        mapping = {}
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT journal_title, short_title FROM journal_details") # Assuming 'journals' table with 'full_name', 'short_name'
            for row in cursor.fetchall():
                mapping[row[0]] = row[1]
            conn.close()
            print(f"Loaded {len(mapping)} journal mappings from {db_path}.")
        except sqlite3.Error as e:
            print(f"Error loading journal mapping from {db_path}: {e}")
        return mapping

    def _apply_journal_mapping(self, journal_name):
        """
        Applies the journal mapping, trying various matching strategies.
        """
        if not isinstance(journal_name, str):
            return journal_name # Return as is if not a string

        original_journal_name_stripped = journal_name.strip()

        # 1. Try direct match (case-sensitive)
        if original_journal_name_stripped in self.journal_mapping:
            return self.journal_mapping[original_journal_name_stripped]

        # 2. Try case-insensitive match
        for full_name, short_name in self.journal_mapping.items():
            if full_name.strip().lower() == original_journal_name_stripped.lower():
                return short_name

        # 3. Strip "Journal of" and try matches again
        journal_name_without_prefix = re.sub(r'Journal of\s*', '', original_journal_name_stripped, flags=re.IGNORECASE).strip()

        if journal_name_without_prefix in self.journal_mapping:
            return self.journal_mapping[journal_name_without_prefix]

        for full_name, short_name in self.journal_mapping.items():
            if full_name.strip().lower() == journal_name_without_prefix.lower():
                return short_name

        # 4. Partial matching (after stripping "Journal of")
        # This is more complex and might lead to false positives.
        # I will prioritize matching the start of the full name.
        for full_name, short_name in self.journal_mapping.items():
            full_name_stripped = full_name.strip().lower()
            if journal_name_without_prefix.lower() in full_name_stripped:
                return short_name # Return the first partial match

        return journal_name # Return original if no match found

    def _extract_short_title_from_campaign_name(self, campaign_name):
        """
        Attempts to extract a short title (acronym) from the campaign name using various patterns,
        and validates it against the known short titles in journal_mapping.
        """
        if not isinstance(campaign_name, str):
            return None

        # Get all known short titles from the mapping for validation
        known_short_titles = set(self.journal_mapping.values())

        # Patterns to try, in order of preference
        patterns = [
            r'(?:CFP_|OPEN_)([A-Z0-9]{2,})', # e.g., CFP_JAN_Issue1
            r'^([A-Z0-9]{2,})_',  # JAN_CampaignUpdate
            r'^([A-Z0-9]{2,})-',  # JAN-CampaignUpdate
            r'_([A-Z0-9]{2,})_', # e.g., Campaign_JAN_Update
            r'-([A-Z0-9]{2,})-', # e.g., Campaign-JAN-Update
            r'_([A-Z0-9]{2,})-', # e.g., Campaign_JAN-Update
            r'-([A-Z0-9]{2,})_', # e.g., Campaign-JAN_Update
        ]

        # Iterate through the campaign name to find all possible matches
        # and check if they are valid short titles.
        # This approach will find the first valid short title based on pattern order and position.
        for pattern in patterns:
            # Use finditer to get all non-overlapping matches
            for match in re.finditer(pattern, campaign_name, re.IGNORECASE):
                extracted_short_title = match.group(1).upper()
                if extracted_short_title in known_short_titles:
                    return extracted_short_title

        return None # No valid short title found

    def extract_journal_interspire(self, campaign_name):
        """
        Extracts Journal from Campaign Name for Interspire data.
        Moved to be a method of the class.
        """
        match = re.search(r'(?:CFP_|OPEN_)(.*?)(?:_|$)', campaign_name, re.IGNORECASE)
        return match.group(1) if match else 'Unknown'

    def load_data(self):
        """
        Loads historical campaign data from Interspire and MailWizz.
        Standardizes the data into pandas DataFrames.
        """
        print("Loading Interspire campaign data...")
        interspire_raw = get_interspire_campaign_stats()
        self.interspire_data = self._standardize_interspire_data(interspire_raw)
        print(f"Loaded {len(self.interspire_data)} rows from Interspire.")

        print("Loading MailWizz campaign data...")
        mailwizz_raw = get_mailwizz_campaign_stats()
        self.mailwizz_data = self._standardize_mailwizz_data(mailwizz_raw)
        print(f"Loaded {len(self.mailwizz_data)} rows from MailWizz.")

        self._combine_data()
        self.analyze_data()

    def _standardize_interspire_data(self, data):
        """
        Standardizes Interspire campaign data into a DataFrame.
        Extracts Journal from Campaign Name.
        """
        if not data:
            return pd.DataFrame(columns=['Source', 'Subject', 'Campaign Name', 'Journal', 'Opens', 'Clicks', 'Bounces', 'Email', 'Sent By'])

        df = pd.DataFrame(data)
        df['Source'] = 'Interspire'
        
        # Rename columns to match the required fields
        df = df.rename(columns={
            'subject': 'Subject',
            'campaign_name': 'Campaign Name',
            'unique_opens': 'Opens', # Use unique opens
            'unique_clicks': 'Clicks', # Use unique clicks
            'bouncecount_hard': 'Bounces',
            'textbody': 'Email',
            'domain': 'Domain', # Use the new 'domain' field
            'sendsize': 'Sent Count' # Add Sent Count
        })

        # Apply mapping and fallback to campaign name short title
        def get_final_journal(row):
            journal_candidate = self.extract_journal_interspire(row['Campaign Name'])
            mapped_journal = self._apply_journal_mapping(journal_candidate.strip() if isinstance(journal_candidate, str) else journal_candidate)

            if mapped_journal == (journal_candidate.strip() if isinstance(journal_candidate, str) else journal_candidate):
                # If mapping failed, try to extract from campaign name
                short_title_from_campaign = self._extract_short_title_from_campaign_name(row['Campaign Name'])
                if short_title_from_campaign:
                    return short_title_from_campaign
            return mapped_journal

        df['Journal'] = df.apply(get_final_journal, axis=1)

        # Determine Draft Type (simple heuristic based on Subject/Campaign Name)
        def determine_draft_type(row):
            subject = row['Subject'].lower() if pd.notna(row['Subject']) else ''
            campaign_name_val = row['Campaign Name'].lower() if pd.notna(row['Campaign Name']) else ''
            
            if 'cfp' in subject or 'cfp' in campaign_name_val:
                return 'CFP'
            elif 'open' in subject or 'open' in campaign_name_val:
                return 'Open'
            else:
                return 'General'

        df['Draft Type'] = df.apply(determine_draft_type, axis=1)
        
        # Ensure all required columns are present, fill missing with None or appropriate default
        required_cols = ['Source', 'Subject', 'Campaign Name', 'Journal', 'Opens', 'Clicks', 'Bounces', 'Email', 'Sent Count', 'Domain', 'Draft Type']
        for col in required_cols:
            if col not in df.columns:
                df[col] = None # Or a suitable default value

        return df[required_cols]

    def _standardize_mailwizz_data(self, data):
        """
        Standardizes MailWizz campaign data into a DataFrame.
        """
        if not data:
            return pd.DataFrame(columns=['Source', 'Subject', 'Campaign Name', 'Journal', 'Opens', 'Clicks', 'Bounces', 'Email', 'Sent By', 'Sent Count', 'Domain', 'Draft Type'])

        df = pd.DataFrame(data)
        df['Source'] = 'MailWizz'

       # Rename columns to match the required fields
        df = df.rename(columns={
            'subject':        'Subject',
            'campaign_name':  'Campaign Name',   # ← use the SQL alias
            # keep the old fallback, just in case
            'name':           'Campaign Name',
            'journal':      'Journal',
            'opens':          'Opens',
            'clicks':         'Clicks',
            'bounces':        'Bounces',
            'email_body':     'Email',
            'from_email':     'Sent By'
        })

        # MailWizz data now provides 'sent_count'
        df['Sent Count'] = df['sent_count']

        # Apply journal mapping and fallback to campaign name short title
        def get_final_journal(row):
            journal_candidate = row['Journal'] # This is the 'journal' field from raw data
            mapped_journal = self._apply_journal_mapping(journal_candidate.strip() if isinstance(journal_candidate, str) else journal_candidate)

            if mapped_journal == (journal_candidate.strip() if isinstance(journal_candidate, str) else journal_candidate):
                # If mapping failed, try to extract from campaign name
                short_title_from_campaign = self._extract_short_title_from_campaign_name(row['Campaign Name'])
                if short_title_from_campaign:
                    return short_title_from_campaign
            return mapped_journal

        df['Journal'] = df.apply(get_final_journal, axis=1)

        # Extract Domain from 'Sent By' email
        df['Domain'] = df['Sent By'].apply(lambda x: x.split('@')[-1] if isinstance(x, str) and '@' in x else 'Unknown')

        # Determine Draft Type (simple heuristic based on Subject/Campaign Name)
        def determine_draft_type(row):
            subject = row['Subject'].lower() if pd.notna(row['Subject']) else ''
            campaign_name_val = row['Campaign Name'].lower() if pd.notna(row['Campaign Name']) else ''
            
            if 'cfp' in subject or 'cfp' in campaign_name_val:
                return 'CFP'
            elif 'open' in subject or 'open' in campaign_name_val:
                return 'Open'
            else:
                return 'General'

        df['Draft Type'] = df.apply(determine_draft_type, axis=1)
        
        # Ensure all required columns are present, fill missing with None or appropriate default
        required_cols = ['Source', 'Subject', 'Campaign Name', 'Journal', 'Opens', 'Clicks', 'Bounces', 'Email', 'Sent By', 'Sent Count', 'Domain', 'Draft Type']
        for col in required_cols:
            if col not in df.columns:
                df[col] = None # Or a suitable default value

        return df[required_cols]

    def _combine_data(self):
        """Combines Interspire and MailWizz data into a single DataFrame."""
        self.combined_data = pd.concat([self.interspire_data, self.mailwizz_data], ignore_index=True)
        print(f"Combined data has {len(self.combined_data)} rows.")

    def analyze_data(self):
        """
        Analyzes the combined historical data to identify patterns and insights.
        """
        if self.combined_data is None or self.combined_data.empty:
            print("No data to analyze.")
            return

        print("Analyzing data for insights...")
        
        # Calculate engagement rates
        # Ensure 'Sent Count' is numeric and handle division by zero
        self.combined_data['Sent Count'] = pd.to_numeric(self.combined_data['Sent Count'], errors='coerce').fillna(1)
        self.combined_data['Opens'] = pd.to_numeric(self.combined_data['Opens'], errors='coerce').fillna(0)
        self.combined_data['Clicks'] = pd.to_numeric(self.combined_data['Clicks'], errors='coerce').fillna(0)
        self.combined_data['Bounces'] = pd.to_numeric(self.combined_data['Bounces'], errors='coerce').fillna(0)

        self.combined_data['Open Rate'] = (self.combined_data['Opens'] / self.combined_data['Sent Count']).fillna(0)
        self.combined_data['Click Rate'] = (self.combined_data['Clicks'] / self.combined_data['Opens'].apply(lambda x: x if x > 0 else 1)).fillna(0) # CTR based on Opens
        self.combined_data['Bounce Rate'] = (self.combined_data['Bounces'] / self.combined_data['Sent Count']).fillna(0)

        # Patterns in high-performing subject lines (example: top 10% open rate)
        # Filter out rows where 'Open Rate' might be NaN due to division by zero if 'Sent Count' was 0
        high_performing_emails = self.combined_data[self.combined_data['Open Rate'].notna() & (self.combined_data['Open Rate'] >= self.combined_data['Open Rate'].quantile(0.9))]
        
        effective_keywords = {}
        if not high_performing_emails.empty:
            all_subjects = " ".join(high_performing_emails['Subject'].dropna().tolist())
            # Simple keyword extraction (can be improved with NLP)
            words = re.findall(r'\b\w+\b', all_subjects.lower())
            from collections import Counter
            keyword_counts = Counter(words)
            effective_keywords = {word: count for word, count in keyword_counts.most_common(10)}
        
        self.analysis_insights['effective_keywords'] = effective_keywords
        
        # Negative patterns (example: high bounce rate)
        high_bounce_emails = self.combined_data[self.combined_data['Bounce Rate'] >= self.combined_data['Bounce Rate'].quantile(0.9)]
        negative_patterns = {}
        if not high_bounce_emails.empty:
            all_subjects_bounced = " ".join(high_bounce_emails['Subject'].dropna().tolist())
            words_bounced = re.findall(r'\b\w+\b', all_subjects_bounced.lower())
            from collections import Counter
            negative_keyword_counts = Counter(words_bounced)
            negative_patterns = {word: count for word, count in negative_keyword_counts.most_common(10)}

        self.analysis_insights['negative_patterns'] = negative_patterns

        # Add more actionable insights here based on analysis
        # For example, subject line length, presence of numbers/emojis, etc.
        # This is a placeholder for more sophisticated analysis.
        self.analysis_insights['recommended_subject_line_structures'] = [
            "Start with a clear call to action (e.g., 'CFP: ...')",
            "Include relevant keywords identified as effective.",
            "Avoid keywords identified as negative patterns."
        ]
        self.analysis_insights['formatting_tips'] = [
            "Use clear and concise language.",
            "Ensure mobile-friendliness for email body.",
            "Personalization (if data available) can increase engagement."
        ]

        print("Data analysis complete. Insights stored.")

    def get_campaign_data(self, source=None):
        """
        Returns the standardized campaign data.
        :param source: 'Interspire', 'MailWizz', or None for combined data.
        :return: pandas DataFrame containing campaign data.
        """
        if source == 'Interspire':
            return self.interspire_data
        elif source == 'MailWizz':
            return self.mailwizz_data
        else:
            return self.combined_data

    def get_analysis_insights(self):
        """
        Returns the analysis insights, including effective keywords, negative patterns,
        recommended subject line structures, and formatting tips.
        :return: Dictionary of analysis insights.
        """
        return self.analysis_insights

    def display_data_table(self, df, filters=None):
        """
        Displays the given DataFrame, optionally filtered.
        :param df: pandas DataFrame to display.
        :param filters: Dictionary of filters, e.g., {'Journal': 'Example Journal', 'Domain': 'example.com'}.
        """
        if df is None or df.empty:
            print("No data to display.")
            return pd.DataFrame()

        filtered_df = df.copy()
        if filters:
            for column, value in filters.items():
                if column in filtered_df.columns:
                    filtered_df = filtered_df[filtered_df[column].astype(str).str.contains(str(value), case=False, na=False)]
        
        print("\n--- Filtered Campaign Data ---")
        print(filtered_df.to_string())
        print("------------------------------")
        return filtered_df

    def score_draft(self, draft):
        """
        Scores a new email draft based on analysis insights.
        :param draft: Dictionary with at least 'Subject' and 'Email Preview' (Email).
        :return: Detailed score/report.
        """
        score = {
            'subject_effectiveness_score': 0,
            'predicted_open_potential': 0,
            'predicted_click_potential': 0,
            'bounce_risk': 0,
            'overall_engagement_potential': 0,
            'feedback': []
        }

        subject = draft.get('Subject', '').lower()
        email_preview = draft.get('Email', '').lower()

        # Subject line effectiveness
        subject_keywords_score = 0
        feedback_subject = []
        for keyword, count in self.analysis_insights.get('effective_keywords', {}).items():
            if keyword in subject:
                subject_keywords_score += count
                feedback_subject.append(f"Contains effective keyword: '{keyword}'")
        score['subject_effectiveness_score'] = subject_keywords_score
        score['feedback'].extend(feedback_subject)

        # Bounce risk
        bounce_score = 0
        feedback_bounce = []
        for keyword, count in self.analysis_insights.get('negative_patterns', {}).items():
            if keyword in subject:
                bounce_score += count
                feedback_bounce.append(f"Contains high-bounce keyword: '{keyword}'")
        score['bounce_risk'] = bounce_score
        score['feedback'].extend(feedback_bounce)

        # Placeholder for predicted open/click potential (requires more advanced NLP/ML)
        # For now, a simple heuristic: higher subject effectiveness, lower bounce risk -> higher potential
        score['predicted_open_potential'] = max(0, score['subject_effectiveness_score'] - score['bounce_risk'])
        score['predicted_click_potential'] = max(0, score['subject_effectiveness_score'] - score['bounce_risk']) # Simplified

        # Overall engagement potential
        score['overall_engagement_potential'] = (
            score['predicted_open_potential'] * 0.5 +
            score['predicted_click_potential'] * 0.3 -
            score['bounce_risk'] * 0.2
        )
        
        if not score['feedback']:
            score['feedback'].append("No specific insights found for this draft based on current analysis.")

        return score

    def rank_drafts(self, drafts):
        """
        Scores a list of drafts and ranks them from most to least promising.
        :param drafts: List of draft dictionaries.
        :return: List of ranked drafts with their scores and confidence.
        """
        scored_drafts = []
        for i, draft in enumerate(drafts):
            draft_score = self.score_draft(draft)
            scored_drafts.append({
                'draft_id': i, # Simple ID for tracking
                'draft': draft,
                'score': draft_score,
                'ranking_score': draft_score['overall_engagement_potential'],
                'confidence': "Medium" # Placeholder, can be refined
            })
        
        # Rank by overall_engagement_potential in descending order
        ranked_drafts = sorted(scored_drafts, key=lambda x: x['ranking_score'], reverse=True)

        # Add rank and explanation
        for i, ranked_draft in enumerate(ranked_drafts):
            ranked_draft['rank'] = i + 1
            ranked_draft['explanation'] = f"Ranked {ranked_draft['rank']} based on overall engagement potential ({ranked_draft['ranking_score']:.2f}). Feedback: {'; '.join(ranked_draft['score']['feedback'])}"
        
        return ranked_drafts

# Example Usage (for testing purposes)
if __name__ == "__main__":
    agent_ranker = AgentRanking()

    # Display Interspire data
    print("\n--- Interspire Data ---")
    agent_ranker.display_data_table(agent_ranker.get_campaign_data(source='Interspire'))

    # Display MailWizz data
    print("\n--- MailWizz Data ---")
    agent_ranker.display_data_table(agent_ranker.get_campaign_data(source='MailWizz'))

    # Display combined data with a filter
    print("\n--- Combined Data (Filtered by Journal 'Unknown') ---")
    agent_ranker.display_data_table(agent_ranker.get_campaign_data(), filters={'Journal': 'Unknown'})

    # Example Draft Scoring
    print("\n--- Draft Scoring Example ---")
    draft1 = {
        'Subject': 'CFP_JournalX_SpecialIssue: Call for Papers on AI in Healthcare',
        'Email': 'Dear Author, We invite you to submit your research...'
    }
    draft2 = {
        'Subject': 'Important Update: New Guidelines for Submissions',
        'Email': 'Please review the updated submission guidelines...'
    }
    draft3 = {
        'Subject': 'Free Webinar: Boost Your Research Impact',
        'Email': 'Join our exclusive webinar to learn strategies...'
    }

    score1 = agent_ranker.score_draft(draft1)
    print(f"\nScore for Draft 1 (Subject: '{draft1['Subject']}'):\n{score1}")

    score2 = agent_ranker.score_draft(draft2)
    print(f"\nScore for Draft 2 (Subject: '{draft2['Subject']}'):\n{score2}")

    # Example Draft Ranking
    print("\n--- Draft Ranking Example ---")
    drafts_to_rank = [draft1, draft2, draft3]
    ranked_drafts = agent_ranker.rank_drafts(drafts_to_rank)

    for ranked_draft in ranked_drafts:
        print(f"\nRank {ranked_draft['rank']}:")
        print(f"  Subject: {ranked_draft['draft']['Subject']}")
        print(f"  Overall Score: {ranked_draft['ranking_score']:.2f}")
        print(f"  Confidence: {ranked_draft['confidence']}")
        print(f"  Explanation: {ranked_draft['explanation']}")

    print("\n--- Analysis Insights ---")
    print("Effective Keywords:", agent_ranker.analysis_insights.get('effective_keywords'))
    print("Negative Patterns:", agent_ranker.analysis_insights.get('negative_patterns'))
