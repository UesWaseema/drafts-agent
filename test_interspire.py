from campaign_stats import get_interspire_campaign_stats

campaigns = get_interspire_campaign_stats()

for c in campaigns:
    print(f"\n🗓️ {c['created_date']} | {c['campaign_name']} (Sent by: {c['sent_by']})")
    print(f"Subject: {c['subject']}")
    print(f"Opens: {c['unique_opens']} ({c['open_rate']}%) | Clicks: {c['unique_clicks']} ({c['click_rate']}%) | Bounces: {c['bouncecount_hard']}")
    print(f"Textbody preview: {c['textbody'][:100]}...")
    print("---")

