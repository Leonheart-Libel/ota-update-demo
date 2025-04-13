#!/usr/bin/env python3
"""
Enhanced test application that generates more complex data, performs analysis,
and provides a simple HTTP API for data access.
This application is the target of OTA updates.
"""
import os
import time
import random
import sqlite3
import logging
import threading
import json
import statistics
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("application/app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("EnhancedApp")

# App version - read from version file
version_files = [
    "application/version.txt",  # Path relative to project root
    "version.txt",              # Path relative to current directory
    "../application/version.txt"  # Another possible path
]

APP_VERSION = "2.0.0"  # Default fallback version
for version_file in version_files:
    try:
        if os.path.exists(version_file):
            with open(version_file, "r") as f:
                version = f.read().strip()
                if version:  # Only use if not empty
                    APP_VERSION = version
                    logger.info(f"Loaded version {APP_VERSION} from {version_file}")
                    break
    except Exception as e:
        logger.warning(f"Error reading version file {version_file}: {str(e)}")

logger.info(f"Current working directory: {os.getcwd()}")
logger.info(f"Using application version: {APP_VERSION}")

# Load configuration
def load_config():
    """Load application configuration from app_config.py"""
    config = {
        "interval": 5,
        "data_mode": "random",
        "api_enabled": True,
        "api_port": 8080,
        "analysis_enabled": True,
        "analysis_window": 60  # seconds
    }
    
    config_path = "application/app_config.py"
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        try:
                            key, value = line.split("=", 1)
                            key = key.strip()
                            value = value.strip()
                            
                            # Convert value to appropriate type
                            if value.lower() == "true":
                                value = True
                            elif value.lower() == "false":
                                value = False
                            elif value.isdigit():
                                value = int(value)
                            elif value.replace(".", "", 1).isdigit():
                                value = float(value)
                                
                            config[key.lower()] = value
                        except ValueError:
                            pass
        except Exception as e:
            logger.warning(f"Error loading config: {str(e)}")
    
    return config

class DataAnalyzer:
    """Analyzes data and computes statistics"""
    def __init__(self, db_path, window_seconds=60):
        self.db_path = db_path
        self.window_seconds = window_seconds
        self.last_analysis = None
    
    def analyze(self):
        """Analyze recent data and return statistics"""
        try:
            # Connect to database
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get data from last window_seconds
            window_start = (datetime.now() - timedelta(seconds=self.window_seconds)).isoformat()
            cursor.execute(
                "SELECT value FROM log_data WHERE timestamp > ? ORDER BY timestamp",
                (window_start,)
            )
            
            values = [row[0] for row in cursor.fetchall()]
            conn.close()
            
            if not values:
                return {
                    "timestamp": datetime.now().isoformat(),
                    "status": "no_data",
                    "count": 0
                }
            
            # Calculate statistics
            result = {
                "timestamp": datetime.now().isoformat(),
                "status": "success",
                "count": len(values),
                "min": min(values),
                "max": max(values),
                "mean": statistics.mean(values),
                "median": statistics.median(values)
            }
            
            # Add standard deviation if we have enough data points
            if len(values) > 1:
                result["std_dev"] = statistics.stdev(values)
            
            self.last_analysis = result
            return result
            
        except Exception as e:
            logger.error(f"Error analyzing data: {str(e)}")
            return {
                "timestamp": datetime.now().isoformat(),
                "status": "error",
                "error": str(e)
            }

class ApiHandler(BaseHTTPRequestHandler):
    """Simple HTTP API handler for data access"""
    def __init__(self, *args, app_instance=None, **kwargs):
        self.app = app_instance
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        """Handle GET requests"""
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(f"""
            <html>
                <head><title>Enhanced App v{APP_VERSION}</title></head>
                <body>
                    <h1>Enhanced Test App v{APP_VERSION}</h1>
                    <p>Available endpoints:</p>
                    <ul>
                        <li><a href="/status">/status</a> - Application status</li>
                        <li><a href="/data">/data</a> - Recent data points</li>
                        <li><a href="/analysis">/analysis</a> - Data analysis</li>
                    </ul>
                </body>
            </html>
            """.encode())
            
        elif self.path == "/status":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            
            status = {
                "version": APP_VERSION,
                "uptime": (datetime.now() - self.app.start_time).total_seconds(),
                "data_count": self.app.get_data_count(),
                "data_mode": self.app.config["data_mode"],
                "config": self.app.config
            }
            
            self.wfile.write(json.dumps(status).encode())
            
        elif self.path == "/data":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            
            recent_data = self.app.get_recent_data(limit=20)
            self.wfile.write(json.dumps(recent_data).encode())
            
        elif self.path == "/analysis":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            
            if self.app.analyzer and self.app.analyzer.last_analysis:
                analysis = self.app.analyzer.last_analysis
            else:
                analysis = {"status": "no_analysis_yet"}
                
            self.wfile.write(json.dumps(analysis).encode())
            
        else:
            self.send_response(404)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Not Found")
    
    def log_message(self, format, *args):
        # Redirect log messages to our logger
        logger.info(f"API: {args[0]} {args[1]} {args[2]}")

class EnhancedApplication:
    def __init__(self, db_path="data/app.db"):
        """Initialize the enhanced application with database connection."""
        self.start_time = datetime.now()
        logger.info(f"Starting Enhanced Application v{APP_VERSION}")
        
        self.config = load_config()
        logger.info(f"Loaded configuration: {self.config}")
        
        # Ensure data directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        
        # Connect to SQLite database
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        
        # Create table if it doesn't exist
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS log_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            value REAL,
            message TEXT,
            version TEXT,
            data_type TEXT
        )
        ''')
        
        # Create analysis table
        self.cursor.execute('''
        CREATE TABLE IF NOT EXISTS analysis_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            count INTEGER,
            min_value REAL,
            max_value REAL,
            mean_value REAL,
            median_value REAL,
            std_dev REAL
        )
        ''')
        self.conn.commit()
        
        # Initialize analyzer if enabled
        self.analyzer = None
        if self.config.get("analysis_enabled", True):
            self.analyzer = DataAnalyzer(
                db_path, 
                window_seconds=self.config.get("analysis_window", 60)
            )
        
        # Initialize API server if enabled
        self.api_server = None
        if self.config.get("api_enabled", True):
            api_port = self.config.get("api_port", 8080)
            
            # Create a custom handler class that has access to our app instance
            def handler_factory(*args, **kwargs):
                return ApiHandler(*args, app_instance=self, **kwargs)
                
            self.api_server = HTTPServer(("0.0.0.0", api_port), handler_factory)
            
            # Start API server in a separate thread
            threading.Thread(
                target=self.api_server.serve_forever,
                daemon=True
            ).start()
            
            logger.info(f"API server started on port {api_port}")
        
    def generate_data(self):
        """Generate data based on the configured mode."""
        timestamp = datetime.now().isoformat()
        data_mode = self.config.get("data_mode", "random")
        data_type = data_mode
        
        if data_mode == "random":
            value = random.uniform(0, 100)
            message = f"Random data point: {value:.2f}"
            
        elif data_mode == "sine":
            # Generate sine wave pattern
            seconds = time.time()
            value = 50 + 50 * math.sin(seconds / 10)
            message = f"Sine wave data point: {value:.2f}"
            
        elif data_mode == "step":
            # Generate stepping pattern (0, 25, 50, 75, 100)
            step = int(time.time() / 5) % 5
            value = step * 25
            message = f"Step data point: {value}"
            
        elif data_mode == "random_walk":
            # Get last value and add random walk
            try:
                self.cursor.execute(
                    "SELECT value FROM log_data ORDER BY id DESC LIMIT 1"
                )
                result = self.cursor.fetchone()
                last_value = result[0] if result else 50
                
                # Add random walk with bounds
                value = max(0, min(100, last_value + random.uniform(-10, 10)))
                message = f"Random walk data point: {value:.2f}"
            except Exception:
                # Fallback to random if error
                value = random.uniform(0, 100)
                message = f"Fallback random data point: {value:.2f}"
        
        else:
            # Default to random if unknown mode
            value = random.uniform(0, 100)
            message = f"Default random data point: {value:.2f}"
            data_type = "random"
        
        return {
            "timestamp": timestamp,
            "value": value,
            "message": message,
            "version": APP_VERSION,
            "data_type": data_type
        }
    
    def store_data(self, data):
        """Store data in SQLite database."""
        self.cursor.execute(
            "INSERT INTO log_data (timestamp, value, message, version, data_type) VALUES (?, ?, ?, ?, ?)",
            (data["timestamp"], data["value"], data["message"], data["version"], data["data_type"])
        )
        self.conn.commit()
    
    def run_analysis(self):
        """Run data analysis and store results."""
        if not self.analyzer:
            return
            
        analysis = self.analyzer.analyze()
        
        if analysis.get("status") == "success":
            # Store analysis results
            self.cursor.execute(
                """
                INSERT INTO analysis_results 
                (timestamp, count, min_value, max_value, mean_value, median_value, std_dev) 
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    analysis["timestamp"], 
                    analysis["count"],
                    analysis["min"],
                    analysis["max"],
                    analysis["mean"],
                    analysis["median"],
                    analysis.get("std_dev", 0)
                )
            )
            self.conn.commit()
            logger.info(f"Analysis complete: {analysis}")
    
    def get_data_count(self):
        """Get the total count of data points."""
        try:
            self.cursor.execute("SELECT COUNT(*) FROM log_data")
            return self.cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"Error getting data count: {str(e)}")
            return 0
    
    def get_recent_data(self, limit=20):
        """Get the most recent data points."""
        try:
            self.cursor.execute(
                "SELECT timestamp, value, message, version, data_type FROM log_data ORDER BY id DESC LIMIT ?",
                (limit,)
            )
            columns = ["timestamp", "value", "message", "version", "data_type"]
            result = []
            for row in self.cursor.fetchall():
                result.append(dict(zip(columns, row)))
            return result
        except Exception as e:
            logger.error(f"Error getting recent data: {str(e)}")
            return []
        
    def run(self):
        """Run the application, generating and storing data periodically."""
        logger.info(f"Enhanced application running with version {APP_VERSION}")
        
        # Track time for analysis scheduling
        last_analysis_time = datetime.now()
        analysis_interval = self.config.get("analysis_interval", 30)  # seconds
        
        try:
            while True:
                # Generate and store data
                data = self.generate_data()
                self.store_data(data)
                logger.info(f"Data stored: {data}")
                
                # Run analysis if it's time
                now = datetime.now()
                if (now - last_analysis_time).total_seconds() >= analysis_interval:
                    self.run_analysis()
                    last_analysis_time = now
                
                # Sleep for the configured interval
                time.sleep(self.config.get("interval", 5))
                
        except KeyboardInterrupt:
            logger.info("Application shutdown requested")
        except Exception as e:
            logger.error(f"Error in application: {str(e)}")
        finally:
            if self.api_server:
                self.api_server.shutdown()
                logger.info("API server stopped")
                
            self.conn.close()
            logger.info("Application stopped")

if __name__ == "__main__":
    try:
        # Import math module needed for sine wave
        import math
    except ImportError:
        logger.error("Required modules not available")
        sys.exit(1)
        
    app = EnhancedApplication()
    app.run()