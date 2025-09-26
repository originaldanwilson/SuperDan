#!/usr/bin/env python3
"""
Download pandas wheel files for Python 3.12 (should work with 3.13)
Since Python 3.13 is very new, we'll download 3.12 wheels which are compatible
"""

import subprocess
import sys
import os
from pathlib import Path

def download_wheels():
    """Download wheel files for pandas and dependencies"""
    
    # Create wheels directory
    wheels_dir = Path("wheels_pandas_py312_compatible")
    wheels_dir.mkdir(exist_ok=True)
    
    print(f"Downloading wheels to: {wheels_dir.absolute()}")
    
    # List of packages to download
    packages = [
        "pandas",
        "numpy", 
        "pytz",
        "python-dateutil",
        "six",
        "tzdata",  # Additional pandas dependency
    ]
    
    # Use Python 3.12 wheels (should be compatible with 3.13)
    python_version = "3.12"
    platform = "linux_x86_64"
    
    for package in packages:
        print(f"\nDownloading {package}...")
        
        cmd = [
            sys.executable, "-m", "pip", "download",
            "--only-binary=:all:",
            "--python-version", python_version,
            "--platform", platform,
            "--dest", str(wheels_dir),
            package
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            print(f"✅ Successfully downloaded {package}")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to download {package} - trying without platform restriction...")
            
            # Try without platform restriction
            cmd_fallback = [
                sys.executable, "-m", "pip", "download",
                "--dest", str(wheels_dir),
                package
            ]
            
            try:
                result = subprocess.run(cmd_fallback, capture_output=True, text=True, check=True)
                print(f"✅ Successfully downloaded {package} (fallback)")
            except subprocess.CalledProcessError as e2:
                print(f"❌ Failed to download {package}")
                print(f"Error: {e2.stderr}")
    
    # List downloaded files
    print(f"\n=== Downloaded Files ===")
    all_files = list(wheels_dir.glob("*"))
    wheel_files = [f for f in all_files if f.suffix == '.whl']
    tar_files = [f for f in all_files if f.suffix == '.gz']
    
    if wheel_files:
        print("Wheel files (.whl):")
        for wheel_file in sorted(wheel_files):
            print(f"  {wheel_file.name}")
    
    if tar_files:
        print("Source distributions (.tar.gz):")
        for tar_file in sorted(tar_files):
            print(f"  {tar_file.name}")
        
    print(f"\n=== Installation Instructions ===")
    print(f"1. Transfer the entire '{wheels_dir}' directory to your RHEL8 system")
    print(f"2. On your RHEL8 system, try these installation methods:")
    print(f"\n   METHOD 1 - Install all at once:")
    print(f"   python3.13 -m pip install --no-index --find-links {wheels_dir} pandas")
    print(f"\n   METHOD 2 - Install dependencies first, then pandas:")
    print(f"   python3.13 -m pip install --no-index --find-links {wheels_dir} numpy pytz python-dateutil six")
    print(f"   python3.13 -m pip install --no-index --find-links {wheels_dir} pandas")
    print(f"\n   METHOD 3 - Install each file individually:")
    for file in sorted(all_files):
        print(f"   python3.13 -m pip install {wheels_dir}/{file.name}")
    
    print(f"\n   NOTE: Python 3.13 should be able to use Python 3.12 wheels")
    print(f"   If you get compatibility errors, you may need to compile from source")
    
    return len(all_files) > 0

if __name__ == "__main__":
    print("=== Pandas Wheel Downloader (Python 3.12 Compatible) ===")
    
    # Check if pip is available
    try:
        subprocess.run([sys.executable, "-m", "pip", "--version"], 
                      capture_output=True, check=True)
    except subprocess.CalledProcessError:
        print("❌ pip is not available. Cannot download wheels.")
        sys.exit(1)
    
    success = download_wheels()
    
    if success:
        print("\n🎉 Download completed successfully!")
    else:
        print("\n💥 Download failed. Check error messages above.")
        sys.exit(1)
