import mysql.connector
import pandas as pd
import json
import logging
from datetime import datetime, timedelta
from agent_ranking import AgentRanking
import schedule
import time
import os
from dotenv import load_dotenv

class DatabaseSyncPipeline:
    interspire_field_mapping = {
        'Campaign Name': 'campaign_name',
        'Subject': 'subject', 
        'Journal': 'journal',
        'Opens': 'opens',
        'Clicks': 'clicks',
        'Bounces': 'bounces', 
        'Email': 'email',
        'Sent Count': 'sent_count',
        'Domain': 'domain',
        'Draft Type': 'draft_type',
        'Sent Date': 'sent_date'
    }


    def __init__(self):
        load_dotenv()
        self.db_config = {
            'host': os.getenv('DRAFTS_DB_HOST', 'localhost'),
            'user': os.getenv('DRAFTS_DB_USER'),
            'password': os.getenv('DRAFTS_DB_PASS'),
            'database': os.getenv('DRAFTS_DB_NAME'),
            'charset': 'utf8mb4'
        }
        self.agent_ranker = AgentRanking()
        self.setup_logging()
    
    def setup_logging(self):
        # Create logs directory if it doesn't exist
        import os
        os.makedirs("logs", exist_ok=True)
        
        logging.basicConfig(level=os.getenv('LOG_LEVEL', 'INFO'),
                            format='%(asctime)s - %(levelname)s - %(message)s',
                            handlers=[
                                logging.FileHandler("logs/database_sync.log"),
                                logging.StreamHandler()  # This ensures console output
                            ])
        self.logger = logging.getLogger(__name__)
    
    def get_db_connection(self):
        try:
            conn = mysql.connector.connect(**self.db_config)
            self.logger.info("Successfully connected to the database.")
            return conn
        except mysql.connector.Error as err:
            self.logger.error(f"Error connecting to database: {err}")
            return None
    
    def sync_interspire_data(self):
        print("  → Fetching Interspire campaign data...")
        try:
            interspire_df = self.agent_ranker.get_campaign_data(source='Interspire')
            print(f"  → Found {len(interspire_df)} Interspire campaigns")
            
            if interspire_df.empty:
                print("  → No Interspire data found!")
                self.logger.warning("No Interspire data found")
                return {'inserted': 0, 'updated': 0, 'total': 0}
            
            print(f"  → Data columns: {list(interspire_df.columns)}")
            
            # Check for duplicates
            new_campaigns = self.check_for_duplicates('interspire_data', interspire_df)
            print(f"  → {len(new_campaigns)} new campaigns to insert")
            
            # Insert data
            if len(new_campaigns) > 0:
                result = self.insert_campaign_batch('interspire_data', new_campaigns)
                print(f"  → Inserted {result} campaigns")
            else:
                print("  → No new campaigns to insert")
                result = 0
            
            self.logger.info(f"Interspire sync: {result} campaigns processed")
            return {'inserted': result, 'total': len(interspire_df)}
            
        except Exception as e:
            print(f"  ❌ Interspire sync failed: {e}")
            self.logger.error(f"Interspire sync failed: {e}")
            raise
    
    def sync_mailwizz_data(self):
        print("  → Fetching MailWizz campaign data...")
        try:
            mailwizz_df = self.agent_ranker.get_campaign_data(source='MailWizz')
            print(f"  → Found {len(mailwizz_df)} MailWizz campaigns")
            
            if mailwizz_df.empty:
                print("  → No MailWizz data found!")
                self.logger.warning("No MailWizz data found")
                return {'inserted': 0, 'updated': 0, 'total': 0}
            
            print(f"  → Data columns: {list(mailwizz_df.columns)}")
            
            # Check for duplicates
            new_campaigns = self.check_for_duplicates('mailwizz_data', mailwizz_df)
            print(f"  → {len(new_campaigns)} new campaigns to insert")
            
            # Insert data
            if len(new_campaigns) > 0:
                result = self.insert_campaign_batch('mailwizz_data', new_campaigns)
                print(f"  → Inserted {result} campaigns")
            else:
                print("  → No new campaigns to insert")
                result = 0
            
            self.logger.info(f"MailWizz sync: {result} campaigns processed")
            return {'inserted': result, 'total': len(mailwizz_df)}
            
        except Exception as e:
            print(f"  ❌ MailWizz sync failed: {e}")
            self.logger.error(f"MailWizz sync failed: {e}")
            raise
    
    def check_for_duplicates(self, table_name, campaign_data):
        """Check if campaign already exists to avoid duplicates"""
        print(f"  → Checking for duplicates in {table_name}...")
        
        conn = None # Initialize conn to None
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            # Get existing campaign names/subjects to check for duplicates
            cursor.execute(f"SELECT subject, campaign_name, sent_date FROM {table_name}")
            existing_campaigns = set(cursor.fetchall())
            
            print(f"  → Found {len(existing_campaigns)} existing campaigns")
            
            # Filter out duplicates
            new_campaigns = []
            for _, row in campaign_data.iterrows():
                campaign_key = (
                    str(row.get('Subject', '')),
                    str(row.get('Campaign Name', '')),
                    str(row.get('Sent Date', ''))
                )
                if campaign_key not in existing_campaigns:
                    new_campaigns.append(row)
            
            new_campaigns_df = pd.DataFrame(new_campaigns) if new_campaigns else pd.DataFrame()
            
            print(f"  → {len(new_campaigns_df)} new campaigns to insert")
            
            conn.close()
            return new_campaigns_df
            
        except Exception as e:
            print(f"  ❌ Duplicate check failed: {e}")
            self.logger.error(f"Duplicate check failed for {table_name}: {e}")
            if conn:
                conn.close()
            # Return all data if duplicate check fails
            return campaign_data

    def insert_campaign_batch(self, table_name, campaigns_df):
        """Batch insert new campaigns into specified table"""
        print(f"  → Inserting {len(campaigns_df)} campaigns into {table_name}...")
        
        if campaigns_df.empty:
            return 0
        
        # Choose the right mapping
        field_mapping = self.interspire_field_mapping if 'interspire' in table_name else self.mailwizz_field_mapping
        
        conn = None # Initialize conn to None
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            # Prepare the insert query
            db_columns = list(field_mapping.values())  # database column names
            placeholders = ', '.join(['%s'] * len(db_columns))
            columns_str = ', '.join(db_columns)
            
            query = f"""
            INSERT INTO {table_name} ({columns_str})
            VALUES ({placeholders})
            ON DUPLICATE KEY UPDATE
                sent_date = VALUES(sent_date)
            """
            
            print(f"  → SQL Query: {query}")
            
            # Prepare data for insertion
            data_to_insert = []
            for _, row in campaigns_df.iterrows():
                row_data = []
                for data_col, db_col in field_mapping.items():
                    # Get value from dataframe using the data column name
                    value = row.get(data_col, None)
                    
                    # Handle data type conversions
                    if db_col in ['opens', 'clicks', 'bounces', 'sent_count']:
                        value = int(value) if value is not None and str(value).isdigit() else 0
                    elif db_col == 'sent_date':
                        # Expect string 'YYYY-MM-DD'; if NaN pass None so MySQL stores NULL
                        value = (
                            pd.to_datetime(value).date().isoformat()
                            if value and str(value) != 'nan' else None
                        )
                    elif value is None:
                        value = ''
                    else:
                        value = str(value)
                    
                    row_data.append(value)
                
                data_to_insert.append(tuple(row_data))
            
            print(f"  → Prepared {len(data_to_insert)} rows for insertion")
            print(f"  → Sample row: {data_to_insert[0] if data_to_insert else 'No data'}")
            
            # Execute the batch insert
            cursor.executemany(query, data_to_insert)
            rows_affected = cursor.rowcount
            
            conn.commit()
            conn.close()
            
            print(f"  → Successfully inserted {rows_affected} campaigns")
            self.logger.info(f"Inserted {rows_affected} campaigns into {table_name}")
            
            return rows_affected
            
        except Exception as e:
            print(f"  ❌ Batch insert failed: {e}")
            self.logger.error(f"Batch insert failed for {table_name}: {e}")
            if conn: # Check if conn is not None before rollback/close
                conn.rollback()
                conn.close()
            raise
    
    def get_sync_statistics(self):
        """Get statistics about last sync operation"""
        # This would typically read from a sync log table or a dedicated stats file
        # For now, we'll return dummy data or implement a simple log parser
        self.logger.info("Fetching sync statistics (dummy data for now).")
        return {
            'last_sync_time': datetime.now().isoformat(),
            'interspire_total': get_campaign_count('interspire_data'),
            'mailwizz_total': get_campaign_count('mailwizz_data'),
            'interspire_inserted_last_run': 0, # Placeholder
            'mailwizz_inserted_last_run': 0 # Placeholder
        }
    
    def run_daily_sync(self):
        print("🚀 Starting daily sync...")
        self.logger.info("--- Starting daily data synchronization ---")
        start_time = time.time()
        
        try:
            print("📡 Syncing Interspire data...")
            interspire_stats = self.sync_interspire_data()
            print(f"✅ Interspire: {interspire_stats}")
            
            print("📡 Syncing MailWizz data...")
            mailwizz_stats = self.sync_mailwizz_data()
            print(f"✅ MailWizz: {mailwizz_stats}")
            
            end_time = time.time()
            duration = end_time - start_time
            
            print(f"🎉 Sync completed in {duration:.2f} seconds")
            self.logger.info(f"Daily sync completed successfully in {duration:.2f} seconds")
            
            return {
                'status': 'success',
                'interspire': interspire_stats,
                'mailwizz': mailwizz_stats,
                'duration': duration
            }
            
        except Exception as e:
            print(f"❌ Sync failed: {e}")
            self.logger.error(f"Daily sync failed: {e}")
            raise
        finally:
            # Update last sync time in a persistent store (e.g., a small DB table or file)
            self._update_last_sync_time()

    def test_database_connection(self):
        """Test database connection and table existence"""
        print("🔍 Testing database connection...")
        
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            # Check if tables exist
            cursor.execute("SHOW TABLES")
            tables = cursor.fetchall()
            table_names = [t[0] for t in tables]
            print(f"📋 Tables found: {table_names}")
            
            # Check required tables
            required_tables = ['interspire_data', 'mailwizz_data', 'interspire_analysis']
            missing_tables = [t for t in required_tables if t not in table_names]
            
            if missing_tables:
                print(f"❌ Missing tables: {missing_tables}")
                return False
            
            # Test record counts
            for table in ['interspire_data', 'mailwizz_data']:
                if table in table_names:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    print(f"📊 Records in {table}: {count}")
            
            conn.close()
            print("✅ Database connection successful!")
            return True
            
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            self.logger.error(f"Database connection test failed: {e}")
            return False

    def _update_last_sync_time(self):
        """Helper to record the last successful sync time."""
        conn = self.get_db_connection()
        if conn:
            cursor = conn.cursor()
            try:
                # Create a simple table to store sync metadata if it doesn't exist
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS sync_metadata (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        last_sync_timestamp DATETIME
                    )
                """)
                # Always keep only one record for last sync time
                cursor.execute("DELETE FROM sync_metadata")
                cursor.execute("INSERT INTO sync_metadata (last_sync_timestamp) VALUES (%s)", (datetime.now(),))
                conn.commit()
                self.logger.info("Last sync timestamp updated in database.")
            except mysql.connector.Error as err:
                self.logger.error(f"Error updating last sync timestamp: {err}")
                conn.rollback()
            finally:
                cursor.close()
                conn.close()

# Helper functions (outside the class for now, or make them static methods if they don't need self)
def get_db_connection_helper():
    load_dotenv()
    db_config = {
        'host': os.getenv('DRAFTS_DB_HOST', 'localhost'),
        'user': os.getenv('DRAFTS_DB_USER'),
        'password': os.getenv('DRAFTS_DB_PASS'),
        'database': os.getenv('DRAFTS_DB_NAME'),
        'charset': 'utf8mb4'
    }
    try:
        conn = mysql.connector.connect(**db_config)
        return conn
    except mysql.connector.Error as err:
        logging.error(f"Error connecting to database in helper function: {err}")
        return None

def get_campaign_count(table_name):
    """Get total number of campaigns in specified table"""
    config = {
        'host': os.getenv('DRAFTS_DB_HOST', 'localhost'),
        'user': os.getenv('DRAFTS_DB_USER'),
        'password': os.getenv('DRAFTS_DB_PASS'),
        'database': os.getenv('DRAFTS_DB_NAME'),
        'charset': 'utf8mb4'
    }
    conn = None
    try:
        conn = mysql.connector.connect(**config)
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        return count
    except mysql.connector.Error as err:
        logging.error(f"Error getting campaign count for {table_name}: {err}")
        return 0
    finally:
        if conn:
            conn.close()

def get_last_sync_time():
    """Get timestamp of last successful sync"""
    conn = get_db_connection_helper()
    if not conn:
        return "N/A"
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT last_sync_timestamp FROM sync_metadata ORDER BY last_sync_timestamp DESC LIMIT 1")
        result = cursor.fetchone()
        if result:
            return result[0].strftime("%Y-%m-%d %H:%M:%S")
        return "Never"
    except mysql.connector.Error as err:
        logging.error(f"Error getting last sync time: {err}")
        return "Error"
    finally:
        cursor.close()
        conn.close()

def get_recent_campaigns(table_name, days=7):
    """Get campaigns added in last N days"""
    conn = get_db_connection_helper()
    if not conn:
        return pd.DataFrame()
    cursor = conn.cursor(dictionary=True)
    try:
        # Assuming 'created_at' or similar timestamp column exists in your tables
        # You might need to add this column to your table schema if not present
        query = f"SELECT * FROM {table_name} WHERE created_at >= %s"
        seven_days_ago = datetime.now() - timedelta(days=days)
        cursor.execute(query, (seven_days_ago,))
        campaigns = cursor.fetchall()
        return pd.DataFrame(campaigns)
    except mysql.connector.Error as err:
        logging.error(f"Error getting recent campaigns for {table_name}: {err}")
        return pd.DataFrame()
    finally:
        cursor.close()
        conn.close()
