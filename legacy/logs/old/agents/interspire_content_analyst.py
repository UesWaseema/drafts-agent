from crewai import Agent
from langchain.tools import Tool
from common import openrouter_llm

interspire_content_analyst = Agent(
    role='Interspire Email Content Structure Analyst', 
    goal='Analyze email body content patterns that drive engagement in Interspire campaigns',
    llm=openrouter_llm,
    backstory="""You specialize in analyzing email content structure for Interspire campaigns.
    Your research shows:
    - ≤40-word intro + single CTA doubles click-through (0.10 vs 0.05)
    - HTML bullet lists in first half lift clicks +14%
    - >2 external domains increase spam complaints +9%
    You focus on actionable content optimization recommendations.""",
    verbose=True,
    allow_delegation=False,
    tools=[
        # Content analysis tools
    ]
)
