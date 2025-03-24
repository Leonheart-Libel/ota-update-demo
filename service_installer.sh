#!/bin/bash

# OTA Update Service Installer Script
# This script installs the OTA updater as a systemd service
# Run as sudo: sudo ./service_installer.sh

# Check if running as root
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root: sudo $0"
  exit 1
fi

# Configuration
SERVICE_NAME="ota-updater"
USER_NAME=$(logname)
INSTALL_DIR="/home/$USER_NAME/ota-service"
CONFIG_FILE="$INSTALL_DIR/ota_config.json"
SERVICE_FILE="/etc/systemd/system/$SERVICE_NAME.service"

# Create installation directory
mkdir -p "$INSTALL_DIR"
echo "Created installation directory: $INSTALL_DIR"

# Copy OTA service files
cp -r ota_service "$INSTALL_DIR/"
cp ota_config.json "$INSTALL_DIR/"
echo "Copied OTA service files to $INSTALL_DIR"

# Set permissions
chown -R "$USER_NAME:$USER_NAME" "$INSTALL_DIR"
chmod -R 755 "$INSTALL_DIR"

# Create application directories if they don't exist
APP_INSTALL_DIR=$(grep -o '"install_dir"[^,}]*' "$CONFIG_FILE" | cut -d '"' -f 4)
APP_VERSIONS_DIR=$(grep -o '"versions_dir"[^,}]*' "$CONFIG_FILE" | cut -d '"' -f 4)

mkdir -p "$APP_INSTALL_DIR"
mkdir -p "$APP_VERSIONS_DIR"
chown -R "$USER_NAME:$USER_NAME" "$APP_INSTALL_DIR" "$APP_VERSIONS_DIR"
echo "Created application directories"

# Install required Python packages
echo "Installing required Python packages..."
sudo -u "$USER_NAME" pip3 install requests pyodbc

# Create systemd service file
cat > "$SERVICE_FILE" << EOL
[Unit]
Description=OTA Update Service
After=network.target

[Service]
Type=simple
User=$USER_NAME
WorkingDirectory=$INSTALL_DIR
ExecStart=/usr/bin/python3 $INSTALL_DIR/ota_service/ota_updater.py $INSTALL_DIR/ota_config.json
Restart=always
RestartSec=10
StandardOutput=syslog
StandardError=syslog
SyslogIdentifier=$SERVICE_NAME

[Install]
WantedBy=multi-user.target
EOL

echo "Created systemd service file: $SERVICE_FILE"

# Reload systemd, enable and start the service
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl start "$SERVICE_NAME"

echo "OTA Update Service installed and started"
echo "Check status with: systemctl status $SERVICE_NAME"