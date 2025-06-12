from crewai import Agent
from langchain.tools import Tool
from common import openrouter_llm

interspire_campaign_strategist = Agent(
    role='Interspire Campaign Strategy Coordinator',
    goal='Synthesize all analysis into actionable campaign recommendations and rankings',
    llm=openrouter_llm,
    backstory="""You are the senior strategist who coordinates insights from all specialists.
    You combine subject line analysis, content structure, risk assessment, and performance predictions
    into comprehensive campaign strategies. You use the validated 40/30/20/10 weighting system:
    - 40% Subject effectiveness  
    - 30% Content quality
    - 20% Engagement potential
    - 10% Risk assessment
    You provide final scores, rankings, and A/B testing recommendations.""",
    verbose=True,
    allow_delegation=True,  # Can delegate to other agents
    tools=[
        # Strategy and ranking tools
    ]
)
