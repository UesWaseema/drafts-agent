import schedule
import time
import logging
from database_sync_pipeline import DatabaseSyncPipeline
import os
from dotenv import load_dotenv

def setup_scheduler():
    """Set up daily sync schedule"""
    load_dotenv() # Load environment variables for LOG_LEVEL
    logging.basicConfig(level=os.getenv('LOG_LEVEL', 'INFO'),
                        format='%(asctime)s - %(levelname)s - %(message)s',
                        handlers=[
                            logging.FileHandler("logs/scheduler.log"),
                            logging.StreamHandler()
                        ])
    logger = logging.getLogger(__name__)

    pipeline = DatabaseSyncPipeline()
    
    sync_time = os.getenv('SYNC_TIME', '02:00')
    schedule.every().day.at(sync_time).do(pipeline.run_daily_sync)
    
    logger.info(f"Scheduler initialized. Daily sync scheduled for {sync_time}")
    
    # Keep the scheduler running
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute

if __name__ == "__main__":
    # Ensure the logs directory exists
    if not os.path.exists('logs'):
        os.makedirs('logs')
    setup_scheduler()
