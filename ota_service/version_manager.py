#!/usr/bin/env python3
"""
Version Manager - Handles version tracking and rollback functionality
"""
import os
import json
import shutil
import logging
import glob

logger = logging.getLogger("Version-Manager")

class VersionManager:
    def __init__(self, versions_dir="versions", max_versions=5):
        """Initialize the version manager."""
        self.versions_dir = versions_dir
        self.max_versions = max_versions
        self.version_file = os.path.join(versions_dir, "versions.json")
        
        # Create versions directory if it doesn't exist
        os.makedirs(versions_dir, exist_ok=True)

        # New initialization check
        if not os.path.exists(self.version_file) or len(self.versions) == 0:
            self.initialize_from_app_dir("application", "2.0.0")
        
        # Load version history if it exists
        self.versions = []
        if os.path.exists(self.version_file):
            try:
                with open(self.version_file, 'r') as f:
                    data = json.load(f)
                    self.versions = data.get("versions", [])
            except Exception as e:
                logger.error(f"Error loading version history: {str(e)}")
        
        logger.info(f"Version history: {self.versions}")

    def initialize_from_app_dir(self, app_dir, version="2.0.0"):
        """Enhanced initialization with automatic file copying"""
        try:
            version_dir = self.get_version_dir(version)
            os.makedirs(version_dir, exist_ok=True)

            # Copy essential files
            essential_files = [
                "app.py", "app_config.py", "database_config.py",
                "version.txt", "requirements.txt"
            ]
            
            for file_name in essential_files:
                src = os.path.join(app_dir, file_name)
                if os.path.exists(src):
                    shutil.copy2(src, os.path.join(version_dir, file_name))
                else:
                    logger.warning(f"Missing essential file: {file_name}")

            # Create version.txt if missing
            version_path = os.path.join(version_dir, "version.txt")
            if not os.path.exists(version_path):
                with open(version_path, "w") as f:
                    f.write(version)

            self.set_current_version(version)
            logger.info(f"Auto-initialized version {version}")
            return True
        except Exception as e:
            logger.error(f"Auto-initialization failed: {str(e)}")
            return False
    
    def get_current_version(self):
        """Get the current version."""
        if self.versions:
            return self.versions[-1]
        return None
    
    def get_previous_version(self):
        """Get the previous version for rollback."""
        if len(self.versions) > 1:
            return self.versions[-2]
        return None
    
    def set_current_version(self, version):
        """Set the current version and update history."""
        if version not in self.versions:
            self.versions.append(version)
            
            # Limit the number of stored versions
            if len(self.versions) > self.max_versions:
                oldest_version = self.versions.pop(0)
                self._cleanup_old_version(oldest_version)
        
        # Save version history
        self._save_version_history()
    
    def get_version_dir(self, version):
        """Get the directory path for a specific version."""
        version_dir = os.path.join(self.versions_dir, version)
        return version_dir
    
    def backup_current_version(self, app_dir):
        """Backup the current version of the application."""
        current_version = self.get_current_version()
        if not current_version:
            logger.warning("No current version to backup")
            return False
        
        try:
            version_dir = self.get_version_dir(current_version)
            os.makedirs(version_dir, exist_ok=True)
            
            # Copy Python files from app directory to version directory
            for file_pattern in ["*.py", "*.txt"]:
                for app_file in glob.glob(os.path.join(app_dir, file_pattern)):
                    file_name = os.path.basename(app_file)
                    shutil.copy2(app_file, os.path.join(version_dir, file_name))
            
            logger.info(f"Backed up version {current_version}")
            return True
        
        except Exception as e:
            logger.error(f"Error backing up current version: {str(e)}")
            return False
    
    def initialize_from_app_dir(self, app_dir, version="2.0.0"):
        """Initialize version history from current app directory."""
        try:
            # Create version directory
            version_dir = self.get_version_dir(version)
            os.makedirs(version_dir, exist_ok=True)
            
            # Copy Python files from app directory to version directory
            for file_pattern in ["*.py", "*.txt"]:
                for app_file in glob.glob(os.path.join(app_dir, file_pattern)):
                    file_name = os.path.basename(app_file)
                    shutil.copy2(app_file, os.path.join(version_dir, file_name))
            
            # Set as current version
            self.set_current_version(version)
            
            logger.info(f"Initialized version history with {version}")
            return True
        
        except Exception as e:
            logger.error(f"Error initializing from app directory: {str(e)}")
            return False
    
    def _save_version_history(self):
        """Save version history to file."""
        try:
            with open(self.version_file, 'w') as f:
                json.dump({"versions": self.versions}, f)
            return True
        except Exception as e:
            logger.error(f"Error saving version history: {str(e)}")
            return False
    
    def _cleanup_old_version(self, version):
        """Clean up files from old versions to save space."""
        try:
            version_dir = self.get_version_dir(version)
            if os.path.exists(version_dir):
                shutil.rmtree(version_dir)
                logger.info(f"Cleaned up old version: {version}")
            return True
        except Exception as e:
            logger.error(f"Error cleaning up old version: {str(e)}")
            return False