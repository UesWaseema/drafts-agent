#!/usr/bin/env python3
import os
from database_sync_pipeline import DatabaseSyncPipeline

def main():
    print("🔧 DEBUGGING SYNC PIPELINE")
    print("=" * 50)
    
    # Test 1: Environment variables
    print("\n1️⃣ Environment Variables:")
    env_vars = ['DRAFTS_DB_HOST', 'DRAFTS_DB_USER', 'DRAFTS_DB_PASS', 'DRAFTS_DB_NAME']
    for var in env_vars:
        value = os.getenv(var)
        print(f"{var}: {'✅ Set' if value else '❌ Missing'}")
    
    # Test 2: Create logs directory
    print("\n2️⃣ Creating logs directory...")
    os.makedirs("logs", exist_ok=True)
    print("✅ Logs directory ready")
    
    # Test 3: Initialize pipeline
    print("\n3️⃣ Initializing pipeline...")
    try:
        pipeline = DatabaseSyncPipeline()
        print("✅ Pipeline initialized")
    except Exception as e:
        print(f"❌ Pipeline initialization failed: {e}")
        return
    
    # Test 4: Database connection
    print("\n4️⃣ Testing database connection...")
    if pipeline.test_database_connection():
        print("✅ Database tests passed")
    else:
        print("❌ Database tests failed")
        return
    
    # Test 5: Data source
    print("\n5️⃣ Testing data source...")
    try:
        data = pipeline.agent_ranker.get_campaign_data(source='Interspire')
        print(f"✅ Data fetched: {len(data)} rows")
        if not data.empty:
            print(f"Columns: {list(data.columns)}")
    except Exception as e:
        print(f"❌ Data fetch failed: {e}")
        return
    
    # Test 6: Manual sync
    print("\n6️⃣ Running manual sync...")
    try:
        result = pipeline.run_daily_sync()
        print("✅ Sync completed successfully")
        print(f"Result: {result}")
    except Exception as e:
        print(f"❌ Sync failed: {e}")

if __name__ == "__main__":
    main()
