import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from crewai_agent.campaign_stats import get_interspire_campaign_stats

print("Testing get_interspire_campaign_stats...")
stats = get_interspire_campaign_stats(limit=5)
if stats:
    for row in stats:
        print(row)
        if 'sent_date' in row:
            print("  'sent_date' found in row.")
        else:
            print("  'sent_date' NOT found in row.")
else:
    print("No stats returned.")
