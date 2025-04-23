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

def get_script_dir():
    """Get the directory of this script to use as base path."""
    return os.path.dirname(os.path.abspath(__file__))

def start_services():
    """Start the application and OTA service and ensure all required directories exist."""
    logger.info("Starting services...")
    
    # Set the working directory to the script directory
    base_dir = get_script_dir()
    os.chdir(base_dir)
    logger.info(f"Working directory set to: {os.getcwd()}")
    
    # Ensure required directories exist
    for directory in ["application", "ota_service", "data", "versions"]:
        os.makedirs(directory, exist_ok=True)
    
    # Start application
    logger.info("Starting Weather Application...")
    app_process = subprocess.Popen(
        [sys.executable, os.path.join(base_dir, "application/app.py")],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    logger.info(f"Weather Application started with PID {app_process.pid}")
    
    # Give the app a moment to initialize
    time.sleep(2)
    
    # Start OTA service
    logger.info("Starting OTA Update Service...")
    ota_process = subprocess.Popen(
        [sys.executable, os.path.join(base_dir, "ota_service/ota_updater.py")],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=dict(os.environ, PYTHONPATH=base_dir)  # Add base directory to Python path
    )
    
    logger.info(f"OTA Service started with PID {ota_process.pid}")
    return app_process, ota_process

if __name__ == "__main__":
    try:
        app_process, ota_process = start_services()
        
        # Keep script running and monitor services
        logger.info("Services started, press Ctrl+C to stop...")
        
        while True:
            # Check if services are still running
            if app_process.poll() is not None:
                logger.error("Weather application has stopped, restarting...")
                app_process, _ = start_services()
            
            if ota_process.poll() is not None:
                logger.error("OTA service has stopped, restarting...")
                _, ota_process = start_services()
            
            time.sleep(10)
    
    except KeyboardInterrupt:
        logger.info("Stopping services...")
        
        # Stop app process
        if app_process:
            app_process.terminate()
            # Wait for process to terminate
            for _ in range(5):
                if app_process.poll() is not None:
                    break
                time.sleep(1)
            
            # Force kill if needed
            if app_process.poll() is None:
                app_process.kill()
        
        # Stop OTA process
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