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


def get_ad_creds():
    """
    Get Active Directory credentials for SolarWinds authentication.
    
    Returns:
        tuple: A tuple containing (username, password)
    """
    # Replace these with your actual SolarWinds credentials
    import getpass
    print("Enter SolarWinds credentials:")
    username = input("Username: ")
    password = getpass.getpass("Password: ")
    return username, password


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
import stat
import pathlib
from datetime import datetime

# Optional screenshot support
try:
    import mss
    import mss.tools
except ImportError:
    mss = None


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


def setupLoggingNew(log_level=logging.INFO, log_file=None):
    """
    New logging setup function for corporate compatibility.
    Same as setupLogging but with different name to avoid conflicts.
    
    Args:
        log_level: Logging level (default: INFO)
        log_file: Optional log file name. If None, uses script name with timestamp
    
    Returns:
        logger: Configured logger instance
    """
    return setupLogging(log_level, log_file)


def set_file_permissions(file_path, permissions=0o777):
    """
    Set file permissions for a given file.
    
    Args:
        file_path (str): Path to the file
        permissions (int): Octal permissions (default: 0o777 for full access)
    
    Returns:
        bool: True if successful, False otherwise
    
    Example:
        set_file_permissions("myfile.xlsx", 0o777)
        set_file_permissions("myfile.xlsx", 0o644)  # rw-r--r--
    """
    try:
        os.chmod(file_path, permissions)
        return True
    except (OSError, IOError) as e:
        print(f"Error setting permissions for {file_path}: {e}")
        return False
    except FileNotFoundError:
        print(f"File not found: {file_path}")
        return False


def get_file_permissions_string(file_path):
    """
    Get file permissions as a human-readable string (like ls -l output).
    
    Args:
        file_path (str): Path to the file
    
    Returns:
        str: Permission string (e.g., 'rwxrwxrwx') or None if error
    """
    try:
        file_stat = os.stat(file_path)
        mode = file_stat.st_mode
        
        # Convert to permission string
        perms = stat.filemode(mode)
        return perms[1:]  # Remove the first character (file type indicator)
    except (OSError, IOError, FileNotFoundError) as e:
        print(f"Error getting permissions for {file_path}: {e}")
        return None


def get_file_permissions_octal(file_path):
    """
    Get file permissions as an octal string.
    
    Args:
        file_path (str): Path to the file
    
    Returns:
        str: Octal permission string (e.g., '755') or None if error
    """
    try:
        file_stat = os.stat(file_path)
        mode = file_stat.st_mode
        
        # Get the last 3 octal digits (permission bits)
        octal_perms = oct(stat.S_IMODE(mode))[2:]
        return octal_perms
    except (OSError, IOError, FileNotFoundError) as e:
        print(f"Error getting permissions for {file_path}: {e}")
        return None


def print_file_with_permissions(file_path, show_size=True, show_timestamp=True):
    """
    Print file information including permissions (similar to ls -l).
    
    Args:
        file_path (str): Path to the file
        show_size (bool): Whether to show file size
        show_timestamp (bool): Whether to show modification timestamp
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        if not os.path.exists(file_path):
            print(f"File not found: {file_path}")
            return False
        
        file_stat = os.stat(file_path)
        
        # Get permission string
        perms = stat.filemode(file_stat.st_mode)
        
        # Get octal permissions
        octal_perms = oct(stat.S_IMODE(file_stat.st_mode))[2:]
        
        # Prepare output components
        components = [perms]
        
        if show_size:
            # Format file size
            size = file_stat.st_size
            if size < 1024:
                size_str = f"{size}B"
            elif size < 1024 * 1024:
                size_str = f"{size / 1024:.1f}KB"
            elif size < 1024 * 1024 * 1024:
                size_str = f"{size / (1024 * 1024):.1f}MB"
            else:
                size_str = f"{size / (1024 * 1024 * 1024):.1f}GB"
            components.append(f"{size_str:>8}")
        
        if show_timestamp:
            # Format modification time
            mod_time = datetime.datetime.fromtimestamp(file_stat.st_mtime)
            time_str = mod_time.strftime("%b %d %H:%M")
            components.append(time_str)
        
        # Add octal permissions in parentheses
        components.append(f"({octal_perms})")
        
        # Add filename
        components.append(os.path.basename(file_path))
        
        # Print the formatted line
        print(" ".join(components))
        return True
        
    except (OSError, IOError) as e:
        print(f"Error accessing {file_path}: {e}")
        return False


def save_file_and_set_permissions(file_path, permissions=0o777, show_info=True):
    """
    Convenience function to set permissions on a file and optionally display the result.
    Useful for Excel files and other saved files.
    
    Args:
        file_path (str): Path to the file
        permissions (int): Octal permissions (default: 0o777)
        show_info (bool): Whether to print file info after setting permissions
    
    Returns:
        bool: True if successful, False otherwise
    
    Example:
        # After saving an Excel file
        save_file_and_set_permissions("report.xlsx")
        save_file_and_set_permissions("report.xlsx", 0o644, show_info=True)
    """
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return False
    
    # Set permissions
    success = set_file_permissions(file_path, permissions)
    
    if success and show_info:
        print(f"File saved with permissions:")
        print_file_with_permissions(file_path)
    elif success:
        print(f"Permissions set successfully for {file_path}")
    
    return success


def take_screenshot(filename: str = None, directory: str = ".", monitor: int = 1) -> str:
    """
    Take a screenshot of the specified monitor.
    
    Args:
        filename: Base filename (without extension). If None, uses timestamp
        directory: Directory to save screenshot (default: current directory)
        monitor: Monitor number to capture (1 = primary, 2 = secondary, etc.)
        
    Returns:
        str: Full path to the saved screenshot file
        
    Raises:
        ImportError: If mss library is not installed
    """
    if mss is None:
        raise ImportError("mss isn't defined. Run: pip install mss")
    
    directory = pathlib.Path(directory).expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=True)
    
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_{timestamp}"
    
    out_path = directory / f"{filename}.png"
    
    with mss.mss() as sct:
        mon = sct.monitors[monitor]
        img = sct.grab(mon)
        mss.tools.to_png(img.rgb, img.size, output=str(out_path))
    
    return str(out_path)


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

