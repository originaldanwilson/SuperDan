#!/usr/bin/env python3
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
        "192.168.1.10": "switch01_config.txt",  # NXOS-SW01
        "192.168.1.11": "switch02_config.txt",  # NXOS-SW02
        "192.168.1.12": "switch03_config.txt",  # NXOS-SW03
        "192.168.1.13": "switch04_config.txt",  # NXOS-SW04
        "192.168.1.14": "switch05_config.txt",  # NXOS-SW05
        "192.168.1.15": "switch06_config.txt",  # NXOS-SW06
        "192.168.1.16": "switch07_config.txt",  # NXOS-SW07
        "192.168.1.17": "switch08_config.txt",  # NXOS-SW08
        "192.168.1.18": "switch09_config.txt",  # NXOS-SW09
        "192.168.1.19": "switch10_config.txt",  # NXOS-SW10
    }
    
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
        print("\nOperation interrupted by user")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
