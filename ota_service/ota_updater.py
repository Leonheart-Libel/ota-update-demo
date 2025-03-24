import os
import sys
import time
import json
import logging
import subprocess
import signal
import requests
from datetime import datetime
import traceback

# Add local modules to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ota_service.github_client import GitHubClient
from ota_service.version_manager import VersionManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("ota_updater.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("ota_updater")

class OTAUpdater:
    """Main OTA update service that checks for and applies updates."""
    
    def __init__(self, config_file):
        """
        Initialize the OTA updater.
        
        Args:
            config_file (str): Path to the configuration file
        """
        self.config_file = config_file
        self.load_config()
        
        self.github_client = GitHubClient(
            owner=self.config['github']['owner'],
            repo=self.config['github']['repo'],
            token=self.config['github'].get('token'),
            branch=self.config['github'].get('branch', 'main')
        )
        
        self.version_manager = VersionManager(
            app_dir=self.config['app']['install_dir'],
            versions_dir=self.config['app']['versions_dir'],
            current_version_file=self.config['app']['version_file']
        )
        
        self.app_process = None
        self.running = False
    
    def load_config(self):
        """Load configuration from the config file."""
        try:
            with open(self.config_file, 'r') as f:
                self.config = json.load(f)
                
            # Ensure required directories exist
            os.makedirs(self.config['app']['install_dir'], exist_ok=True)
            os.makedirs(self.config['app']['versions_dir'], exist_ok=True)
                
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            sys.exit(1)
    
    def check_for_updates(self):
        """
        Check if updates are available.
        
        Returns:
            tuple: (update_available, version_info)
        """
        try:
            # Get the latest commit from GitHub
            latest_commit = self.github_client.get_latest_commit()
            if not latest_commit:
                return False, None
            
            # Get version information from the repository
            version_info = self.github_client.get_version_info(
                self.config['app'].get('version_file_repo', 'application/version.json')
            )
            if not version_info:
                return False, None
            
            # Get current version
            current_version = self.version_manager.get_current_version()
            
            # Check if the version is newer
            if version_info.get('version') != current_version.get('version'):
                logger.info(f"New version available: {version_info.get('version')} "
                           f"(current: {current_version.get('version')})")
                return True, version_info
            
            # Check if commit hash is different (for same version but different code)
            if (latest_commit.get('sha') != current_version.get('commit') and 
                current_version.get('commit') is not None):
                logger.info(f"New commit detected: {latest_commit.get('sha')[:7]}")
                version_info['commit'] = latest_commit.get('sha')
                return True, version_info
            
            return False, None
            
        except Exception as e:
            logger.error(f"Error checking for updates: {e}")
            return False, None
    
    def stop_application(self):
        """
        Stop the running application.
        
        Returns:
            bool: True if successful, False otherwise
        """
        if self.app_process:
            try:
                # Try graceful termination first
                self.app_process.terminate()
                
                # Wait for process to terminate
                for _ in range(10):  # 5 seconds timeout
                    if self.app_process.poll() is not None:
                        break
                    time.sleep(0.5)
                
                # Force kill if not terminated
                if self.app_process.poll() is None:
                    self.app_process.kill()
                    self.app_process.wait()
                
                self.app_process = None
                logger.info("Application stopped successfully")
                return True
                
            except Exception as e:
                logger.error(f"Error stopping application: {e}")
                return False
        
        # Try to find and kill the process by name if we didn't start it
        try:
            app_name = os.path.basename(self.config['app']['start_command'].split()[0])
            subprocess.run(['pkill', '-f', app_name], check=False)
            logger.info(f"Attempted to stop application using pkill -f {app_name}")
            time.sleep(2)  # Give it time to stop
            return True
        except Exception as e:
            logger.error(f"Error trying to pkill application: {e}")
            return False
    
    def start_application(self):
        """
        Start the application.
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Change to the app directory
            os.chdir(self.config['app']['install_dir'])
            
            # Start the application
            cmd = self.config['app']['start_command'].split()
            self.app_process = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
            # Wait a bit to make sure it starts
            time.sleep(2)
            
            # Check if process is running
            if self.app_process.poll() is None:
                logger.info(f"Application started successfully: {self.config['app']['start_command']}")
                return True
            else:
                stdout, stderr = self.app_process.communicate()
                logger.error(f"Application failed to start: {stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Error starting application: {e}")
            return False
    
    def update_application(self, version_info):
        """
        Update the application to the new version.
        
        Args:
            version_info (dict): New version information
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Backup current version
            backup_dir = self.version_manager.backup_current_version()
            if not backup_dir and self.version_manager.get_current_version().get('version') != "0.0.0":
                logger.error("Failed to backup current version, aborting update")
                return False
            
            # Stop the application
            if not self.stop_application():
                logger.warning("Failed to stop application, continuing with update anyway")
            
            # Download new version
            app_repo_path = self.config['app'].get('repo_path', 'application')
            if not self.github_client.download_directory(
                app_repo_path, 
                self.config['app']['install_dir']
            ):
                logger.error("Failed to download new version")
                return False
            
            # Update version information
            commit = version_info.get('commit')
            version = version_info.get('version')
            self.version_manager.update_version(version, commit)
            
            # Start the application
            if not self.start_application():
                logger.error("Failed to start updated application, rolling back")
                self.rollback()
                return False
            
            logger.info(f"Successfully updated to version {version}")
            
            # Clean up old backups
            self.version_manager.cleanup_old_backups(
                keep_count=self.config.get('keep_backups', 3)
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error updating application: {traceback.format_exc()}")
            self.rollback()
            return False
    
    def rollback(self):
        """
        Rollback to the previous version if the update fails.
        
        Returns:
            bool: True if successful, False otherwise
        """
        logger.info("Rolling back to previous version")
        
        try:
            # Stop the application
            self.stop_application()
            
            # Rollback to previous version
            prev_version = self.version_manager.rollback()
            if not prev_version:
                logger.error("No previous version to rollback to")
                return False
            
            # Restart the application
            if not self.start_application():
                logger.error("Failed to start application after rollback")
                return False
            
            logger.info(f"Successfully rolled back to version {prev_version.get('version')}")
            return True
            
        except Exception as e:
            logger.error(f"Error during rollback: {e}")
            return False
    
    def health_check(self):
        """
        Check if the application is healthy.
        
        Returns:
            bool: True if healthy, False otherwise
        """
        try:
            # Simple process check
            if self.app_process and self.app_process.poll() is None:
                return True
            
            # HTTP health check if configured
            if 'health_check_url' in self.config['app']:
                try:
                    response = requests.get(
                        self.config['app']['health_check_url'],
                        timeout=5
                    )
                    return response.status_code == 200
                except requests.RequestException:
                    return False
            
            # If no health check is configured, assume it's healthy
            if self.app_process is None:
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"Error in health check: {e}")
            return False
    
    def run_once(self):
        """Run a single update check cycle."""
        try:
            logger.info("Checking for updates...")
            update_available, version_info = self.check_for_updates()
            
            if update_available and version_info:
                logger.info(f"Updating to version {version_info.get('version')}")
                self.update_application(version_info)
            else:
                logger.info("No updates available")
                
            # Check application health
            if not self.health_check() and self.config['app'].get('restart_on_failure', True):
                logger.warning("Application health check failed, attempting to restart")
                self.stop_application()
                self.start_application()
                
        except Exception as e:
            logger.error(f"Error in update cycle: {e}")
    
    def run_forever(self):
        """Run the updater service continuously."""
        self.running = True
        
        # Start the application if it's not running
        if not self.health_check():
            logger.info("Starting application")
            self.start_application()
        
        def handle_signal(signum, frame):
            logger.info(f"Received signal {signum}, shutting down")
            self.running = False
        
        # Register signal handlers
        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)
        
        logger.info("OTA updater service started")
        
        while self.running:
            try:
                self.run_once()
                
                # Sleep until next check
                check_interval = self.config.get('check_interval_seconds', 300)
                logger.info(f"Sleeping for {check_interval} seconds")
                
                # Break sleep into smaller chunks to respond to signals faster
                for _ in range(check_interval):
                    if not self.running:
                        break
                    time.sleep(1)
                    
            except Exception as e:
                logger.error(f"Unexpected error in main loop: {e}")
                time.sleep(10)  # Shorter sleep on error
        
        # Cleanup on shutdown
        logger.info("Shutting down OTA updater service")
        self.stop_application()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ota_updater.py <config_file>")
        sys.exit(1)
        
    config_file = sys.argv[1]
    if not os.path.exists(config_file):
        print(f"Config file not found: {config_file}")
        sys.exit(1)
    
    updater = OTAUpdater(config_file)
    updater.run_forever()