#!/usr/bin/env python3
"""
Multi-Device Configuration Setup Helper

This script helps you set up the multi-device NX-OS configuration environment
by creating sample configuration files and device mappings.

Usage:
    python3 setup_multi_device_config.py
"""

import os


def create_sample_config_files():
    """
    Create sample configuration files for 10 switches.
    """
    
    # Base configuration template
    base_config_template = """! Configuration for {switch_name}
! IP: {ip_address}

hostname {switch_name}
clock timezone EST -5 0
ip domain-name example.com

! Enable features
feature bgp
feature ospf
feature interface-vlan
feature lacp
feature vpc
feature lldp

! VLAN configuration
vlan {data_vlan}
  name DATA_VLAN_{switch_num}
  state active

vlan {voice_vlan}
  name VOICE_VLAN_{switch_num}
  state active

vlan {mgmt_vlan}
  name MGMT_VLAN_{switch_num}
  state active

! VRF configuration (if applicable)
{vrf_config}

! Interface configurations
interface mgmt0
  description Management Interface
  ip address {mgmt_ip}/24
  vrf member management
  no shutdown

interface Ethernet1/1
  description Uplink to Core
  switchport mode trunk
  switchport trunk allowed vlan {data_vlan},{voice_vlan}
  switchport trunk native vlan 999
  no shutdown

interface Ethernet1/2
  description Uplink to Core - Backup
  switchport mode trunk
  switchport trunk allowed vlan {data_vlan},{voice_vlan}
  switchport trunk native vlan 999
  no shutdown

! Access port configurations
{access_ports}

! SVI configurations
interface Vlan{data_vlan}
  description Data VLAN SVI
  ip address {data_svi_ip}/24
  no shutdown

interface Vlan{voice_vlan}
  description Voice VLAN SVI
  ip address {voice_svi_ip}/24
  no shutdown

! Routing configuration
{routing_config}

! Global settings
spanning-tree mode rapid-pvst
spanning-tree vlan {data_vlan} priority {stp_priority}
spanning-tree vlan {voice_vlan} priority {stp_priority}

! Logging
logging server 192.168.1.200 6
logging timestamp microseconds

! SNMP
snmp-server community public ro
snmp-server location "Switch {switch_num} Location"
snmp-server contact "Network Team"

! NTP
ntp server 192.168.1.10 prefer
ntp server 192.168.1.11

! End of configuration
"""

    # Create configurations for 10 switches
    devices = []
    
    for i in range(1, 11):
        switch_name = f"NXOS-SW{i:02d}"
        ip_address = f"192.168.1.{9+i}"
        mgmt_ip = f"192.168.100.{9+i}"
        
        # Different VLANs per switch
        data_vlan = 10 + (i-1) * 10  # 10, 20, 30, ..., 100
        voice_vlan = data_vlan + 5   # 15, 25, 35, ..., 105
        mgmt_vlan = 200 + i          # 201, 202, 203, ..., 210
        
        # Different IP ranges per switch
        data_svi_ip = f"10.{i}.10.1"
        voice_svi_ip = f"10.{i}.15.1"
        
        # STP priority (some switches are primary, others secondary)
        stp_priority = 4096 if i <= 5 else 8192
        
        # VRF configuration for some switches
        if i <= 3:
            vrf_config = f"""vrf context PROD_{i}
  rd 65001:{100+i}
  address-family ipv4 unicast
    route-target import 65001:{100+i}
    route-target export 65001:{100+i}"""
        else:
            vrf_config = "! No VRF configuration for this switch"
        
        # Access ports configuration (different per switch)
        access_ports = ""
        port_start = 10 + (i-1) * 5  # Different starting ports per switch
        for j in range(port_start, port_start + 5):
            access_ports += f"""
interface Ethernet1/{j}
  description Access Port {j}
  switchport mode access
  switchport access vlan {data_vlan}
  switchport voice vlan {voice_vlan}
  spanning-tree port type edge
  no shutdown"""
        
        # Routing configuration (OSPF for some, BGP for others)
        if i <= 5:
            routing_config = f"""router ospf UNDERLAY_{i}
  router-id {data_svi_ip}
  area 0.0.0.{i} authentication message-digest"""
        else:
            routing_config = f"""router bgp 6500{i}
  router-id {data_svi_ip}
  bestpath as-path multipath-relax
  address-family ipv4 unicast
    maximum-paths 4"""
        
        # Format the configuration
        config_content = base_config_template.format(
            switch_name=switch_name,
            switch_num=i,
            ip_address=ip_address,
            mgmt_ip=mgmt_ip,
            data_vlan=data_vlan,
            voice_vlan=voice_vlan,
            mgmt_vlan=mgmt_vlan,
            data_svi_ip=data_svi_ip,
            voice_svi_ip=voice_svi_ip,
            stp_priority=stp_priority,
            vrf_config=vrf_config,
            access_ports=access_ports,
            routing_config=routing_config
        )
        
        # Write configuration file
        config_filename = f"switch{i:02d}_config.txt"
        with open(config_filename, 'w') as f:
            f.write(config_content)
        
        print(f"Created {config_filename} for {switch_name} ({ip_address})")
        
        # Add to devices list for mapping
        devices.append({
            'ip': ip_address,
            'hostname': switch_name,
            'config_file': config_filename
        })
    
    return devices


