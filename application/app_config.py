# Enhanced Application configuration
# This file is updated by the OTA service

# Data generation interval in seconds
INTERVAL = 10

# Enable extended logging (more detailed output)
ENABLE_EXTENDED_LOGGING = True

# Data retention period in days (0 = keep indefinitely)
DATA_RETENTION_DAYS = 30

# Azure SQL Database connection parameters
SQL_SERVER = "your-server.database.windows.net"
SQL_DATABASE = "IotWeatherData"
SQL_USERNAME = "your_username"
SQL_PASSWORD = "your_password"
TRUST_SERVER_CERT = "no"

# Additional configuration parameters can be added here
# as the application evolves through OTA updates