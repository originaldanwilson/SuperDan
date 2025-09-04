#!/usr/bin/env python3
"""
Simple PerfStack SSO Wrapper
Easy-to-use wrapper for the enhanced SSO script
"""

import os
import subprocess
import sys
from pathlib import Path

# Configuration
BROWSER_PROFILE_DIR = Path.home() / ".solarwinds_browser_profile"
STATE_FILE = Path.home() / ".solarwinds_state.json"

def run_perfstack(host, interface, method='profile', hours=168, headed=False):
    """
    Simple function to run PerfStack with SSO
    
    Args:
        host: Device hostname or IP
        interface: Interface name
        method: 'profile', 'state', or 'cdp'
        hours: Time window in hours
        headed: Show browser window
    """
    
    script_dir = Path(__file__).parent
    enhanced_script = script_dir / "perfstack_sso_enhanced.py"
    
    if not enhanced_script.exists():
        print("❌ Enhanced SSO script not found!")
        return False
    
    # Build command
    cmd = [
        "python3", str(enhanced_script),
        "--host", host,
        "--interface", interface,
        "--hours", str(hours)
    ]
    
    if headed:
        cmd.append("--headed")
    
    # Choose SSO method
    if method == 'profile':
        cmd.extend(["--profile", str(BROWSER_PROFILE_DIR)])
        print(f"🔐 Using persistent profile: {BROWSER_PROFILE_DIR}")
    elif method == 'state':
        cmd.extend(["--state", str(STATE_FILE)])
        print(f"🔐 Using state file: {STATE_FILE}")
    elif method == 'cdp':
        cmd.extend(["--cdp", "http://localhost:9222"])
        print("🔐 Using CDP attach (make sure browser is running with --remote-debugging-port=9222)")
    elif method == 'manual':
        cmd.extend(["--manual", "--headed"])
        print("🔐 Using manual authentication (interactive)")
    
    print(f"🚀 Running: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, check=True)
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"❌ Error running command: {e}")
        return False
    except KeyboardInterrupt:
        print("\n⏹️  Cancelled by user")
        return False

def setup_browser_for_cdp():
    """
    Instructions for setting up browser for CDP method
    """
    print("""
🔧 To use CDP method, start your browser with remote debugging:

For Chrome:
  google-chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome_debug

For Edge:
  microsoft-edge --remote-debugging-port=9222 --user-data-dir=/tmp/edge_debug

Then log into SolarWinds manually in that browser, and run this script with method='cdp'
    """)

def main():
    """Interactive mode"""
    print("🌟 SolarWinds PerfStack SSO - Easy Mode")
    print("=" * 45)
    
    # Get user input
    host = input("Enter device hostname or IP: ").strip()
    if not host:
        print("❌ Hostname required!")
        return
    
    interface = input("Enter interface name (e.g., Gi0/1, Po5): ").strip()
    if not interface:
        print("❌ Interface required!")
        return
    
    print("\nSSO Methods:")
    print("1. Persistent Profile (recommended)")
    print("2. State File") 
    print("3. CDP Attach")
    print("4. Manual Authentication")
    
    method_choice = input("\nChoose method (1-4): ").strip()
    method_map = {
        '1': 'profile',
        '2': 'state', 
        '3': 'cdp',
        '4': 'manual'
    }
    
    method = method_map.get(method_choice, 'profile')
    
    # Time window
    hours_input = input("Hours to look back (default 168 = 7 days): ").strip()
    hours = int(hours_input) if hours_input.isdigit() else 168
    
    # Headed mode
    headed_input = input("Show browser window? (y/N): ").strip().lower()
    headed = headed_input in ['y', 'yes']
    
    # Special handling for CDP
    if method == 'cdp':
        setup_browser_for_cdp()
        ready = input("Browser ready with remote debugging? (y/N): ").strip().lower()
        if ready not in ['y', 'yes']:
            print("⏹️  Setup browser first, then try again")
            return
    
    print(f"\n🎯 Generating PerfStack for:")
    print(f"   Device: {host}")
    print(f"   Interface: {interface}")
    print(f"   Method: {method}")
    print(f"   Time window: {hours} hours")
    print(f"   Show browser: {headed}")
    print()
    
    success = run_perfstack(host, interface, method, hours, headed)
    
    if success:
        print("\n✅ PerfStack screenshot generated successfully!")
        if method == 'profile':
            print(f"💡 Profile saved for future use: {BROWSER_PROFILE_DIR}")
        elif method == 'state':
            print(f"💡 State saved for future use: {STATE_FILE}")
    else:
        print("\n❌ Failed to generate screenshot")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Command line mode
        import argparse
        parser = argparse.ArgumentParser(description="Simple PerfStack SSO wrapper")
        parser.add_argument("host", help="Device hostname or IP")
        parser.add_argument("interface", help="Interface name")
        parser.add_argument("--method", choices=['profile', 'state', 'cdp', 'manual'], 
                           default='profile', help="SSO method")
        parser.add_argument("--hours", type=int, default=168, help="Hours to look back")
        parser.add_argument("--headed", action="store_true", help="Show browser")
        
        args = parser.parse_args()
        success = run_perfstack(args.host, args.interface, args.method, args.hours, args.headed)
        sys.exit(0 if success else 1)
    else:
        # Interactive mode
        main()
