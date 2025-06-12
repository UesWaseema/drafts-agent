import logging
import os
from crewai import Crew, Task
from agents.interspire_subject_analyst import interspire_subject_analyst
from agents.interspire_content_analyst import interspire_content_analyst  
from agents.interspire_risk_analyst import interspire_risk_analyst
from agents.interspire_performance_predictor import interspire_performance_predictor
from agents.interspire_campaign_strategist import interspire_campaign_strategist

class InterspireCampaignCrew:
    def __init__(self):
        self.setup_logging() # Call setup_logging here
        self.crew = Crew(
            agents=[
                interspire_subject_analyst,
                interspire_content_analyst,
                interspire_risk_analyst, 
                interspire_performance_predictor,
                interspire_campaign_strategist
            ],
            tasks=[],  # Tasks will be defined based on analysis type
            verbose=True
        )
    
    def setup_logging(self):
        os.makedirs("logs", exist_ok=True)
        logging.basicConfig(
            level=logging.INFO, # Default to INFO, DEBUG if LOG_LEVEL is set
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler("logs/crew_analysis.log"), # New log file for crew
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        if os.getenv('LOG_LEVEL') == 'DEBUG':
            self.logger.setLevel(logging.DEBUG)

    def analyze_single_draft(self, email_draft):
        subject_line_analysis_task = Task(
            description=f"Analyze the subject line of the email draft: '{email_draft['subject_line']}' for performance prediction based on Interspire historical patterns.",
            agent=interspire_subject_analyst,
            expected_output="A detailed analysis of the subject line's predicted performance, including character length, capitalization, and keyword impact."
        )

        content_structure_task = Task(
            description=f"Evaluate the content structure of the email draft: '{email_draft['body']}' to identify engagement-driving patterns based on Interspire campaign data.",
            agent=interspire_content_analyst,
            expected_output="An assessment of the email body's content structure, focusing on intro length, CTA placement, use of bullet lists, and external domain count, with recommendations for optimization."
        )

        risk_assessment_task = Task(
            description=f"Assess the email draft for potential bounce and spam risks specific to Interspire sending patterns. Subject: '{email_draft['subject_line']}', Body: '{email_draft['body']}'",
            agent=interspire_risk_analyst,
            expected_output="A comprehensive risk assessment, detailing potential bounce rates, spam flagging risks, and deliverability issues based on subject line, sender domain, and content."
        )

        performance_prediction_task = Task(
            description=f"Predict open rates, click rates, and overall engagement metrics for the email draft based on historical Interspire data. Subject: '{email_draft['subject_line']}', Body: '{email_draft['body']}'",
            agent=interspire_performance_predictor,
            expected_output="Forecasted open rates, click-through rates, and engagement scores with confidence intervals, along with a statistical confidence level."
        )

        strategy_synthesis_task = Task(
            description=f"""Synthesize all analyses (subject line, content, risk, performance) into a structured JSON output.
            The JSON should contain the following keys, mirroring the structure expected by the database schema:
            {{
              "subject_analysis": {{
                "subject_line": "...",
                "character_count": 0,
                "optimal_range": true,
                "performance_score": 0,
                "caps_percentage": 0,
                "caps_status": "Pass/Fail",
                "recommendation": "...",
                "spam_risk_score": 0,
                "patterns_found": [],
                "keyword_boost": 0,
                "beneficial_keywords": [],
                "punctuation_ok": true,
                "overall_effectiveness": 0
              }},
              "content_analysis": {{
                "intro_word_count": 0,
                "intro_optimal_length": true,
                "intro_score_contribution": 0,
                "bullets_found": true,
                "bullets_position": "...",
                "bullets_score_contribution": 0,
                "cta_count": 0,
                "cta_status": "...",
                "cta_score_contribution": 0,
                "external_domains_count": 0,
                "domains_found": [],
                "domain_risk_level": "...",
                "structure_pattern_compliant": true,
                "structure_type": "...",
                "html_validation_score": 0,
                "formatting_issues": [],
                "mobile_friendly": true,
                "overall_content_score": 0
              }},
              "composite_scoring": {{
                "weighted_composite": 0,
                "confidence_level": "Low/Medium/High"
              }},
              "overall_compliance_status": "Pass/Fail",
              "improvement_priority": [],
              "overall_feedback": []
            }}
            
            Ensure all numerical values are actual numbers, boolean values are true/false, and lists are proper JSON arrays.
            The 'subject_line' in 'subject_analysis' should be the original subject line from the email_draft.
            The 'overall_compliance_status' should be 'Pass' if 'weighted_composite' is >= 70, otherwise 'Fail'.
            The 'confidence_level' should be inferred from the quality and completeness of the analysis.
            The 'improvement_priority' should be a list of strings, e.g., ["Subject Line Length", "CTA Placement"].
            The 'overall_feedback' should be a list of strings with general recommendations.
            """,
            agent=interspire_campaign_strategist,
            expected_output="A JSON string containing the synthesized analysis results, strictly following the specified schema."
        )

        self.crew.tasks = [
            subject_line_analysis_task,
            content_structure_task,
            risk_assessment_task,
            performance_prediction_task,
            strategy_synthesis_task
        ]
        
        # Add debug logging before kickoff
        self.logger.debug(f"[AI] Draft {email_draft.get('id')} | Subject='{email_draft['subject_line']}' | Body[0:80]='{email_draft['body'][:80].replace(chr(10),' ')}'")
        
        # Kickoff the crew and parse the result
        raw_result = self.crew.kickoff()
        
        # CrewAI ≥ 0.2 returns a CrewOutput – get its text payload
        if not isinstance(raw_result, str):
            raw_result = getattr(raw_result, "output", None) or str(raw_result)

        # Add debug logging after kickoff
        self.logger.debug(f"[AI] Draft {email_draft.get('id')} | Raw result[0:120]='{str(raw_result)[:120].replace(chr(10),' ')}'")
        
        # Attempt to parse the JSON output from the strategist
        try:
            # Assuming the last task's output is the JSON string
            # CrewAI's kickoff returns the final output, which should be the strategist's JSON
            import json
            # The raw_result might contain extra text before/after the JSON.
            # Try to find the JSON block.
            json_start = raw_result.find('{')
            json_end = raw_result.rfind('}') + 1
            if json_start != -1 and json_end != -1 and json_end > json_start:
                json_string = raw_result[json_start:json_end]
                parsed_analysis_result = json.loads(json_string)
            else:
                raise ValueError("Could not find valid JSON in agent output.")
            
            # Add original subject_line and email_content to the parsed result for mapping
            # This is a workaround as the agents don't directly pass these through the analysis chain
            parsed_analysis_result['original_subject'] = email_draft['subject_line']
            parsed_analysis_result['original_email_content'] = email_draft['body']

            return parsed_analysis_result
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON from agent output: {e}")
            print(f"Raw agent output: {raw_result}")
            return {"error": "JSON decoding failed", "raw_output": raw_result}
        except ValueError as e:
            print(f"Error parsing agent output: {e}")
            print(f"Raw agent output: {raw_result}")
            return {"error": "Output parsing failed", "raw_output": raw_result}
    
    def rank_multiple_drafts(self, draft_list):
        ranked_results = []
        for i, draft in enumerate(draft_list):
            print(f"\n--- Analyzing Draft {i+1}/{len(draft_list)} ---")
            analysis_result = self.analyze_single_draft(draft)
            ranked_results.append({
                "draft": draft,
                "analysis": analysis_result
            })
        # Further logic to rank based on analysis_result would go here
        return ranked_results
    
    def generate_insights(self, historical_data):
        # This method would define tasks for analyzing historical data
        # and generating broader insights, potentially using all agents.
        # Example:
        # task1 = Task(description="Analyze historical subject line data...", agent=interspire_subject_analyst)
        # task2 = Task(description="Analyze historical content data...", agent=interspire_content_analyst)
        # ...
        # self.crew.tasks = [task1, task2, ...]
        # return self.crew.kickoff()
        print("Method for generating insights from historical data is not yet fully implemented.")
        return "Insights generation placeholder."
