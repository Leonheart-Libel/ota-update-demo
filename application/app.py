#!/usr/bin/env python3
"""
Enhanced test application that generates sophisticated data including simulated
weather patterns, system metrics, and stores it in SQLite with an expanded schema.
This application is the target of OTA updates.
"""
import os
import time
import random
import sqlite3
import logging
import platform
import psutil
import json
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("application/app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("EnhancedTestApp")

# App version - read from version file
version_files = [
    "application/version.txt",  # Path relative to project root
    "version.txt",              # Path relative to current directory
    "../application/version.txt"  # Another possible path
]

APP_VERSION = "3.0.0"  # Updated version number
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

class WeatherSimulator:
    """Simulates weather conditions that change gradually over time."""
    
    def __init__(self):
        self.temperature = random.uniform(0, 30)  # Initial temp in Celsius
        self.humidity = random.uniform(30, 90)    # Initial humidity percentage
        self.pressure = random.uniform(990, 1030) # Initial pressure in hPa
        self.wind_speed = random.uniform(0, 30)   # Initial wind speed in km/h
        self.conditions = random.choice(["Sunny", "Cloudy", "Rainy", "Stormy", "Windy", "Foggy"])
        self.last_update = datetime.now()
    
    def update(self):
        """Update weather conditions realistically."""
        # Calculate time difference to scale changes
        now = datetime.now()
        time_diff = (now - self.last_update).total_seconds() / 60.0  # Minutes
        self.last_update = now
        
        # Apply small random changes scaled by time
        self.temperature += random.uniform(-2, 2) * time_diff / 30
        self.temperature = max(-30, min(45, self.temperature))  # Constrain to realistic range
        
        self.humidity += random.uniform(-5, 5) * time_diff / 30
        self.humidity = max(10, min(100, self.humidity))
        
        self.pressure += random.uniform(-3, 3) * time_diff / 30
        self.pressure = max(950, min(1050, self.pressure))
        
        self.wind_speed += random.uniform(-5, 5) * time_diff / 30
        self.wind_speed = max(0, min(100, self.wind_speed))
        
        # Occasionally change weather conditions
        if random.random() < 0.1 * time_diff / 30:
            self.conditions = random.choice(["Sunny", "Cloudy", "Rainy", "Stormy", "Windy", "Foggy"])
    
    def get_data(self):
        """Return current weather data."""
        self.update()
        return {
            "temperature": round(self.temperature, 1),
            "humidity": round(self.humidity, 1),
            "pressure": round(self.pressure, 1),
            "wind_speed": round(self.wind_speed, 1),
            "conditions": self.conditions
        }

class SystemMetrics:
    """Collects system performance metrics."""
    
    @staticmethod
    def get_data():
        """Get current system metrics."""
        try:
            return {
                "cpu_percent": psutil.cpu_percent(interval=0.5),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_percent": psutil.disk_usage('/').percent,
                "boot_time": datetime.fromtimestamp(psutil.boot_time()).isoformat(),
                "platform": platform.platform(),
                "python_version": platform.python_version()
            }
        except Exception as e:
            logger.error(f"Error getting system metrics: {e}")
            return {
                "error": str(e)
            }

class EnhancedTestApplication:
    def __init__(self, db_path="data/app.db"):
        """Initialize the enhanced test application with database connection."""
        logger.info(f"Starting Enhanced Test Application v{APP_VERSION}")
        
        # Ensure data directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # Initialize weather simulator
        self.weather = WeatherSimulator()
        
        # Connect to SQLite database
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        
        # Create enhanced tables (migrate old data)
        self.upgrade_database()
        
    def upgrade_database(self):
        """Upgrade database schema while preserving existing data."""
        # Check if the old table exists
        self.cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='log_data'")
        old_table_exists = bool(self.cursor.fetchone())
        
        if old_table_exists:
            # Backup old data
            self.cursor.execute("CREATE TABLE IF NOT EXISTS log_data_backup AS SELECT * FROM log_data")
            self.conn.commit()
            logger.info("Backed up old log_data table")
            
            # Drop the old table
            self.cursor.execute("DROP TABLE log_data")
            self.conn.commit()
        
        # Create new enhanced table
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS log_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            value REAL,
            message TEXT,
            version TEXT,
            weather_data TEXT,
            system_metrics TEXT,
            data_quality INTEGER,
            tags TEXT
        )
        ''')
        self.conn.commit()
        
        # Create index for faster queries
        self.cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON log_data (timestamp)")
        self.conn.commit()
        
        if old_table_exists:
            # Migrate old data to new schema
            self.cursor.execute('''
            INSERT INTO log_data (timestamp, value, message, version)
            SELECT timestamp, value, message, version FROM log_data_backup
            ''')
            self.conn.commit()
            logger.info("Migrated old data to new schema")
        
    def generate_data(self):
        """Generate enhanced data points with timestamp, weather, and system metrics."""
        timestamp = datetime.now().isoformat()
        base_value = random.uniform(0, 100)
        
        # Get weather data
        weather_data = self.weather.get_data()
        
        # Get system metrics
        system_metrics = SystemMetrics.get_data()
        
        # Calculate a "data quality" score (0-100)
        data_quality = random.randint(50, 100)
        
        # Generate tags for this data point
        tags = random.sample(["production", "test", "critical", "normal", "high", "low"], 
                             random.randint(1, 3))
        
        # Create message with enhanced information
        message = (f"Enhanced data point: {base_value:.2f}, "
                   f"Weather: {weather_data['conditions']} {weather_data['temperature']}°C, "
                   f"System load: {system_metrics.get('cpu_percent', 0)}% CPU")
        
        return {
            "timestamp": timestamp,
            "value": base_value,
            "message": message,
            "version": APP_VERSION,
            "weather_data": json.dumps(weather_data),
            "system_metrics": json.dumps(system_metrics),
            "data_quality": data_quality,
            "tags": json.dumps(tags)
        }
    
    def store_data(self, data):
        """Store enhanced data in SQLite database."""
        self.cursor.execute(
            '''INSERT INTO log_data 
               (timestamp, value, message, version, weather_data, system_metrics, data_quality, tags) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            (data["timestamp"], data["value"], data["message"], data["version"],
             data["weather_data"], data["system_metrics"], data["data_quality"], data["tags"])
        )
        self.conn.commit()
        
    def run(self, interval=5):
        """Run the application, generating and storing enhanced data periodically."""
        logger.info(f"Enhanced Application running with version {APP_VERSION}")
        
        try:
            while True:
                data = self.generate_data()
                self.store_data(data)
                logger.info(f"Enhanced data stored: {data['timestamp']} - {data['message']}")
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
    
    app = EnhancedTestApplication()
    app.run(interval=interval)