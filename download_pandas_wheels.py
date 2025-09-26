#!/usr/bin/env python3
"""
Download pandas wheel files for offline installation on RHEL8 with Python 3.13
This script downloads the wheels you can transfer to your target system.
"""

import subprocess
import sys
import os
from pathlib import Path

def download_wheels():
    """Download wheel files for pandas and dependencies"""
    
    # Create wheels directory
    wheels_dir = Path("wheels_for_rhel8_py313")
    wheels_dir.mkdir(exist_ok=True)
    
    print(f"Downloading wheels to: {wheels_dir.absolute()}")
    
    # List of packages to download
    packages = [
        "pandas",
        "numpy", 
        "pytz",
        "python-dateutil",  # pandas dependency
        "six",              # python-dateutil dependency
    ]
    
    # Python version and platform info for RHEL8
    python_version = "cp313"
    abi = "cp313"
    platform = "linux_x86_64"
    
    for package in packages:
        print(f"\nDownloading {package}...")
        
        cmd = [
            sys.executable, "-m", "pip", "download",
            "--only-binary=:all:",
            "--python-version", "3.13",
            "--platform", platform,
            "--abi", abi,
            "--implementation", "cp",
            "--dest", str(wheels_dir),
            package
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            print(f"✅ Successfully downloaded {package}")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to download {package}")
            print(f"Error: {e.stderr}")
    
    # List downloaded files
    print(f"\n=== Downloaded Wheel Files ===")
    wheel_files = list(wheels_dir.glob("*.whl"))
    
    if wheel_files:
        for wheel_file in sorted(wheel_files):
            print(f"  {wheel_file.name}")
        
        print(f"\n=== Installation Instructions ===")
        print(f"1. Transfer the entire '{wheels_dir}' directory to your RHEL8 system")
        print(f"2. On your RHEL8 system, run:")
        print(f"   python3.13 -m pip install --no-index --find-links wheels_for_rhel8_py313 pandas")
        print(f"   OR install each wheel individually:")
        for wheel_file in sorted(wheel_files):
            print(f"   python3.13 -m pip install wheels_for_rhel8_py313/{wheel_file.name}")
            
    else:
        print("⚠️  No wheel files were downloaded. Check the error messages above.")
    
    return len(wheel_files) > 0

if __name__ == "__main__":
    print("=== Pandas Wheel Downloader for RHEL8 Python 3.13 ===")
    
    # Check if pip is available
    try:
        subprocess.run([sys.executable, "-m", "pip", "--version"], 
                      capture_output=True, check=True)
    except subprocess.CalledProcessError:
        print("❌ pip is not available. Cannot download wheels.")
        sys.exit(1)
    
    success = download_wheels()
    
    if success:
        print("\n🎉 Wheel download completed successfully!")
        print("Transfer the wheels directory to your RHEL8 system for offline installation.")
    else:
        print("\n💥 Wheel download failed. Check error messages above.")
        sys.exit(1)
