#!/usr/bin/env python3
"""
Database Manager - Handles connections and operations with Azure SQL Database
"""
import os
import pyodbc
import logging
import socket
import uuid
import json

logger = logging.getLogger("DB-Manager")

class DBManager:
    def __init__(self, config_path="db_config.json"):
        """Initialize the database manager with Azure SQL connection details."""
        logger.info("Initializing Database Manager")
        
        # Load configuration
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        
        # Get device ID or generate one if it doesn't exist
        self.device_id = self._get_device_id()
        logger.info(f"Device ID: {self.device_id}")
        
        # Initialize connection
        self.conn = None
        self._init_database()
    
    def _get_device_id(self):
        """Get the device ID or generate a new one if not found."""
        id_file = "device_id.txt"
        
        if os.path.exists(id_file):
            with open(id_file, 'r') as f:
                device_id = f.read().strip()
                if device_id:
                    return device_id
        
        # Generate a new device ID based on hostname and MAC address
        hostname = socket.gethostname()
        device_id = f"{hostname}-{str(uuid.uuid4())[:8]}"
        
        # Save the device ID for future use
        with open(id_file, 'w') as f:
            f.write(device_id)
        
        return device_id
    
    def _init_database(self):
        """Initialize database connection and create tables if they don't exist."""
        try:
            # Build connection string from config
            conn_str = (
                f"DRIVER={{ODBC Driver 18 for SQL Server}};"
                f"SERVER={self.config['server']};"
                f"DATABASE={self.config['database']};"
                f"UID={self.config['username']};"
                f"PWD={self.config['password']};"
                f"Encrypt=yes;TrustServerCertificate=no;"
            )
            
            logger.info("Connecting to Azure SQL Database...")
            self.conn = pyodbc.connect(conn_str)
            
            # Create tables if they don't exist
            self._create_tables()
            
            # Register the device if not already registered
            self._register_device()
            
            logger.info("Database connection established")
        except Exception as e:
            logger.error(f"Error connecting to database: {str(e)}")
            raise
    
    def _create_tables(self):
        """Create required tables if they don't exist."""
        cursor = self.conn.cursor()
        
        # Create devices table
        cursor.execute('''
        IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'devices')
        CREATE TABLE devices (
            device_id VARCHAR(50) PRIMARY KEY,
            hostname VARCHAR(100),
            ip_address VARCHAR(50),
            last_seen DATETIME,
            current_version VARCHAR(20),
            first_registered DATETIME
        )
        ''')
        
        # Create weather_data table
        cursor.execute('''
        IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'weather_data')
        CREATE TABLE weather_data (
            id INT IDENTITY(1,1) PRIMARY KEY,
            device_id VARCHAR(50),
            timestamp DATETIME,
            temperature FLOAT,
            humidity FLOAT,
            pressure FLOAT,
            wind_speed FLOAT,
            wind_direction FLOAT,
            precipitation FLOAT,
            condition VARCHAR(50),
            message VARCHAR(255),
            version VARCHAR(20),
            FOREIGN KEY (device_id) REFERENCES devices(device_id)
        )
        ''')
        
        self.conn.commit()
        logger.info("Database tables created or verified")
    
    def _register_device(self, version="1.0.0"):
        """Register this device in the database or update if already exists."""
        try:
            cursor = self.conn.cursor()
            
            # Get hostname and IP address
            hostname = socket.gethostname()
            ip_address = socket.gethostbyname(hostname)
            
            # Check if device already exists
            cursor.execute(
                "SELECT device_id FROM devices WHERE device_id = ?", 
                (self.device_id,)
            )
            device_exists = cursor.fetchone() is not None
            
            if device_exists:
                # Update existing device
                cursor.execute('''
                UPDATE devices 
                SET hostname = ?, ip_address = ?, last_seen = GETDATE(), current_version = ? 
                WHERE device_id = ?
                ''', (hostname, ip_address, version, self.device_id))
            else:
                # Insert new device
                cursor.execute('''
                INSERT INTO devices 
                (device_id, hostname, ip_address, last_seen, current_version, first_registered) 
                VALUES (?, ?, ?, GETDATE(), ?, GETDATE())
                ''', (self.device_id, hostname, ip_address, version))
            
            self.conn.commit()
            logger.info(f"Device registered/updated with ID: {self.device_id}")
        except Exception as e:
            logger.error(f"Error registering device: {str(e)}")
            self.conn.rollback()
    
    def update_device_version(self, version):
        """Update the device version in the database."""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
            UPDATE devices 
            SET current_version = ?, last_seen = GETDATE() 
            WHERE device_id = ?
            ''', (version, self.device_id))
            self.conn.commit()
            logger.info(f"Device version updated to {version}")
            return True
        except Exception as e:
            logger.error(f"Error updating device version: {str(e)}")
            self.conn.rollback()
            return False
    
    def store_weather_data(self, data):
        """Store weather data in the database."""
        try:
            cursor = self.conn.cursor()
            
            # Parse timestamp
            timestamp = data["timestamp"]
            weather = data["weather"]
            version = data["version"]
            message = data["message"]
            
            # Insert weather data
            cursor.execute('''
            INSERT INTO weather_data
            (device_id, timestamp, temperature, humidity, pressure, wind_speed, 
             wind_direction, precipitation, condition, message, version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                self.device_id, timestamp, weather["temperature"], weather["humidity"],
                weather["pressure"], weather["wind_speed"], weather["wind_direction"],
                weather["precipitation"], weather["condition"], message, version
            ))
            
            # Update device last seen
            cursor.execute('''
            UPDATE devices SET last_seen = GETDATE() WHERE device_id = ?
            ''', (self.device_id,))
            
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error storing weather data: {str(e)}")
            self.conn.rollback()
            return False
    
    def get_last_data_timestamp(self):
        """Get the timestamp of the last data entry for this device."""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
            SELECT TOP 1 timestamp FROM weather_data 
            WHERE device_id = ? 
            ORDER BY timestamp DESC
            ''', (self.device_id,))
            
            result = cursor.fetchone()
            return result[0] if result else None
        except Exception as e:
            logger.error(f"Error getting last data timestamp: {str(e)}")
            return None
    
    def clean_old_data(self, days):
        """Clean up old data beyond the retention period."""
        if days <= 0:
            return  # No cleanup if retention is set to keep indefinitely
        
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
            DELETE FROM weather_data 
            WHERE timestamp < DATEADD(day, ?, GETDATE())
            ''', (-days,))
            
            self.conn.commit()
            logger.info(f"Cleaned up weather data older than {days} days")
        except Exception as e:
            logger.error(f"Error cleaning old data: {str(e)}")
            self.conn.rollback()
    
    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")