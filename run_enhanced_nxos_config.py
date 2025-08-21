#!/usr/bin/env python3
"""
Enhanced NX-OS Configuration Manager - Usage Example

This script demonstrates the enhanced NX-OS Configuration Manager that handles
ALL types of configuration sections, not just interfaces.

Enhanced Features Demonstrated:
- VLANs, VRFs, routing protocols, ACLs, policy maps, etc.
- Section-specific error handling
- Comprehensive before/after analysis
- Detailed Excel reporting with section type breakdowns

Usage:
    python3 run_enhanced_nxos_config.py
"""

from nxos_config_manager_enhanced import EnhancedNXOSConfigManager


def main():
    """
    Example usage of the Enhanced NXOSConfigManager
    """
    print("Enhanced NX-OS Configuration Manager - Comprehensive Configuration")
    print("=" * 70)
    
    # Configuration file containing ALL types of NX-OS commands
    config_file = "nxos_config.txt"
    
    # List of NX-OS devices to configure
    # Replace these with your actual device IP addresses or hostnames
    device_list = [
        # "192.168.1.100",    # NX-OS Switch 1
        # "192.168.1.101",    # NX-OS Switch 2
        # "10.10.10.20",      # NX-OS Switch 3
        # "datacenter-sw01.example.com",  # NX-OS Switch by hostname
    ]
    
    # For demonstration, we'll use localhost (remove this for real switches)
    # This will fail to connect, but show you how error handling works
    device_list = ["127.0.0.1"]  # This will demonstrate connection failure handling
    
    try:
        print(f"Initializing enhanced configuration manager...")
        print(f"Configuration file: {config_file}")
        print(f"Target devices: {device_list}")
        print()
        
        # Show what the enhanced version can handle
        print("This enhanced version handles ALL configuration sections:")
        print("✓ VLANs and VLAN configurations")
        print("✓ VRF contexts and routing")
        print("✓ Interface configurations (all types)")
        print("✓ Routing protocols (OSPF, BGP, EIGRP, etc.)")
        print("✓ Route maps and prefix lists")
        print("✓ Access control lists (ACLs)")
        print("✓ QoS class maps and policy maps")
        print("✓ Port-channel configurations")
        print("✓ Global configuration commands")
        print("✓ Any other hierarchical or non-hierarchical sections")
        print()
        
        # Initialize the enhanced configuration manager
        manager = EnhancedNXOSConfigManager(config_file, device_list)
        
        # Process all devices with comprehensive section handling
        print("Starting comprehensive device configuration process...")
        manager.process_devices()
        
        # Generate enhanced Excel report with section breakdowns
        print("Generating comprehensive spreadsheet report...")
        report_file = manager.generate_spreadsheet_report()
        
        # Display detailed summary
        manager.print_summary()
        
        print(f"\nEnhanced process complete!")
        print(f"Comprehensive report saved to: {report_file}")
        print(f"Log files are stored in the 'logs' directory")
        print("\nReport includes:")
        print("• Summary with section type breakdowns")
        print("• All sections details (not just interfaces)")
        print("• Failed sections with detailed error analysis")
        print("• Before-after comparison for all configuration types")
        print("• Section type summary with success rates")
        
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
