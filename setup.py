#!/usr/bin/env python3
"""Auto-setup script with dependency installation"""
import os
import shutil
import subprocess

def install_dependencies():
    print("Installing system and Python dependencies...")
    
    # Install system packages (for pymssql)
    subprocess.run([
        "sudo", "apt-get", "update"
    ], check=True)
    
    subprocess.run([
        "sudo", "apt-get", "install", "-y", 
        "freetds-dev", "libsybdb5"
    ], check=True)

    # Install Python packages
    subprocess.run([
        "pip3", "install", "-r", "requirements.txt"
    ], check=True)

def setup_project():
    print("Running automatic project setup...")
    
    # Install dependencies FIRST
    install_dependencies()
    
    # Create essential files if missing
    if not os.path.exists("config.json"):
        with open("config.json", "w") as f:
            f.write("""{
    "github_token": "YOUR_TOKEN_HERE",
    "repo_owner": "your_username",
    "repo_name": "your_repo",
    "app_dir": "application",
    "check_interval": 300
}""")

    # Copy sample config if needed
    if not os.path.exists("application/app_config.py"):
        shutil.copy("app_config.py", "application/app_config.py")

    print("Setup completed. Please configure config.json before running services.")

if __name__ == "__main__":
    setup_project()