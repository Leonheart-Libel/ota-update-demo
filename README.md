# Over-The-Air Application Updater
This is a project that i developed as part of my undergraduate thesis.

It is an Over-The-Air Update Mechanism/System, specifically designed to update a python application. In this case i also developed a weather application generating dummy data in the form of weather sensor data metrics. This app will also send the generated data to an Azure SQL Database with additional device details like what version of the app is running on each devices that is implemented. Here is the database diagram to give a rough idea
<img width="3840" height="3286" alt="Database Diagram" src="https://github.com/user-attachments/assets/71c17ede-1323-439c-9c33-75c8294d387e" />

The system is designed to run in a Raspberry Pi 4 device, using Github as the Code Server/Code Manager. Below is the sequence diagram of the system to give an understanding of how it works
<img width="2259" height="3840" alt="Untitled diagram _ Mermaid Chart-2025-07-14-100745" src="https://github.com/user-attachments/assets/c9858599-1df8-4369-ae0b-c031691a224c" />

This system is pull-based, using HTTP polling mechanisms to get the data in the Github repository as opposed to other widely available OTA update systems that uses an MQTT Broker/Trigger that uses a push-based approach.

The system has multiple features like Version rollback, Version History and Backup, Unique Device ID Generation (To make each device have a globally unique name), and Graceful Shutdown (through SIGTERM and SIGINT).
___
Services SETUP
Github Repository
The repo you will be using in the implementation could be set to private or public, as long as what the system needs that is the Personal Access Tokens (PAT) are generated. This is what it will use to authenticate to the Github API.

To make the system work this is how the repository folder structure should look like
<img width="462" height="389" alt="Direktori Sistem" src="https://github.com/user-attachments/assets/6826f31b-cada-46dd-b6e1-c10a002a1e2c" />


Azure SQL Database
Setup the database using SQL Authentication, the rest of the settings are up to you. When the database is made you will need to add the ip address to the Inbound Firewall at the Database Server where the database is made to make it possible to connect to it.

The authentication details of both the Github Repo and Azure SQL Database will be put on the config.json file of the system.
___
System SETUP Raspberry Pi 4
Here is the set of instructions that is needed to set up the system in the raspberry pi 4 device through the terminal

1.	Update Device
sudo apt update
sudo apt upgrade -y
2.	Install system packages
sudo apt install -y git python3-pip python3-dev unixodbc unixodbc-dev freetds-dev freetds-bin tdsodbc
3.	Setup FreeTDS & ODBC
sudo nano /etc/freetds/freetds.conf

“””
[iotcentralhub]
host = databasename.database.windows.net
port = 1433
tds version = 8.0
“””

sudo nano /etc/odbcinst.ini

“””
[FreeTDS]
Description = FreeTDS Driver
Driver = /usr/lib/aarch64-linux-gnu/odbc/libtdsodbc.so
Setup = /usr/lib/arm-linux-gnueabihf/odbc/libtdsS.so
FileUsage = 1
“””

#Testing SQL Connection
tsql -S databaseservername -U sqlusername -P sqlpassword


4.	Clone Repository
git clone https://github.com/yourrepository
cd ota-update-demo

6.	Install requirements.txt using python VENV
sudo apt install python3-venv
python3 -m venv myenv
source myenv/bin/activate
pip install -r requirements.txt

7.	Configure Config.json file for credentials
{
    "github_token": "Your Github PAT",
    "repo_owner": "Repo Owner Name",
    "repo_name": "REPO NAME",
    "app_dir": "application",
    "versions_dir": "versions",
    "max_versions": 5, #Configurable
    "check_interval": 60, #Configurable
    "azure_sql": {
        "server": "databaseservername.database.windows.net",
        "database": "DATABASE NAME",
        "username": "SQL AUTHENTICATION USERNAME",
        "password": "SQL AUTHENTICATION PASSWORD",
        "trust_server_cert": "no"
    }
}
8.	Start Service
•	Start the system
python3 start_services.py
___

start_services.py is the service manager. It will start the OTA updater, and in turn the OTA updater will run the application as a subprocess. You can monitor the system through the logs.

tail -f  /service.log
tail -f application/app.log
tail -f ota_service/ota.log



Note: As the system is modular in architecture, the application component in this system is naturally replaceable. The only requirement is that the application needs to be in python. You would also of course need to adjust the database side of things to make it work to whatever application you decide to implement it with.




