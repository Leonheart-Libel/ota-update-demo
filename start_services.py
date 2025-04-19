#!/usr/bin/env python3
"""
Script to start both the application and OTA service.
"""
import os
import sys
import time
import subprocess
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("service.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("Service-Manager")

# Add this at the top of start_services.py
def check_dependencies():
    """Verify critical dependencies are installed"""
    try:
        import pymssql
        import requests
    except ImportError:
        print("ERROR: Missing dependencies. Run 'python3 setup.py' first!")
        exit(1)

# Add this at the start of start_services()
def start_services():
    """Start services with dependency checks"""
    check_dependencies()  # <-- New check
    logger.info("Starting services with auto-configuration...")
    
    # Create all required directories
    required_dirs = [
        "application", "ota_service", "data", "versions",
        "application/data", "ota_service/logs"
    ]
    
    for directory in required_dirs:
        os.makedirs(directory, exist_ok=True)
        logger.debug(f"Created directory: {directory}")

    # Ensure version.txt exists
    version_path = "application/version.txt"
    if not os.path.exists(version_path):
        with open(version_path, "w") as f:
            f.write("1.0.0\n")
    
    # Ensure required directories exist
    for directory in ["application", "ota_service", "data", "versions"]:
        os.makedirs(directory, exist_ok=True)
    
    # Start OTA service
    logger.info("Starting OTA Update Service...")
    ota_process = subprocess.Popen(
        [sys.executable, "ota_service/ota_updater.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    logger.info(f"OTA Service started with PID {ota_process.pid}")
    return ota_process

if __name__ == "__main__":
    try:
        ota_process = start_services()
        
        # Keep script running and monitor services
        logger.info("Services started, press Ctrl+C to stop...")
        
        while True:
            # Check if OTA service is still running
            if ota_process.poll() is not None:
                logger.error("OTA service has stopped, restarting...")
                ota_process = start_services()
            
            time.sleep(10)
    
    except KeyboardInterrupt:
        logger.info("Stopping services...")
        if ota_process:
            ota_process.terminate()
            # Wait for process to terminate
            for _ in range(5):
                if ota_process.poll() is not None:
                    break
                time.sleep(1)
            
            # Force kill if needed
            if ota_process.poll() is None:
                ota_process.kill()
        
        logger.info("Services stopped")