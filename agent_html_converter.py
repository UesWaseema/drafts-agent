import re
from crewai import Agent, Task
from common import openrouter_llm # Import the LLM from common

html_converter_agent = Agent(
    role='Expert HTML formatter and web content stylist',
    goal='Convert plain text drafts into well-formatted HTML, applying specified styles and ensuring links are functional.',
    backstory="""You are a meticulous HTML developer with an eye for clean code and effective presentation.
    You specialize in taking raw text and transforming it into visually appealing and semantically correct HTML.
    Your expertise includes applying CSS styles for font sizes, bolding, italics, underlining, and converting plain URLs into clickable hyperlinks.
    You ensure the output HTML is ready for web display.""",
    verbose=False,
    allow_delegation=False,
    llm=openrouter_llm,
    # If your framework supports, add:
    # generation_config={"stop_sequences": ["Explanation:", "Thought:", "Plan:"], "temperature": 0.0}
)

html_conversion_task = Task(
    description=(
        "Convert the following draft into HTML. Apply the following formatting rules:\n"
        "- Ensure the main body text has a readable font size (e.g., 16px).\n"
        "- Convert any detected URLs (e.g., http://example.com, https://example.com) into clickable HTML `<a>` tags.\n"
        "- Preserve paragraph breaks and line breaks.\n"
        "- Use appropriate HTML tags for structure (e.g., `<p>` for paragraphs).\n"
        "- If any words or phrases are explicitly marked for bold, italics, or underline (e.g., using **bold**, *italics*, _underline_), convert them to `<strong>`, `<em>`, and `<u>` tags respectively.\n"
        "- The output should be ONLY the HTML code, without any conversational text or explanations.\n"
        "- Do not include any internal thoughts, reasoning, or commentary. Output must be pure HTML only.\n\n"
        "Draft to convert:\n{draft_to_convert}"
    ),
    agent=html_converter_agent,
    expected_output="A complete HTML string representing the formatted draft."
)

def html_output_sanitizer(raw_html: str) -> str:
    """Extracts only HTML code, removes any non-HTML commentary."""
    # Remove any lines that do not start with < or <! (for DOCTYPE)
    html_lines = [line for line in raw_html.splitlines() if line.strip().startswith('<') or line.strip().startswith('<!')]
    # If nothing starts with <, fallback to original (in case it's minified HTML)
    if not html_lines and raw_html.strip().startswith('<'):
        return raw_html.strip()
    return '\n'.join(html_lines).strip()
