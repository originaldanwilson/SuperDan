#!/usr/bin/env python3
"""
Multi-Device NX-OS Configuration Manager

This script connects to multiple Cisco NX-OS switches using netmiko, where each
switch has its own individual configuration file. Handles ALL types of
configuration commands (not just interfaces), with comprehensive error handling
and detailed spreadsheet reporting.

Features:
- Supports individual configuration files per device
- Handles ALL configuration sections (VLANs, VRFs, routing, ACLs, etc.)
- Section-specific error handling with skip capability
- Before/after configuration comparison for all sections
- Comprehensive logging and Excel reporting
- Device mapping from IP addresses to configuration files

Author: Multi-Device Network Automation Script
"""

import os
import sys
import re
import logging
import traceback
from datetime import datetime
from typing import List, Dict, Tuple, Optional, Union
import json

# Third-party imports
try:
    from netmiko import ConnectHandler
    from netmiko.exceptions import NetmikoTimeoutException, NetmikoAuthenticationException
except ImportError:
    print("Error: netmiko library not found. Install with: pip install netmiko")
    sys.exit(1)

try:
    import pandas as pd
except ImportError:
    print("Error: pandas library not found. Install with: pip install pandas openpyxl")
    sys.exit(1)

# Local imports
from tools import getScriptName, setupLogging, get_netmiko_creds


