#!/usr/bin/env python3
"""
GitHub Client - Handles interaction with GitHub API
"""
import os
import requests
import logging
import zipfile
import io
import base64

logger = logging.getLogger("GitHub-Client")

class GitHubClient:
    def __init__(self, token, owner, repo):
        """Initialize GitHub client with token and repository information."""
        self.token = token
        self.owner = owner
        self.repo = repo
        self.api_base = "https://api.github.com"
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
    
    def get_latest_release(self):
        """Get the latest release from GitHub."""
        url = f"{self.api_base}/repos/{self.owner}/{self.repo}/releases/latest"
        
        try:
            response = requests.get(url, headers=self.headers)
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                logger.info(f"No releases found for {self.owner}/{self.repo}")
                return None
            else:
                logger.error(f"Failed to get latest release. Status code: {response.status_code}")
                logger.error(f"Response: {response.text}")
                return None
        
        except Exception as e:
            logger.error(f"Error getting latest release: {str(e)}")
            return None
    
    def get_latest_commit(self):
        """Get the latest commit from the default branch."""
        url = f"{self.api_base}/repos/{self.owner}/{self.repo}/commits"
        
        try:
            response = requests.get(url, headers=self.headers, params={"per_page": 1})
            
            if response.status_code == 200:
                commits = response.json()
                if commits:
                    return commits[0]
                return None
            else:
                logger.error(f"Failed to get latest commit. Status code: {response.status_code}")
                return None
        
        except Exception as e:
            logger.error(f"Error getting latest commit: {str(e)}")
            return None
    
    def download_release_assets(self, release_id, destination_dir):
        """Download assets from a specific release."""
        url = f"{self.api_base}/repos/{self.owner}/{self.repo}/releases/{release_id}/assets"
        
        try:
            response = requests.get(url, headers=self.headers)
            
            if response.status_code != 200:
                logger.error(f"Failed to get release assets. Status code: {response.status_code}")
                return False, []
            
            assets = response.json()
            downloaded_files = []
            
            # Create destination directory if it doesn't exist
            os.makedirs(destination_dir, exist_ok=True)
            
            for asset in assets:
                asset_url = asset["browser_download_url"]
                asset_name = asset["name"]
                
                # Download the asset
                asset_response = requests.get(asset_url, headers=self.headers)
                
                if asset_response.status_code == 200:
                    file_path = os.path.join(destination_dir, asset_name)
                    
                    with open(file_path, "wb") as f:
                        f.write(asset_response.content)
                    
                    downloaded_files.append(asset_name)
                    logger.info(f"Downloaded {asset_name}")
                else:
                    logger.error(f"Failed to download {asset_name}. Status code: {asset_response.status_code}")
            
            return len(downloaded_files) > 0, downloaded_files
        
        except Exception as e:
            logger.error(f"Error downloading release assets: {str(e)}")
            return False, []
    
    def download_repository_files(self, destination_dir, app_dir="application"):
        """Download the latest code from the repository."""
        try:
            # Create destination directory if it doesn't exist
            os.makedirs(destination_dir, exist_ok=True)
            
            # Get repository contents specifically for the application directory
            url = f"{self.api_base}/repos/{self.owner}/{self.repo}/contents/{app_dir}"
            
            response = requests.get(url, headers=self.headers)
            
            if response.status_code != 200:
                logger.error(f"Failed to get repository contents. Status code: {response.status_code}")
                return False, []
            
            contents = response.json()
            downloaded_files = []
            
            # Download each Python file
            for item in contents:
                if item["type"] == "file" and (item["name"].endswith(".py") or item["name"].endswith(".txt")):
                    file_url = item["download_url"]
                    file_name = item["name"]
                    
                    # Download the file
                    file_response = requests.get(file_url)
                    
                    if file_response.status_code == 200:
                        file_path = os.path.join(destination_dir, file_name)
                        
                        with open(file_path, "wb") as f:
                            f.write(file_response.content)
                        
                        downloaded_files.append(file_name)
                        logger.info(f"Downloaded {file_name}")
            
            return len(downloaded_files) > 0, downloaded_files
        
        except Exception as e:
            logger.error(f"Error downloading repository files: {str(e)}")
            return False, []
    
    def get_file_content(self, file_path):
        """Get the content of a specific file from the repository."""
        url = f"{self.api_base}/repos/{self.owner}/{self.repo}/contents/{file_path}"
        
        try:
            response = requests.get(url, headers=self.headers)
            
            if response.status_code == 200:
                content = response.json()
                
                if content["encoding"] == "base64":
                    file_content = base64.b64decode(content["content"]).decode("utf-8")
                    return True, file_content
                else:
                    logger.error(f"Unsupported encoding: {content['encoding']}")
                    return False, None
            else:
                logger.error(f"Failed to get file content. Status code: {response.status_code}")
                return False, None
        
        except Exception as e:
            logger.error(f"Error getting file content: {str(e)}")
            return False, None