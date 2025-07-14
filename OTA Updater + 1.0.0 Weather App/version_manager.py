#!/usr/bin/env python3
import os
import json
import shutil
import logging
import glob

logger = logging.getLogger("Version-Manager")

class VersionManager:
    def __init__(self, versions_dir="versions", max_versions=5):
        self.versions_dir = versions_dir
        self.max_versions = max_versions
        self.version_file = os.path.join(versions_dir, "versions.json")
        
        os.makedirs(versions_dir, exist_ok=True)
        
        self.versions = []
        if os.path.exists(self.version_file):
            try:
                with open(self.version_file, 'r') as f:
                    data = json.load(f)
                    self.versions = data.get("versions", [])
            except Exception as e:
                logger.error(f"Error loading version history: {str(e)}")
        
        logger.info(f"Version history: {self.versions}")
    
    def get_current_version(self):
        if self.versions:
            return self.versions[-1]
        return None
    
    def get_previous_version(self):
        if len(self.versions) > 1:
            return self.versions[-2]
        return None
    
    def set_current_version(self, version):
        if version not in self.versions:
            self.versions.append(version)
            
            if len(self.versions) > self.max_versions:
                oldest_version = self.versions.pop(0)
                self._cleanup_old_version(oldest_version)
        
        self._save_version_history()
    
    def get_version_dir(self, version):
        version_dir = os.path.join(self.versions_dir, version)
        return version_dir
    
    def backup_current_version(self, app_dir):
        current_version = self.get_current_version()
        if not current_version:
            logger.warning("No current version to backup")
            return False
        
        try:
            version_dir = self.get_version_dir(current_version)
            os.makedirs(version_dir, exist_ok=True)
            
            for file_pattern in ["*.py", "*.txt"]:
                for app_file in glob.glob(os.path.join(app_dir, file_pattern)):
                    file_name = os.path.basename(app_file)
                    shutil.copy2(app_file, os.path.join(version_dir, file_name))
            
            logger.info(f"Backed up version {current_version}")
            return True
        
        except Exception as e:
            logger.error(f"Error backing up current version: {str(e)}")
            return False
    
    def initialize_from_app_dir(self, app_dir, version="1.0.0"):
        try:
            version_dir = self.get_version_dir(version)
            os.makedirs(version_dir, exist_ok=True)
            
            for file_pattern in ["*.py", "*.txt"]:
                for app_file in glob.glob(os.path.join(app_dir, file_pattern)):
                    file_name = os.path.basename(app_file)
                    shutil.copy2(app_file, os.path.join(version_dir, file_name))
            
            self.set_current_version(version)
            
            logger.info(f"Initialized version history with {version}")
            return True
        
        except Exception as e:
            logger.error(f"Error initializing from app directory: {str(e)}")
            return False
    
    def _save_version_history(self):
        try:
            with open(self.version_file, 'w') as f:
                json.dump({"versions": self.versions}, f)
            return True
        except Exception as e:
            logger.error(f"Error saving version history: {str(e)}")
            return False
    
    def _cleanup_old_version(self, version):
        try:
            version_dir = self.get_version_dir(version)
            if os.path.exists(version_dir):
                shutil.rmtree(version_dir)
                logger.info(f"Cleaned up old version: {version}")
            return True
        except Exception as e:
            logger.error(f"Error cleaning up old version: {str(e)}")
            return False