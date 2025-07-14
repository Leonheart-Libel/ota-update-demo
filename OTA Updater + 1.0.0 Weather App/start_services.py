#!/usr/bin/env python3
import os
import sys
import time
import subprocess
import logging

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
APP_DIR = os.path.join(BASE_DIR, "application")
OTA_DIR = os.path.join(BASE_DIR, "ota_service")

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
    return os.path.dirname(os.path.abspath(__file__))

def start_services():
    logger.info("Starting services...")
    
    base_dir = get_script_dir()
    os.chdir(base_dir)
    logger.info(f"Working directory set to: {os.getcwd()}")
    
    for directory in ["application", "ota_service", "data", "versions"]:
        os.makedirs(directory, exist_ok=True)
    
    logger.info("Starting OTA Update Service...")
    ota_process = subprocess.Popen(
        [sys.executable, os.path.join(base_dir, "ota_service/ota_updater.py")],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=dict(os.environ, PYTHONPATH=base_dir)
    )
    
    logger.info(f"OTA Service started with PID {ota_process.pid}")
    return ota_process

if __name__ == "__main__":
    try:
        ota_process = start_services()
        
        logger.info("OTA service started, press Ctrl+C to stop...")
        
        while True:
            if ota_process.poll() is not None:
                logger.error("OTA service has stopped, restarting...")
                ota_process = start_services()
            
            time.sleep(10)
    
    except KeyboardInterrupt:
        logger.info("Stopping services...")
        
        if ota_process:
            ota_process.terminate()
            for _ in range(5):
                if ota_process.poll() is not None:
                    break
                time.sleep(1)
            
            if ota_process.poll() is None:
                ota_process.kill()
        
        logger.info("Services stopped")