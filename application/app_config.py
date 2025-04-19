# Enhanced Application configuration
# This file is updated by the OTA service

# Data generation interval in seconds
INTERVAL = 10

# Enable extended logging (more detailed output)
ENABLE_EXTENDED_LOGGING = True

# Data retention period in days (0 = keep indefinitely)
DATA_RETENTION_DAYS = 30

# Additional configuration parameters can be added here
# as the application evolves through OTA updates

# Add Azure SQL configuration
AZURE_SQL_SERVER = "your-azure-sql-server.database.windows.net"
AZURE_SQL_DB = "your-database-name"
AZURE_SQL_USER = "admin@your-azure-sql-server"
AZURE_SQL_PASSWORD = "your-password"