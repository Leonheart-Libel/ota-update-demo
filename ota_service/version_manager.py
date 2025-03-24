import os
import json
import shutil
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("ota_version.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("version_manager")

class VersionManager:
    """Manages application versions and rollback for OTA updates."""
    
    def __init__(self, app_dir, versions_dir, current_version_file):
        """
        Initialize the version manager.
        
        Args:
            app_dir (str): Directory where the application is installed
            versions_dir (str): Directory to store version backups
            current_version_file (str): File to store current version information
        """
        self.app_dir = app_dir
        self.versions_dir = versions_dir
        self.current_version_file = current_version_file
        
        # Create directories if they don't exist
        os.makedirs(app_dir, exist_ok=True)
        os.makedirs(versions_dir, exist_ok=True)
        
        # Initialize current version file if it doesn't exist
        if not os.path.exists(current_version_file):
            self._save_version_info({
                "version": "0.0.0",
                "commit": None,
                "install_date": datetime.now().isoformat(),
                "history": []
            })
    
    def get_current_version(self):
        """Get the current version information."""
        try:
            with open(self.current_version_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Error reading current version: {e}")
            return {
                "version": "0.0.0",
                "commit": None,
                "install_date": datetime.now().isoformat(),
                "history": []
            }
    
    def _save_version_info(self, version_info):
        """Save version information to the current version file."""
        try:
            with open(self.current_version_file, 'w') as f:
                json.dump(version_info, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error saving version info: {e}")
            return False
    
    def backup_current_version(self):
        """
        Backup the current version before updating.
        
        Returns:
            str: Backup directory path or None if failed
        """
        current_version = self.get_current_version()
        version = current_version.get("version", "unknown")
        
        # Create a backup directory for this version
        backup_dir = os.path.join(self.versions_dir, f"v{version}_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        
        try:
            if os.path.exists(self.app_dir):
                os.makedirs(backup_dir, exist_ok=True)
                
                # Copy all files from app_dir to backup_dir
                for item in os.listdir(self.app_dir):
                    source = os.path.join(self.app_dir, item)
                    destination = os.path.join(backup_dir, item)
                    
                    if os.path.isdir(source):
                        shutil.copytree(source, destination)
                    else:
                        shutil.copy2(source, destination)
                
                # Save version metadata in the backup dir
                with open(os.path.join(backup_dir, "version_info.json"), 'w') as f:
                    json.dump(current_version, f, indent=2)
                
                logger.info(f"Backed up version {version} to {backup_dir}")
                return backup_dir
            else:
                logger.warning(f"App directory {self.app_dir} does not exist, nothing to backup")
                return None
                
        except Exception as e:
            logger.error(f"Error backing up current version: {e}")
            return None
    
    def update_version(self, new_version, commit_hash):
        """
        Update the current version information.
        
        Args:
            new_version (str): New version number
            commit_hash (str): GitHub commit hash of the new version
            
        Returns:
            bool: True if successful, False otherwise
        """
        current_info = self.get_current_version()
        
        # Add current version to history
        if current_info.get("version") != "0.0.0" and current_info.get("commit"):
            current_info["history"].append({
                "version": current_info["version"],
                "commit": current_info["commit"],
                "install_date": current_info["install_date"]
            })
            
            # Keep only the last 5 versions in history
            if len(current_info["history"]) > 5:
                current_info["history"] = current_info["history"][-5:]
        
        # Update current version
        current_info["version"] = new_version
        current_info["commit"] = commit_hash
        current_info["install_date"] = datetime.now().isoformat()
        
        return self._save_version_info(current_info)
    
    def rollback(self):
        """
        Rollback to the previous version.
        
        Returns:
            dict: Previous version info or None if rollback failed
        """
        current_info = self.get_current_version()
        
        if not current_info["history"]:
            logger.warning("No previous versions to rollback to")
            return None
        
        # Get the most recent previous version
        prev_version = current_info["history"].pop()
        
        # Find the backup directory for this version
        backup_dirs = [d for d in os.listdir(self.versions_dir) 
                      if d.startswith(f"v{prev_version['version']}_")]
        
        if not backup_dirs:
            logger.error(f"No backup found for version {prev_version['version']}")
            return None
        
        # Use the most recent backup (sorted by name which includes timestamp)
        backup_dirs.sort(reverse=True)
        backup_dir = os.path.join(self.versions_dir, backup_dirs[0])
        
        try:
            # Clear the app directory
            for item in os.listdir(self.app_dir):
                item_path = os.path.join(self.app_dir, item)
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                else:
                    os.remove(item_path)
            
            # Copy from backup to app directory
            for item in os.listdir(backup_dir):
                source = os.path.join(backup_dir, item)
                destination = os.path.join(self.app_dir, item)
                
                # Skip the version_info.json file
                if item == "version_info.json":
                    continue
                    
                if os.path.isdir(source):
                    shutil.copytree(source, destination)
                else:
                    shutil.copy2(source, destination)
            
            # Update current version
            current_info["version"] = prev_version["version"]
            current_info["commit"] = prev_version["commit"]
            current_info["install_date"] = datetime.now().isoformat()
            
            self._save_version_info(current_info)
            
            logger.info(f"Rolled back to version {prev_version['version']}")
            return prev_version
            
        except Exception as e:
            logger.error(f"Error during rollback: {e}")
            return None
    
    def cleanup_old_backups(self, keep_count=3):
        """
        Remove old backups, keeping only the most recent ones.
        
        Args:
            keep_count (int): Number of recent backups to keep
            
        Returns:
            int: Number of backups removed
        """
        try:
            backup_dirs = [os.path.join(self.versions_dir, d) for d in os.listdir(self.versions_dir)]
            backup_dirs = [d for d in backup_dirs if os.path.isdir(d)]
            
            # Sort by modification time (oldest first)
            backup_dirs.sort(key=lambda d: os.path.getmtime(d))
            
            # Remove oldest backups beyond keep_count
            removed = 0
            for backup_dir in backup_dirs[:-keep_count] if len(backup_dirs) > keep_count else []:
                shutil.rmtree(backup_dir)
                logger.info(f"Removed old backup: {backup_dir}")
                removed += 1
                
            return removed
            
        except Exception as e:
            logger.error(f"Error cleaning up old backups: {e}")
            return 0