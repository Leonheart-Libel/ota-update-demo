#!/usr/bin/env python3
"""
Enhanced application that generates simulated environmental data and stores it in Azure SQL Database.
This version adds weather metrics simulation and device tracking.
"""
import os
import time
import random
import logging
import json
import pyodbc
from datetime import datetime
import math
import signal
import socket

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("application/app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("EnhancedWeatherApp")


# App version - read from version file
version_files = [
    "application/version.txt",  # Path relative to project root
    "version.txt",              # Path relative to current directory
    "../application/version.txt"  # Another possible path
]

APP_VERSION = "1.0.0"  # Default fallback version
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
    """Simulates weather patterns with realistic variations over time"""
    
    def __init__(self):
        # Base values for different metrics
        self.base_temperature = random.uniform(15.0, 25.0)  # Celsius
        self.base_humidity = random.uniform(40.0, 70.0)     # Percentage
        self.base_pressure = random.uniform(1000.0, 1020.0) # hPa
        self.base_wind_speed = random.uniform(5.0, 15.0)    # km/h
        self.base_wind_direction = random.uniform(0, 360)   # Degrees
        self.base_precipitation = random.uniform(0, 5.0)    # mm
        
        # Time counters for oscillation
        self.time_counter = 0
        
        # Possible weather conditions
        self.weather_conditions = [
            "Clear", "Partly Cloudy", "Cloudy", "Overcast", 
            "Light Rain", "Moderate Rain", "Heavy Rain",
            "Light Snow", "Moderate Snow", "Heavy Snow",
            "Foggy", "Windy"
        ]
        self.current_condition = random.choice(self.weather_conditions)
        self.condition_duration = random.randint(5, 20)  # Duration in cycles
        self.condition_counter = 0
    
    def update(self):
        """Update weather values with realistic variations"""
        self.time_counter += 1
        self.condition_counter += 1
        
        # Potentially change weather condition
        if self.condition_counter >= self.condition_duration:
            self.condition_counter = 0
            self.condition_duration = random.randint(5, 20)
            
            # Weather tends to change gradually
            current_index = self.weather_conditions.index(self.current_condition)
            possible_indices = [
                max(0, current_index - 1),
                current_index,
                min(len(self.weather_conditions) - 1, current_index + 1)
            ]
            self.current_condition = self.weather_conditions[random.choice(possible_indices)]
        
        # Calculate oscillating variations
        temp_variation = math.sin(self.time_counter / 10) * 3 + random.uniform(-1, 1)
        humidity_variation = math.sin(self.time_counter / 12) * 5 + random.uniform(-2, 2)
        pressure_variation = math.sin(self.time_counter / 15) * 2 + random.uniform(-0.5, 0.5)
        wind_speed_variation = math.sin(self.time_counter / 8) * 2 + random.uniform(-1, 1)
        wind_dir_variation = random.uniform(-10, 10)
        precip_variation = 0
        
        # Add precipitation based on condition
        if "Rain" in self.current_condition or "Snow" in self.current_condition:
            intensity = 1
            if "Light" in self.current_condition:
                intensity = 0.5
            elif "Heavy" in self.current_condition:
                intensity = 2
            
            precip_variation = random.uniform(0, 2) * intensity
        
        # Update values with variations
        temperature = self.base_temperature + temp_variation
        humidity = min(100, max(0, self.base_humidity + humidity_variation))
        pressure = self.base_pressure + pressure_variation
        wind_speed = max(0, self.base_wind_speed + wind_speed_variation)
        wind_direction = (self.base_wind_direction + wind_dir_variation) % 360
        precipitation = max(0, self.base_precipitation + precip_variation)
        
        # Return weather data
        return {
            "temperature": round(temperature, 1),
            "humidity": round(humidity, 1),
            "pressure": round(pressure, 1),
            "wind_speed": round(wind_speed, 1),
            "wind_direction": round(wind_direction, 1),
            "precipitation": round(precipitation, 2),
            "condition": self.current_condition
        }


class EnhancedApplication:
    def __init__(self, config_path="config.json"):
        """Initialize the enhanced application with Azure SQL database connection."""
        logger.info(f"Starting Enhanced Weather Application v{APP_VERSION}")
        
        # Load configuration
        try:
            with open(config_path, 'r') as f:
                self.config = json.load(f)
        except Exception as e:
            logger.error(f"Error loading config file: {str(e)}")
            self.config = {}
        
        # Get device ID from config or generate one from hostname
        self.device_id = self.config.get("device_id", None)
        if not self.device_id:
            self.device_id = f"iot-{socket.gethostname()}"
        
        # Connect to Azure SQL database
        self.connect_to_database()
        
        # Initialize weather simulator
        self.weather_simulator = WeatherSimulator()
        
        # Load application configuration
        self.load_app_config()

        # Add shutdown flag and signal handler
        self.shutdown_requested = False
        signal.signal(signal.SIGTERM, self.handle_termination)
        
        # Register device in the device table
        self.register_device()
    
    def handle_termination(self, signum, frame):
        """Handle graceful shutdown signal"""
        logger.info("Shutdown signal received, finishing current operation...")
        self.shutdown_requested = True
    
    def connect_to_database(self):
        """Connect to Azure SQL Database using pyodbc"""
        try:
            azure_config = self.config.get("azure_sql", {})
            server = azure_config.get("server")
            database = azure_config.get("database")
            username = azure_config.get("username")
            password = azure_config.get("password")
            
            if not all([server, database, username, password]):
                raise ValueError("Missing Azure SQL configuration parameters")
            
            # Connect to Azure SQL using ODBC Driver 18
            connection_string = (
                f"Driver={{ODBC Driver 18 for SQL Server}};"
                f"Server={server};"
                f"Database={database};"
                f"Uid={username};"
                f"Pwd={password};"
                f"Encrypt=yes;"
                f"TrustServerCertificate=no;"
                f"Connection Timeout=30;"
            )
            
            self.conn = pyodbc.connect(connection_string)
            self.cursor = self.conn.cursor()
            
            # Create database tables if they don't exist
            self._setup_database()
            logger.info("Successfully connected to Azure SQL Database")
            return True
            
        except Exception as e:
            logger.error(f"Error connecting to Azure SQL Database: {str(e)}")
            
            # Create a fallback local SQLite database for reliability
            self._setup_fallback_database()
            return False
    
    def _setup_database(self):
        """Set up database schema in Azure SQL"""
        # Create weather data table
        self.cursor.execute('''
        IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'weather_data')
        CREATE TABLE weather_data (
            id INT IDENTITY(1,1) PRIMARY KEY,
            device_id VARCHAR(50) NOT NULL,
            timestamp DATETIMEOFFSET NOT NULL,
            temperature FLOAT,
            humidity FLOAT,
            pressure FLOAT,
            wind_speed FLOAT,
            wind_direction FLOAT,
            precipitation FLOAT,
            condition VARCHAR(50),
            message VARCHAR(255),
            version VARCHAR(20)
        )
        ''')
        
        # Create device info table
        self.cursor.execute('''
        IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'device_info')
        CREATE TABLE device_info (
            device_id VARCHAR(50) PRIMARY KEY,
            hostname VARCHAR(100),
            ip_address VARCHAR(50),
            last_seen DATETIMEOFFSET,
            app_version VARCHAR(20),
            status VARCHAR(20),
            location VARCHAR(100) NULL
        )
        ''')
        
        self.conn.commit()
    
    def _setup_fallback_database(self):
        """Setup a fallback SQLite database in case Azure SQL is unavailable"""
        import sqlite3
        
        # Ensure data directory exists
        os.makedirs("data", exist_ok=True)
        
        # Connect to SQLite database
        self.conn = sqlite3.connect("data/app.db")
        self.cursor = self.conn.cursor()
        
        # Create tables
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS weather_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT,
            timestamp TEXT,
            temperature REAL,
            humidity REAL,
            pressure REAL,
            wind_speed REAL,
            wind_direction REAL,
            precipitation REAL,
            condition TEXT,
            message TEXT,
            version TEXT
        )
        ''')
        
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS device_info (
            device_id TEXT PRIMARY KEY,
            hostname TEXT,
            ip_address TEXT,
            last_seen TEXT,
            app_version TEXT,
            status TEXT,
            location TEXT
        )
        ''')
        
        self.conn.commit()
        logger.warning("Using fallback SQLite database")
    
    def register_device(self):
        """Register or update device information in the device_info table"""
        try:
            # Get system information
            hostname = socket.gethostname()
            ip_address = socket.gethostbyname(hostname)
            timestamp = datetime.now().isoformat()
            
            # Check if device already exists
            self.cursor.execute(
                "SELECT COUNT(*) FROM device_info WHERE device_id = ?", 
                (self.device_id,)
            )
            count = self.cursor.fetchone()[0]
            
            if count > 0:
                # Update existing device
                self.cursor.execute(
                    """UPDATE device_info 
                       SET hostname = ?, ip_address = ?, last_seen = ?, 
                           app_version = ?, status = ? 
                       WHERE device_id = ?""",
                    (hostname, ip_address, timestamp, APP_VERSION, "online", self.device_id)
                )
            else:
                # Insert new device
                self.cursor.execute(
                    """INSERT INTO device_info 
                       (device_id, hostname, ip_address, last_seen, app_version, status) 
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (self.device_id, hostname, ip_address, timestamp, APP_VERSION, "online")
                )
            
            self.conn.commit()
            logger.info(f"Device registered with ID: {self.device_id}")
            
        except Exception as e:
            logger.error(f"Error registering device: {str(e)}")
    
    def load_app_config(self):
        """Load application configuration"""
        self.interval = 5  # Default interval
        self.enable_extended_logging = True  # Default extended logging
        self.data_retention_days = 30  # Default data retention
        
        config_path = "application/app_config.py"
        
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    for line in f:
                        if line.startswith("INTERVAL"):
                            self.interval = int(line.split("=")[1].strip())
                        elif line.startswith("ENABLE_EXTENDED_LOGGING"):
                            value = line.split("=")[1].strip()
                            self.enable_extended_logging = value.lower() == "true"
                        elif line.startswith("DATA_RETENTION_DAYS"):
                            self.data_retention_days = int(line.split("=")[1].strip())
                            
                logger.info(f"Loaded configuration: interval={self.interval}s, extended_logging={self.enable_extended_logging}")
            except Exception as e:
                logger.warning(f"Error loading config: {str(e)}")
        
    def generate_data(self):
        """Generate enhanced weather data with timestamp."""
        timestamp = datetime.now().isoformat()
        
        # Get simulated weather data
        weather_data = self.weather_simulator.update()
        
        # Generate a meaningful message based on the weather condition
        condition = weather_data["condition"]
        temp = weather_data["temperature"]
        
        message = f"Current weather: {condition} at {temp}°C"
        if "Rain" in condition:
            message += f", precipitation: {weather_data['precipitation']}mm"
        if weather_data["wind_speed"] > 20:
            message += f", strong winds: {weather_data['wind_speed']}km/h"
        
        # Create complete data record
        data = {
            "device_id": self.device_id,
            "timestamp": timestamp,
            "weather": weather_data,
            "message": message,
            "version": APP_VERSION
        }
        
        # For backward compatibility
        data["value"] = weather_data["temperature"]
        
        return data
    
    def store_data(self, data):
        """Store enhanced data in Azure SQL database."""
        try:
            # Store in the weather_data table
            weather = data["weather"]
            self.cursor.execute(
                """INSERT INTO weather_data 
                   (device_id, timestamp, temperature, humidity, pressure, wind_speed, wind_direction, 
                    precipitation, condition, message, version) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (data["device_id"], data["timestamp"], weather["temperature"], weather["humidity"], 
                 weather["pressure"], weather["wind_speed"], weather["wind_direction"],
                 weather["precipitation"], weather["condition"], data["message"], data["version"])
            )
            
            # Update device last_seen time
            self.cursor.execute(
                "UPDATE device_info SET last_seen = ?, app_version = ? WHERE device_id = ?",
                (data["timestamp"], data["version"], data["device_id"])
            )
            
            self.conn.commit()
            
            # Clean up old data if retention period is set
            if self.data_retention_days > 0:
                cutoff_date = datetime.now().replace(
                    hour=0, minute=0, second=0, microsecond=0
                ).toordinal() - self.data_retention_days
                
                cutoff_timestamp = datetime.fromordinal(cutoff_date).isoformat()
                
                self.cursor.execute(
                    "DELETE FROM weather_data WHERE timestamp < ?", 
                    (cutoff_timestamp,)
                )
                self.conn.commit()
            
            return True
        except Exception as e:
            logger.error(f"Error storing data: {str(e)}")
            return False
        
    def run(self):
        """Modified run loop with shutdown handling"""
        logger.info(f"Enhanced Weather Application running with version {APP_VERSION}")
        
        try:
            while not self.shutdown_requested:
                data = self.generate_data()
                success = self.store_data(data)
                
                if success:
                    if self.enable_extended_logging:
                        logger.info(f"Weather data stored: {json.dumps(data['weather'], indent=2)}")
                    else:
                        logger.info(f"Data stored: {data['message']}")
                else:
                    logger.warning("Failed to store data, will retry in next cycle")
                    
                time.sleep(self.interval)
        except KeyboardInterrupt:
            logger.info("Application shutdown requested")
        except Exception as e:
            logger.error(f"Error in application: {str(e)}")
        finally:
            # Update device status to offline on shutdown
            try:
                self.cursor.execute(
                    "UPDATE device_info SET status = ? WHERE device_id = ?",
                    ("offline", self.device_id)
                )
                self.conn.commit()
            except:
                pass
                
            try:
                self.conn.close()
            except:
                pass
                
            logger.info("Application stopped")

if __name__ == "__main__":
    app = EnhancedApplication()
    app.run()