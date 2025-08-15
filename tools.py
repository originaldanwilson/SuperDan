#!/usr/bin/env python3
"""
Credentials file for Cisco Network Device Authentication

This file contains the credentials used for authenticating with Cisco network devices.
The variables in this file are imported by other scripts that need to connect to network devices.

Warning: Keep this file secure and do not share it or commit it to version control systems.
"""

# Network device authentication credentials
netmikoUser = "admin"       # Username for device login
passwd = "cisco123"         # Password for device login
enable = "cisco123"         # Enable secret for privileged mode access

#!/usr/bin/env python3
"""
getCreds.py - Module for providing network device credentials.
This module provides functions to retrieve credentials for Netmiko connections.
"""


def get_credentials():
    """
    Return the username and password for Netmiko connections.
    
    Returns:
        tuple: A tuple containing (username, password)
    """
    # In a production environment, these credentials should be stored securely
    # Options include environment variables, secure vaults, or encrypted files
    netmikoUser = "admin"  # Replace with actual username
    netmikoPassword = "password123"  # Replace with actual password
    
    return netmikoUser, netmikoPassword


def get_netmiko_creds():
    """
    Get netmiko credentials including enable secret.
    
    Returns:
        tuple: A tuple containing (username, password, enable_secret)
    """
    # Use the global variables defined at the top of the file
    global netmikoUser, passwd, enable
    return netmikoUser, passwd, enable


def get_netmiko_device_config(hostname, device_type="cisco_ios", timeout_multiplier=3):
    """
    Get Netmiko device configuration with extended timeouts for large transfers.
    
    Args:
        hostname (str): Target device hostname or IP
        device_type (str): Netmiko device type
        timeout_multiplier (int): Multiplier for default timeouts
    
    Returns:
        dict: Device configuration dictionary
    """
    username, password = get_netmiko_creds()
    
    # Base timeout values (in seconds)
    base_timeout = 60 * timeout_multiplier  # Default: 180 seconds
    
    device_config = {
        'device_type': device_type,
        'host': hostname,
        'username': username,
        'password': password,
        'timeout': base_timeout,
        'session_timeout': base_timeout * 2,  # Even longer for session
        'auth_timeout': base_timeout,
        'banner_timeout': 30,
        'blocking_timeout': base_timeout,
        'conn_timeout': 30,
        'keepalive': 30,  # Send keepalive every 30 seconds
        'global_delay_factor': 2,  # Slow down command execution
        'fast_cli': False,  # Disable fast CLI for stability
    }
    
    return device_config


import logging
import os
import sys
from datetime import datetime


def getScriptName():
    """
    Get the name of the current script without path and extension.
    
    Returns:
        str: Script name without path and .py extension
    """
    script_path = os.path.basename(sys.argv[0])
    script_name = os.path.splitext(script_path)[0]
    return script_name


def setupLogging(log_level=logging.INFO, log_file=None):
    """
    Set up logging configuration with both console and file output.
    
    Args:
        log_level: Logging level (default: INFO)
        log_file: Optional log file name. If None, uses script name with timestamp
    
    Returns:
        logger: Configured logger instance
    """
    if log_file is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = f"{getScriptName()}_{timestamp}.log"
    
    # Create logs directory if it doesn't exist
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    log_path = os.path.join(log_dir, log_file)
    
    # Configure logging
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
        handlers=[
            logging.FileHandler(log_path, mode='w'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized. Log file: {log_path}")
    return logger


if __name__ == "__main__":
    # Simple test if this file is run directly
    username, password = get_credentials()
    print(f"Username: {username}")
    print(f"Password: {password} (This is just for testing, don't print passwords in production!)")
    
    # Test logging functions
    script_name = getScriptName()
    print(f"Script name: {script_name}")
    
    logger = setupLogging()
    logger.info("Test logging message")

