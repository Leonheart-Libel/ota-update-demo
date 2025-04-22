#!/usr/bin/env python3
"""
Database Manager - Handles connection and operations for Azure SQL Database
"""
import os
import json
import logging
import pyodbc
from datetime import datetime

logger = logging.getLogger("Database-Manager")

class DatabaseManager:
    def __init__(self, config_path="config.json"):
        """Initialize the database manager."""
        logger.info("Initializing Database Manager")
        
        # Load configuration
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        
        # Azure SQL connection configuration
        self.azure_config = self.config.get("azure_sql", {})
        self.device_id = self.config.get("device_id", "unknown-device")
        
        # Validate configuration
        required_keys = ["server", "database", "username", "password", "driver"]
        for key in required_keys:
            if key not in self.azure_config:
                logger.error(f"Missing required Azure SQL configuration: {key}")
                raise ValueError(f"Missing required Azure SQL configuration: {key}")
        
        # Initialize connection
        self._initialize_database()
    
    def _get_connection_string(self):
        """Get the connection string for Azure SQL Database."""
        config = self.azure_config
        return (
            f"Driver={config['driver']};"
            f"Server={config['server']};"
            f"Database={config['database']};"
            f"Uid={config['username']};"
            f"Pwd={config['password']};"
            "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
        )
    
    def _initialize_database(self):
        """Set up database schema if tables don't exist."""
        try:
            conn = pyodbc.connect(self._get_connection_string())
            cursor = conn.cursor()
            
            # Create device table if it doesn't exist
            cursor.execute('''
            IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'devices')
            BEGIN
                CREATE TABLE devices (
                    id VARCHAR(100) PRIMARY KEY,
                    first_seen DATETIME,
                    last_seen DATETIME,
                    app_version VARCHAR(50),
                    status VARCHAR(20)
                )
            END
            ''')
            
            # Create weather_data table if it doesn't exist
            cursor.execute('''
            IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'weather_data')
            BEGIN
                CREATE TABLE weather_data (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    device_id VARCHAR(100),
                    timestamp DATETIME,
                    temperature FLOAT,
                    humidity FLOAT,
                    pressure FLOAT,
                    wind_speed FLOAT,
                    wind_direction FLOAT,
                    precipitation FLOAT,
                    condition VARCHAR(50),
                    message VARCHAR(255),
                    version VARCHAR(50),
                    FOREIGN KEY (device_id) REFERENCES devices(id)
                )
            END
            ''')
            
            conn.commit()
            logger.info("Database schema initialized")
            
            # Register or update this device
            self.register_device()
            
        except Exception as e:
            logger.error(f"Database initialization error: {str(e)}")
            raise
    
    def register_device(self, app_version="1.0.0"):
        """Register or update the device in the devices table."""
        try:
            conn = pyodbc.connect(self._get_connection_string())
            cursor = conn.cursor()
            
            # Check if device exists
            cursor.execute(
                "SELECT id FROM devices WHERE id = ?", 
                (self.device_id,)
            )
            
            now = datetime.now()
            
            if cursor.fetchone():
                # Update existing device
                cursor.execute(
                    """UPDATE devices 
                       SET last_seen = ?, app_version = ?, status = ?
                       WHERE id = ?""",
                    (now, app_version, "active", self.device_id)
                )
                logger.info(f"Updated device registration: {self.device_id}")
            else:
                # Insert new device
                cursor.execute(
                    """INSERT INTO devices 
                       (id, first_seen, last_seen, app_version, status)
                       VALUES (?, ?, ?, ?, ?)""",
                    (self.device_id, now, now, app_version, "active")
                )
                logger.info(f"Registered new device: {self.device_id}")
            
            conn.commit()
            return True
            
        except Exception as e:
            logger.error(f"Error registering device: {str(e)}")
            return False
    
    def store_weather_data(self, data):
        """Store weather data in Azure SQL Database."""
        try:
            conn = pyodbc.connect(self._get_connection_string())
            cursor = conn.cursor()
            
            # Extract weather data from the nested dictionary
            weather = data["weather"]
            
            # Log the actual SQL and parameters for debugging
            logger.info(f"Inserting weather data for device: {self.device_id}, time: {data['timestamp']}")
            logger.debug(f"SQL params: temperature={weather['temperature']}, humidity={weather['humidity']}")
            
            cursor.execute(
                """INSERT INTO weather_data 
                (device_id, timestamp, temperature, humidity, pressure, wind_speed, 
                    wind_direction, precipitation, condition, message, version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (self.device_id, datetime.fromisoformat(data["timestamp"]), 
                weather["temperature"], weather["humidity"], weather["pressure"],
                weather["wind_speed"], weather["wind_direction"], weather["precipitation"],
                weather["condition"], data["message"], data["version"])
            )
            
            conn.commit()
            logger.info("Weather data successfully inserted into database")
            return True
            
        except Exception as e:
            logger.error(f"Error storing weather data: {str(e)}")
            logger.error(f"Data that failed: {data}")
            # Log the specific SQL error for ODBC
            if hasattr(e, 'args') and len(e.args) > 0:
                logger.error(f"SQL error details: {e.args[0]}")
            return False
    
    def get_latest_data_timestamp(self):
        """Get the timestamp of the latest data record for this device."""
        try:
            conn = pyodbc.connect(self._get_connection_string())
            cursor = conn.cursor()
            
            cursor.execute(
                """SELECT TOP 1 timestamp 
                   FROM weather_data 
                   WHERE device_id = ? 
                   ORDER BY timestamp DESC""",
                (self.device_id,)
            )
            
            result = cursor.fetchone()
            if result:
                return result[0]
            return None
            
        except Exception as e:
            logger.error(f"Error getting latest data timestamp: {str(e)}")
            return None
    
    def update_device_version(self, app_version):
        """Update the device's app version in the database."""
        try:
            conn = pyodbc.connect(self._get_connection_string())
            cursor = conn.cursor()
            
            cursor.execute(
                """UPDATE devices 
                   SET app_version = ?, last_seen = ?
                   WHERE id = ?""",
                (app_version, datetime.now(), self.device_id)
            )
            
            conn.commit()
            logger.info(f"Updated device version to {app_version}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating device version: {str(e)}")
            return False