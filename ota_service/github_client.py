import os
import requests
import json
import base64
from datetime import datetime
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("ota_github.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("github_client")

class GitHubClient:
    """Client for interacting with GitHub API for OTA updates."""
    
    def __init__(self, owner, repo, token=None, branch="main"):
        """
        Initialize the GitHub client.
        
        Args:
            owner (str): GitHub repository owner/username
            repo (str): GitHub repository name
            token (str, optional): GitHub personal access token for API authentication
            branch (str, optional): Repository branch to track. Defaults to "main".
        """
        self.owner = owner
        self.repo = repo
        self.branch = branch
        self.headers = {}
        
        if token:
            self.headers["Authorization"] = f"token {token}"
        
        self.api_base = "https://api.github.com"
        
    def get_latest_commit(self):
        """Get the latest commit hash from the repository."""
        url = f"{self.api_base}/repos/{self.owner}/{self.repo}/commits/{self.branch}"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            commit_data = response.json()
            return {
                "sha": commit_data["sha"],
                "date": commit_data["commit"]["author"]["date"],
                "message": commit_data["commit"]["message"]
            }
        except requests.RequestException as e:
            logger.error(f"Error fetching latest commit: {e}")
            return None
    
    def download_file(self, path, output_path):
        """
        Download a file from the repository.
        
        Args:
            path (str): Path to the file in the repository
            output_path (str): Local path to save the file
        
        Returns:
            bool: True if successful, False otherwise
        """
        url = f"{self.api_base}/repos/{self.owner}/{self.repo}/contents/{path}?ref={self.branch}"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            content_data = response.json()
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Decode and save the file
            content = base64.b64decode(content_data["content"])
            with open(output_path, "wb") as f:
                f.write(content)
            
            logger.info(f"Downloaded {path} to {output_path}")
            return True
        
        except requests.RequestException as e:
            logger.error(f"Error downloading file {path}: {e}")
            return False
    
    def download_directory(self, repo_path, local_path):
        """
        Download all files from a directory in the repository.
        
        Args:
            repo_path (str): Path to the directory in the repository
            local_path (str): Local path to save the directory
        
        Returns:
            bool: True if successful, False otherwise
        """
        url = f"{self.api_base}/repos/{self.owner}/{self.repo}/contents/{repo_path}?ref={self.branch}"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            contents = response.json()
            
            # Ensure the local directory exists
            os.makedirs(local_path, exist_ok=True)
            
            success = True
            
            for item in contents:
                if item["type"] == "file":
                    output_file = os.path.join(local_path, item["name"])
                    if not self.download_file(item["path"], output_file):
                        success = False
                elif item["type"] == "dir":
                    subdir_path = os.path.join(local_path, item["name"])
                    if not self.download_directory(item["path"], subdir_path):
                        success = False
            
            return success
            
        except requests.RequestException as e:
            logger.error(f"Error downloading directory {repo_path}: {e}")
            return False
    
    def get_version_info(self, version_file_path="application/version.json"):
        """
        Get version information from the repository.
        
        Args:
            version_file_path (str): Path to the version file in the repository
        
        Returns:
            dict: Version information or None if error
        """
        url = f"{self.api_base}/repos/{self.owner}/{self.repo}/contents/{version_file_path}?ref={self.branch}"
        
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            content_data = response.json()
            content = base64.b64decode(content_data["content"]).decode('utf-8')
            
            return json.loads(content)
        
        except requests.RequestException as e:
            logger.error(f"Error fetching version info: {e}")
            return None