def create_device_mapping_script(devices):
    """
    Create a Python script with the device mapping.
    """
    
    mapping_script = '''#!/usr/bin/env python3
"""
Multi-Device NX-OS Configuration Script

This script configures 10 NX-OS switches with their individual configuration files.
Each switch has its own specific configuration tailored to its role and location.

Generated automatically by setup_multi_device_config.py
"""

from nxos_multi_device_manager import MultiDeviceNXOSConfigManager


def main():
    """
    Configure all 10 NX-OS switches with their individual configurations.
    """
    print("Multi-Device NX-OS Configuration Manager")
    print("=" * 50)
    print("Configuring 10 switches with individual config files...")
    print()
    
    # Device to configuration file mapping
    device_config_mapping = {
'''
    
    # Add device mappings
    for device in devices:
        mapping_script += f'        "{device["ip"]}": "{device["config_file"]}",  # {device["hostname"]}\n'
    
    mapping_script += '''    }
    
    try:
        print("Device Configuration Mapping:")
        for device_ip, config_file in device_config_mapping.items():
            print(f"  {device_ip} -> {config_file}")
        print()
        
        # Initialize multi-device configuration manager
        manager = MultiDeviceNXOSConfigManager(device_config_mapping)
        
        # Process all devices
        manager.process_all_devices()
        
        # Generate comprehensive report
        report_file = manager.generate_comprehensive_report()
        
        # Print summary
        manager.print_comprehensive_summary()
        
        print(f"Multi-device configuration complete!")
        print(f"Detailed report saved to: {report_file}")
        print(f"Log files stored in 'logs' directory")
        
    except KeyboardInterrupt:
        print("\\nOperation interrupted by user")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
'''
    
    with open('configure_all_switches.py', 'w') as f:
        f.write(mapping_script)
    
    print(f"\nCreated configure_all_switches.py with device mappings")


def create_inventory_file(devices):
    """
    Create an inventory file for reference.
    """
    
    inventory_content = """# NX-OS Switch Inventory
# Generated automatically by setup_multi_device_config.py

Device IP       | Hostname      | Config File           | Management IP    | Data VLAN | Voice VLAN
----------------|---------------|----------------------|------------------|-----------|------------
"""
    
    for i, device in enumerate(devices, 1):
        mgmt_ip = f"192.168.100.{9+i}"
        data_vlan = 10 + (i-1) * 10
        voice_vlan = data_vlan + 5
        
        inventory_content += f"{device['ip']:<15} | {device['hostname']:<13} | {device['config_file']:<20} | {mgmt_ip:<15} | {data_vlan:<9} | {voice_vlan}\n"
    
    with open('switch_inventory.txt', 'w') as f:
        f.write(inventory_content)
    
    print("Created switch_inventory.txt for reference")


def main():
    """
    Main setup function.
    """
    print("Multi-Device NX-OS Configuration Setup")
    print("=" * 40)
    print()
    
    print("Creating sample configuration files for 10 switches...")
    devices = create_sample_config_files()
    print()
    
    print("Creating device mapping script...")
    create_device_mapping_script(devices)
    print()
    
    print("Creating inventory file...")
    create_inventory_file(devices)
    print()
    
    print("Setup complete!")
    print()
    print("Files created:")
    print("• switch01_config.txt through switch10_config.txt - Individual switch configurations")
    print("• configure_all_switches.py - Main script to configure all switches")
    print("• switch_inventory.txt - Device inventory for reference")
    print()
    print("Next steps:")
    print("1. Update credentials in tools.py")
    print("2. Modify device IP addresses in configure_all_switches.py if needed")
    print("3. Customize individual switch config files as needed")
    print("4. Run: python3 configure_all_switches.py")


if __name__ == "__main__":
    main()
