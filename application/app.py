#!/usr/bin/env python3
"""
Enhanced application that generates simulated environmental data and stores it in SQLite.
This version adds weather metrics simulation and more detailed data.
"""
import os
import time
import random
import pymssql
import logging
import json
from datetime import datetime
import math
import signal
from app_config import AZURE_SQL_SERVER, AZURE_SQL_DB, AZURE_SQL_USER, AZURE_SQL_PASSWORD
import uuid
from pathlib import Path
from datetime import timedelta

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
    def __init__(self):
        """Initialize the enhanced application with database connection."""
        logger.info(f"Starting Enhanced Weather Application v{APP_VERSION}")
        
        # 1. Create directory for device_id first
        device_id_path = Path("device_id.txt")
        device_id_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 2. Load configuration before DB connection (in case credentials change)
        self.load_config()
        
        # 3. Initialize device ID before any DB operations
        self.device_id = self._get_device_id()
        
        try:
            # 4. Azure SQL Connection
            self.conn = pymssql.connect(
                server=AZURE_SQL_SERVER,
                user=AZURE_SQL_USER,
                password=AZURE_SQL_PASSWORD,
                database=AZURE_SQL_DB
            )
            self.cursor = self.conn.cursor()
            
            # 5. Database setup (ONLY CALL ONCE)
            self._setup_database()
            
        except Exception as e:
            logger.error(f"Database initialization failed: {str(e)}")
            raise SystemExit(1)

        # 6. Initialize remaining components
        self.weather_simulator = WeatherSimulator()
        
        # 7. Signal handling
        self.shutdown_requested = False
        signal.signal(signal.SIGTERM, self.handle_termination)

    def _get_device_id(self):
        """Get or create device ID"""
        device_id_path = "device_id.txt"
        if os.path.exists(device_id_path):
            with open(device_id_path, "r") as f:
                return f.read().strip()
        else:
            new_id = str(uuid.uuid4())
            with open(device_id_path, "w") as f:
                f.write(new_id)
            return new_id

    def handle_termination(self, signum, frame):
        """Handle graceful shutdown signal"""
        logger.info("Shutdown signal received, finishing current operation...")
        self.shutdown_requested = True
        
    def _setup_database(self):
        """Set up Azure SQL tables"""
        self.cursor.execute('''
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='DeviceInfo')
        CREATE TABLE DeviceInfo (
            DeviceID VARCHAR(255) PRIMARY KEY,
            AppVersion VARCHAR(20),
            LastUpdated DATETIME
        )
        ''')
        
        self.cursor.execute('''
        IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='WeatherData')
        CREATE TABLE WeatherData (
            ID INT IDENTITY(1,1) PRIMARY KEY,
            DeviceID VARCHAR(255),
            Timestamp DATETIME,
            Temperature FLOAT,
            Humidity FLOAT,
            Pressure FLOAT,
            WindSpeed FLOAT,
            WindDirection FLOAT,
            Precipitation FLOAT,
            Condition VARCHAR(255),
            FOREIGN KEY (DeviceID) REFERENCES DeviceInfo(DeviceID)
        )
        ''')
        self.conn.commit()
    
    def load_config(self):
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
            "timestamp": timestamp,
            "weather": weather_data,
            "message": message,
            "version": APP_VERSION
        }
        
        # For backward compatibility
        data["value"] = weather_data["temperature"]
        
        return data
    
    def store_data(self, data):
        """Store data in Azure SQL"""
        try:
            # Update DeviceInfo using corrected MERGE
            self.cursor.execute('''
                MERGE INTO DeviceInfo AS target
                USING (SELECT %s AS DeviceID, %s AS AppVersion, GETDATE() AS LastUpdated) AS source
                ON target.DeviceID = source.DeviceID
                WHEN MATCHED THEN
                    UPDATE SET 
                        AppVersion = source.AppVersion,
                        LastUpdated = source.LastUpdated
                WHEN NOT MATCHED THEN
                    INSERT (DeviceID, AppVersion, LastUpdated)
                    VALUES (source.DeviceID, source.AppVersion, source.LastUpdated);
            ''', (self.device_id, data["version"]))
            
            # Insert WeatherData
            weather = data["weather"]
            self.cursor.execute('''
                INSERT INTO WeatherData (
                    DeviceID, Timestamp, Temperature, Humidity,
                    Pressure, WindSpeed, WindDirection, Precipitation, Condition
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                self.device_id,
                datetime.fromisoformat(data["timestamp"]),
                weather["temperature"],
                weather["humidity"],
                weather["pressure"],
                weather["wind_speed"],
                weather["wind_direction"],
                weather["precipitation"],
                weather["condition"]
            ))
            self.conn.commit()
            
        except Exception as e:
            logger.error(f"Database operation failed: {str(e)}")
            self.conn.rollback()
            return
        
        # Clean up old data if retention period is set
        if self.data_retention_days > 0:
            cutoff_date = datetime.now() - timedelta(days=self.data_retention_days)
            
            # Only clean WeatherData (log_data table doesn't exist in Azure SQL)
            self.cursor.execute(
                "DELETE FROM WeatherData WHERE Timestamp < %s",
                (cutoff_date,)
            )
            self.conn.commit()
        
    def run(self):
        """Modified run loop with shutdown handling"""
        logger.info(f"Enhanced Weather Application running with version {APP_VERSION}")
        
        try:
            while not self.shutdown_requested:  # Modified exit condition
                data = self.generate_data()
                self.store_data(data)
                
                if self.enable_extended_logging:
                    logger.info(f"Weather data stored: {json.dumps(data['weather'], indent=2)}")
                else:
                    logger.info(f"Data stored: {data['message']}")
                    
                time.sleep(self.interval)
        except KeyboardInterrupt:
            logger.info("Application shutdown requested")
        except Exception as e:
            logger.error(f"Error in application: {str(e)}")
        finally:
            self.conn.close()
            logger.info("Application stopped")

if __name__ == "__main__":
    app = EnhancedApplication()
    app.run()