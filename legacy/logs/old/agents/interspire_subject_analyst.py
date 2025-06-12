from crewai import Agent
from langchain.tools import Tool
from common import openrouter_llm

interspire_subject_analyst = Agent(
    role='Interspire Subject Line Performance Analyst',
    goal='Analyze subject lines using validated Interspire historical patterns to predict performance',
    llm=openrouter_llm,
    backstory="""You are an expert email marketing analyst specializing in Interspire campaign data. 
    You have analyzed thousands of campaigns and identified that:
    - 35-55 character subject lines perform best (0.62 open rate at 50-60 chars)
    - 10-20% capitalization is optimal (45% better than other ranges)
    - >30% caps increases bounces 13× 
    - "call for papers" boosts clicks +0.008
    Your analysis achieves 81% accuracy in identifying top-quartile campaigns.""",
    verbose=True,
    allow_delegation=False,
    tools=[
        # Subject analysis tools will be defined here
    ]
)
