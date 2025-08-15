#!/usr/bin/env python3
"""
NX-OS Configuration Manager

This script connects to Cisco NX-OS switches using netmiko, applies configuration
commands from a text file, handles interface configuration errors gracefully,
and generates a detailed spreadsheet report of all configuration changes.

Features:
- Netmiko-based connectivity to NX-OS switches
- Configuration command parsing and execution
- Interface-specific error handling with skip capability
- Before/after configuration comparison
- Detailed logging with console and file output
- Excel spreadsheet generation for configuration tracking

Author: Network Automation Script
"""

import os
import sys
import re
import logging
import traceback
from datetime import datetime
from typing import List, Dict, Tuple, Optional
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


class NXOSConfigManager:
    """
    Main class for managing NX-OS device configuration.
    """
    
    def __init__(self, config_file: str, device_list: List[str]):
        """
        Initialize the NX-OS Configuration Manager.
        
        Args:
            config_file: Path to the text file containing configuration commands
            device_list: List of device IP addresses or hostnames
        """
        self.config_file = config_file
        self.device_list = device_list
        self.logger = setupLogging()
        
        # Get credentials
        netmikoUser, passwd, enable = get_netmiko_creds()
        self.username = netmikoUser
        self.password = passwd
        
        # Configuration tracking
        self.results = []
        self.failed_devices = []
        self.interface_results = []
        
        # Load configuration commands
        self.config_commands = self._load_config_commands()
        
        self.logger.info(f"Initialized NXOSConfigManager for {len(device_list)} devices")
        self.logger.info(f"Loaded {len(self.config_commands)} configuration commands")

    def _load_config_commands(self) -> List[str]:
        """
        Load configuration commands from the text file.
        
        Returns:
            List of configuration commands
        """
        try:
            with open(self.config_file, 'r') as f:
                commands = [line.strip() for line in f if line.strip() and not line.strip().startswith('!')]
            
            self.logger.info(f"Loaded {len(commands)} commands from {self.config_file}")
            return commands
            
        except FileNotFoundError:
            self.logger.error(f"Configuration file not found: {self.config_file}")
            raise
        except Exception as e:
            self.logger.error(f"Error loading configuration file: {str(e)}")
            raise

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

    def _get_interface_config(self, connection: ConnectHandler, interface: str) -> Dict:
        """
        Get current interface configuration.
        
        Args:
            connection: Active netmiko connection
            interface: Interface name (e.g., 'Ethernet1/1')
            
        Returns:
            Dictionary with interface configuration details
        """
        try:
            # Get interface configuration
            config_output = connection.send_command(f"show running-config interface {interface}")
            
            # Get interface status
            status_output = connection.send_command(f"show interface {interface} status")
            
            # Parse interface details
            interface_data = {
                'interface': interface,
                'config': config_output,
                'status': status_output,
                'exists': 'Invalid interface' not in config_output.lower(),
                'timestamp': datetime.now().isoformat()
            }
            
            self.logger.debug(f"Retrieved config for interface {interface}")
            return interface_data
            
        except Exception as e:
            self.logger.warning(f"Could not retrieve config for interface {interface}: {str(e)}")
            return {
                'interface': interface,
                'config': '',
                'status': '',
                'exists': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }

    def _parse_interface_from_config(self, config_commands: List[str]) -> Dict[str, List[str]]:
        """
        Parse interface-specific commands from the configuration.
        
        Args:
            config_commands: List of all configuration commands
            
        Returns:
            Dictionary mapping interface names to their configuration commands
        """
        interface_configs = {}
        current_interface = None
        global_commands = []
        
        for command in config_commands:
            if command.lower().startswith('interface '):
                # Extract interface name
                current_interface = command.split('interface ', 1)[1].strip()
                if current_interface not in interface_configs:
                    interface_configs[current_interface] = []
                interface_configs[current_interface].append(command)
                
            elif command.lower() == 'exit':
                if current_interface:
                    interface_configs[current_interface].append(command)
                    current_interface = None
                else:
                    global_commands.append(command)
                    
            elif current_interface:
                # Command belongs to current interface
                interface_configs[current_interface].append(command)
            else:
                # Global command
                global_commands.append(command)
        
        # Add global commands as a special entry
        if global_commands:
            interface_configs['_global_'] = global_commands
            
        self.logger.info(f"Parsed {len(interface_configs)} interface/global sections")
        return interface_configs

    def _apply_configuration(self, connection: ConnectHandler, device_ip: str, 
                           interface_configs: Dict[str, List[str]]) -> Dict:
        """
        Apply configuration to the device with interface-level error handling.
        
        Args:
            connection: Active netmiko connection
            device_ip: Device IP address
            interface_configs: Dictionary of interface configurations
            
        Returns:
            Dictionary with configuration results
        """
        device_results = {
            'device': device_ip,
            'timestamp': datetime.now().isoformat(),
            'interfaces': {},
            'global_config': {},
            'failed_interfaces': [],
            'successful_interfaces': [],
            'total_interfaces': len([k for k in interface_configs.keys() if k != '_global_'])
        }
        
        # Apply global configuration first
        if '_global_' in interface_configs:
            self.logger.info(f"Applying global configuration to {device_ip}")
            try:
                global_commands = interface_configs['_global_']
                output = connection.send_config_set(global_commands)
                device_results['global_config'] = {
                    'commands': global_commands,
                    'output': output,
                    'success': True
                }
                self.logger.info(f"Global configuration applied successfully to {device_ip}")
                
            except Exception as e:
                self.logger.error(f"Failed to apply global configuration to {device_ip}: {str(e)}")
                device_results['global_config'] = {
                    'commands': global_commands,
                    'output': '',
                    'success': False,
                    'error': str(e)
                }
        
        # Apply interface configurations
        for interface_name, commands in interface_configs.items():
            if interface_name == '_global_':
                continue
                
            self.logger.info(f"Processing interface {interface_name} on {device_ip}")
            
            # Get before configuration
            before_config = self._get_interface_config(connection, interface_name)
            
            interface_result = {
                'interface': interface_name,
                'device': device_ip,
                'commands': commands,
                'before_config': before_config,
                'after_config': {},
                'success': False,
                'error': None,
                'output': '',
                'timestamp': datetime.now().isoformat()
            }
            
            try:
                # Apply interface configuration
                output = connection.send_config_set(commands)
                
                # Get after configuration
                after_config = self._get_interface_config(connection, interface_name)
                
                interface_result.update({
                    'success': True,
                    'output': output,
                    'after_config': after_config
                })
                
                device_results['successful_interfaces'].append(interface_name)
                self.logger.info(f"Successfully configured interface {interface_name} on {device_ip}")
                
            except Exception as e:
                error_msg = str(e)
                interface_result.update({
                    'success': False,
                    'error': error_msg,
                    'output': ''
                })
                
                device_results['failed_interfaces'].append(interface_name)
                self.logger.warning(f"Failed to configure interface {interface_name} on {device_ip}: {error_msg}")
                
                # Continue with next interface instead of stopping
                continue
            
            device_results['interfaces'][interface_name] = interface_result
            self.interface_results.append(interface_result)
        
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

    def process_devices(self) -> None:
        """
        Process all devices in the device list.
        """
        self.logger.info(f"Starting configuration process for {len(self.device_list)} devices")
        
        # Parse interface configurations
        interface_configs = self._parse_interface_from_config(self.config_commands)
        
        for device_ip in self.device_list:
            self.logger.info(f"Processing device: {device_ip}")
            
            # Connect to device
            connection = self._connect_to_device(device_ip)
            if not connection:
                self.failed_devices.append({
                    'device': device_ip,
                    'error': 'Failed to establish connection',
                    'timestamp': datetime.now().isoformat()
                })
                continue
            
            try:
                # Apply configuration
                device_results = self._apply_configuration(connection, device_ip, interface_configs)
                
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

    def generate_spreadsheet_report(self, output_file: Optional[str] = None) -> str:
        """
        Generate a comprehensive Excel spreadsheet report.
        
        Args:
            output_file: Optional output file path
            
        Returns:
            Path to the generated spreadsheet
        """
        if not output_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"nxos_config_report_{timestamp}.xlsx"
        
        self.logger.info(f"Generating spreadsheet report: {output_file}")
        
        try:
            with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
                # Summary sheet
                summary_data = []
                for result in self.results:
                    summary_data.append({
                        'Device': result['device'],
                        'Total Interfaces': result['total_interfaces'],
                        'Successful Interfaces': len(result['successful_interfaces']),
                        'Failed Interfaces': len(result['failed_interfaces']),
                        'Config Saved': result.get('config_saved', False),
                        'Timestamp': result['timestamp']
                    })
                
                # Add failed devices
                for failed in self.failed_devices:
                    summary_data.append({
                        'Device': failed['device'],
                        'Total Interfaces': 0,
                        'Successful Interfaces': 0,
                        'Failed Interfaces': 0,
                        'Config Saved': False,
                        'Error': failed['error'],
                        'Timestamp': failed['timestamp']
                    })
                
                summary_df = pd.DataFrame(summary_data)
                summary_df.to_excel(writer, sheet_name='Summary', index=False)
                
                # Interface details sheet
                interface_data = []
                for interface_result in self.interface_results:
                    interface_data.append({
                        'Device': interface_result['device'],
                        'Interface': interface_result['interface'],
                        'Success': interface_result['success'],
                        'Error': interface_result.get('error', ''),
                        'Commands Applied': '; '.join(interface_result['commands']),
                        'Before Config Available': bool(interface_result['before_config'].get('config')),
                        'After Config Available': bool(interface_result['after_config'].get('config')),
                        'Interface Exists': interface_result['before_config'].get('exists', False),
                        'Timestamp': interface_result['timestamp']
                    })
                
                if interface_data:
                    interface_df = pd.DataFrame(interface_data)
                    interface_df.to_excel(writer, sheet_name='Interface Details', index=False)
                
                # Failed interfaces sheet
                failed_interface_data = []
                for interface_result in self.interface_results:
                    if not interface_result['success']:
                        failed_interface_data.append({
                            'Device': interface_result['device'],
                            'Interface': interface_result['interface'],
                            'Error': interface_result.get('error', ''),
                            'Commands': '; '.join(interface_result['commands']),
                            'Output': interface_result.get('output', ''),
                            'Timestamp': interface_result['timestamp']
                        })
                
                if failed_interface_data:
                    failed_df = pd.DataFrame(failed_interface_data)
                    failed_df.to_excel(writer, sheet_name='Failed Interfaces', index=False)
                
                # Configuration comparison sheet
                comparison_data = []
                for interface_result in self.interface_results:
                    if interface_result['success']:
                        comparison_data.append({
                            'Device': interface_result['device'],
                            'Interface': interface_result['interface'],
                            'Before Config': interface_result['before_config'].get('config', ''),
                            'After Config': interface_result['after_config'].get('config', ''),
                            'Before Status': interface_result['before_config'].get('status', ''),
                            'After Status': interface_result['after_config'].get('status', ''),
                            'Commands Applied': '; '.join(interface_result['commands']),
                            'Timestamp': interface_result['timestamp']
                        })
                
                if comparison_data:
                    comparison_df = pd.DataFrame(comparison_data)
                    comparison_df.to_excel(writer, sheet_name='Before-After Comparison', index=False)
            
            self.logger.info(f"Spreadsheet report generated successfully: {output_file}")
            return output_file
            
        except Exception as e:
            self.logger.error(f"Failed to generate spreadsheet report: {str(e)}")
            raise

    def print_summary(self) -> None:
        """
        Print a summary of the configuration process.
        """
        print(f"\n{'='*60}")
        print("NX-OS CONFIGURATION SUMMARY")
        print(f"{'='*60}")
        
        total_devices = len(self.device_list)
        successful_devices = len(self.results)
        failed_devices = len(self.failed_devices)
        
        print(f"Total Devices: {total_devices}")
        print(f"Successful Devices: {successful_devices}")
        print(f"Failed Devices: {failed_devices}")
        
        if self.interface_results:
            total_interfaces = len(self.interface_results)
            successful_interfaces = len([r for r in self.interface_results if r['success']])
            failed_interfaces = total_interfaces - successful_interfaces
            
            print(f"\nInterface Configuration:")
            print(f"Total Interfaces: {total_interfaces}")
            print(f"Successful Interfaces: {successful_interfaces}")
            print(f"Failed Interfaces: {failed_interfaces}")
        
        if self.failed_devices:
            print(f"\nFailed Devices:")
            for failed in self.failed_devices:
                print(f"  - {failed['device']}: {failed['error']}")
        
        print(f"{'='*60}\n")


def main():
    """
    Main function to run the NX-OS configuration manager.
    """
    # Configuration
    config_file = "testconfig1c.txt"  # Path to your configuration file
    
    # Device list - replace with your actual device IPs/hostnames
    device_list = [
        "192.168.1.10",
        "192.168.1.11",
        # Add more devices as needed
    ]
    
    try:
        # Initialize and run configuration manager
        manager = NXOSConfigManager(config_file, device_list)
        manager.process_devices()
        
        # Generate report
        report_file = manager.generate_spreadsheet_report()
        
        # Print summary
        manager.print_summary()
        
        print(f"Configuration complete. Report saved to: {report_file}")
        
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
