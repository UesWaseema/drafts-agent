import logging
from py_scripts_old.interspire_subject_analyzer import InterspireSubjectAnalyzer
from py_scripts_old.interspire_content_analyzer import InterspireContentAnalyzer

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class InterspireCompositeScorer:
    def __init__(self):
        self.subject_analyzer = InterspireSubjectAnalyzer()
        self.content_analyzer = InterspireContentAnalyzer()
        self.ENGAGEMENT_BASELINE = 70.0
        self.RISK_BASELINE = 85.0

    def score_single_draft(self, draft_id, subject_line, email_content):
        subject_analysis = {}
        content_analysis = {}
        
        try:
            # Use the CORRECT methods from your existing analyzers
            subject_analysis = {
                'subject_line': subject_line,
                'length_analysis': self.subject_analyzer.analyze_subject_length(subject_line),
                'caps_analysis': self.subject_analyzer.analyze_caps_ratio(subject_line),
                'spam_risk': self.subject_analyzer.detect_spam_patterns(subject_line),
                'keyword_boost': self.subject_analyzer.extract_keyword_performance(subject_line),
                'punctuation_validation': self.subject_analyzer.validate_punctuation(subject_line),
                'overall_effectiveness': self.subject_analyzer.calculate_subject_effectiveness(subject_line),
                'feedback': self.subject_analyzer.generate_subject_feedback(subject_line),
                'compliance_report': self.subject_analyzer.validate_against_rules(subject_line)
            }
            logging.info(f"Subject analysis successful for draft {draft_id}")
        except Exception as e:
            logging.error(f"Error analyzing subject line for draft {draft_id}: {e}")
            subject_analysis = {"error": str(e)}

        try:
            # Use the CORRECT method from your content analyzer
            content_analysis = self.content_analyzer.analyze_email_content(email_content)
            logging.info(f"Content analysis successful for draft {draft_id}")
        except Exception as e:
            logging.error(f"Error analyzing content for draft {draft_id}: {e}")
            content_analysis = {"error": str(e)}

        # Calculate scores using the ACTUAL data structure
        subject_score = subject_analysis.get('overall_effectiveness', 0.0) if 'error' not in subject_analysis else 0.0
        content_score = content_analysis.get('overall_content_score', 0.0) if 'error' not in content_analysis else 0.0

        # Calculate baseline engagement risk
        engagement_component = self.ENGAGEMENT_BASELINE * 0.20
        risk_component = self.RISK_BASELINE * 0.10
        baseline_engagement_risk = engagement_component + risk_component

        # Composite scoring formula
        # composite_score = (0.4 × subject_score) + (0.3 × content_score) + (0.3 × baseline_engagement_risk)
        weighted_composite = (0.4 * subject_score) + \
                             (0.3 * content_score) + \
                             (0.3 * baseline_engagement_risk)
        
        # Ensure score is within 0-100 range
        weighted_composite = max(0, min(100, weighted_composite))

        confidence_level = self.determine_confidence_level({
            'subject_analysis': subject_analysis,
            'content_analysis': content_analysis,
            'composite_score': weighted_composite
        })

        overall_feedback = self.recommend_improvements({
            'subject_analysis': subject_analysis,
            'content_analysis': content_analysis,
            'composite_score': weighted_composite
        })
        
        improvement_priority = self.recommend_improvements({
            'subject_analysis': subject_analysis,
            'content_analysis': content_analysis,
            'composite_score': weighted_composite
        })

        # Placeholder for performance prediction
        performance_prediction = {
            'estimated_open_rate': weighted_composite * 0.5, # Example
            'estimated_click_rate': weighted_composite * 0.2, # Example
            'risk_assessment': 'Low' if self.RISK_BASELINE >= 80 else 'Medium' # Example
        }

        return {
            'draft_id': draft_id,
            'subject_analysis': subject_analysis,
            'content_analysis': content_analysis,
            'composite_scoring': {
                'subject_score': round(subject_score, 2),
                'content_score': round(content_score, 2),
                'engagement_baseline': round(self.ENGAGEMENT_BASELINE, 2),
                'risk_baseline': round(self.RISK_BASELINE, 2),
                'weighted_composite': round(weighted_composite, 2),
                'confidence_level': confidence_level
            },
            'overall_feedback': overall_feedback,
            'improvement_priority': improvement_priority,
            'performance_prediction': performance_prediction
        }

    def score_multiple_drafts(self, draft_list):
        scored_drafts = []
        for draft in draft_list:
            try:
                draft_id = draft.get('draft_id', 'N/A')
                subject_line = draft.get('subject_line', '')
                email_content = draft.get('email_content', '')
                score_result = self.score_single_draft(draft_id, subject_line, email_content)
                scored_drafts.append(score_result)
            except Exception as e:
                logging.error(f"Error scoring draft {draft.get('draft_id', 'N/A')}: {e}")
                scored_drafts.append({
                    'draft_id': draft.get('draft_id', 'N/A'),
                    'error': str(e),
                    'composite_scoring': {'weighted_composite': 0.0}
                })
        
        # Rank drafts by weighted_composite score in descending order
        ranked_drafts = sorted(scored_drafts, key=lambda x: x['composite_scoring'].get('weighted_composite', 0.0), reverse=True)
        return ranked_drafts

    def generate_comparison_report(self, draft_scores):
        report = {
            "title": "Email Draft Comparison Report",
            "summary": f"Analyzed {len(draft_scores)} drafts.",
            "draft_details": []
        }

        for draft in draft_scores:
            detail = {
                "draft_id": draft.get('draft_id'),
                "composite_score": draft['composite_scoring'].get('weighted_composite'),
                "subject_score": draft['composite_scoring'].get('subject_score'),
                "content_score": draft['composite_scoring'].get('content_score'),
                "confidence_level": draft['composite_scoring'].get('confidence_level'),
                "overall_feedback": draft.get('overall_feedback'),
                "performance_prediction": draft.get('performance_prediction')
            }
            report["draft_details"].append(detail)
        
        # Add overall insights or top/bottom performers
        if draft_scores:
            best_draft = max(draft_scores, key=lambda x: x['composite_scoring'].get('weighted_composite', 0.0))
            worst_draft = min(draft_scores, key=lambda x: x['composite_scoring'].get('weighted_composite', 0.0))
            report["insights"] = {
                "best_performing_draft": best_draft.get('draft_id'),
                "best_score": best_draft['composite_scoring'].get('weighted_composite'),
                "worst_performing_draft": worst_draft.get('draft_id'),
                "worst_score": worst_draft['composite_scoring'].get('weighted_composite')
            }
        
        return report

    def recommend_improvements(self, draft_analysis):
        suggestions = []
        subject_analysis = draft_analysis.get('subject_analysis', {})
        content_analysis = draft_analysis.get('content_analysis', {})
        composite_score = draft_analysis.get('composite_score', 0.0)

        # General feedback based on composite score
        if composite_score < 50:
            suggestions.append("Overall score is low. Significant improvements are needed in both subject and content.")
        elif 50 <= composite_score < 75:
            suggestions.append("Good potential, but there's room for improvement to maximize engagement.")
        else:
            suggestions.append("Excellent draft! Minor refinements might further enhance performance.")

        # Subject line specific feedback
        if subject_analysis.get('score', 100) < 60:
            suggestions.append("Subject line needs attention. Consider making it more concise, engaging, or relevant.")
            if 'sentiment' in subject_analysis and subject_analysis['sentiment'] == 'negative':
                suggestions.append("Review subject line sentiment; aim for positive or neutral tone.")
            if 'length' in subject_analysis and subject_analysis['length'] > 50:
                suggestions.append("Subject line might be too long; try to keep it under 50 characters for better visibility.")
        
        # Content specific feedback
        if content_analysis.get('score', 100) < 60:
            suggestions.append("Email content requires improvement. Focus on clarity, call-to-action, and readability.")
            if 'readability_score' in content_analysis and content_analysis['readability_score'] < 50:
                suggestions.append("Content readability is low. Simplify language and sentence structure.")
            if 'spam_score' in content_analysis and content_analysis['spam_score'] > 70:
                suggestions.append("High spam risk detected in content. Remove suspicious keywords or formatting.")

        # Prioritize suggestions (simple example: critical issues first)
        prioritized_suggestions = sorted(suggestions, key=lambda x: 0 if "Overall score is low" in x else 1)
        return prioritized_suggestions

    def determine_confidence_level(self, analysis_results):
        subject_analysis = analysis_results.get('subject_analysis', {})
        content_analysis = analysis_results.get('content_analysis', {})
        
        # Check for errors from analyzers
        if "error" in subject_analysis or "error" in content_analysis:
            return "Low"
        
        subject_score = subject_analysis.get('score', 0.0)
        content_score = content_analysis.get('score', 0.0)

        # Simple logic for confidence:
        # High if both scores are good (e.g., > 70)
        # Medium if one is good and other is moderate (e.g., 50-70)
        # Low if any score is poor (e.g., < 50) or errors occurred
        
        if subject_score >= 70 and content_score >= 70:
            return "High"
        elif (subject_score >= 50 and content_score >= 50):
            return "Medium"
        else:
            return "Low"
