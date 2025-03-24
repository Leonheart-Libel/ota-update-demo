import os
import json
import time
import random
import logging
import uuid
import sqlite3
import pyodbc
import sys
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("data_generator")

class DataGenerator:
    """
    Sample application that generates timestamped dummy data
    and stores it in a database.
    """
    
    def __init__(self, config_file):
        """
        Initialize the data generator.
        
        Args:
            config_file (str): Path to the configuration file
        """
        self.config_file = config_file
        self.load_config()
        self.setup_storage()
        self.app_id = str(uuid.uuid4())[:8]  # Unique ID for this instance
        self.counter = 0
    
    def load_config(self):
        """Load configuration from the config file."""
        try:
            with open(self.config_file, 'r') as f:
                self.config = json.load(f)
                
            # Set defaults if not specified
            if 'storage' not in self.config:
                self.config['storage'] = {'type': 'file', 'path': 'data.log'}
                
            if 'generate_interval_seconds' not in self.config:
                self.config['generate_interval_seconds'] = 5
                
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            # Default configuration
            self.config = {
                'storage': {'type': 'file', 'path': 'data.log'},
                'generate_interval_seconds': 5
            }
    
    def setup_storage(self):
        """Set up the storage system based on configuration."""
        storage_type = self.config['storage']['type']
        
        if storage_type == 'file':
            # File-based storage - nothing to set up
            logger.info(f"Using file-based storage: {self.config['storage']['path']}")
            self.store_data = self.store_data_file
            
        elif storage_type == 'sqlite':
            # SQLite database storage
            db_path = self.config['storage']['path']
            logger.info(f"Using SQLite storage: {db_path}")
            
            # Create the database and table if they don't exist
            self.conn = sqlite3.connect(db_path)
            cursor = self.conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS data_points (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    value REAL,
                    app_version TEXT,
                    app_id TEXT
                )
            ''')
            self.conn.commit()
            self.store_data = self.store_data_sqlite
            
        elif storage_type == 'azure_sql':
            # Azure SQL Database storage
            logger.info("Using Azure SQL Database storage")
            self.setup_azure_sql()
            self.store_data = self.store_data_azure_sql
            
        else:
            # Default to file storage
            logger.warning(f"Unknown storage type: {storage_type}, defaulting to file")
            self.config['storage'] = {'type': 'file', 'path': 'data.log'}
            self.store_data = self.store_data_file
    
    def setup_azure_sql(self):
        """Set up connection to Azure SQL Database."""
        try:
            conn_str = self.config['storage']['connection_string']
            self.azure_conn = pyodbc.connect(conn_str)
            cursor = self.azure_conn.cursor()
            
            # Create table if it doesn't exist
            cursor.execute('''
                IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'data_points')
                BEGIN
                    CREATE TABLE data_points (
                        id INT IDENTITY(1,1) PRIMARY KEY,
                        timestamp DATETIME,
                        value FLOAT,
                        app_version VARCHAR(50),
                        app_id VARCHAR(50)
                    )
                END
            ''')
            self.azure_conn.commit()
            logger.info("Successfully connected to Azure SQL Database")
            
        except Exception as e:
            logger.error(f"Error connecting to Azure SQL Database: {e}")
            logger.warning("Falling back to file storage")
            self.config['storage'] = {'type': 'file', 'path': 'data.log'}
            self.store_data = self.store_data_file
    
    def get_app_version(self):
        """Get the current application version."""
        try:
            version_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "version.json")
            with open(version_file, 'r') as f:
                version_info = json.load(f)
            return version_info.get('version', 'unknown')
        except Exception as e:
            logger.warning(f"Error reading version info: {e}")
            return "unknown"
    
    def generate_data_point(self):
        """Generate a random data point."""
        self.counter += 1
        timestamp = datetime.now().isoformat()
        value = random.uniform(0, 100)
        app_version = self.get_app_version()
        
        return {
            "timestamp": timestamp,
            "value": value,
            "app_version": app_version,
            "app_id": self.app_id,
            "counter": self.counter
        }
    
    def store_data_file(self, data_point):
        """Store data point to a file."""
        try:
            file_path = self.config['storage']['path']
            with open(file_path, 'a') as f:
                f.write(json.dumps(data_point) + '\n')
            return True
        except Exception as e:
            logger.error(f"Error writing to file: {e}")
            return False
    
    def store_data_sqlite(self, data_point):
        """Store data point to SQLite database."""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "INSERT INTO data_points (timestamp, value, app_version, app_id) VALUES (?, ?, ?, ?)",
                (data_point['timestamp'], data_point['value'], data_point['app_version'], data_point['app_id'])
            )
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error writing to SQLite: {e}")
            return False
    
    def store_data_azure_sql(self, data_point):
        """Store data point to Azure SQL Database."""
        try:
            cursor = self.azure_conn.cursor()
            cursor.execute(
                "INSERT INTO data_points (timestamp, value, app_version, app_id) VALUES (?, ?, ?, ?)",
                (data_point['timestamp'], data_point['value'], data_point['app_version'], data_point['app_id'])
            )
            self.azure_conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error writing to Azure SQL: {e}")
            # Try to reconnect
            try:
                self.setup_azure_sql()
                return self.store_data_azure_sql(data_point)
            except:
                return False
    
    def run(self):
        """Run the data generator continuously."""
        logger.info(f"Starting data generator (App ID: {self.app_id}, Version: {self.get_app_version()})")
        
        try:
            # Create a health check endpoint
            self.create_health_check_file()
            
            while True:
                # Generate and store a data point
                data_point = self.generate_data_point()
                success = self.store_data(data_point)
                
                if success:
                    logger.info(f"Generated data point #{self.counter}: {data_point['value']:.2f}")
                else:
                    logger.warning(f"Failed to store data point #{self.counter}")
                
                # Update health check
                self.update_health_check_file()
                
                # Sleep until next generation
                time.sleep(self.config['generate_interval_seconds'])
                
        except KeyboardInterrupt:
            logger.info("Data generator stopped by user")
        except Exception as e:
            logger.error(f"Error in data generator: {e}")
    
    def create_health_check_file(self):
        """Create a health check file for the OTA updater to monitor."""
        try:
            health_file = "health.json"
            with open(health_file, 'w') as f:
                json.dump({
                    "status": "healthy",
                    "app_id": self.app_id,
                    "version": self.get_app_version(),
                    "last_update": datetime.now().isoformat()
                }, f)
        except Exception as e:
            logger.error(f"Error creating health check file: {e}")
    
    def update_health_check_file(self):
        """Update the health check file."""
        try:
            health_file = "health.json"
            with open(health_file, 'w') as f:
                json.dump({
                    "status": "healthy",
                    "app_id": self.app_id,
                    "version": self.get_app_version(),
                    "last_update": datetime.now().isoformat(),
                    "data_points_generated": self.counter
                }, f)
        except Exception as e:
            logger.error(f"Error updating health check file: {e}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        config_file = "app_config.json"
        print(f"No config file provided, using default: {config_file}")
    else:
        config_file = sys.argv[1]
    
    if not os.path.exists(config_file):
        # Create a default config file
        with open(config_file, 'w') as f:
            json.dump({
                "storage": {"type": "file", "path": "data.log"},
                "generate_interval_seconds": 5
            }, f, indent=2)
        print(f"Created default config file: {config_file}")
    
    app = DataGenerator(config_file)
    app.run()