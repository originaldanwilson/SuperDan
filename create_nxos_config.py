#!/usr/bin/env python3
"""
NX-OS Configuration File Creator

This script converts IOS-style commands to NX-OS format and creates a proper
NX-OS configuration file for use with the NX-OS Configuration Manager.

The script reads the existing testconfig1c.txt and converts it to NX-OS syntax.
"""

import re


def convert_ios_to_nxos(ios_commands):
    """
    Convert IOS commands to NX-OS equivalents.
    
    Args:
        ios_commands: List of IOS commands
        
    Returns:
        List of NX-OS commands
    """
    nxos_commands = []
    
    for command in ios_commands:
        command = command.strip()
        if not command:
            continue
            
        # Convert common IOS to NX-OS mappings
        if command.lower().startswith('vlan '):
            nxos_commands.append(command)
            
        elif command.lower().startswith('name '):
            nxos_commands.append(f"  {command}")
            
        elif command.lower().startswith('interface port-channel'):
            # Convert Port-channel to port-channel (lowercase)
            nxos_commands.append(command.lower())
            
        elif command.lower().startswith('interface range'):
            # Convert range syntax - NX-OS uses different syntax
            # IOS: interface range T1/1/1 , T1/1/8
            # NX-OS: interface ethernet1/1-8 (if consecutive)
            range_match = re.search(r'interface range\s+(\S+)\s*,\s*(\S+)', command, re.IGNORECASE)
            if range_match:
                # For now, convert to individual interfaces
                start_int = range_match.group(1)
                end_int = range_match.group(2)
                nxos_commands.append(f"interface {start_int}")
            else:
                nxos_commands.append(command)
                
        elif command.lower().startswith('interface gigabitethernet'):
            # Convert GigabitEthernet to Ethernet
            # IOS: interface GigabitEthernet1/0/1
            # NX-OS: interface Ethernet1/1
            gig_match = re.search(r'interface gigabitethernet(\d+)/0/(\d+)', command, re.IGNORECASE)
            if gig_match:
                slot = gig_match.group(1)
                port = gig_match.group(2)
                nxos_commands.append(f"interface Ethernet{slot}/{port}")
            else:
                nxos_commands.append(command)
                
        elif command.lower().startswith('interface t1/'):
            # Convert TenGigabit interfaces
            # IOS: interface T1/1/1
            # NX-OS: interface Ethernet1/1
            ten_match = re.search(r'interface t(\d+)/\d+/(\d+)', command, re.IGNORECASE)
            if ten_match:
                slot = ten_match.group(1)
                port = ten_match.group(2)
                nxos_commands.append(f"interface Ethernet{slot}/{port}")
            else:
                nxos_commands.append(command)
                
        elif command.lower().startswith('interface vlan'):
            nxos_commands.append(command)
            
        elif command.lower() == 'switchport trunk encapsulation dot1q':
            # NX-OS doesn't need trunk encapsulation command
            nxos_commands.append("! Trunk encapsulation not needed in NX-OS")
            
        elif command.lower().startswith('switchport'):
            nxos_commands.append(f"  {command}")
            
        elif command.lower().startswith('channel-group'):
            nxos_commands.append(f"  {command}")
            
        elif command.lower().startswith('spanning-tree portfast'):
            # NX-OS uses different spanning-tree syntax
            nxos_commands.append("  spanning-tree port type edge")
            
        elif command.lower().startswith('description'):
            nxos_commands.append(f"  {command}")
            
        elif command.lower().startswith('ip address'):
            nxos_commands.append(f"  {command}")
            
        elif command.lower() == 'no shutdown':
            nxos_commands.append("  no shutdown")
            
        elif command.lower() == 'exit':
            nxos_commands.append(command)
            
        else:
            # Keep other commands as-is
            nxos_commands.append(command)
    
    return nxos_commands


def create_nxos_config_file():
    """
    Create a proper NX-OS configuration file.
    """
    
    # Read existing IOS config
    try:
        with open('testconfig1c.txt', 'r') as f:
            ios_commands = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print("testconfig1c.txt not found. Creating sample NX-OS configuration.")
        ios_commands = []
    
    # Convert to NX-OS if we have IOS commands
    if ios_commands:
        nxos_commands = convert_ios_to_nxos(ios_commands)
    else:
        # Create sample NX-OS configuration
        nxos_commands = [
            "! Sample NX-OS Configuration",
            "vlan 10",
            "  name User_Data",
            "vlan 110", 
            "  name Voice",
            "vlan 243",
            "  name Native_VLAN",
            "",
            "interface port-channel1",
            "  description Uplink_to_Core",
            "  switchport mode trunk",
            "  switchport trunk native vlan 243",
            "  switchport trunk allowed vlan 10,110",
            "",
            "interface Ethernet1/1",
            "  channel-group 1 mode active",
            "  no shutdown",
            "",
            "interface Ethernet1/8", 
            "  channel-group 1 mode active",
            "  no shutdown",
            "",
            "interface Vlan10",
            "  ip address 192.168.10.1/24",
            "  no shutdown",
            "",
            "interface Ethernet1/10",
            "  description Access Port",
            "  switchport mode access",
            "  switchport access vlan 10",
            "  spanning-tree port type edge",
            "  no shutdown",
            "",
            "interface Ethernet1/11",
            "  description Access Port with Voice",
            "  switchport mode access", 
            "  switchport access vlan 10",
            "  switchport voice vlan 110",
            "  spanning-tree port type edge",
            "  no shutdown",
            "",
            "interface Ethernet1/12",
            "  description Trunk Port",
            "  switchport mode trunk",
            "  switchport trunk allowed vlan 10,110",
            "  no shutdown"
        ]
    
    # Write NX-OS configuration file
    nxos_filename = 'nxos_config.txt'
    with open(nxos_filename, 'w') as f:
        for command in nxos_commands:
            f.write(command + '\n')
    
    print(f"Created NX-OS configuration file: {nxos_filename}")
    print(f"Total commands: {len(nxos_commands)}")
    
    return nxos_filename


if __name__ == "__main__":
    create_nxos_config_file()
