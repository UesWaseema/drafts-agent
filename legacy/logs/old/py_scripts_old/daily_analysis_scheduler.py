import schedule
import time
import logging
from crewai_agent.batch_interspire_analysis import BatchInterspireAnalyzer

def run_daily_analysis():
    """Run daily analysis for new campaigns using EXISTING analyzers"""
    analyzer = BatchInterspireAnalyzer()
    
    # Get statistics before
    stats_before = analyzer.get_analysis_statistics()
    print(f"📊 Before analysis: {stats_before['unanalyzed_campaigns']} campaigns pending")
    
    # Run analysis using EXISTING composite scorer
    analyzer.run_batch_analysis(batch_size=50)
    
    # Get statistics after
    stats_after = analyzer.get_analysis_statistics()
    print(f"✅ After analysis: {stats_after['unanalyzed_campaigns']} campaigns pending")

def setup_daily_scheduler():
    """Schedule daily analysis at 3:00 AM"""
    schedule.every().day.at("03:00").do(run_daily_analysis)
    
    print("📅 Daily analysis scheduled for 3:00 AM using EXISTING analyzers")
    
    while True:
        schedule.run_pending()
        time.sleep(3600)

if __name__ == "__main__":
    setup_daily_scheduler()
