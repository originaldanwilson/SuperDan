#!/usr/bin/env python3
"""
Simple usage example for NX-OS File Manager
Demonstrates how to use the class-based approach for large file transfers
"""

from nxos_file_manager import NXOSFileManager, NXOSTransferExample
from tools import get_netmiko_creds
import sys

def main():
    """Main example function"""
    
    # Example 1: Basic file transfer using the manager directly
    print("=== NX-OS File Transfer Example ===")
    
    # Test credentials
    user, password = get_netmiko_creds()
    print(f"Using credentials for user: {user}")
    
    # Example usage - replace with your actual values
    nxos_hostname = "192.168.1.10"  # Replace with your NX-OS switch IP
    local_file = "/path/to/your/large_file.bin"  # Replace with actual file path
    
    # Method 1: Using the class directly with context manager
    try:
        with NXOSFileManager(nxos_hostname, debug=True) as nxos:
            print(f"Connected to NX-OS device: {nxos_hostname}")
            
            # Transfer file to bootflash
            remote_file = f"bootflash:{local_file.split('/')[-1]}"
            success = nxos.transfer_file_scp_nxos(local_file, remote_file)
            
            if success:
                print("Transfer completed successfully!")
                
                # Optional: Copy file within NX-OS filesystems
                # nxos.copy_file_within_nxos("bootflash:myfile.bin", "slot0:myfile.bin")
                
            else:
                print("Transfer failed!")
                
    except Exception as e:
        print(f"Error: {e}")
    
    # Method 2: Using the convenience function
    print("\n=== Using Convenience Function ===")
    success = NXOSTransferExample.transfer_large_file_to_nxos(
        nxos_hostname, 
        local_file, 
        "bootflash:"
    )
    print(f"Convenience function result: {'Success' if success else 'Failed'}")

def transfer_nxos_image_example():
    """Example for transferring and installing NX-OS image"""
    
    nxos_hostname = "192.168.1.10"
    nxos_image = "/path/to/nxos-image.bin"
    
    print("=== NX-OS Image Installation Example ===")
    
    # This would transfer the image and attempt to install it
    success = NXOSTransferExample.install_nxos_image(
        nxos_hostname, 
        nxos_image,
        install_timeout=3600  # 1 hour timeout for installation
    )
    
    print(f"Image installation: {'Success' if success else 'Failed'}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "image":
        transfer_nxos_image_example()
    else:
        main()
