#!/usr/bin/env python3
"""
OTA Update Service - Checks for updates from GitHub repository and applies them.
"""
import os
import sys
import json
import time
import shutil
import logging
import subprocess
import signal
from datetime import datetime

from github_client import GitHubClient
from version_manager import VersionManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("ota_service/ota.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("OTA-Service")

class OTAUpdater:
    def __init__(self, config_path="config.json"):
        """Initialize the OTA Update Service."""
        logger.info("Starting OTA Update Service")
        
        # Load configuration
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        
        # Initialize GitHub client
        self.github_client = GitHubClient(
            self.config["github_token"],
            self.config["repo_owner"],
            self.config["repo_name"]
        )
        
        # Initialize version manager
        self.version_manager = VersionManager(
            versions_dir=self.config.get("versions_dir", "versions"),
            max_versions=self.config.get("max_versions", 5)
        )
        
        # Set up paths
        self.app_dir = self.config.get("app_dir", "application")
        self.app_process = None
        
        # Connect to database to check application health
        db_path = self.config.get("db_path", "data/app.db")
        self.db_path = db_path
        
        # Make sure directories exist
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        os.makedirs(self.app_dir, exist_ok=True)
        
        # Get current version if available
        self.current_version = self.version_manager.get_current_version()
        logger.info(f"Current version: {self.current_version or 'None'}")
    
    def check_for_update(self):
        """Check GitHub for newer version of the application."""
        logger.info("Checking for updates...")
        
        try:
            # Get latest release or commit from GitHub
            latest_release = self.github_client.get_latest_release()
            
            if not latest_release:
                logger.info("No releases found, checking latest commit")
                latest_commit = self.github_client.get_latest_commit()
                if not latest_commit:
                    logger.info("No updates available")
                    return False
                
                latest_version = latest_commit["sha"][:7]  # Use commit SHA as version
                is_newer = self.current_version != latest_version
                
                if is_newer:
                    logger.info(f"New commit found: {latest_version}")
                    return {"version": latest_version, "commit": latest_commit["sha"]}
            else:
                latest_version = latest_release["tag_name"]
                is_newer = self.current_version != latest_version
                
                if is_newer:
                    logger.info(f"New release found: {latest_version}")
                    return {"version": latest_version, "release": latest_release["id"]}
            
            logger.info("No new updates available")
            return False
        
        except Exception as e:
            logger.error(f"Error checking for updates: {str(e)}")
            return False
    
    def download_update(self, update_info):
        """Download the latest version from GitHub."""
        logger.info(f"Downloading update {update_info['version']}...")
        
        try:
            # Download the application files from GitHub
            if "release" in update_info:
                # Download from release assets
                success, files = self.github_client.download_release_assets(
                    update_info["release"], 
                    self.version_manager.get_version_dir(update_info["version"])
                )
            else:
                # Download latest code
                success, files = self.github_client.download_repository_files(
                    self.version_manager.get_version_dir(update_info["version"]),
                    app_dir=self.app_dir
                )
            
            if success:
                logger.info(f"Downloaded files: {files}")
                return True
            else:
                logger.error("Failed to download update")
                return False
        
        except Exception as e:
            logger.error(f"Error downloading update: {str(e)}")
            return False
    
    def apply_update(self, update_info):
        """Apply the downloaded update."""
        logger.info(f"Applying update {update_info['version']}...")
        
        try:
            version = update_info["version"]
            version_dir = self.version_manager.get_version_dir(version)
            
            # Stop the current application if running
            self.stop_application()
            
            # Backup current application
            if self.current_version:
                self.version_manager.backup_current_version(self.app_dir)
            
            # Copy new version to application directory
            app_files = [f for f in os.listdir(version_dir) if f.endswith((".py", ".txt"))]
            for file in app_files:
                shutil.copy2(
                    os.path.join(version_dir, file),
                    os.path.join(self.app_dir, file)
                )
            
            # Update current version
            self.version_manager.set_current_version(version)
            self.current_version = version
            
            # Start the updated application
            self.start_application()
            
            # Verify the update works correctly
            if self.verify_update():
                logger.info(f"Update to version {version} successful")
                return True
            else:
                logger.error(f"Update verification failed, rolling back")
                self.rollback()
                return False
        
        except Exception as e:
            logger.error(f"Error applying update: {str(e)}")
            self.rollback()
            return False
    
    def verify_update(self, timeout=30):
        """Verify the updated application is working correctly with Azure SQL."""
        logger.info("Verifying update...")
        
        # Wait a moment for the application to start
        time.sleep(5)
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # Check if application is running
                if self.app_process and self.app_process.poll() is not None:
                    logger.error("Application process has terminated")
                    return False
                
                # Check application log file for successful database connection
                log_file = "application/app.log"
                if os.path.exists(log_file):
                    with open(log_file, 'r') as f:
                        log_content = f.read()
                        
                        # Look for successful database operations
                        if "Successfully connected to Azure SQL Database" in log_content:
                            recent_log = log_content[-5000:]  # Check the last 5000 chars
                            
                            # Check if there are any recent data storage operations
                            if "Data stored:" in recent_log or "Weather data stored:" in recent_log:
                                logger.info("Application is running and connecting to Azure SQL")
                                return True
                
            except Exception as e:
                logger.warning(f"Error during verification: {str(e)}")
            
            time.sleep(2)
        
        logger.error("Update verification timed out")
        return False
    
    def stop_application(self):
        """Modified graceful shutdown"""
        if self.app_process:
            logger.info(f"Stopping application with PID {self.app_process.pid}")
            try:
                # Send SIGTERM instead of terminate()
                self.app_process.send_signal(signal.SIGTERM)
                
                # Wait longer for graceful shutdown (30 seconds)
                for _ in range(30):
                    if self.app_process.poll() is not None:
                        break
                    time.sleep(1)
                
                # Force kill if still running
                if self.app_process.poll() is None:
                    logger.warning("Force killing application")
                    self.app_process.kill()
                
                logger.info("Application stopped")
            except Exception as e:
                logger.error(f"Error stopping application: {str(e)}")
            
            self.app_process = None
    
    def rollback(self):
        """Roll back to the previous version."""
        logger.info("Rolling back to previous version...")
        
        try:
            # Stop the current application
            self.stop_application()
            
            # Get previous version
            previous_version = self.version_manager.get_previous_version()
            
            if not previous_version:
                logger.error("No previous version available for rollback")
                return False
            
            # Apply the previous version
            previous_dir = self.version_manager.get_version_dir(previous_version)
            
            # Copy previous version files to application directory
            app_files = [f for f in os.listdir(previous_dir) if f.endswith(".py")]
            for file in app_files:
                shutil.copy2(
                    os.path.join(previous_dir, file),
                    os.path.join(self.app_dir, file)
                )
            
            # Update current version
            self.version_manager.set_current_version(previous_version)
            self.current_version = previous_version
            
            # Start the rolled back application
            self.start_application()
            
            logger.info(f"Rolled back to version {previous_version}")
            return True
        
        except Exception as e:
            logger.error(f"Error during rollback: {str(e)}")
            return False
    
    def start_application(self):
        """Start the application process."""
        logger.info("Starting application...")
        
        try:
            # Start the application as a subprocess
            self.app_process = subprocess.Popen(
                [sys.executable, f"{self.app_dir}/app.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            logger.info(f"Application started with PID {self.app_process.pid}")
            return True
        except Exception as e:
            logger.error(f"Error starting application: {str(e)}")
            return False

    def run(self):
        """Run the OTA update service, periodically checking for updates."""
        logger.info("OTA Update Service running")
        
        # Start the current version of the application
        if not self.start_application():
            logger.error("Failed to start application, initializing with default version")
            # Initialize with the current files in app directory
            self.version_manager.initialize_from_app_dir(self.app_dir)
            self.current_version = self.version_manager.get_current_version()
            self.start_application()
        
        try:
            while True:
                # Check for updates
                update_info = self.check_for_update()
                
                if update_info:
                    logger.info(f"Update available: {update_info['version']}")
                    
                    # Download and apply the update
                    if self.download_update(update_info):
                        self.apply_update(update_info)
                
                # Wait for the configured interval before checking again
                check_interval = self.config.get("check_interval", 300)  # 5 minutes by default
                logger.info(f"Next update check in {check_interval} seconds")
                time.sleep(check_interval)
        
        except KeyboardInterrupt:
            logger.info("OTA Update Service shutdown requested")
        except Exception as e:
            logger.error(f"Error in OTA Update Service: {str(e)}")
        finally:
            self.stop_application()
            logger.info("OTA Update Service stopped")

if __name__ == "__main__":
    updater = OTAUpdater()
    updater.run()