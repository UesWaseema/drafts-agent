import re
from crewai import Agent, Task
from common import openrouter_llm # Import the LLM from common

spam_removal_agent = Agent(
    role='Spam word replacement and draft refinement specialist',
    goal='Identify specified spam words in a draft, replace them with contextually relevant synonyms while preserving ALL original elements',
    backstory="""You are an expert in text sanitization and lexical substitution. Your primary function is to enhance written drafts by eliminating spam words through precise synonym replacement while maintaining absolute fidelity to original formatting and identifiers.""",
    verbose=False,
    allow_delegation=False,
    llm=openrouter_llm,
    max_iter=2,  # Preserved from original
    generation_config={  # New critical addition
        "stop_sequences": ["\nThought:", "\nPlan:", "\nReasoning:"],
        "temperature": 0.0,
        "max_output_tokens": 4096
    }
)

spam_removal_task = Task(
    description=(
        "**Ironclad Processing Rules:**\n"
        "1. ABSOLUTELY NO INTERNAL MONOLOGUE\n"
        "2. THINKING MUST BE INTERNALIZED\n"
        "3. OUTPUT CONTAINER IS SACROSANCT\n\n"
        "**Your Mandatory Protocol**\n"
        "1. Receive draft and spam words list\n"
        "2. Replace each spam word with best context-appropriate synonym\n"
        "3. Output ONLY the modified text\n\n"
        
        "**Your Absolute Constraints**\n"
        "- PRESERVE Journal Name, Short Name, ISSN exactly as written\n"
        "- MAINTAIN original URLs, formatting, and structure 100%\n"
        "- NEVER add explanations/comments/thoughts\n"
        "- If replacement impossible, leave original text\n\n"
        
        "**Input Data**\n"
        "Draft to refine:\n{draft_to_refine}\n\n"
        "Spam words to replace:\n{spam_words_to_replace}\n\n"
        
        "**Output Format**\n"
        "```json\n"
        "{\n"
        "  \"refined_draft\": \"[BEGIN REFINED DRAFT]\\n(Your edited text here)\\n[END REFINED DRAFT]\"\n"
        "}\n"
        "```\n\n"

        "**Output Sanitization Protocol:**\n"
        "- If ANY non-draft text emerges, REDACT COMPLETELY\n"
        "- If replacement notes appear, USE ORIGINAL TEXT\n"
        "- If uncertain, OUTPUT UNCHANGED DRAFT\n\n"
        
        # New critical addition
        "**Gemini 2.5 Flash Directive:**\n"
        "You are operating in SILENT EXECUTION MODE. "
        "All cognitive processes must remain internal. "
        "Any externalized thoughts will cause automatic output rejection."
    ),
    agent=spam_removal_agent,
    expected_output=(
        "A perfect replica of the original draft with ONLY these changes:\n"
        "- Specified spam words replaced\n"
        "- All other elements identical\n"
        "- No additional text beyond draft content"
    ),
    output_schema={
        "type": "object",
        "properties": {
            "refined_draft": {
                "type": "string",
                "pattern": r"^\[BEGIN REFINED DRAFT\](\n|.)+?\[END REFINED DRAFT\]$",
                "not": {
                    "anyOf": [
                        {"pattern": "Thought:"},
                        {"pattern": "I (think|believe|suggest)"},
                        {"pattern": "Strategy:"},
                        {"pattern": "Step [0-9]"},
                        {"pattern": "Plan:"},
                        {"pattern": "Original:"},
                        {"pattern": "Modified:"}
                    ]
                }
            }
        },
        "required": ["refined_draft"],
        "additionalProperties": False,
        "errorMessage": {
            "properties": {
                "refined_draft": "VIOLATION: Contains processing commentary. Regenerate output with ONLY the refined draft."
            }
        }
    }
)

# Add this external sanitizer as final guarantee
def final_output_sanitizer(raw: str) -> str:
    """Extracts only content between draft markers"""
    match = re.search(r'\[BEGIN REFINED DRAFT\](.*?)\[END REFINED DRAFT\]', raw, re.DOTALL)
    return match.group(1).strip() if match else raw