class MultiDeviceNXOSConfigManager:
    """
    Multi-Device NX-OS Configuration Manager that handles individual config files per device.
    """
    
    # Define configuration section types and their characteristics
    CONFIG_SECTIONS = {
        # Hierarchical sections (require 'exit' command)
        'interface': {
            'pattern': r'^interface\s+(.+)$',
            'hierarchical': True,
            'show_command': 'show running-config interface {}',
            'status_command': 'show interface {} status'
        },
        'vlan': {
            'pattern': r'^vlan\s+(.+)$',
            'hierarchical': True,
            'show_command': 'show running-config vlan {}',
            'status_command': 'show vlan id {}'
        },
        'vrf': {
            'pattern': r'^vrf\s+context\s+(.+)$',
            'hierarchical': True,
            'show_command': 'show running-config vrf {}',
            'status_command': 'show vrf {}'
        },
        'router': {
            'pattern': r'^router\s+(\w+)(?:\s+(.+))?$',
            'hierarchical': True,
            'show_command': 'show running-config router {}',
            'status_command': 'show ip route summary'
        },
        'route-map': {
            'pattern': r'^route-map\s+(.+?)(?:\s+permit\s+\d+|\s+deny\s+\d+)?$',
            'hierarchical': True,
            'show_command': 'show running-config route-map {}',
            'status_command': 'show route-map {}'
        },
        'ip access-list': {
            'pattern': r'^ip\s+access-list\s+(.+)$',
            'hierarchical': True,
            'show_command': 'show running-config access-list {}',
            'status_command': 'show access-lists {}'
        },
        'class-map': {
            'pattern': r'^class-map\s+(.+)$',
            'hierarchical': True,
            'show_command': 'show running-config class-map {}',
            'status_command': 'show class-map {}'
        },
        'policy-map': {
            'pattern': r'^policy-map\s+(.+)$',
            'hierarchical': True,
            'show_command': 'show running-config policy-map {}',
            'status_command': 'show policy-map {}'
        },
        'vpc': {
            'pattern': r'^vpc\s+domain\s+(\d+)$',
            'hierarchical': True,
            'show_command': 'show running-config vpc',
            'status_command': 'show vpc'
        },
        'port-channel': {
            'pattern': r'^port-channel\s+load-balance',
            'hierarchical': False,
            'show_command': 'show running-config | include port-channel',
            'status_command': 'show port-channel summary'
        },
        # Global/non-hierarchical sections
        'global': {
            'pattern': None,  # Catch-all for non-matching commands
            'hierarchical': False,
            'show_command': 'show running-config | include {}',
            'status_command': None
        }
    }
    
    def __init__(self, device_config_mapping: Dict[str, str]):
        """
        Initialize the Multi-Device NX-OS Configuration Manager.
        
        Args:
            device_config_mapping: Dictionary mapping device IPs to their config files
                                  Example: {
                                      "192.168.1.10": "switch01_config.txt",
                                      "192.168.1.11": "switch02_config.txt",
                                      ...
                                  }
        """
        self.device_config_mapping = device_config_mapping
        self.logger = setupLogging()
        
        # Get credentials
        netmikoUser, passwd, enable = get_netmiko_creds()
        self.username = netmikoUser
        self.password = passwd
        
        # Configuration tracking
        self.results = []
        self.failed_devices = []
        self.section_results = []
        self.device_configs = {}  # Store loaded configs per device
        
        # Load all configuration files
        self._load_all_device_configs()
        
        self.logger.info(f"Initialized Multi-Device NXOSConfigManager for {len(device_config_mapping)} devices")

    def _load_all_device_configs(self) -> None:
        """
        Load configuration commands for all devices from their respective files.
        """
        for device_ip, config_file in self.device_config_mapping.items():
            try:
                with open(config_file, 'r') as f:
                    commands = [line.strip() for line in f if line.strip() and not line.strip().startswith('!')]
                
                self.device_configs[device_ip] = {
                    'config_file': config_file,
                    'commands': commands,
                    'sections': self._parse_configuration_sections(commands)
                }
                
                self.logger.info(f"Loaded {len(commands)} commands from {config_file} for device {device_ip}")
                
            except FileNotFoundError:
                self.logger.error(f"Configuration file not found for device {device_ip}: {config_file}")
                self.failed_devices.append({
                    'device': device_ip,
                    'error': f'Configuration file not found: {config_file}',
                    'timestamp': datetime.now().isoformat()
                })
            except Exception as e:
                self.logger.error(f"Error loading configuration file {config_file} for device {device_ip}: {str(e)}")
                self.failed_devices.append({
                    'device': device_ip,
                    'error': f'Error loading config file: {str(e)}',
                    'timestamp': datetime.now().isoformat()
                })

    def _connect_to_device(self, device_ip: str) -> Optional[ConnectHandler]:
        """
        Establish connection to NX-OS device.
        
        Args:
            device_ip: IP address or hostname of the device
            
        Returns:
            ConnectHandler object if successful, None otherwise
        """
        device_config = {
            'device_type': 'cisco_nxos',
            'host': device_ip,
            'username': self.username,
            'password': self.password,
            'timeout': 120,
            'session_timeout': 300,
            'auth_timeout': 60,
            'banner_timeout': 30,
            'global_delay_factor': 2,
            'fast_cli': False,
        }
        
        try:
            self.logger.info(f"Connecting to {device_ip}...")
            connection = ConnectHandler(**device_config)
            
            # Test connection with a simple command
            output = connection.send_command("show version | head lines 5")
            self.logger.info(f"Successfully connected to {device_ip}")
            self.logger.debug(f"Device response: {output[:100]}...")
            
            return connection
            
        except NetmikoAuthenticationException as e:
            self.logger.error(f"Authentication failed for {device_ip}: {str(e)}")
            return None
        except NetmikoTimeoutException as e:
            self.logger.error(f"Connection timeout for {device_ip}: {str(e)}")
            return None
        except Exception as e:
            self.logger.error(f"Connection failed for {device_ip}: {str(e)}")
            return None

    def _identify_section_type(self, command: str) -> Tuple[str, str]:
        """
        Identify what type of configuration section a command belongs to.
        
        Args:
            command: Configuration command
            
        Returns:
            Tuple of (section_type, section_name)
        """
        command_lower = command.lower().strip()
        
        for section_type, section_info in self.CONFIG_SECTIONS.items():
            if section_info['pattern']:
                pattern = section_info['pattern']
                match = re.match(pattern, command_lower)
                if match:
                    if len(match.groups()) >= 1:
                        section_name = match.group(1)
                        if len(match.groups()) >= 2 and match.group(2):
                            section_name += f" {match.group(2)}"
                    else:
                        section_name = section_type
                    return section_type, section_name
        
        # Default to global
        return 'global', 'global-commands'

    def _get_section_config(self, connection: ConnectHandler, section_type: str, section_name: str) -> Dict:
        """
        Get current configuration for any type of section.
        
        Args:
            connection: Active netmiko connection
            section_type: Type of section (interface, vlan, etc.)
            section_name: Name/identifier of the section
            
        Returns:
            Dictionary with section configuration details
        """
        try:
            section_info = self.CONFIG_SECTIONS[section_type]
            
            # Get section configuration
            if '{}' in section_info['show_command']:
                config_output = connection.send_command(section_info['show_command'].format(section_name))
            else:
                config_output = connection.send_command(section_info['show_command'])
            
            # Get section status (if applicable)
            status_output = ""
            if section_info['status_command']:
                try:
                    if '{}' in section_info['status_command']:
                        status_output = connection.send_command(section_info['status_command'].format(section_name))
                    else:
                        status_output = connection.send_command(section_info['status_command'])
                except:
                    status_output = "Status command failed or not applicable"
            
            # Check if section exists
            exists = not any(error in config_output.lower() for error in [
                'invalid', 'not found', 'does not exist', 'error'
            ])
            
            section_data = {
                'section_type': section_type,
                'section_name': section_name,
                'config': config_output,
                'status': status_output,
                'exists': exists,
                'timestamp': datetime.now().isoformat()
            }
            
            self.logger.debug(f"Retrieved config for {section_type} {section_name}")
            return section_data
            
        except Exception as e:
            self.logger.warning(f"Could not retrieve config for {section_type} {section_name}: {str(e)}")
            return {
                'section_type': section_type,
                'section_name': section_name,
                'config': '',
                'status': '',
                'exists': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }

    def _parse_configuration_sections(self, config_commands: List[str]) -> Dict[str, List[str]]:
        """
        Parse ALL configuration commands into their respective sections.
        
        Args:
            config_commands: List of all configuration commands
            
        Returns:
            Dictionary mapping section identifiers to their configuration commands
        """
        sections = {}
        current_section = None
        current_section_type = None
        
        for command in config_commands:
            command = command.strip()
            if not command:
                continue
            
            # Identify the section type
            section_type, section_name = self._identify_section_type(command)
            section_key = f"{section_type}:{section_name}"
            
            # Check if this starts a new hierarchical section
            section_info = self.CONFIG_SECTIONS[section_type]
            
            if section_info['hierarchical'] and section_info['pattern']:
                # This is a section header command
                if re.match(section_info['pattern'], command.lower()):
                    current_section = section_key
                    current_section_type = section_type
                    if section_key not in sections:
                        sections[section_key] = []
                    sections[section_key].append(command)
                    continue
            
            # Handle 'exit' command
            if command.lower() == 'exit':
                if current_section:
                    sections[current_section].append(command)
                    current_section = None
                    current_section_type = None
                else:
                    # Orphaned exit - add to global
                    if 'global:global-commands' not in sections:
                        sections['global:global-commands'] = []
                    sections['global:global-commands'].append(command)
                continue
            
            # Add command to appropriate section
            if current_section and current_section_type:
                # We're inside a hierarchical section
                sections[current_section].append(command)
            else:
                # This is a global/standalone command
                global_key = 'global:global-commands'
                if global_key not in sections:
                    sections[global_key] = []
                sections[global_key].append(command)
        
        return sections

    def _apply_device_configuration(self, connection: ConnectHandler, device_ip: str) -> Dict:
        """
        Apply device-specific configuration sections with section-level error handling.
        
        Args:
            connection: Active netmiko connection
            device_ip: Device IP address
            
        Returns:
            Dictionary with configuration results
        """
        if device_ip not in self.device_configs:
            raise ValueError(f"No configuration found for device {device_ip}")
        
        device_config_info = self.device_configs[device_ip]
        sections = device_config_info['sections']
        config_file = device_config_info['config_file']
        
        device_results = {
            'device': device_ip,
            'config_file': config_file,
            'timestamp': datetime.now().isoformat(),
            'sections': {},
            'failed_sections': [],
            'successful_sections': [],
            'total_sections': len(sections),
            'section_types': {}
        }
        
        # Process sections in a logical order (global first, then hierarchical)
        section_order = ['global', 'vlan', 'vrf', 'interface', 'router', 'route-map', 
                        'ip access-list', 'class-map', 'policy-map', 'vpc', 'port-channel']
        
        ordered_sections = []
        
        # Add sections in preferred order
        for section_type in section_order:
            for section_key in sections:
                if section_key.startswith(f"{section_type}:"):
                    ordered_sections.append(section_key)
        
        # Add any remaining sections
        for section_key in sections:
            if section_key not in ordered_sections:
                ordered_sections.append(section_key)
        
        # Track section types
        for section_key in sections:
            section_type = section_key.split(':', 1)[0]
            if section_type not in device_results['section_types']:
                device_results['section_types'][section_type] = {
                    'total': 0, 'successful': 0, 'failed': 0
                }
            device_results['section_types'][section_type]['total'] += 1
        
        # Apply each section
        for section_key in ordered_sections:
            section_type, section_name = section_key.split(':', 1)
            commands = sections[section_key]
            
            self.logger.info(f"Processing {section_type} section '{section_name}' on {device_ip}")
            
            # Get before configuration
            before_config = self._get_section_config(connection, section_type, section_name)
            
            section_result = {
                'section_type': section_type,
                'section_name': section_name,
                'section_key': section_key,
                'device': device_ip,
                'config_file': config_file,
                'commands': commands,
                'before_config': before_config,
                'after_config': {},
                'success': False,
                'error': None,
                'output': '',
                'timestamp': datetime.now().isoformat()
            }
            
            try:
                # Apply section configuration
                self.logger.debug(f"Applying {len(commands)} commands to {section_type} {section_name}")
                output = connection.send_config_set(commands)
                
                # Get after configuration
                after_config = self._get_section_config(connection, section_type, section_name)
                
                section_result.update({
                    'success': True,
                    'output': output,
                    'after_config': after_config
                })
                
                device_results['successful_sections'].append(section_key)
                device_results['section_types'][section_type]['successful'] += 1
                self.logger.info(f"Successfully configured {section_type} '{section_name}' on {device_ip}")
                
            except Exception as e:
                error_msg = str(e)
                section_result.update({
                    'success': False,
                    'error': error_msg,
                    'output': ''
                })
                
                device_results['failed_sections'].append(section_key)
                device_results['section_types'][section_type]['failed'] += 1
                self.logger.warning(f"Failed to configure {section_type} '{section_name}' on {device_ip}: {error_msg}")
                
                # Continue with next section instead of stopping
            
            device_results['sections'][section_key] = section_result
            self.section_results.append(section_result)
        
        return device_results

    def _save_configuration(self, connection: ConnectHandler, device_ip: str) -> bool:
        """
        Save the running configuration to startup configuration.
        
        Args:
            connection: Active netmiko connection
            device_ip: Device IP address
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.logger.info(f"Saving configuration on {device_ip}")
            output = connection.send_command("copy running-config startup-config")
            self.logger.info(f"Configuration saved successfully on {device_ip}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save configuration on {device_ip}: {str(e)}")
            return False

    def process_all_devices(self) -> None:
        """
        Process all devices with their individual configuration files.
        """
        self.logger.info(f"Starting configuration process for {len(self.device_config_mapping)} devices")
        
        for device_ip in self.device_config_mapping.keys():
            self.logger.info(f"Processing device: {device_ip}")
            
            # Skip if device config failed to load
            if device_ip not in self.device_configs:
                self.logger.warning(f"Skipping {device_ip} - configuration file not loaded")
                continue
            
            # Connect to device
            connection = self._connect_to_device(device_ip)
            if not connection:
                if not any(failed['device'] == device_ip for failed in self.failed_devices):
                    self.failed_devices.append({
                        'device': device_ip,
                        'error': 'Failed to establish connection',
                        'timestamp': datetime.now().isoformat()
                    })
                continue
            
            try:
                # Apply device-specific configuration
                device_results = self._apply_device_configuration(connection, device_ip)
                
                # Save configuration
                save_success = self._save_configuration(connection, device_ip)
                device_results['config_saved'] = save_success
                
                self.results.append(device_results)
                self.logger.info(f"Completed processing device {device_ip}")
                
            except Exception as e:
                self.logger.error(f"Unexpected error processing {device_ip}: {str(e)}")
                self.logger.error(f"Traceback: {traceback.format_exc()}")
                
                self.failed_devices.append({
                    'device': device_ip,
                    'error': f'Unexpected error: {str(e)}',
                    'timestamp': datetime.now().isoformat()
                })
                
            finally:
                # Always disconnect
                try:
                    connection.disconnect()
                    self.logger.debug(f"Disconnected from {device_ip}")
                except:
                    pass
        
        self.logger.info("Completed processing all devices")

    def generate_comprehensive_report(self, output_file: Optional[str] = None) -> str:
        """
        Generate a comprehensive Excel spreadsheet report for all devices and sections.
        
        Args:
            output_file: Optional output file path
            
        Returns:
            Path to the generated spreadsheet
        """
        if not output_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"multi_device_nxos_config_report_{timestamp}.xlsx"
        
        self.logger.info(f"Generating comprehensive multi-device report: {output_file}")
        
        try:
            with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
                # Device summary sheet
                device_summary_data = []
                for result in self.results:
                    row = {
                        'Device IP': result['device'],
                        'Config File': result['config_file'],
                        'Total Sections': result['total_sections'],
                        'Successful Sections': len(result['successful_sections']),
                        'Failed Sections': len(result['failed_sections']),
                        'Config Saved': result.get('config_saved', False),
                        'Success Rate': f"{(len(result['successful_sections'])/result['total_sections']*100):.1f}%" if result['total_sections'] > 0 else "0%",
                        'Timestamp': result['timestamp']
                    }
                    
                    # Add section type breakdown
                    for section_type, stats in result.get('section_types', {}).items():
                        row[f'{section_type.title()} Total'] = stats['total']
                        row[f'{section_type.title()} Success'] = stats['successful']
                        row[f'{section_type.title()} Failed'] = stats['failed']
                    
                    device_summary_data.append(row)
                
                # Add failed devices
                for failed in self.failed_devices:
                    device_summary_data.append({
                        'Device IP': failed['device'],
                        'Config File': self.device_config_mapping.get(failed['device'], 'Unknown'),
                        'Total Sections': 0,
                        'Successful Sections': 0,
                        'Failed Sections': 0,
                        'Config Saved': False,
                        'Success Rate': '0%',
                        'Error': failed['error'],
                        'Timestamp': failed['timestamp']
                    })
                
                device_summary_df = pd.DataFrame(device_summary_data)
                device_summary_df.to_excel(writer, sheet_name='Device Summary', index=False)
                
                # All sections details sheet
                all_sections_data = []
                for section_result in self.section_results:
                    all_sections_data.append({
                        'Device IP': section_result['device'],
                        'Config File': section_result['config_file'],
                        'Section Type': section_result['section_type'],
                        'Section Name': section_result['section_name'],
                        'Success': section_result['success'],
                        'Error': section_result.get('error', ''),
                        'Command Count': len(section_result['commands']),
                        'Commands Applied': '; '.join(section_result['commands'][:3]) + ('...' if len(section_result['commands']) > 3 else ''),
                        'Before Config Available': bool(section_result['before_config'].get('config')),
                        'After Config Available': bool(section_result['after_config'].get('config')),
                        'Section Exists': section_result['before_config'].get('exists', False),
                        'Timestamp': section_result['timestamp']
                    })
                
                if all_sections_data:
                    all_sections_df = pd.DataFrame(all_sections_data)
                    all_sections_df.to_excel(writer, sheet_name='All Sections', index=False)
                
                # Failed sections sheet
                failed_sections_data = []
                for section_result in self.section_results:
                    if not section_result['success']:
                        failed_sections_data.append({
                            'Device IP': section_result['device'],
                            'Config File': section_result['config_file'],
                            'Section Type': section_result['section_type'],
                            'Section Name': section_result['section_name'],
                            'Error': section_result.get('error', ''),
                            'Commands': '; '.join(section_result['commands']),
                            'Output': section_result.get('output', ''),
                            'Timestamp': section_result['timestamp']
                        })
                
                if failed_sections_data:
                    failed_sections_df = pd.DataFrame(failed_sections_data)
                    failed_sections_df.to_excel(writer, sheet_name='Failed Sections', index=False)
                
                # Before-After comparison sheet
                comparison_data = []
                for section_result in self.section_results:
                    if section_result['success']:
                        comparison_data.append({
                            'Device IP': section_result['device'],
                            'Config File': section_result['config_file'],
                            'Section Type': section_result['section_type'],
                            'Section Name': section_result['section_name'],
                            'Before Config': section_result['before_config'].get('config', '')[:500] + ('...' if len(section_result['before_config'].get('config', '')) > 500 else ''),
                            'After Config': section_result['after_config'].get('config', '')[:500] + ('...' if len(section_result['after_config'].get('config', '')) > 500 else ''),
                            'Commands Applied': '; '.join(section_result['commands']),
                            'Timestamp': section_result['timestamp']
                        })
                
                if comparison_data:
                    comparison_df = pd.DataFrame(comparison_data)
                    comparison_df.to_excel(writer, sheet_name='Before-After Comparison', index=False)
                
                # Section type summary across all devices
                section_type_summary = []
                all_section_types = set()
                for result in self.results:
                    for section_type in result.get('section_types', {}):
                        all_section_types.add(section_type)
                
                for section_type in sorted(all_section_types):
                    total_across_devices = 0
                    successful_across_devices = 0
                    failed_across_devices = 0
                    devices_with_section = 0
                    
                    for result in self.results:
                        if section_type in result.get('section_types', {}):
                            devices_with_section += 1
                            stats = result['section_types'][section_type]
                            total_across_devices += stats['total']
                            successful_across_devices += stats['successful']
                            failed_across_devices += stats['failed']
                    
                    section_type_summary.append({
                        'Section Type': section_type.title(),
                        'Devices with Section': devices_with_section,
                        'Total Sections': total_across_devices,
                        'Successful': successful_across_devices,
                        'Failed': failed_across_devices,
                        'Success Rate': f"{(successful_across_devices/total_across_devices*100):.1f}%" if total_across_devices > 0 else "N/A",
                        'Avg per Device': f"{total_across_devices/devices_with_section:.1f}" if devices_with_section > 0 else "0"
                    })
                
                if section_type_summary:
                    section_type_df = pd.DataFrame(section_type_summary)
                    section_type_df.to_excel(writer, sheet_name='Section Type Summary', index=False)
            
            self.logger.info(f"Multi-device report generated successfully: {output_file}")
            return output_file
            
        except Exception as e:
            self.logger.error(f"Failed to generate spreadsheet report: {str(e)}")
            raise

    def print_comprehensive_summary(self) -> None:
        """
        Print a comprehensive summary of the multi-device configuration process.
        """
        print(f"\n{'='*80}")
        print("MULTI-DEVICE NX-OS CONFIGURATION SUMMARY")
        print(f"{'='*80}")
        
        total_devices = len(self.device_config_mapping)
        successful_devices = len(self.results)
        failed_devices = len(self.failed_devices)
        
        print(f"Total Devices: {total_devices}")
        print(f"Successful Devices: {successful_devices}")
        print(f"Failed Devices: {failed_devices}")
        
        if self.results:
            print(f"\nDevice Details:")
            for result in self.results:
                success_rate = (len(result['successful_sections'])/result['total_sections']*100) if result['total_sections'] > 0 else 0
                print(f"  {result['device']}: {len(result['successful_sections'])}/{result['total_sections']} sections ({success_rate:.1f}%) - {result['config_file']}")
        
        if self.section_results:
            total_sections = len(self.section_results)
            successful_sections = len([r for r in self.section_results if r['success']])
            failed_sections = total_sections - successful_sections
            
            print(f"\nOverall Configuration Sections:")
            print(f"Total Sections: {total_sections}")
            print(f"Successful Sections: {successful_sections}")
            print(f"Failed Sections: {failed_sections}")
            print(f"Overall Success Rate: {(successful_sections/total_sections*100):.1f}%")
            
            # Section type breakdown
            section_types = {}
            for result in self.section_results:
                section_type = result['section_type']
                if section_type not in section_types:
                    section_types[section_type] = {'total': 0, 'success': 0}
                section_types[section_type]['total'] += 1
                if result['success']:
                    section_types[section_type]['success'] += 1
            
            print(f"\nSection Type Breakdown:")
            for section_type, stats in sorted(section_types.items()):
                success_rate = (stats['success'] / stats['total'] * 100) if stats['total'] > 0 else 0
                print(f"  {section_type.title()}: {stats['success']}/{stats['total']} ({success_rate:.1f}%)")
        
        if self.failed_devices:
            print(f"\nFailed Devices:")
            for failed in self.failed_devices:
                print(f"  - {failed['device']}: {failed['error']}")
        
        print(f"{'='*80}\n")


def main():
    """
    Main function demonstrating multi-device NX-OS configuration management.
    """
    # Define your device to config file mapping
    device_config_mapping = {
        # Example mapping - replace with your actual devices and config files
        "192.168.1.10": "switch01_config.txt",
        "192.168.1.11": "switch02_config.txt",
        "192.168.1.12": "switch03_config.txt",
        "192.168.1.13": "switch04_config.txt",
        "192.168.1.14": "switch05_config.txt",
        "192.168.1.15": "switch06_config.txt",
        "192.168.1.16": "switch07_config.txt",
        "192.168.1.17": "switch08_config.txt",
        "192.168.1.18": "switch09_config.txt",
        "192.168.1.19": "switch10_config.txt",
    }
    
    try:
        # Initialize and run multi-device configuration manager
        manager = MultiDeviceNXOSConfigManager(device_config_mapping)
        
        # Process all devices with their individual configurations
        manager.process_all_devices()
        
        # Generate comprehensive report
        report_file = manager.generate_comprehensive_report()
        
        # Print summary
        manager.print_comprehensive_summary()
        
        print(f"Multi-device configuration complete. Report saved to: {report_file}")
        
    except KeyboardInterrupt:
        print("\nOperation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        logging.error(f"Unexpected error in main: {str(e)}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        sys.exit(1)


if __name__ == "__main__":
    main()
