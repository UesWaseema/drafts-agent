import mysql.connector
import pandas as pd
import json
import logging
from datetime import datetime
import os
from dotenv import load_dotenv

# Import the EXISTING analyzer files - use these exactly as implemented
from py_scripts_old.interspire_subject_analyzer import InterspireSubjectAnalyzer
from py_scripts_old.interspire_content_analyzer import InterspireContentAnalyzer
from py_scripts_old.interspire_composite_scorer import InterspireCompositeScorer

class BatchInterspireAnalyzer:
    def __init__(self):
        load_dotenv()
        self.db_config = {
            'host': os.getenv('DRAFTS_DB_HOST'),
            'user': os.getenv('DRAFTS_DB_USER'),
            'password': os.getenv('DRAFTS_DB_PASS'),
            'database': os.getenv('DRAFTS_DB_NAME'),
            'charset': 'utf8mb4'
        }
        
        # Use the EXISTING composite scorer - do not modify its logic
        self.scorer = InterspireCompositeScorer()
        self.setup_logging()

        # Log the method signature for debugging
        import inspect
        sig = inspect.signature(self.scorer.score_single_draft)
        self.logger.info(f"InterspireCompositeScorer.score_single_draft signature: {sig}")
        print(f"🔍 Method signature: score_single_draft{sig}")
    
    def setup_logging(self):
        os.makedirs("logs", exist_ok=True)
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler("logs/batch_analysis.log"),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def get_unanalyzed_campaigns(self):
        """Get campaigns from interspire_data that don't have analysis"""
        try:
            conn = mysql.connector.connect(**self.db_config)
            cursor = conn.cursor(dictionary=True)
            
            query = """
            SELECT d.id, d.campaign_name, d.subject, d.email, d.journal, d.domain, d.draft_type
            FROM interspire_data d
            LEFT JOIN interspire_analysis a ON d.id = a.campaign_id
            WHERE a.campaign_id IS NULL AND d.subject IS NOT NULL AND d.subject != ''
            """
            
            cursor.execute(query)
            campaigns = cursor.fetchall()
            
            conn.close()
            return campaigns
            
        except Exception as e:
            self.logger.error(f"Failed to get unanalyzed campaigns: {e}")
            return []
    
    def analyze_single_campaign(self, campaign_row):
        """Analyze one campaign using EXISTING composite scorer"""
        self.logger.debug(f"[RULE] Draft {campaign_row['id']} | Subject='{campaign_row['subject']}' | Body[0:80]='{(campaign_row['email'] or '')[:80].replace(chr(10),' ')}'")
        try:
            # Try the 3-parameter version first
            try:
                analysis_result = self.scorer.score_single_draft(
                    campaign_row['id'],           # draft_id
                    campaign_row['subject'],      # subject_line
                    campaign_row['email'] or ''   # email_content
                )
            except TypeError as e:
                if "missing" in str(e) or "takes" in str(e):
                    # Fall back to 2-parameter version (though we know it's 3 now)
                    analysis_result = self.scorer.score_single_draft(
                        campaign_row['subject'],      # subject_line
                        campaign_row['email'] or ''   # email_content
                    )
                else:
                    raise e
            
            # Add debug logging after analysis_result
            self.logger.debug(f"[RULE] Draft {campaign_row['id']} | First composite_scoring keys: {list(analysis_result.get('composite_scoring', {}).items())[:3]}")
            
            # Map the EXISTING analysis result structure to database schema
            return self.map_analysis_to_schema(campaign_row['id'], analysis_result)
            
        except Exception as e:
            self.logger.error(f"Failed to analyze campaign {campaign_row['id']}: {e}")
            return None
    
    def map_analysis_to_schema(self, campaign_id, analysis_result):
        """Map the EXISTING InterspireCompositeScorer output to database schema"""
        
        subject_analysis = analysis_result.get('subject_analysis', {})
        content_analysis = analysis_result.get('content_analysis', {})
        composite_scoring = analysis_result.get('composite_scoring', {})
        
        # Extract subject data using CORRECT field names from your analyzers
        length_analysis = subject_analysis.get('length_analysis', {})
        caps_analysis = subject_analysis.get('caps_analysis', {})
        spam_risk = subject_analysis.get('spam_risk', {})
        keyword_boost = subject_analysis.get('keyword_boost', {})
        punctuation_validation = subject_analysis.get('punctuation_validation', {})
        
        return {
            'campaign_id': campaign_id,
            'subject_line': subject_analysis.get('subject_line', ''),
            'subject_length': length_analysis.get('character_count', 0),
            'email_type': 'standard',
            
            # Use CORRECT field mappings from your actual analyzer output
            'subject_length_ok': length_analysis.get('optimal_range', False),
            'subject_length_score': length_analysis.get('performance_score', 0),
            'subject_caps_percentage': caps_analysis.get('caps_percentage', 0),
            'subject_caps_status': 'Pass' if caps_analysis.get('caps_percentage', 0) <= 30 else 'Fail',
            'subject_caps_recommendation': caps_analysis.get('recommendation', ''),
            'subject_spam_risk_score': spam_risk.get('risk_score', 0),
            'subject_spam_patterns': json.dumps(spam_risk.get('patterns_found', [])),
            'subject_keyword_boost': keyword_boost.get('estimated_boost', 0),
            'subject_keywords': json.dumps(keyword_boost.get('beneficial_keywords', [])),
            'subject_punctuation_ok': punctuation_validation.get('compliance_status', False),
            'subject_overall_score': subject_analysis.get('overall_effectiveness', 0),
            
            # Content analysis using CORRECT field names
            'intro_word_count': content_analysis.get('intro_analysis', {}).get('word_count', 0),
            'intro_optimal_length': content_analysis.get('intro_analysis', {}).get('optimal_length', False),
            'intro_score_contribution': content_analysis.get('intro_analysis', {}).get('score_contribution', 0),
            'bullets_present': content_analysis.get('bullet_analysis', {}).get('bullets_found', False),
            'bullets_position': content_analysis.get('bullet_analysis', {}).get('position', 'none'),
            'bullets_score_contribution': content_analysis.get('bullet_analysis', {}).get('score_contribution', 0),
            'cta_count': content_analysis.get('cta_analysis', {}).get('cta_count', 0),
            'cta_status': content_analysis.get('cta_analysis', {}).get('optimization_status', 'Suboptimal'),
            'cta_score_contribution': content_analysis.get('cta_analysis', {}).get('score_contribution', 0),
            'external_domains_count': content_analysis.get('domain_analysis', {}).get('external_domain_count', 0),
            'external_domains': json.dumps(content_analysis.get('domain_analysis', {}).get('domains_found', [])),
            'domain_risk_level': content_analysis.get('domain_analysis', {}).get('risk_level', 'Low'),
            'structure_pattern_compliant': content_analysis.get('structure_analysis', {}).get('pattern_compliance', False),
            'structure_type': content_analysis.get('structure_analysis', {}).get('structure_type', 'Suboptimal'),
            'html_validation_score': content_analysis.get('html_quality', {}).get('validation_score', 0),
            'html_issues': json.dumps(content_analysis.get('html_quality', {}).get('formatting_issues', [])),
            'mobile_friendly': content_analysis.get('html_quality', {}).get('mobile_friendly', False),
            'email_content_score': content_analysis.get('overall_content_score', 0),
            
            # Compliance and meta data
            'overall_compliance_status': 'Pass' if composite_scoring.get('weighted_composite', 0) >= 70 else 'Fail',
            'compliance_length_status': 'Pass' if length_analysis.get('optimal_range', False) else 'Fail',
            'compliance_caps_status': 'Pass' if caps_analysis.get('caps_percentage', 0) <= 30 else 'Fail',
            'compliance_spam_status': 'Pass' if spam_risk.get('risk_score', 0) < 20 else 'Fail',
            'compliance_keyword_status': 'Pass' if keyword_boost.get('estimated_boost', 0) > 0 else 'N/A',
            'compliance_punctuation_status': 'Pass' if punctuation_validation.get('compliance_status', False) else 'Fail',
            'optimization_priority_list': json.dumps(analysis_result.get('improvement_priority', [])),
            
            'overall_score': composite_scoring.get('weighted_composite', 0),
            'confidence_level': composite_scoring.get('confidence_level', 'Low'),
            'feedback_json': json.dumps(analysis_result.get('overall_feedback', [])),
            'optimizer_version': '1.0'
        }
    
    def insert_analysis_result(self, analysis_data):
        """Insert analysis result into interspire_analysis table"""
        try:
            conn = mysql.connector.connect(**self.db_config)
            cursor = conn.cursor()
            
            # Insert query matching your exact table schema
            insert_query = """
            INSERT INTO interspire_analysis
            (campaign_id, subject_line, subject_length, email_type, 
             subject_length_ok, subject_length_score, subject_caps_percentage, subject_caps_status, 
             subject_caps_recommendation, subject_spam_risk_score, subject_spam_patterns, 
             subject_keyword_boost, subject_keywords, subject_punctuation_ok, subject_overall_score, 
             intro_word_count, intro_optimal_length, intro_score_contribution, bullets_present, 
             bullets_position, bullets_score_contribution, cta_count, cta_status, cta_score_contribution, 
             external_domains_count, external_domains, domain_risk_level, structure_pattern_compliant, 
             structure_type, html_validation_score, html_issues, mobile_friendly, email_content_score, 
             overall_compliance_status, compliance_length_status, compliance_caps_status, 
             compliance_spam_status, compliance_keyword_status, compliance_punctuation_status, 
             optimization_priority_list, overall_score, confidence_level, feedback_json, optimizer_version)
            VALUES (%(campaign_id)s, %(subject_line)s, %(subject_length)s, %(email_type)s, 
                    %(subject_length_ok)s, %(subject_length_score)s, %(subject_caps_percentage)s, %(subject_caps_status)s,
                    %(subject_caps_recommendation)s, %(subject_spam_risk_score)s, %(subject_spam_patterns)s,
                    %(subject_keyword_boost)s, %(subject_keywords)s, %(subject_punctuation_ok)s, %(subject_overall_score)s,
                    %(intro_word_count)s, %(intro_optimal_length)s, %(intro_score_contribution)s, %(bullets_present)s,
                    %(bullets_position)s, %(bullets_score_contribution)s, %(cta_count)s, %(cta_status)s, %(cta_score_contribution)s,
                    %(external_domains_count)s, %(external_domains)s, %(domain_risk_level)s, %(structure_pattern_compliant)s,
                    %(structure_type)s, %(html_validation_score)s, %(html_issues)s, %(mobile_friendly)s, %(email_content_score)s,
                    %(overall_compliance_status)s, %(compliance_length_status)s, %(compliance_caps_status)s,
                    %(compliance_spam_status)s, %(compliance_keyword_status)s, %(compliance_punctuation_status)s,
                    %(optimization_priority_list)s, %(overall_score)s, %(confidence_level)s, %(feedback_json)s, %(optimizer_version)s)
            """
            
            cursor.execute(insert_query, analysis_data)
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to insert analysis result: {e}")
            return False
    
    def run_batch_analysis(self, batch_size=100):
        """Process all unanalyzed campaigns in batches"""
        campaigns = self.get_unanalyzed_campaigns()
        total_campaigns = len(campaigns)
        
        if total_campaigns == 0:
            print("✅ No campaigns need analysis")
            return
        
        print(f"🔍 Found {total_campaigns} campaigns to analyze")
        
        processed = 0
        successful = 0
        
        for i in range(0, total_campaigns, batch_size):
            batch = campaigns[i:i + batch_size]
            
            for campaign in batch:
                try:
                    # Use EXISTING analyzers
                    analysis_data = self.analyze_single_campaign(campaign)
                    
                    if analysis_data and self.insert_analysis_result(analysis_data):
                        successful += 1
                    
                    processed += 1
                    
                    if processed % 100 == 0:
                        print(f"📊 Progress: {processed}/{total_campaigns} ({processed/total_campaigns*100:.1f}%)")
                        
                except Exception as e:
                    self.logger.error(f"Failed to process campaign {campaign['id']}: {e}")
                    processed += 1
                    continue
        
        print(f"✅ Batch analysis completed: {successful}/{processed} successful")
        self.logger.info(f"Batch analysis completed: {successful}/{processed} successful")
    
    def get_analysis_statistics(self):
        """Get statistics about analysis completion"""
        try:
            conn = mysql.connector.connect(**self.db_config)
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM interspire_data")
            total_campaigns = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM interspire_analysis")
            analyzed_campaigns = cursor.fetchone()[0]
            
            conn.close()
            
            return {
                'total_campaigns': total_campaigns,
                'analyzed_campaigns': analyzed_campaigns,
                'unanalyzed_campaigns': total_campaigns - analyzed_campaigns,
                'completion_percentage': (analyzed_campaigns / total_campaigns * 100) if total_campaigns > 0 else 0
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get statistics: {e}")
            return {'error': str(e)}
