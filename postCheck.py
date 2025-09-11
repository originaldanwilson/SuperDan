#!/usr/bin/env python3
"""
postCheck.py - Simple post-check tool for Cisco NX-OS devices
Quick and dirty script to capture device state after changes
"""

import os
from datetime import datetime
from netmiko import ConnectHandler
from tools import get_netmiko_creds, setupLoggingNew, getScriptName

# Configure your devices and commands here
DEVICES = [
    "nxos-switch-01",
    "nxos-switch-02", 
    "nxos-switch-03",
    "nxos-switch-04",
    "nxos-switch-05",
]

COMMANDS = [
    "show version",
    "show inventory", 
    "show interface status",
    "show ip route summary",
    "show logging last 100",
]

def main():
    logger = setupLoggingNew()
    username, password, enable_secret = get_netmiko_creds()
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = f"postcheck_{timestamp}"
    os.makedirs(output_dir, exist_ok=True)
    
    device_config = {
        'device_type': 'cisco_nxos',
        'username': username,
        'password': password,
        'secret': enable_secret,
        'timeout': 60,
        'fast_cli': False,
    }
    
    for device in DEVICES:
        logger.info(f"Connecting to {device}")
        device_config['host'] = device
        
        try:
            with ConnectHandler(**device_config) as conn:
                conn.enable()
                
                for command in COMMANDS:
                    logger.info(f"Running '{command}' on {device}")
                    output = conn.send_command(command, read_timeout=90)
                    
                    # Save to file
                    safe_command = command.replace(" ", "_").replace("/", "_")
                    filename = f"{device}_{safe_command}.txt"
                    filepath = os.path.join(output_dir, filename)
                    
                    with open(filepath, 'w') as f:
                        f.write(f"Device: {device}\n")
                        f.write(f"Command: {command}\n")
                        f.write(f"Timestamp: {datetime.now()}\n")
                        f.write("=" * 60 + "\n")
                        f.write(output)
                        f.write("\n" + "=" * 60 + "\n")
                    
                    logger.info(f"Saved: {filepath}")
        
        except Exception as e:
            logger.error(f"Failed on {device}: {e}")
            continue
    
    logger.info(f"Post-check complete. Files saved in: {output_dir}")
    print(f"\nPost-check complete. Files saved in: {output_dir}")

if __name__ == "__main__":
    main()
