#!/usr/bin/env python3
"""
Simple test application that generates timestamped dummy data and stores it in SQLite.
This application will be the target of OTA updates.
"""
import os
import time
import random
import sqlite3
import logging
from datetime import datetime
import json

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("application/app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("TestApp")

# App version - this will change with updates
APP_VERSION = "1.0.0"

class TestApplication:
    def __init__(self, db_path="data/app.db"):
        """Initialize the test application with database connection."""
        logger.info(f"Starting Test Application v{APP_VERSION}")
        
        # Ensure data directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # Connect to SQLite database
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        
        # Create table if it doesn't exist
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS log_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            value REAL,
            message TEXT,
            version TEXT
        )
        ''')
        self.conn.commit()
        
    def generate_data(self):
        """Generate random dummy data with timestamp."""
        timestamp = datetime.now().isoformat()
        value = random.uniform(0, 100)
        message = f"Sample data point: {value:.2f}"
        
        return {
            "timestamp": timestamp,
            "value": value,
            "message": message,
            "version": APP_VERSION
        }
    
    def store_data(self, data):
        """Store data in SQLite database."""
        self.cursor.execute(
            "INSERT INTO log_data (timestamp, value, message, version) VALUES (?, ?, ?, ?)",
            (data["timestamp"], data["value"], data["message"], data["version"])
        )
        self.conn.commit()
        
    def run(self, interval=5):
        """Run the application, generating and storing data periodically."""
        logger.info(f"Application running with version {APP_VERSION}")
        
        try:
            while True:
                data = self.generate_data()
                self.store_data(data)
                logger.info(f"Data stored: {data}")
                time.sleep(interval)
        except KeyboardInterrupt:
            logger.info("Application shutdown requested")
        except Exception as e:
            logger.error(f"Error in application: {str(e)}")
        finally:
            self.conn.close()
            logger.info("Application stopped")

if __name__ == "__main__":
    # Load configuration if exists
    config_path = "application/app_config.py"
    interval = 5  # Default interval
    
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                for line in f:
                    if line.startswith("INTERVAL"):
                        interval = int(line.split("=")[1].strip())
        except Exception as e:
            logger.warning(f"Error loading config: {str(e)}")
    
    app = TestApplication()
    app.run(interval=interval)