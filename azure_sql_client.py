# azure_sql_client.py
import pyodbc
import logging
import os
import socket
import uuid

logger = logging.getLogger("Azure-SQL-Client")

class AzureSQLClient:
    def __init__(self, connection_string=None):
        """Initialize Azure SQL Database connection."""
        self.connection_string = connection_string or os.getenv("AZURE_SQL_CONNECTION_STRING")
        if not self.connection_string:
            raise ValueError("Azure SQL connection string not provided")
        
        # Generate a unique device ID if not already set
        self.device_id = os.getenv("DEVICE_ID") or self._generate_device_id()
        self.hostname = socket.gethostname()
        self.ip_address = socket.gethostbyname(self.hostname)
        
        # Store device ID for future use
        if not os.getenv("DEVICE_ID"):
            os.environ["DEVICE_ID"] = self.device_id
            
        logger.info(f"Device ID: {self.device_id}, Hostname: {self.hostname}")
    
    def _generate_device_id(self):
        """Generate a unique device ID that persists across reboots."""
        device_id_file = "data/device_id.txt"
        os.makedirs(os.path.dirname(device_id_file), exist_ok=True)
        
        if os.path.exists(device_id_file):
            with open(device_id_file, "r") as f:
                device_id = f.read().strip()
                if device_id:
                    return device_id
        
        # Generate new ID if not found
        device_id = str(uuid.uuid4())
        with open(device_id_file, "w") as f:
            f.write(device_id)
        
        return device_id
    
    def connect(self):
        """Connect to Azure SQL Database."""
        try:
            conn = pyodbc.connect(self.connection_string)
            return conn
        except Exception as e:
            logger.error(f"Error connecting to Azure SQL: {str(e)}")
            raise
    
    def setup_database(self):
        """Set up database schema for weather data and device information."""
        try:
            conn = self.connect()
            cursor = conn.cursor()
            
            # Create weather_data table
            cursor.execute('''
            IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'weather_data')
            BEGIN
                CREATE TABLE weather_data (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    device_id NVARCHAR(50),
                    timestamp DATETIMEOFFSET,
                    temperature FLOAT,
                    humidity FLOAT,
                    pressure FLOAT,
                    wind_speed FLOAT,
                    wind_direction FLOAT,
                    precipitation FLOAT,
                    condition NVARCHAR(50),
                    message NVARCHAR(MAX)
                )
            END
            ''')
            
            # Create device_info table
            cursor.execute('''
            IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'device_info')
            BEGIN
                CREATE TABLE device_info (
                    id INT IDENTITY(1,1) PRIMARY KEY,
                    device_id NVARCHAR(50),
                    hostname NVARCHAR(100),
                    ip_address NVARCHAR(50),
                    app_version NVARCHAR(20),
                    last_updated DATETIMEOFFSET,
                    status NVARCHAR(20)
                )
            END
            ''')
            
            conn.commit()
            logger.info("Database schema setup complete")
            return True
        
        except Exception as e:
            logger.error(f"Error setting up database schema: {str(e)}")
            return False
        finally:
            if 'conn' in locals():
                conn.close()
    
    def update_device_info(self, app_version, status="Running"):
        """Update or insert device information in database."""
        try:
            conn = self.connect()
            cursor = conn.cursor()
            
            # Check if device exists
            cursor.execute(
                "SELECT COUNT(*) FROM device_info WHERE device_id = ?", 
                (self.device_id,)
            )
            exists = cursor.fetchone()[0] > 0
            
            if exists:
                # Update existing record
                cursor.execute('''
                UPDATE device_info 
                SET hostname = ?, ip_address = ?, app_version = ?, 
                    last_updated = GETUTCDATE(), status = ?
                WHERE device_id = ?
                ''', (self.hostname, self.ip_address, app_version, status, self.device_id))
            else:
                # Insert new record
                cursor.execute('''
                INSERT INTO device_info 
                    (device_id, hostname, ip_address, app_version, last_updated, status)
                VALUES (?, ?, ?, ?, GETUTCDATE(), ?)
                ''', (self.device_id, self.hostname, self.ip_address, app_version, status))
            
            conn.commit()
            logger.info(f"Device info updated: {self.device_id}, Version: {app_version}, Status: {status}")
            return True
        
        except Exception as e:
            logger.error(f"Error updating device info: {str(e)}")
            return False
        finally:
            if 'conn' in locals():
                conn.close()