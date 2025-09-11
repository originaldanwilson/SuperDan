#!/usr/bin/env python3
"""
Device Configuration for Pre/Post Check Scripts

This module contains the configuration for devices and commands to be executed
during pre-check and post-check operations.

Modify the DEVICES and COMMANDS lists as needed for your specific environment.
"""

# List of devices to check (hostnames or IP addresses)
DEVICES = [
    "nxos-switch-01",
    "nxos-switch-02", 
    "nxos-switch-03",
    "nxos-switch-04",
    "nxos-switch-05",
    # Add more devices as needed (up to 12)
    # "nxos-switch-06",
    # "nxos-switch-07",
    # "nxos-switch-08",
    # "nxos-switch-09",
    # "nxos-switch-10",
    # "nxos-switch-11",
    # "nxos-switch-12",
]

# Commands to execute on each device
COMMANDS = [
    "show version",
    "show inventory", 
    "show interface status",
    "show ip route summary",
    "show logging last 100",
    # Add more commands as needed (up to 7 total)
    # "show spanning-tree summary",
    # "show vpc",
]

# Device type for Netmiko (Cisco NX-OS)
DEVICE_TYPE = "cisco_nxos"

# Connection timeout settings
CONNECTION_TIMEOUT = 120
COMMAND_TIMEOUT = 60

# Output settings
OUTPUT_DIRECTORY = "check_results"
MAX_RETRIES = 2
