#!/usr/bin/env python3
"""
Enhanced application that generates simulated environmental data and stores it in Azure SQL Database.
This version adds device identification and uses Azure SQL instead of SQLite.
"""
import os
import time
import random
import logging
import json
import pyodbc
import socket
import math
import signal
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
    def __init__(self, db_config_path="application/db_config.json"):
        """Initialize the enhanced application with database connection."""
        logger.info(f"Starting Enhanced Weather Application v{APP_VERSION}")
        
        # Load database configuration
        self.db_config = self._load_db_config(db_config_path)
        
        # Establish connection to Azure SQL
        self.conn = self._connect_to_azure_sql()
        
        # Setup database tables
        self._setup_database()
        
        # Initialize device identification
        self.device_id = self._get_device_id()
        
        # Initialize weather simulator
        self.weather_simulator = WeatherSimulator()
        
        # Load application configuration
        self.load_config()

        # Register device in the database
        self._register_device()

        # Add shutdown flag and signal handler
        self.shutdown_requested = False
        signal.signal(signal.SIGTERM, self.handle_termination)
    
    def _load_db_config(self, config_path):
        """Load database configuration from JSON file"""
        default_config = {
            "server": "your-server-name.database.windows.net",
            "database": "WeatherDB",
            "username": "your-username",
            "password": "your-password",
            "driver": "{ODBC Driver 18 for SQL Server}"
        }
        
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    return json.load(f)
            else:
                logger.warning(f"Database config file not found at {config_path}, using default configuration")
                # Create a default config file
                os.makedirs(os.path.dirname(config_path), exist_ok=True)
                with open(config_path, 'w') as f:
                    json.dump(default_config, f, indent=4)
                return default_config
        except Exception as e:
            logger.error(f"Error loading database config: {str(e)}, using default")
            return default_config
    
    def _connect_to_azure_sql(self):
        """Establish connection to Azure SQL Database"""
        try:
            connection_string = (
                f"DRIVER={self.db_config['driver']};"
                f"SERVER={self.db_config['server']};"
                f"DATABASE={self.db_config['database']};"
                f"UID={self.db_config['username']};"
                f"PWD={self.db_config['password']};"
                "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
            )
            
            logger.info(f"Connecting to Azure SQL Database: {self.db_config['server']}/{self.db_config['database']}")
            conn = pyodbc.connect(connection_string)
            logger.info("Successfully connected to Azure SQL Database")
            return conn
        except Exception as e:
            logger.error(f"Failed to connect to Azure SQL Database: {str(e)}")
            # Retry with local file-based logging as fallback
            logger.warning("Using local file-based logging as fallback")
            self._setup_local_fallback()
            return None
    
    def _setup_local_fallback(self):
        """Set up local file-based logging as fallback when Azure SQL is unavailable"""
        self.local_data_file = "data/local_weather_data.json"
        os.makedirs(os.path.dirname(self.local_data_file), exist_ok=True)
        logger.info(f"Local fallback data will be stored in {self.local_data_file}")
    
    def _get_device_id(self):
        """Generate a unique device ID using hostname and MAC address"""
        hostname = socket.gethostname()
        
        # Try to get a unique identifier from the machine
        try:
            # Get MAC address (platform independent)
            import uuid
            mac = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff) 
                           for elements in range(0, 48, 8)])
            device_id = f"{hostname}-{mac}"
        except:
            # Fallback to just hostname with timestamp if MAC retrieval fails
            device_id = f"{hostname}-{int(time.time())}"
        
        logger.info(f"Device identified as: {device_id}")
        return device_id
    
    def _setup_database(self):
        """Set up database schema for weather data and device information"""
        if self.conn is None:
            logger.warning("Database connection not available, skipping database setup")
            return
        
        try:
            cursor = self.conn.cursor()
            
            # Create table for weather data
            cursor.execute('''
            IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[weather_data]') AND type in (N'U'))
            BEGIN
                CREATE TABLE [dbo].[weather_data] (
                    [id] [int] IDENTITY(1,1) PRIMARY KEY,
                    [device_id] [varchar](100) NOT NULL,
                    [timestamp] [datetime2](7) NOT NULL,
                    [temperature] [float] NULL,
                    [humidity] [float] NULL,
                    [pressure] [float] NULL,
                    [wind_speed] [float] NULL,
                    [wind_direction] [float] NULL,
                    [precipitation] [float] NULL,
                    [condition] [varchar](50) NULL,
                    [message] [varchar](255) NULL
                )
            END
            ''')
            
            # Create table for device information
            cursor.execute('''
            IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[device_info]') AND type in (N'U'))
            BEGIN
                CREATE TABLE [dbo].[device_info] (
                    [device_id] [varchar](100) PRIMARY KEY,
                    [hostname] [varchar](100) NOT NULL,
                    [app_version] [varchar](20) NOT NULL,
                    [first_seen] [datetime2](7) NOT NULL,
                    [last_seen] [datetime2](7) NOT NULL,
                    [status] [varchar](20) NOT NULL
                )
            END
            ''')
            
            self.conn.commit()
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Failed to set up database schema: {str(e)}")
    
    def _register_device(self):
        """Register or update device information in the database"""
        if self.conn is None:
            logger.warning("Database connection not available, skipping device registration")
            return
        
        try:
            cursor = self.conn.cursor()
            now = datetime.now()
            hostname = socket.gethostname()
            
            # Check if device exists
            cursor.execute(
                "SELECT device_id FROM device_info WHERE device_id = ?", 
                (self.device_id,)
            )
            result = cursor.fetchone()
            
            if result:
                # Update existing device
                cursor.execute(
                    """UPDATE device_info 
                       SET hostname = ?, app_version = ?, last_seen = ?, status = ?
                       WHERE device_id = ?""",
                    (hostname, APP_VERSION, now, "active", self.device_id)
                )
                logger.info(f"Device {self.device_id} updated in the database")
            else:
                # Insert new device
                cursor.execute(
                    """INSERT INTO device_info 
                       (device_id, hostname, app_version, first_seen, last_seen, status)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (self.device_id, hostname, APP_VERSION, now, now, "active")
                )
                logger.info(f"Device {self.device_id} registered in the database")
            
            self.conn.commit()
        except Exception as e:
            logger.error(f"Failed to register device: {str(e)}")
    
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
    
    def handle_termination(self, signum, frame):
        """Handle graceful shutdown signal"""
        logger.info("Shutdown signal received, finishing current operation...")
        self.shutdown_requested = True
        
    def generate_data(self):
        """Generate enhanced weather data with timestamp."""
        timestamp = datetime.now()
        
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
        
        # Create complete data record with device ID
        data = {
            "device_id": self.device_id,
            "timestamp": timestamp,
            "weather": weather_data,
            "message": message,
            "version": APP_VERSION
        }
        
        return data
    
    def store_data(self, data):
        """Store data in Azure SQL Database or local fallback"""
        if self.conn is not None:
            try:
                cursor = self.conn.cursor()
                
                # Store in the weather_data table
                weather = data["weather"]
                cursor.execute(
                    """INSERT INTO weather_data 
                       (device_id, timestamp, temperature, humidity, pressure, wind_speed, 
                        wind_direction, precipitation, condition, message) 
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        data["device_id"], 
                        data["timestamp"],
                        weather["temperature"], 
                        weather["humidity"], 
                        weather["pressure"], 
                        weather["wind_speed"], 
                        weather["wind_direction"],
                        weather["precipitation"], 
                        weather["condition"], 
                        data["message"]
                    )
                )
                
                # Update last_seen in device_info
                cursor.execute(
                    "UPDATE device_info SET last_seen = ? WHERE device_id = ?",
                    (data["timestamp"], data["device_id"])
                )
                
                self.conn.commit()
                
                # Clean up old data if retention period is set
                if self.data_retention_days > 0:
                    cutoff_date = datetime.now().replace(
                        hour=0, minute=0, second=0, microsecond=0
                    )
                    
                    # Calculate cutoff date
                    import datetime as dt
                    cutoff_date = cutoff_date - dt.timedelta(days=self.data_retention_days)
                    
                    cursor.execute(
                        "DELETE FROM weather_data WHERE timestamp < ?", 
                        (cutoff_date,)
                    )
                    self.conn.commit()
                
                return True
            except Exception as e:
                logger.error(f"Error storing data in Azure SQL Database: {str(e)}")
                self._store_local_fallback(data)
                return False
        else:
            # Use local fallback if no database connection
            self._store_local_fallback(data)
            return False
    
    def _store_local_fallback(self, data):
        """Store data locally as fallback when Azure SQL is unavailable"""
        try:
            # Convert datetime to string for JSON serialization
            data["timestamp"] = data["timestamp"].isoformat()
            
            # Load existing data if file exists
            local_data = []
            if os.path.exists(self.local_data_file):
                try:
                    with open(self.local_data_file, 'r') as f:
                        local_data = json.load(f)
                except:
                    pass
            
            # Append new data
            local_data.append(data)
            
            # Limit size to prevent excessive growth
            max_local_entries = 1000
            if len(local_data) > max_local_entries:
                local_data = local_data[-max_local_entries:]
            
            # Save to file
            with open(self.local_data_file, 'w') as f:
                json.dump(local_data, f)
            
            logger.info(f"Stored data locally (entries: {len(local_data)})")
        except Exception as e:
            logger.error(f"Error storing local fallback data: {str(e)}")
    
    def run(self):
        """Modified run loop with shutdown handling"""
        logger.info(f"Enhanced Weather Application running with version {APP_VERSION}")
        
        try:
            while not self.shutdown_requested:
                data = self.generate_data()
                success = self.store_data(data)
                
                if self.enable_extended_logging:
                    logger.info(f"Weather data {'stored in database' if success else 'stored locally'}: {json.dumps(data['weather'], indent=2)}")
                else:
                    logger.info(f"Data stored: {data['message']}")
                    
                # Try to reconnect to Azure SQL if connection was lost
                if self.conn is None:
                    logger.info("Attempting to reconnect to Azure SQL Database...")
                    self.conn = self._connect_to_azure_sql()
                    if self.conn is not None:
                        self._setup_database()
                        self._register_device()
                
                time.sleep(self.interval)
        except KeyboardInterrupt:
            logger.info("Application shutdown requested")
        except Exception as e:
            logger.error(f"Error in application: {str(e)}")
        finally:
            if self.conn is not None:
                # Update device status to inactive
                try:
                    cursor = self.conn.cursor()
                    cursor.execute(
                        "UPDATE device_info SET status = ? WHERE device_id = ?",
                        ("inactive", self.device_id)
                    )
                    self.conn.commit()
                except:
                    pass
                self.conn.close()
            logger.info("Application stopped")

if __name__ == "__main__":
    app = EnhancedApplication()
    app.run()