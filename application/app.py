import os
import json
import time
import random
import logging
import uuid
import sqlite3
import pyodbc
import sys
from datetime import datetime

# Configure logging with more detailed format
logging.basicConfig(
    level=logging.DEBUG,  # Changed from INFO to DEBUG
    format='%(asctime)s - %(levelname)s - [%(name)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("data_generator")

class DataGenerator:
    """
    Enhanced data generator with more detailed logging and additional diagnostics.
    """
    
    def __init__(self, config_file):
        """
        Initialize the data generator with enhanced logging.
        
        Args:
            config_file (str): Path to the configuration file
        """
        self.config_file = config_file
        self.load_config()
        self.setup_storage()
        self.app_id = str(uuid.uuid4())[:8]  # Unique ID for this instance
        self.counter = 0
        
        # New: System diagnostics logging
        logger.info(f"System Diagnostics:")
        logger.info(f"Python Version: {sys.version}")
        logger.info(f"Operating System: {sys.platform}")
    
    # ... [rest of the code remains the same as in the original app.py] ...
    
    def generate_data_point(self):
        """Generate a random data point with more detailed information."""
        self.counter += 1
        timestamp = datetime.now().isoformat()
        value = random.uniform(0, 100)
        app_version = self.get_app_version()
        
        # Enhanced data point with more metadata
        return {
            "timestamp": timestamp,
            "value": value,
            "app_version": app_version,
            "app_id": self.app_id,
            "counter": self.counter,
            "system_info": {
                "python_version": sys.version.split()[0],
                "platform": sys.platform
            }
        }
    
    # ... [rest of the code remains the same as in the original app.py] ...

# ... [rest of the file remains the same] ...