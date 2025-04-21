#!/usr/bin/env python3
"""
Azure SQL Database Client - Handles connection and operations with Azure SQL Database
"""
import os
import logging
import json
from datetime import datetime
import uuid
import platform

# For Azure SQL Database connection
# Note: Using pymssql instead of pyodbc as requested
import pymssql

logger = logging.getLogger("Azure-DB-Client")

class AzureDBClient:
    def __init__(self, config_path="config/db_config.json"):
        """Initialize the Azure SQL Database client."""
        self.conn = None
        self.config = self._load_config(config_path)
        self.device_id = self._get_device_id()
        self.hostname = platform.node()
        self._connect()
        self._setup_tables()
    
    def _load_config(self, config_path):
        """Load database configuration from JSON file."""
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            logger.info("Database configuration loaded successfully")
            return config
        except Exception as e:
            logger.error(f"Error loading database configuration: {str(e)}")
            # Return minimal default config to avoid errors
            return {
                "server": "",
                "database": "",
                "username": "",
                "password": ""
            }
    
    def _get_device_id(self):
        """Get or generate a unique device ID."""
        device_id_path = "config/device_id.txt"
        
        # Create config directory if it doesn't exist
        os.makedirs(os.path.dirname(device_id_path), exist_ok=True)
        
        # Try to read existing device ID
        if os.path.exists(device_id_path):
            try:
                with open(device_id_path, 'r') as f:
                    device_id = f.read().strip()
                    if device_id:
                        return device_id
            except Exception as e:
                logger.warning(f"Error reading device ID: {str(e)}")
        
        # Generate new device ID if none exists
        device_id = str(uuid.uuid4())
        try:
            with open(device_id_path, 'w') as f:
                f.write(device_id)
            logger.info(f"Generated new device ID: {device_id}")
            return device_id
        except Exception as e:
            logger.error(f"Error saving device ID: {str(e)}")
            return device_id
    
    def _connect(self):
        """Connect to Azure SQL Database."""
        try:
            self.conn = pymssql.connect(
                server=self.config["server"],
                database=self.config["database"],
                user=self.config["username"],
                password=self.config["password"]
            )
            logger.info("Connected to Azure SQL Database")
        except Exception as e:
            logger.error(f"Error connecting to Azure SQL Database: {str(e)}")
            self.conn = None
    
    def _setup_tables(self):
        """Set up database tables if they don't exist."""
        if not self.conn:
            logger.error("Cannot set up tables: No database connection")
            return False
        
        try:
            cursor = self.conn.cursor()
            
            # Create device table
            cursor.execute('''
            IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'devices')
            BEGIN
                CREATE TABLE devices (
                    id VARCHAR(36) PRIMARY KEY,
                    hostname VARCHAR(255) NOT NULL,
                    first_seen DATETIME NOT NULL,
                    last_seen DATETIME NOT NULL,
                    current_version VARCHAR(50) NOT NULL,
                    ip_address VARCHAR(50),
                    status VARCHAR(20) DEFAULT 'active'
                )
            END
            ''')
            
            # Create weather data table
            cursor.execute('''
            IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'weather_data')
            BEGIN
                CREATE TABLE weather_data (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    device_id VARCHAR(36) NOT NULL,
                    timestamp DATETIME NOT NULL,
                    temperature FLOAT,
                    humidity FLOAT,
                    pressure FLOAT,
                    wind_speed FLOAT,
                    wind_direction FLOAT,
                    precipitation FLOAT,
                    condition VARCHAR(50),
                    message VARCHAR(255),
                    app_version VARCHAR(50),
                    FOREIGN KEY (device_id) REFERENCES devices(id)
                )
            END
            ''')
            
            self.conn.commit()
            logger.info("Database tables setup complete")
            return True
        except Exception as e:
            logger.error(f"Error setting up database tables: {str(e)}")
            return False
    
    def register_device(self, version):
        """Register or update device information."""
        if not self.conn:
            logger.error("Cannot register device: No database connection")
            return False
        
        try:
            cursor = self.conn.cursor()
            
            # Check if device exists
            cursor.execute("SELECT id FROM devices WHERE id = %s", (self.device_id,))
            exists = cursor.fetchone()
            
            now = datetime.now()
            
            if exists:
                # Update existing device
                cursor.execute('''
                UPDATE devices 
                SET hostname = %s, last_seen = %s, current_version = %s
                WHERE id = %s
                ''', (self.hostname, now, version, self.device_id))
            else:
                # Insert new device
                cursor.execute('''
                INSERT INTO devices (id, hostname, first_seen, last_seen, current_version)
                VALUES (%s, %s, %s, %s, %s)
                ''', (self.device_id, self.hostname, now, now, version))
            
            self.conn.commit()
            logger.info(f"Device {self.device_id} registered with version {version}")
            return True
        except Exception as e:
            logger.error(f"Error registering device: {str(e)}")
            return False
    
    def store_weather_data(self, data):
        """Store weather data in Azure SQL Database."""
        if not self.conn:
            logger.error("Cannot store data: No database connection")
            return False
        
        try:
            cursor = self.conn.cursor()
            
            # Parse the timestamp
            timestamp = datetime.fromisoformat(data["timestamp"])
            weather = data["weather"]
            
            # Insert weather data
            cursor.execute('''
            INSERT INTO weather_data 
            (device_id, timestamp, temperature, humidity, pressure, wind_speed, 
             wind_direction, precipitation, condition, message, app_version)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (
                self.device_id,
                timestamp,
                weather["temperature"],
                weather["humidity"],
                weather["pressure"],
                weather["wind_speed"],
                weather["wind_direction"],
                weather["precipitation"],
                weather["condition"],
                data["message"],
                data["version"]
            ))
            
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error storing weather data: {str(e)}")
            self.reconnect()
            return False
    
    def reconnect(self):
        """Attempt to reconnect to the database."""
        logger.info("Attempting to reconnect to database...")
        try:
            if self.conn:
                try:
                    self.conn.close()
                except:
                    pass
            
            self._connect()
            return self.conn is not None
        except Exception as e:
            logger.error(f"Error reconnecting to database: {str(e)}")
            return False
    
    def close(self):
        """Close the database connection."""
        if self.conn:
            try:
                self.conn.close()
                logger.info("Database connection closed")
            except Exception as e:
                logger.error(f"Error closing database connection: {str(e)}")