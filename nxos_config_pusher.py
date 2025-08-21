#!/usr/bin/env python3
"""
NX-OS Configuration Pusher

A simple, focused tool for pushing configuration changes to NX-OS datacenter switches.
No assumptions, no categories - just reliable configuration deployment with error handling.

For production datacenter use - handles your configuration files as-is.
"""

import os
import sys
import logging
import traceback
from datetime import datetime
from typing import List, Dict, Optional

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

from tools import getScriptName, setupLogging, get_netmiko_creds


class NXOSConfigPusher:
    """
    Simple NX-OS configuration pusher for datacenter operations.
    """
    
    def __init__(self, device_config_mapping: Dict[str, str]):
        """
        Initialize the configuration pusher.
        
        Args:
            device_config_mapping: Dict mapping device IPs to their config files
                                  {"192.168.1.10": "switch1_changes.txt", ...}
        """
        self.device_config_mapping = device_config_mapping
        self.logger = setupLogging()
        
        # Get credentials
        netmikoUser, passwd, enable = get_netmiko_creds()
        self.username = netmikoUser
        self.password = passwd
        
        # Results tracking
        self.results = []
        self.failed_devices = []
        
        self.logger.info(f"Initialized NX-OS Config Pusher for {len(device_config_mapping)} devices")

    def _load_config_file(self, config_file: str) -> List[str]:
        """Load configuration commands from file."""
        try:
            with open(config_file, 'r') as f:
                commands = [line.strip() for line in f if line.strip() and not line.strip().startswith('!')]
            
            self.logger.info(f"Loaded {len(commands)} commands from {config_file}")
            return commands
            
        except FileNotFoundError:
            self.logger.error(f"Configuration file not found: {config_file}")
            raise
        except Exception as e:
            self.logger.error(f"Error loading configuration file {config_file}: {str(e)}")
            raise

    def _connect_to_device(self, device_ip: str) -> Optional[ConnectHandler]:
        """Connect to NX-OS device."""
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
            
            # Test connection
            output = connection.send_command("show version | head lines 3")
            self.logger.info(f"Connected to {device_ip}")
            
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

    def _get_before_config(self, connection: ConnectHandler) -> str:
        """Get running config before changes (for diff/audit)."""
        try:
            return connection.send_command("show running-config")
        except Exception as e:
            self.logger.warning(f"Could not retrieve before config: {str(e)}")
            return ""

    def _push_config(self, connection: ConnectHandler, device_ip: str, config_file: str) -> Dict:
        """Push configuration to device."""
        
        # Load config commands
        try:
            commands = self._load_config_file(config_file)
        except Exception as e:
            return {
                'device': device_ip,
                'config_file': config_file,
                'success': False,
                'error': f'Failed to load config file: {str(e)}',
                'commands_attempted': 0,
                'timestamp': datetime.now().isoformat()
            }
        
        # Get before state
        before_config = self._get_before_config(connection)
        
        result = {
            'device': device_ip,
            'config_file': config_file,
            'commands_attempted': len(commands),
            'before_config_length': len(before_config),
            'timestamp': datetime.now().isoformat()
        }
        
        try:
            self.logger.info(f"Pushing {len(commands)} commands to {device_ip}")
            
            # Push configuration
            output = connection.send_config_set(commands)
            
            # Get after state
            after_config = self._get_before_config(connection)
            
            result.update({
                'success': True,
                'output': output,
                'after_config_length': len(after_config),
                'config_changed': len(after_config) != len(before_config)
            })
            
            self.logger.info(f"Successfully pushed config to {device_ip}")
            
        except Exception as e:
            error_msg = str(e)
            result.update({
                'success': False,
                'error': error_msg,
                'output': ''
            })
            
            self.logger.error(f"Failed to push config to {device_ip}: {error_msg}")
        
        return result

    def _save_config(self, connection: ConnectHandler, device_ip: str) -> bool:
        """Save running config to startup config."""
        try:
            self.logger.info(f"Saving configuration on {device_ip}")
            connection.send_command("copy running-config startup-config")
            self.logger.info(f"Configuration saved on {device_ip}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to save config on {device_ip}: {str(e)}")
            return False

    def push_all_configs(self, save_configs: bool = True) -> None:
        """
        Push configurations to all devices.
        
        Args:
            save_configs: Whether to save to startup-config after applying
        """
        self.logger.info(f"Starting config push to {len(self.device_config_mapping)} devices")
        
        for device_ip, config_file in self.device_config_mapping.items():
            self.logger.info(f"Processing {device_ip} with {config_file}")
            
            # Connect
            connection = self._connect_to_device(device_ip)
            if not connection:
                self.failed_devices.append({
                    'device': device_ip,
                    'config_file': config_file,
                    'error': 'Failed to connect',
                    'timestamp': datetime.now().isoformat()
                })
                continue
            
            try:
                # Push config
                result = self._push_config(connection, device_ip, config_file)
                
                # Save config if successful and requested
                if result['success'] and save_configs:
                    result['config_saved'] = self._save_config(connection, device_ip)
                else:
                    result['config_saved'] = False
                
                self.results.append(result)
                
            except Exception as e:
                self.logger.error(f"Unexpected error with {device_ip}: {str(e)}")
                self.failed_devices.append({
                    'device': device_ip,
                    'config_file': config_file,
                    'error': f'Unexpected error: {str(e)}',
                    'timestamp': datetime.now().isoformat()
                })
                
            finally:
                try:
                    connection.disconnect()
                except:
                    pass
        
        self.logger.info("Completed config push to all devices")

    def generate_report(self, output_file: Optional[str] = None) -> str:
        """Generate Excel report of results."""
        if not output_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"nxos_config_push_report_{timestamp}.xlsx"
        
        self.logger.info(f"Generating report: {output_file}")
        
        with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
            # Summary sheet
            summary_data = []
            
            for result in self.results:
                summary_data.append({
                    'Device IP': result['device'],
                    'Config File': result['config_file'],
                    'Success': result['success'],
                    'Commands Attempted': result['commands_attempted'],
                    'Config Saved': result.get('config_saved', False),
                    'Config Changed': result.get('config_changed', 'Unknown'),
                    'Error': result.get('error', ''),
                    'Timestamp': result['timestamp']
                })
            
            for failed in self.failed_devices:
                summary_data.append({
                    'Device IP': failed['device'],
                    'Config File': failed['config_file'],
                    'Success': False,
                    'Commands Attempted': 0,
                    'Config Saved': False,
                    'Config Changed': False,
                    'Error': failed['error'],
                    'Timestamp': failed['timestamp']
                })
            
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='Summary', index=False)
            
            # Detailed results for successful pushes
            if self.results:
                detail_data = []
                for result in self.results:
                    if result['success']:
                        detail_data.append({
                            'Device IP': result['device'],
                            'Config File': result['config_file'],
                            'Commands Applied': result['commands_attempted'],
                            'Before Config Size': result['before_config_length'],
                            'After Config Size': result['after_config_length'],
                            'Output': result['output'][:1000] + ('...' if len(result['output']) > 1000 else ''),
                            'Timestamp': result['timestamp']
                        })
                
                if detail_data:
                    detail_df = pd.DataFrame(detail_data)
                    detail_df.to_excel(writer, sheet_name='Successful Pushes', index=False)
        
        self.logger.info(f"Report generated: {output_file}")
        return output_file

    def print_summary(self) -> None:
        """Print summary to console."""
        print(f"\n{'='*60}")
        print("NX-OS CONFIGURATION PUSH SUMMARY")
        print(f"{'='*60}")
        
        total = len(self.device_config_mapping)
        successful = len([r for r in self.results if r['success']])
        failed = total - successful
        
        print(f"Total Devices: {total}")
        print(f"Successful: {successful}")
        print(f"Failed: {failed}")
        
        if self.results:
            total_commands = sum(r['commands_attempted'] for r in self.results)
            print(f"Total Commands Pushed: {total_commands}")
        
        if failed > 0:
            print(f"\nFailed Devices:")
            for result in self.results:
                if not result['success']:
                    print(f"  {result['device']}: {result.get('error', 'Unknown error')}")
            
            for failed_device in self.failed_devices:
                print(f"  {failed_device['device']}: {failed_device['error']}")
        
        print(f"{'='*60}\n")


def main():
    """Example usage - customize for your environment."""
    
    # Your device to config file mapping
    device_config_mapping = {
        # "192.168.1.10": "dc-sw01-changes.txt",
        # "192.168.1.11": "dc-sw02-changes.txt",  
        # "10.0.1.100": "core-sw01-updates.txt",
        "127.0.0.1": "test_config.txt",  # Remove this - just for demo
    }
    
    # Create simple test config if it doesn't exist
    if not os.path.exists("test_config.txt"):
        with open("test_config.txt", "w") as f:
            f.write("! Test configuration\nlogging timestamp microseconds\n")
        print("Created test_config.txt for demo")
    
    try:
        pusher = NXOSConfigPusher(device_config_mapping)
        pusher.push_all_configs(save_configs=True)
        
        report_file = pusher.generate_report()
        pusher.print_summary()
        
        print(f"Configuration push complete. Report: {report_file}")
        
    except Exception as e:
        print(f"Error: {e}")
        logging.error(f"Error: {e}")


if __name__ == "__main__":
    main()
