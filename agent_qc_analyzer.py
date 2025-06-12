from crewai import Agent, Task
from common import openrouter_llm

qc_analysis_agent = Agent(
    role="Draft Compliance Analyst",
    goal="Return a pass/fail checklist for each rule—no extra commentary.",
    backstory="You enforce fixed rules but never reveal ‘Thoughts’.",
    llm=openrouter_llm,
    verbose=False,          # ← suppress internal “thoughts”
)

qc_analysis_task = Task(
    description="""
You are given a CFP email draft.
Apply each of the following 9 rules:

1. Word count must be > 320
2. No buzzword / spam words (e.g., groundbreaking, discount, etc.)
3. Must NOT mention “full waiver”
4. Must NOT mention indexing (in any form)
5. Must NOT mention fast-track peer review (use “rigorous”)
6. Must NOT mention double-blind review (only single-blind is valid)
7. If article types (review, case study, etc.) are listed the draft must also say “all types welcome”
8. Deadline must contain a full date in either “31 July 2025” or “July 31 2025” style
9. The phrase “open access”/“open-access” is forbidden—only “openaccess” or “oa”

Return a checklist:

✔ Rule text   (if passed)  
❌ Rule text — short reason   (if failed)
""",
    agent=qc_analysis_agent,
    expected_output="Checklist of 9 rules (✔ / ❌ + short reason)."
)
