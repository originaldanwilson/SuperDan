#!/usr/bin/env python3
"""
Example usage of the NX-OS Configuration Manager

This script demonstrates how to use the NX-OS Configuration Manager
to configure multiple NX-OS switches with proper error handling,
logging, and report generation.

Before running this script:
1. Update the device_list with your actual switch IP addresses
2. Ensure your NX-OS configuration file is ready (nxos_config.txt)
3. Update credentials in tools.py
4. Install required packages: pip install netmiko pandas openpyxl

Usage:
    python3 run_nxos_config_example.py
"""

from nxos_config_manager import NXOSConfigManager


def main():
    """
    Example usage of NXOSConfigManager
    """
    print("NX-OS Configuration Manager - Example Usage")
    print("=" * 50)
    
    # Configuration file containing NX-OS commands
    config_file = "nxos_config.txt"
    
    # List of NX-OS devices to configure
    # Replace these with your actual device IP addresses or hostnames
    device_list = [
        # "192.168.1.100",    # NX-OS Switch 1
        # "192.168.1.101",    # NX-OS Switch 2
        # "10.10.10.20",      # NX-OS Switch 3
        # "switch01.example.com",  # NX-OS Switch by hostname
    ]
    
    # For demonstration, we'll use localhost (remove this for real switches)
    # This will fail to connect, but show you how error handling works
    device_list = ["127.0.0.1"]  # This will demonstrate connection failure handling
    
    try:
        print(f"Initializing configuration manager...")
        print(f"Configuration file: {config_file}")
        print(f"Target devices: {device_list}")
        print()
        
        # Initialize the configuration manager
        manager = NXOSConfigManager(config_file, device_list)
        
        # Process all devices
        print("Starting device configuration process...")
        manager.process_devices()
        
        # Generate comprehensive Excel report
        print("Generating spreadsheet report...")
        report_file = manager.generate_spreadsheet_report()
        
        # Display summary
        manager.print_summary()
        
        print(f"Process complete!")
        print(f"Detailed report saved to: {report_file}")
        print(f"Log files are stored in the 'logs' directory")
        
    except FileNotFoundError as e:
        print(f"Error: Configuration file not found - {e}")
        print("Make sure 'nxos_config.txt' exists in the current directory")
        print("Run 'python3 create_nxos_config.py' to create a sample config file")
        
    except ImportError as e:
        print(f"Error: Missing required package - {e}")
        print("Install required packages with:")
        print("pip install netmiko pandas openpyxl")
        
    except Exception as e:
        print(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
