# Enhanced Application configuration
# This file is updated by the OTA service

# Data generation interval in seconds
INTERVAL = 15

# Enable extended logging (more detailed output)
ENABLE_EXTENDED_LOGGING = True

# Data retention period in days (0 = keep indefinitely)
DATA_RETENTION_DAYS = 30

# Azure SQL Database connection parameters
SQL_SERVER = "iotcentralhub.database.windows.net"
SQL_DATABASE = "otasqldb"
SQL_USERNAME = "rozemyne"
SQL_PASSWORD = "alexandria_7"
TRUST_SERVER_CERT = "no"

# Additional configuration parameters can be added here
# as the application evolves through OTA updates