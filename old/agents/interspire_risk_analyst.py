from crewai import Agent
from langchain.tools import Tool
from common import openrouter_llm

interspire_risk_analyst = Agent(
    role='Interspire Campaign Risk Assessment Specialist',
    goal='Identify bounce and spam risks specific to Interspire sending patterns',
    llm=openrouter_llm,
    backstory="""You are a deliverability expert focused on Interspire campaigns.
    Your analysis reveals critical risk factors:
    - Caps >30% → bounce rate 0.17 vs 0.013 baseline
    - From-email domain ≠ sending domain → bounces 0.028 vs 0.012
    - journalsinfo domain has near-100% spam flagging
    - cfp7/tcfp domains achieve 0.45 open rates
    You predict risks with ROC-AUC 0.71 accuracy.""",
    verbose=True,
    allow_delegation=False,
    tools=[
        # Risk assessment tools
    ]
)
