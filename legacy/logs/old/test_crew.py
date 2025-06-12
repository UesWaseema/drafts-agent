from agents.interspire_crew import InterspireCampaignCrew
from py_scripts_old.batch_interspire_analysis import BatchInterspireAnalyzer
import os
from dotenv import load_dotenv

if __name__ == "__main__":
    load_dotenv() # Load environment variables from .env file

    print("Initializing Interspire Campaign Crew...")
    crew_instance = InterspireCampaignCrew()

    print("\nInitializing Batch Interspire Analyzer...")
    batch_analyzer = BatchInterspireAnalyzer()

    print("\nFetching unanalyzed campaigns from database...")
    campaigns = batch_analyzer.get_unanalyzed_campaigns()

    all_drafts = []
    for campaign in campaigns:
        # Ensure 'subject' and 'email' keys exist and are not None
        subject_line = campaign.get('subject', '') or ''
        email_body = campaign.get('email', '') or ''
        campaign_id = campaign.get('id') # Get the original campaign ID
        
        if subject_line and email_body and campaign_id is not None:
            all_drafts.append({
                "id": campaign_id, # Include the original campaign ID
                "subject_line": subject_line,
                "body": email_body
            })

    if not all_drafts:
        print("No unanalyzed email drafts found in the 'interspire_data' table. Please ensure the table has data and that 'subject' and 'email' fields are populated.")
    else:
        print(f"Found {len(all_drafts)} unanalyzed email drafts.")
        
        # Limit to 10 records for analysis as requested
        drafts_to_analyze = all_drafts[:10]
        print(f"Analyzing {len(drafts_to_analyze)} records as requested.")

        # Analyze multiple drafts
        if len(drafts_to_analyze) > 0:
            print("\nAnalyzing email drafts and saving to DB...")
            for i, draft in enumerate(drafts_to_analyze):
                print(f"\n--- Analyzing Draft {i+1}/{len(drafts_to_analyze)} ---")
                analysis_result_from_crew = crew_instance.analyze_single_draft(draft)
                
                if "error" in analysis_result_from_crew:
                    print(f"Error analyzing draft {draft['subject_line']}: {analysis_result_from_crew['error']}")
                    print(f"Raw output: {analysis_result_from_crew.get('raw_output', 'N/A')}")
                    continue

                # Map the structured analysis result to the database schema
                # The map_analysis_to_schema expects a 'campaign_row' dictionary
                # We need to construct a dummy campaign_row with at least 'id', 'subject', 'email'
                # For testing, we can use a simple counter for id or generate a UUID
                # For now, let's use a simple counter and the original subject/email from the draft
                
                # Ensure the analysis_result_from_crew contains the necessary structure
                # It should contain 'subject_analysis', 'content_analysis', 'composite_scoring'
                # If the agent successfully outputs JSON, these keys should be present.
                
                # Create a dummy campaign_row for map_analysis_to_schema
                # The 'id' here is crucial for the database. If we're re-running,
                # we might insert duplicates. For a real system, this would be
                # linked to an actual campaign ID from interspire_data.
                # For this test, let's use a unique ID or a placeholder.
                # Since we are fetching unanalyzed campaigns, we should use their actual IDs.
                # However, the current `all_drafts` list doesn't retain the original campaign ID.
                # I need to modify the `all_drafts` creation to include the original `id`.
                
                # Temporarily, I will use a placeholder ID and assume the structure is correct.
                # This will need to be fixed by passing the original campaign ID from `batch_analyzer.get_unanalyzed_campaigns()`
                
                # Re-reading the `all_drafts` creation in test_crew.py:
                # all_drafts.append({"subject_line": subject_line, "body": email_body})
                # This needs to be:
                # all_drafts.append({"id": campaign['id'], "subject_line": subject_line, "body": email_body})
                
                # Construct a campaign_row dictionary for map_analysis_to_schema
                campaign_row_for_mapping = {
                    'id': draft['id'],
                    'subject': draft['subject_line'],
                    'email': draft['body']
                }
                
                # Map the structured analysis result to the database schema
                # The analysis_result_from_crew is the JSON output from the strategist agent
                mapped_analysis_data = batch_analyzer.map_analysis_to_schema(
                    campaign_row_for_mapping['id'], # Pass the actual campaign ID
                    analysis_result_from_crew
                )
                
                # Insert the analysis result into the database
                if mapped_analysis_data:
                    try:
                        if batch_analyzer.insert_analysis_result(mapped_analysis_data):
                            print(f"Successfully analyzed and saved data for campaign ID: {draft['id']}")
                        else:
                            print(f"Failed to save analysis data for campaign ID: {draft['id']}")
                    except Exception as db_e:
                        print(f"Database error saving analysis for campaign ID {draft['id']}: {db_e}")
                else:
                    print(f"Mapped analysis data was empty for campaign ID: {draft['id']}")
        else:
            print("\nNo drafts to analyze after limiting to 10.")
