#!/usr/bin/env python3
"""
Enhanced test application that generates more complex data, performs analysis,
and provides a simple HTTP API for data access.
This application is the target of OTA updates.
"""
import os
import sys
import time
import random
import sqlite3
import logging
import threading
import json
from datetime import datetime, timedelta

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("application/app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("EnhancedApp")

# App version - read from version file
version_files = [
    "application/version.txt",  # Path relative to project root
    "version.txt",              # Path relative to current directory
    "../application/version.txt"  # Another possible path
]

APP_VERSION = "2.0.0"  # Default fallback version
for version_file in version_files:
    try:
        if os.path.exists(version_file):
            with open(version_file, "r") as f:
                version = f.read().strip()
                if version:  # Only use if not empty
                    APP_VERSION = version
                    logger.info(f"Loaded version {APP_VERSION} from {version_file}")
                    break
    except Exception as e:
        logger.warning(f"Error reading version file {version_file}: {str(e)}")

logger.info(f"Current working directory: {os.getcwd()}")
logger.info(f"Using application version: {APP_VERSION}")

# Load configuration
def load_config():
    """Load application configuration from app_config.py"""
    config = {
        "interval": 5,
        "data_mode": "random",
        "api_enabled": False,  # Default to disabled for safety
        "api_port": 8080,
        "analysis_enabled": True,
        "analysis_window": 60  # seconds
    }
    
    config_path = "application/app_config.py"
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        try:
                            key, value = line.split("=", 1)
                            key = key.strip()
                            value = value.strip()
                            
                            # Convert value to appropriate type
                            if value.lower() == "true":
                                value = True
                            elif value.lower() == "false":
                                value = False
                            elif value.isdigit():
                                value = int(value)
                            elif value.replace(".", "", 1).isdigit():
                                value = float(value)
                                
                            config[key.lower()] = value
                        except ValueError:
                            pass
        except Exception as e:
            logger.warning(f"Error loading config: {str(e)}")
    
    return config

class DataAnalyzer:
    """Analyzes data and computes statistics"""
    def __init__(self, db_path, window_seconds=60):
        self.db_path = db_path
        self.window_seconds = window_seconds
        self.last_analysis = None
    
    def analyze(self):
        """Analyze recent data and return statistics"""
        try:
            # Connect to database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get data from last window_seconds
            window_start = (datetime.now() - timedelta(seconds=self.window_seconds)).isoformat()
            cursor.execute(
                "SELECT value FROM log_data WHERE timestamp > ? ORDER BY timestamp",
                (window_start,)
            )
            
            values = [row[0] for row in cursor.fetchall()]
            conn.close()
            
            if not values:
                return {
                    "timestamp": datetime.now().isoformat(),
                    "status": "no_data",
                    "count": 0
                }
            
            # Calculate statistics
            result = {
                "timestamp": datetime.now().isoformat(),
                "status": "success",
                "count": len(values),
                "min": min(values),
                "max": max(values),
                "mean": sum(values) / len(values),
                "median": sorted(values)[len(values) // 2]
            }
            
            # Add standard deviation if we have enough data points
            if len(values) > 1:
                mean = result["mean"]
                variance = sum((x - mean) ** 2 for x in values) / len(values)
                result["std_dev"] = variance ** 0.5
            
            self.last_analysis = result
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing data: {str(e)}")
            return {
                "timestamp": datetime.now().isoformat(),
                "status": "error",
                "error": str(e)
            }

class EnhancedApplication:
    def __init__(self, db_path="data/app.db"):
        """Initialize the enhanced application with database connection."""
        self.start_time = datetime.now()
        logger.info(f"Starting Enhanced Application v{APP_VERSION}")
        logger.info(f"Current working directory: {os.getcwd()}")
        
        self.config = load_config()
        logger.info(f"Loaded configuration: {self.config}")
        
        # Ensure data directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        
        # Connect to SQLite database
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        
        # Check if log_data table has data_type column
        try:
            self.cursor.execute("PRAGMA table_info(log_data)")
            columns = [info[1] for info in self.cursor.fetchall()]
            has_data_type = "data_type" in columns
            
            if not has_data_type:
                logger.info("Adding data_type column to log_data table")
                self.cursor.execute("ALTER TABLE log_data ADD COLUMN data_type TEXT DEFAULT 'random'")
                self.conn.commit()
        except Exception as e:
            logger.critical(f"Fatal error during initialization: {str(e)}", exc_info=True)
            sys.exit(1)
        
        # Ensure log_data table exists
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS log_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            value REAL,
            message TEXT,
            version TEXT,
            data_type TEXT DEFAULT 'random'
        )
        ''')
        
        # Create analysis table if it doesn't exist
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS analysis_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            count INTEGER,
            min_value REAL,
            max_value REAL,
            mean_value REAL,
            median_value REAL,
            std_dev REAL
        )
        ''')
        self.conn.commit()
        
        # Initialize analyzer if enabled
        self.analyzer = None
        if self.config.get("analysis_enabled", True):
            self.analyzer = DataAnalyzer(
                db_path, 
                window_seconds=self.config.get("analysis_window", 60)
            )
        
        # We'll enable API functionality in a future update
        # Start simple first to ensure stability
        self.api_server = None
    
    def generate_data(self):
        """Generate data based on the configured mode."""
        timestamp = datetime.now().isoformat()
        data_mode = self.config.get("data_mode", "random")
        data_type = data_mode
        
        if data_mode == "sine":
            # Generate sine wave pattern
            # Using inline sin calculation without math module
            seconds = time.time()
            # Simple approximation of sin
            angle = (seconds % 6.28) / 10
            value = 50 + 50 * (-1 if angle > 3.14 else 1) * (angle % 3.14) / 3.14
            message = f"Sine approximation data point: {value:.2f}"
        
        elif data_mode == "step":
            # Generate stepping pattern (0, 25, 50, 75, 100)
            step = int(time.time() / 5) % 5
            value = step * 25
            message = f"Step data point: {value}"
            
        elif data_mode == "random_walk":
            # Get last value and add random walk
            try:
                self.cursor.execute(
                    "SELECT value FROM log_data ORDER BY id DESC LIMIT 1"
                )
                result = self.cursor.fetchone()
                last_value = result[0] if result else 50
                
                # Add random walk with bounds
                value = max(0, min(100, last_value + random.uniform(-10, 10)))
                message = f"Random walk data point: {value:.2f}"
            except Exception:
                # Fallback to random if error
                value = random.uniform(0, 100)
                message = f"Fallback random data point: {value:.2f}"
        
        else:
            # Default to random
            value = random.uniform(0, 100)
            message = f"Random data point: {value:.2f}"
            data_type = "random"
        
        return {
            "timestamp": timestamp,
            "value": value,
            "message": message,
            "version": APP_VERSION,
            "data_type": data_type
        }
    
    def store_data(self, data):
        """Store data in SQLite database."""
        try:
            self.cursor.execute(
                "INSERT INTO log_data (timestamp, value, message, version, data_type) VALUES (?, ?, ?, ?, ?)",
                (data["timestamp"], data["value"], data["message"], data["version"], data["data_type"])
            )
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error storing data: {str(e)}")
            # Try with the original schema as fallback
            try:
                self.cursor.execute(
                    "INSERT INTO log_data (timestamp, value, message, version) VALUES (?, ?, ?, ?)",
                    (data["timestamp"], data["value"], data["message"], data["version"])
                )
                self.conn.commit()
                return True
            except Exception as e2:
                logger.error(f"Failed fallback insert: {str(e2)}")
                return False
    
    def run_analysis(self):
        """Run data analysis and store results."""
        if not self.analyzer:
            return
            
        analysis = self.analyzer.analyze()
        
        if analysis.get("status") == "success":
            try:
                # Store analysis results
                self.cursor.execute(
                    """
                    INSERT INTO analysis_results 
                    (timestamp, count, min_value, max_value, mean_value, median_value, std_dev) 
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        analysis["timestamp"], 
                        analysis["count"],
                        analysis["min"],
                        analysis["max"],
                        analysis["mean"],
                        analysis["median"],
                        analysis.get("std_dev", 0)
                    )
                )
                self.conn.commit()
                logger.info(f"Analysis complete: {analysis}")
            except Exception as e:
                logger.error(f"Error storing analysis: {str(e)}")
    
    def get_data_count(self):
        """Get the total count of data points."""
        try:
            self.cursor.execute("SELECT COUNT(*) FROM log_data")
            return self.cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"Error getting data count: {str(e)}")
            return 0
    
    def get_recent_data(self, limit=20):
        """Get the most recent data points."""
        try:
            self.cursor.execute(
                "SELECT timestamp, value, message, version FROM log_data ORDER BY id DESC LIMIT ?",
                (limit,)
            )
            columns = ["timestamp", "value", "message", "version"]
            result = []
            for row in self.cursor.fetchall():
                result.append(dict(zip(columns, row)))
            return result
        except Exception as e:
            logger.error(f"Error getting recent data: {str(e)}")
            return []
        
    def run(self):
        """Run the application, generating and storing data periodically."""
        logger.info(f"Enhanced application running with version {APP_VERSION}")
        
        # Track time for analysis scheduling
        last_analysis_time = datetime.now()
        analysis_interval = self.config.get("analysis_interval", 30)  # seconds
        
        try:
            while True:
                # Generate and store data
                data = self.generate_data()
                if self.store_data(data):
                    logger.info(f"Data stored: {data}")
                
                # Run analysis if it's time
                now = datetime.now()
                if (now - last_analysis_time).total_seconds() >= analysis_interval:
                    self.run_analysis()
                    last_analysis_time = now
                
                # Sleep for the configured interval
                time.sleep(self.config.get("interval", 5))
                
        except KeyboardInterrupt:
            logger.info("Application shutdown requested")
        except Exception as e:
            logger.error(f"Error in application: {str(e)}")
        finally:
            if self.api_server:
                logger.info("Shutting down API server...")
                try:
                    self.api_server.shutdown()
                except Exception as e:
                    logger.error(f"Error shutting down API server: {str(e)}")
                
            self.conn.close()
            logger.info("Application stopped")

    def migrate_database(self):
        """Handle database schema migrations between versions."""
        try:
            # Check for existing tables
            self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [table[0] for table in self.cursor.fetchall()]
            
            # Create required tables if they don't exist
            if "log_data" not in tables:
                self.cursor.execute('''
                CREATE TABLE log_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    value REAL,
                    message TEXT,
                    version TEXT,
                    data_type TEXT DEFAULT 'random'
                )
                ''')
                logger.info("Created log_data table")
            else:
                # Add data_type column if it doesn't exist
                self.cursor.execute("PRAGMA table_info(log_data)")
                columns = [info[1] for info in self.cursor.fetchall()]
                if "data_type" not in columns:
                    self.cursor.execute("ALTER TABLE log_data ADD COLUMN data_type TEXT DEFAULT 'random'")
                    logger.info("Added data_type column to log_data table")
            
            # Create analysis table
            if "analysis_results" not in tables:
                self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS analysis_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    count INTEGER,
                    min_value REAL,
                    max_value REAL,
                    mean_value REAL,
                    median_value REAL,
                    std_dev REAL
                )
                ''')
                logger.info("Created analysis_results table")
            
            self.conn.commit()
        except Exception as e:
            logger.error(f"Error during database migration: {str(e)}")
            raise

if __name__ == "__main__":
    app = EnhancedApplication()
    app.run()