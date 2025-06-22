from campaign_stats import get_mailwizz_campaign_stats

campaigns = get_mailwizz_campaign_stats()

for c in campaigns:
    print(f"\n🗓️ {c['send_at']} | {c['campaign_name']}")
    print(f"Subject: {c['subject']}")
    print(f"Journal: {c['journal']} | From Email: {c['from_email']}")
    print(f"Opens: {c['opens']} | Clicks: {c['clicks']} | Bounces: {c['bounces']}")
    print(f"Body Preview: {c['email_body']}...")
    print("---")

