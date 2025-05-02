#!/usr/bin/env python3
import os
import time
import random
import logging
import json
import socket
import uuid
import pyodbc
import math
import signal
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("application/app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("EnhancedWeatherApp")

version_files = [
    "application/version.txt",  
    "version.txt",             
    "../application/version.txt"  
]

APP_VERSION = "2.0.0" 
for version_file in version_files:
    try:
        if os.path.exists(version_file):
            with open(version_file, "r") as f:
                version = f.read().strip()
                if version:
                    APP_VERSION = version
                    logger.info(f"Loaded version {APP_VERSION} from {version_file}")
                    break
    except Exception as e:
        logger.warning(f"Error reading version file {version_file}: {str(e)}")

logger.info(f"Current working directory: {os.getcwd()}")
logger.info(f"Using application version: {APP_VERSION}")

def ensure_single_instance():
    """Ensure only one instance of the application is running."""
    lock_file = "/tmp/weather_app.lock"
    
    try:
        # Try to create a lock file
        with open(lock_file, 'x') as f:
            f.write(str(os.getpid()))
        
        # Register cleanup on exit
        import atexit
        atexit.register(lambda: os.remove(lock_file) if os.path.exists(lock_file) else None)
        return True
    except FileExistsError:
        # Lock file exists, check if process is still running
        try:
            with open(lock_file, 'r') as f:
                pid = int(f.read().strip())
            
            # Check if process still exists
            os.kill(pid, 0)  # This will raise an exception if process doesn't exist
            logger.warning(f"Another instance is already running with PID {pid}")
            return False
        except (ProcessLookupError, ValueError):
            # Process doesn't exist, we can take over
            os.remove(lock_file)
            return ensure_single_instance()
        except PermissionError:
            logger.error("Cannot check existing process, insufficient permissions")
            return False

class WeatherSimulator:
    
    def __init__(self):
        self.base_temperature = random.uniform(15.0, 25.0) 
        self.base_humidity = random.uniform(40.0, 70.0)   
        self.base_pressure = random.uniform(1000.0, 1020.0)
        self.base_wind_speed = random.uniform(5.0, 15.0)   
        self.base_wind_direction = random.uniform(0, 360) 
        self.base_precipitation = random.uniform(0, 5.0)   
        
        self.base_air_quality = random.uniform(30.0, 70.0)
        
        self.time_counter = 0
        
        self.weather_conditions = [
            "Clear", "Partly Cloudy", "Cloudy", "Overcast", 
            "Light Rain", "Moderate Rain", "Heavy Rain",
            "Light Snow", "Moderate Snow", "Heavy Snow",
            "Foggy", "Windy"
        ]
        self.current_condition = random.choice(self.weather_conditions)
        self.condition_duration = random.randint(5, 20) 
        self.condition_counter = 0
        
        self.air_quality_categories = [
            "Good", "Moderate", "Unhealthy for Sensitive Groups", 
            "Unhealthy", "Very Unhealthy", "Hazardous"
        ]
    
    def get_air_quality_category(self, aqi):
        if aqi <= 50:
            return self.air_quality_categories[0]
        elif aqi <= 100:
            return self.air_quality_categories[1]
        elif aqi <= 150:
            return self.air_quality_categories[2]
        elif aqi <= 200:
            return self.air_quality_categories[3]
        elif aqi <= 300:
            return self.air_quality_categories[4]
        else:
            return self.air_quality_categories[5]
    
    def update(self):
        self.time_counter += 1
        self.condition_counter += 1
        
        if self.condition_counter >= self.condition_duration:
            self.condition_counter = 0
            self.condition_duration = random.randint(5, 20)
            
            current_index = self.weather_conditions.index(self.current_condition)
            possible_indices = [
                max(0, current_index - 1),
                current_index,
                min(len(self.weather_conditions) - 1, current_index + 1)
            ]
            self.current_condition = self.weather_conditions[random.choice(possible_indices)]
        
        temp_variation = math.sin(self.time_counter / 10) * 3 + random.uniform(-1, 1)
        humidity_variation = math.sin(self.time_counter / 12) * 5 + random.uniform(-2, 2)
        pressure_variation = math.sin(self.time_counter / 15) * 2 + random.uniform(-0.5, 0.5)
        wind_speed_variation = math.sin(self.time_counter / 8) * 2 + random.uniform(-1, 1)
        wind_dir_variation = random.uniform(-10, 10)
        precip_variation = 0
        
        air_quality_variation = math.sin(self.time_counter / 20) * 10 + random.uniform(-5, 5)
        
        if "Rain" in self.current_condition or "Snow" in self.current_condition:
            intensity = 1
            if "Light" in self.current_condition:
                intensity = 0.5
            elif "Heavy" in self.current_condition:
                intensity = 2
            
            precip_variation = random.uniform(0, 2) * intensity
            
            air_quality_variation -= intensity * 3
        
        if "Foggy" in self.current_condition:
            air_quality_variation += random.uniform(5, 15)
        
        tempature = self.base_temperature + temp_variation
        huidity = min(100, max(0, self.base_humidity + humidity_variation))
        presure = self.base_pressure + pressure_variation
        wind_eed = max(0, self.base_wind_speed + wind_speed_variation)
        wind_direction = (self.base_wind_direction + wind_dir_variation) % 360
        precipitation = max(0, self.base_precipitation + precip_variation)
        
        air_quality = max(0, min(300, self.base_air_quality + air_quality_variation))
        air_quality_category = self.get_air_quality_category(air_quality)
        
        return {
            "temperature": round(temperature, 1),
            "humidity": round(humidity, 1),
            "pressure": round(pressure, 1),
            "wind_speed": round(wind_speed, 1),
            "wind_direction": round(wind_direction, 1),
            "precipitation": round(precipitation, 2),
            "condition": self.current_condition,
            "air_quality": round(air_quality, 1),  # NEW
            "air_quality_category": air_quality_category  # NEW
        }


class EnhancedApplication:
    def __init__(self):
        """Initialize the enhanced application with Azure SQL connection."""
        logger.info(f"Starting Enhanced Weather Application v{APP_VERSION}")
        
        self.load_config()
        
        self.initialize_device_id()
        
        self.conn = self.create_db_connection()
        
        self._ensure_tables_exist()
        
        self.register_device()
        
        self.weather_simulator = WeatherSimulator()

        self.shutdown_requested = False
        signal.signal(signal.SIGTERM, self.handle_termination)
        signal.signal(signal.SIGINT, self.handle_termination)
    
    def handle_termination(self, signum, frame):
        logger.info(f"Shutdown signal {signum} received, finishing current operation...")
        self.shutdown_requested = True
    
    def initialize_device_id(self):
        device_id_file = "data/device_id.txt"
        os.makedirs(os.path.dirname(device_id_file), exist_ok=True)
        
        if os.path.exists(device_id_file):
            try:
                with open(device_id_file, "r") as f:
                    self.device_id = f.read().strip()
                    logger.info(f"Loaded existing device ID: {self.device_id}")
            except Exception as e:
                logger.error(f"Error reading device ID: {str(e)}")
                self.device_id = self.generate_device_id()
        else:
            self.device_id = self.generate_device_id()
            try:
                with open(device_id_file, "w") as f:
                    f.write(self.device_id)
                logger.info(f"Generated and saved new device ID: {self.device_id}")
            except Exception as e:
                logger.error(f"Error saving device ID: {str(e)}")
    
    def generate_device_id(self):
        hostname = socket.gethostname()
        unique_id = str(uuid.uuid4())[:8]
        device_id = f"{hostname}-{unique_id}"
        return device_id
    
    def create_db_connection(self):
        try:
            conn_string = (
                f"DRIVER={{FreeTDS}};"
                f"SERVER={self.sql_server};"
                f"DATABASE={self.sql_database};"
                f"UID={self.sql_username};"
                f"PWD={self.sql_password};"
                f"TDS_Version=8.0;"
                f"Port=1433;"
            )
            
            conn = pyodbc.connect(conn_string)
            logger.info("Successfully connected to Azure SQL Database")
            return conn
        except Exception as e:
            logger.error(f"Error connecting to database: {str(e)}")
            raise
    
    def _ensure_tables_exist(self):
        try:
            cursor = self.conn.cursor()
            
            cursor.execute("""
                IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'device_info')
                CREATE TABLE device_info (
                    device_id VARCHAR(50) PRIMARY KEY,
                    hostname VARCHAR(100),
                    ip_address VARCHAR(50),
                    first_seen DATETIME2 NOT NULL,
                    last_seen DATETIME2 NOT NULL,
                    current_version VARCHAR(20),
                    os_info VARCHAR(255),
                    status VARCHAR(20) DEFAULT 'active'
                )
            """)
            
            cursor.execute("""
                IF EXISTS (SELECT * FROM sys.tables WHERE name = 'weather_data')
                AND NOT EXISTS (SELECT * FROM sys.columns WHERE name = 'air_quality' AND object_id = OBJECT_ID('weather_data'))
                ALTER TABLE weather_data ADD air_quality FLOAT, air_quality_category VARCHAR(50)
            """)
            
            cursor.execute("""
                IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'weather_data')
                CREATE TABLE weather_data (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    device_id VARCHAR(50) NOT NULL,
                    timestamp DATETIME2 NOT NULL,
                    temperature FLOAT,
                    humidity FLOAT,
                    pressure FLOAT,
                    wind_speed FLOAT,
                    wind_direction FLOAT,
                    precipitation FLOAT,
                    condition VARCHAR(50),
                    air_quality FLOAT,
                    air_quality_category VARCHAR(50),
                    message NVARCHAR(500),
                    version VARCHAR(20)
                )
            """)
            
            cursor.execute("""
                IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_weather_data_timestamp')
                CREATE INDEX IX_weather_data_timestamp ON weather_data (timestamp)
            """)
            
            cursor.execute("""
                IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_weather_data_device_id')
                CREATE INDEX IX_weather_data_device_id ON weather_data (device_id)
            """)
            
            cursor.execute("""
                IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'IX_device_info_last_seen')
                CREATE INDEX IX_device_info_last_seen ON device_info (last_seen)
            """)
            
            self.conn.commit()
            logger.info("Database schema verified/created successfully")
        except Exception as e:
            logger.error(f"Error ensuring tables exist: {str(e)}")
            raise
    
    def register_device(self):
        try:
            cursor = self.conn.cursor()
            
            hostname = socket.gethostname()
            try:
                ip_address = socket.gethostbyname(hostname)
            except:
                ip_address = "unknown"
                
            import platform
            os_info = f"{platform.system()} {platform.release()}"
            current_time = datetime.now()
            
            cursor.execute("SELECT device_id FROM device_info WHERE device_id = ?", (self.device_id,))
            row = cursor.fetchone()
            
            if row:
                cursor.execute("""
                    UPDATE device_info 
                    SET hostname = ?, ip_address = ?, last_seen = ?, 
                        current_version = ?, os_info = ?, status = 'active'
                    WHERE device_id = ?
                """, (hostname, ip_address, current_time, APP_VERSION, os_info, self.device_id))
                logger.info(f"Updated device info for {self.device_id}")
            else:
                cursor.execute("""
                    INSERT INTO device_info 
                    (device_id, hostname, ip_address, first_seen, last_seen, current_version, os_info, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'active')
                """, (self.device_id, hostname, ip_address, current_time, current_time, APP_VERSION, os_info))
                logger.info(f"Registered new device with ID: {self.device_id}")
            
            self.conn.commit()
        except Exception as e:
            logger.error(f"Error registering device: {str(e)}")
    
    def load_config(self):
        self.interval = 5  # Default interval
        self.enable_extended_logging = True  # Default extended logging
        self.data_retention_days = 30  # Default data retention
        
        self.sql_server = "your-server.database.windows.net"
        self.sql_database = "IotWeatherData"
        self.sql_username = "your_username"
        self.sql_password = "your_password"
        self.trust_server_cert = "no"
        
        config_paths = [
            "config.json",           
            "../config.json",         
            "../../config.json"        
        ]
        
        config_loaded = False
        for config_path in config_paths:
            if os.path.exists(config_path):
                try:
                    with open(config_path, 'r') as f:
                        config = json.load(f)
                        
                        if "azure_sql" in config:
                            sql_config = config["azure_sql"]
                            self.sql_server = sql_config.get("server", self.sql_server)
                            self.sql_database = sql_config.get("database", self.sql_database)
                            self.sql_username = sql_config.get("username", self.sql_username)
                            self.sql_password = sql_config.get("password", self.sql_password)
                            self.trust_server_cert = sql_config.get("trust_server_cert", self.trust_server_cert)
                            config_loaded = True
                            logger.info(f"Loaded SQL configuration from {config_path}")
                    
                    if config_loaded:
                        break
                        
                except Exception as e:
                    logger.warning(f"Error loading config.json: {str(e)}")
        
        app_config_path = "application/app_config.py"
        
        if os.path.exists(app_config_path):
            try:
                with open(app_config_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                            
                        if "=" not in line:
                            continue
                            
                        key, value = line.split("=", 1)
                        key = key.strip()
                        value = value.strip().strip('"\'')
                        
                        if key == "INTERVAL":
                            self.interval = int(value)
                        elif key == "ENABLE_EXTENDED_LOGGING":
                            self.enable_extended_logging = value.lower() == "true"
                        elif key == "DATA_RETENTION_DAYS":
                            self.data_retention_days = int(value)
                        
                        if not config_loaded:
                            if key == "SQL_SERVER":
                                self.sql_server = value
                            elif key == "SQL_DATABASE":
                                self.sql_database = value
                            elif key == "SQL_USERNAME":
                                self.sql_username = value
                            elif key == "SQL_PASSWORD":
                                self.sql_password = value
                            elif key == "TRUST_SERVER_CERT":
                                self.trust_server_cert = value
                            
                logger.info(f"Loaded application configuration: interval={self.interval}s, extended_logging={self.enable_extended_logging}")
            except Exception as e:
                logger.warning(f"Error loading app_config.py: {str(e)}")
        
    def generate_data(self):
        timestamp = datetime.now()
        
        weather_data = self.weather_simulator.update()
        
        condition = weather_data["condition"]
        temp = weather_data["temperature"]
        air_quality = weather_data["air_quality"]
        air_quality_category = weather_data["air_quality_category"]
        
        message = f"Current weather: {condition} at {temp}°C, Air Quality: {air_quality_category} ({air_quality})"
        if "Rain" in condition:
            message += f", precipitation: {weather_data['precipitation']}mm"
        if weather_data["wind_speed"] > 20:
            message += f", strong winds: {weather_data['wind_speed']}km/h"
        
        data = {
            "timestamp": timestamp,
            "weather": weather_data,
            "message": message,
            "version": APP_VERSION,
            "device_id": self.device_id
        }
        
        return data
    
    def store_data(self, data):
        try:
            cursor = self.conn.cursor()
            
            weather = data["weather"]
            cursor.execute("""
                INSERT INTO weather_data 
                (device_id, timestamp, temperature, humidity, pressure, wind_speed, 
                wind_direction, precipitation, condition, air_quality, air_quality_category, message, version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data["device_id"],
                data["timestamp"],
                weather["temperature"],
                weather["humidity"],
                weather["pressure"],
                weather["wind_speed"],
                weather["wind_direction"],
                weather["precipitation"],
                weather["condition"],
                weather.get("air_quality", 0), 
                weather.get("air_quality_category", "Unknown"), 
                data["message"],
                data["version"]
            ))
            
            cursor.execute("""
                UPDATE device_info 
                SET last_seen = ?, current_version = ?
                WHERE device_id = ?
            """, (data["timestamp"], data["version"], data["device_id"]))
            
            self.conn.commit()
            
            if self.data_retention_days > 0:
                try:
                    cutoff_date = datetime.now().replace(
                        hour=0, minute=0, second=0, microsecond=0
                    )
                    
                    import datetime as dt
                    cutoff_date = cutoff_date - dt.timedelta(days=self.data_retention_days)
                    
                    cursor.execute(
                        "DELETE FROM weather_data WHERE timestamp < ?", 
                        (cutoff_date,)
                    )
                    self.conn.commit()
                except Exception as e:
                    logger.error(f"Error cleaning up old data: {str(e)}")
            
        except Exception as e:
            logger.error(f"Error storing data: {str(e)}")
            try:
                self.conn = self.create_db_connection()
                cursor = self.conn.cursor()
                weather = data["weather"]
                cursor.execute("""
                    INSERT INTO weather_data 
                    (device_id, timestamp, temperature, humidity, pressure, wind_speed, 
                    wind_direction, precipitation, condition, air_quality, air_quality_category, message, version)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    data["device_id"],
                    data["timestamp"],
                    weather["temperature"],
                    weather["humidity"],
                    weather["pressure"],
                    weather["wind_speed"],
                    weather["wind_direction"],
                    weather["precipitation"],
                    weather["condition"],
                    weather.get("air_quality", 0),
                    weather.get("air_quality_category", "Unknown"),
                    data["message"],
                    data["version"]
                ))
                self.conn.commit()
                logger.info("Successfully reconnected and stored data")
            except Exception as retry_error:
                logger.error(f"Failed to store data after reconnection attempt: {str(retry_error)}")
        
    def run(self):
        logger.info(f"Enhanced Weather Application running with version {APP_VERSION}")
        
        try:
            while not self.shutdown_requested:  
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
            if hasattr(self, 'conn') and self.conn:
                self.conn.close()
            logger.info("Application stopped")

if __name__ == "__main__":
    if ensure_single_instance():
        app = EnhancedApplication()
        app.run()
    else:
        logger.info("Exiting: Another instance is already running")