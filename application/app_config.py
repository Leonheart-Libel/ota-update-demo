# Enhanced Application configuration
# This file is updated by the OTA service

# Data generation interval in seconds
INTERVAL = 10

# Enable extended logging (more detailed output)
ENABLE_EXTENDED_LOGGING = True

# Data retention period in days (0 = keep indefinitely)
DATA_RETENTION_DAYS = 30

# New simulation parameters
ENABLE_UV_SIMULATION = True
ENABLE_FEELS_LIKE = True
MAX_WIND_GUST = 20  # km/h

# Azure SQL Database connection parameters
SQL_SERVER = "iotcentralhub.database.windows.net"
SQL_DATABASE = "otasqldb"
SQL_USERNAME = "rozemyne"
SQL_PASSWORD = "alexandria_7"
TRUST_SERVER_CERT = "no"