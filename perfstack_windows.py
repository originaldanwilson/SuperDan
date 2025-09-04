#!/usr/bin/env python3
"""
Windows-Compatible SolarWinds PerfStack Solution
Works with existing browsers - no embedded browsers required
"""

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.parse
import webbrowser
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from tools import get_ad_creds

# Configuration
DEFAULT_SWIS = "https://orionApi.company.com:17774"
DEFAULT_WEB = "https://orion.company.com"
SWIS_QUERY_PATH = "/SolarWinds/InformationService/v3/Json/Query"

class WindowsPerfStackSolution:
    def __init__(self, swis_base=DEFAULT_SWIS, web_base=DEFAULT_WEB):
        self.swis_base = swis_base
        self.web_base = web_base
        self.session = requests.Session()
        self.session.verify = False
        requests.packages.urllib3.disable_warnings()

    def swis_query(self, user, password, swql):
        """Execute SWIS query with authentication"""
        url = self.swis_base.rstrip("/") + SWIS_QUERY_PATH
        try:
            r = self.session.get(
                url, 
                params={"query": swql}, 
                auth=(user, password), 
                timeout=30
            )
            r.raise_for_status()
            return r.json().get("results", [])
        except Exception as e:
            print(f"SWIS query error: {e}")
            return []

    def resolve_node_id(self, user, password, host):
        """Resolve hostname/IP to NodeID"""
        host_esc = host.replace("'", "''")
        
        if self._looks_like_ip(host):
            swql = f"SELECT TOP 1 NodeID FROM Orion.Nodes WHERE IPAddress='{host_esc}'"
        else:
            swql = (
                "SELECT TOP 1 NodeID FROM Orion.Nodes "
                f"WHERE Caption='{host_esc}' OR DNS='{host_esc}' "
                f"OR NodeName='{host_esc}' OR SysName='{host_esc}'"
            )
        
        results = self.swis_query(user, password, swql)
        if not results:
            raise RuntimeError(f"No node found for '{host}'")
        
        return int(results[0]["NodeID"])

    def resolve_interface_id(self, user, password, node_id, interface):
        """Resolve interface name to InterfaceID"""
        iface_esc = interface.replace("'", "''")
        swql = (
            "SELECT TOP 1 InterfaceID FROM Orion.NPM.Interfaces "
            f"WHERE NodeID={node_id} AND "
            f"(Name LIKE '%{iface_esc}%' OR Caption LIKE '%{iface_esc}%')"
        )
        
        results = self.swis_query(user, password, swql)
        if not results:
            raise RuntimeError(f"No interface containing '{interface}' on NodeID {node_id}")
        
        return int(results[0]["InterfaceID"])

    def _looks_like_ip(self, s):
        """Check if string looks like an IP address"""
        import ipaddress
        try:
            ipaddress.ip_address(s)
            return True
        except ValueError:
            return False

    def build_time_window(self, hours):
        """Build time window for PerfStack"""
        # Get current time and ensure we have enough precision
        now = datetime.now(timezone.utc)
        
        # Calculate start time - ensure it's significantly different from end
        start = now - timedelta(hours=hours)
        
        # For very short time windows, ensure at least 1 minute difference
        if hours < 1:
            start = now - timedelta(hours=1)  # Minimum 1 hour window
            hours = 1
            print(f"⚠️  Adjusted to minimum 1-hour window")
        
        # Try different SolarWinds time formats (some versions are picky)
        # Format 1: Full ISO with milliseconds
        start_str = start.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        end_str = now.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        
        # Alternative format if the above doesn't work (uncomment if needed):
        # start_str = start.strftime("%Y-%m-%dT%H:%M:%SZ")
        # end_str = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        # Debug output
        print(f"🕐 Time window calculation:")
        print(f"   Start: {start_str} ({hours} hours ago)")
        print(f"   End:   {end_str} (now)")
        print(f"   Duration: {hours} hours")
        
        # Double-check times are different
        if start_str == end_str:
            print(f"⚠️  ERROR: Start and end times are still identical!")
            # Force a different start time
            start = now - timedelta(hours=hours, minutes=1)
            start_str = start.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            print(f"   Forced adjustment - Start: {start_str}")
        
        return (start_str, end_str)

    def build_perfstack_url(self, interface_id, time_from, time_to, metrics=None):
        """Build PerfStack URL with explicit time window"""
        if metrics is None:
            metrics = [
                f"Orion.NPM.Interfaces_{interface_id}-Orion.NPM.InterfaceTraffic.InAveragebps",
                f"Orion.NPM.Interfaces_{interface_id}-Orion.NPM.InterfaceTraffic.OutAveragebps"
            ]
        
        charts = "0_" + ",".join(metrics) + ";"
        
        # Debug the time parameters
        print(f"🔗 URL parameters:")
        print(f"   timeFrom: {time_from}")
        print(f"   timeTo:   {time_to}")
        print(f"   charts:   {charts}")
        
        params = {
            "charts": charts,
            "timeFrom": time_from,
            "timeTo": time_to
        }
        
        # Build URL with proper encoding
        base_url = self.web_base.rstrip("/") + "/apps/perfstack/?"
        query_string = urllib.parse.urlencode(params, safe='-_,:;')
        full_url = base_url + query_string
        
        print(f"🌐 Full URL: {full_url}")
        print()
        
        return full_url

    def build_login_url(self, return_url):
        """Build login URL with return path"""
        base = self.web_base.rstrip("/")
        if return_url.startswith(base):
            path_query = return_url[len(base):]
        else:
            path_query = return_url
        
        return f"{base}/Orion/Login.aspx?ReturnUrl={urllib.parse.quote(path_query, safe='')}"

    def open_in_browser(self, url, browser_choice=None):
        """Open URL in system browser"""
        print(f"🌐 Opening URL in browser: {url}")
        
        if browser_choice:
            # Try to use specific browser
            browsers = {
                'chrome': ['chrome', 'google-chrome', 'chromium'],
                'edge': ['msedge', 'microsoft-edge'],
                'firefox': ['firefox'],
                'ie': ['iexplore']
            }
            
            browser_cmds = browsers.get(browser_choice.lower(), [browser_choice])
            
            for cmd in browser_cmds:
                try:
                    if sys.platform.startswith('win'):
                        # Windows
                        subprocess.Popen([cmd, url], shell=True)
                    else:
                        # Linux/Mac
                        subprocess.Popen([cmd, url])
                    print(f"✅ Opened in {cmd}")
                    return True
                except (subprocess.SubprocessError, FileNotFoundError):
                    continue
            
            print(f"⚠️  Could not find {browser_choice}, using default browser")
        
        # Fall back to default system browser
        try:
            webbrowser.open(url)
            print("✅ Opened in default browser")
            return True
        except Exception as e:
            print(f"❌ Could not open browser: {e}")
            return False

    def create_batch_file(self, url, filename="open_perfstack.bat"):
        """Create a Windows batch file to open the URL"""
        batch_content = f'''@echo off
echo Opening SolarWinds PerfStack...
echo URL: {url}
echo.
start "" "{url}"
echo.
echo PerfStack should now be opening in your default browser.
echo Please log in if needed, then take a screenshot manually.
pause
'''
        
        try:
            with open(filename, 'w') as f:
                f.write(batch_content)
            print(f"✅ Created batch file: {filename}")
            print(f"   You can double-click {filename} to open the PerfStack URL")
            return True
        except Exception as e:
            print(f"❌ Could not create batch file: {e}")
            return False

    def create_powershell_script(self, url, filename="Open-PerfStack.ps1"):
        """Create a PowerShell script to open the URL"""
        ps_content = f'''# SolarWinds PerfStack Opener
Write-Host "Opening SolarWinds PerfStack..." -ForegroundColor Green
Write-Host "URL: {url}" -ForegroundColor Yellow
Write-Host ""

# Try to open in different browsers
$browsers = @(
    "msedge",
    "chrome", 
    "firefox",
    "iexplore"
)

$opened = $false
foreach ($browser in $browsers) {{
    try {{
        Start-Process $browser "{url}"
        Write-Host "✅ Opened in $browser" -ForegroundColor Green
        $opened = $true
        break
    }}
    catch {{
        continue
    }}
}}

if (-not $opened) {{
    # Fall back to default browser
    try {{
        Start-Process "{url}"
        Write-Host "✅ Opened in default browser" -ForegroundColor Green
    }}
    catch {{
        Write-Host "❌ Could not open browser" -ForegroundColor Red
        Write-Host "Please manually navigate to:" -ForegroundColor Yellow
        Write-Host "{url}" -ForegroundColor Cyan
    }}
}}

Write-Host ""
Write-Host "Please log in if needed, then take a screenshot manually."
Read-Host "Press Enter to continue"
'''
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(ps_content)
            print(f"✅ Created PowerShell script: {filename}")
            print(f"   Run in PowerShell: .\\{filename}")
            return True
        except Exception as e:
            print(f"❌ Could not create PowerShell script: {e}")
            return False

    def create_url_file(self, url, filename="PerfStack.url"):
        """Create a Windows .url file"""
        url_content = f'''[InternetShortcut]
URL={url}
'''
        
        try:
            with open(filename, 'w') as f:
                f.write(url_content)
            print(f"✅ Created URL file: {filename}")
            print(f"   Double-click {filename} to open in browser")
            return True
        except Exception as e:
            print(f"❌ Could not create URL file: {e}")
            return False

    def save_url_info(self, host, interface, url, hours, filename="perfstack_info.txt"):
        """Save URL and device info to text file"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        info_content = f'''SolarWinds PerfStack Information
Generated: {timestamp}

Device: {host}
Interface: {interface}
Time Window: {hours} hours
URL: {url}

Instructions:
1. Copy the URL above
2. Open it in your browser
3. Log in to SolarWinds if needed
4. Take a screenshot of the PerfStack view
5. Save the screenshot with a descriptive filename

Note: This URL includes the exact time window, so the chart will show
the requested time period automatically.
'''
        
        try:
            with open(filename, 'w') as f:
                f.write(info_content)
            print(f"✅ Saved URL information to: {filename}")
            return True
        except Exception as e:
            print(f"❌ Could not save URL info: {e}")
            return False


def main():
    parser = argparse.ArgumentParser(
        description="Windows-compatible SolarWinds PerfStack solution",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Windows Solutions (no embedded browsers required):
  1. --open           : Open URL directly in system browser
  2. --batch          : Create Windows batch file
  3. --powershell     : Create PowerShell script  
  4. --url-file       : Create .url shortcut file
  5. --info-only      : Just save URL to text file

Examples:
  # Open directly in browser
  python perfstack_windows.py --host router01 --interface Gi0/1 --open

  # Create batch file for Windows
  python perfstack_windows.py --host 10.1.1.1 --interface Po5 --batch

  # Create PowerShell script
  python perfstack_windows.py --host switch01 --interface Ethernet1/1 --powershell

  # Just get the URL
  python perfstack_windows.py --host router01 --interface Gi0/1 --info-only
        """
    )
    
    # Required arguments
    parser.add_argument("--host", required=True, 
                       help="Hostname/IP/DNS name (IP most reliable)")
    parser.add_argument("--interface", required=True, 
                       help="Interface name (e.g., GigabitEthernet0/1, Po5)")
    
    # Optional arguments
    parser.add_argument("--hours", type=int, default=168,
                       help="Time window in hours (default: 168 = 7 days)")
    
    # Output method arguments
    action_group = parser.add_mutually_exclusive_group()
    action_group.add_argument("--open", action="store_true",
                             help="Open URL directly in system browser")
    action_group.add_argument("--batch", action="store_true",
                             help="Create Windows batch file (.bat)")
    action_group.add_argument("--powershell", action="store_true", 
                             help="Create PowerShell script (.ps1)")
    action_group.add_argument("--url-file", action="store_true",
                             help="Create Windows URL shortcut (.url)")
    action_group.add_argument("--info-only", action="store_true",
                             help="Save URL information to text file only")
    
    parser.add_argument("--browser", choices=['chrome', 'edge', 'firefox', 'ie'],
                       help="Preferred browser (only with --open)")
    
    args = parser.parse_args()
    
    # Default action if none specified
    if not any([args.open, args.batch, args.powershell, args.url_file, args.info_only]):
        args.open = True  # Default to opening in browser
    
    try:
        print("🔍 Windows-Compatible PerfStack Solution")
        print("=" * 45)
        
        # Initialize SolarWinds API client
        sw = WindowsPerfStackSolution(DEFAULT_SWIS, DEFAULT_WEB)
        
        # Get credentials
        print("🔑 Getting credentials...")
        user, password = get_ad_creds()
        
        # Resolve node and interface
        print(f"🔍 Resolving node: {args.host}")
        node_id = sw.resolve_node_id(user, password, args.host)
        print(f"   NodeID: {node_id}")
        
        print(f"🔍 Resolving interface: {args.interface}")
        iface_id = sw.resolve_interface_id(user, password, node_id, args.interface)
        print(f"   InterfaceID: {iface_id}")
        
        # Build time window and URLs
        time_from, time_to = sw.build_time_window(args.hours)
        perfstack_url = sw.build_perfstack_url(iface_id, time_from, time_to)
        login_url = sw.build_login_url(perfstack_url)
        
        print(f"🕐 Time window: {time_from} to {time_to}")
        print()
        
        # Create filename base
        safe_host = args.host.replace(".", "_").replace(":", "_")
        safe_interface = args.interface.replace("/", "_").replace("\\", "_")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_filename = f"perfstack_{safe_host}_{safe_interface}_{timestamp}"
        
        success = True
        
        # Execute chosen action
        if args.open:
            print("🌐 Opening URL in browser...")
            success = sw.open_in_browser(login_url, args.browser)
            
        elif args.batch:
            batch_filename = f"{base_filename}.bat"
            print("📝 Creating Windows batch file...")
            success = sw.create_batch_file(login_url, batch_filename)
            
        elif args.powershell:
            ps_filename = f"{base_filename}.ps1"
            print("📝 Creating PowerShell script...")
            success = sw.create_powershell_script(login_url, ps_filename)
            
        elif args.url_file:
            url_filename = f"{base_filename}.url"
            print("📝 Creating URL shortcut file...")
            success = sw.create_url_file(login_url, url_filename)
            
        elif args.info_only:
            info_filename = f"{base_filename}_info.txt"
            print("📝 Saving URL information...")
            success = sw.save_url_info(args.host, args.interface, login_url, args.hours, info_filename)
        
        # Always save URL info for reference
        if success and not args.info_only:
            info_filename = f"{base_filename}_info.txt"
            sw.save_url_info(args.host, args.interface, login_url, args.hours, info_filename)
        
        if success:
            print()
            print("✅ Success! Next steps:")
            print("   1. Log into SolarWinds in the browser")
            print("   2. Wait for the PerfStack charts to load")
            print("   3. Take a screenshot (Windows: Windows+Shift+S)")
            print("   4. Save with a descriptive filename")
            print()
            print(f"💡 Direct URL (for copy/paste):")
            print(f"   {login_url}")
            
            # Show file with permissions if available
            try:
                from tools import print_file_with_permissions
                if args.info_only or not args.open:
                    created_files = []
                    if args.batch:
                        created_files.append(f"{base_filename}.bat")
                    elif args.powershell:
                        created_files.append(f"{base_filename}.ps1")
                    elif args.url_file:
                        created_files.append(f"{base_filename}.url")
                    created_files.append(f"{base_filename}_info.txt")
                    
                    print(f"\n📁 Created files:")
                    for file in created_files:
                        if os.path.exists(file):
                            print_file_with_permissions(file)
            except ImportError:
                pass
        else:
            print("❌ Failed to complete the operation")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n⏹️  Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


def test_time_window():
    """Test function to debug time window calculation"""
    print("Testing time window calculation...")
    sw = WindowsPerfStackSolution()
    
    for hours in [1, 24, 168]:
        print(f"\nTesting {hours} hour window:")
        start_str, end_str = sw.build_time_window(hours)
        print(f"  Start: {start_str}")
        print(f"  End:   {end_str}")
        print(f"  Same?  {start_str == end_str}")

if __name__ == "__main__":
    # Check if this is a test run
    if len(sys.argv) > 1 and sys.argv[1] == '--test-time':
        test_time_window()
    else:
        main()
