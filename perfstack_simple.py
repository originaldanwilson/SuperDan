#!/usr/bin/env python3
"""
Simple PerfStack launcher - just open the basic URL without time parameters
Since SolarWinds ignores our time parameters anyway, just open the interface
and let the user manually adjust the time frame.
"""

import argparse
import sys
import urllib.parse
import webbrowser
from datetime import datetime
from tools import get_ad_creds

# Configuration
DEFAULT_SWIS = "https://orionApi.company.com:17774"
DEFAULT_WEB = "https://orion.company.com"

def main():
    parser = argparse.ArgumentParser(
        description="Simple PerfStack launcher - opens basic URL without time hassles"
    )
    parser.add_argument("--host", required=True, help="Hostname/IP")
    parser.add_argument("--interface", required=True, help="Interface name")
    parser.add_argument("--interface-id", type=int, help="Skip resolution, use this InterfaceID directly")
    parser.add_argument("--screenshot", action="store_true", help="Take screenshot after opening PerfStack (requires mss: pip install mss)")
    
    args = parser.parse_args()
    
    try:
        if args.interface_id:
            iface_id = args.interface_id
            print(f"📊 Using InterfaceID: {iface_id}")
        else:
            # Import and resolve interface ID
            from perfstack_windows import WindowsPerfStackSolution
            sw = WindowsPerfStackSolution(DEFAULT_SWIS, DEFAULT_WEB)
            
            print("🔑 Getting credentials...")
            user, password = get_ad_creds()
            
            print(f"🔍 Resolving node: {args.host}")
            node_id = sw.resolve_node_id(user, password, args.host)
            print(f"   NodeID: {node_id}")
            
            print(f"🔍 Resolving interface: {args.interface}")
            iface_id = sw.resolve_interface_id(user, password, node_id, args.interface)
            print(f"   InterfaceID: {iface_id}")
        
        # Build PerfStack URL with ACTUAL working format from browser
        metrics = [
            f"0_Orion.NPM.Interfaces_{iface_id}-Orion.NPM.InterfaceTraffic.InAveragebps",
            f"0_Orion.NPM.Interfaces_{iface_id}-Orion.NPM.InterfaceTraffic.OutAveragebps"
        ]
        charts = ",".join(metrics)  # No semicolon, just comma-separated
        
        # Use the ACTUAL working parameters from manual browser test
        params = {
            "presetTime": "last7Days",  # Capital D - this is what works!
            "charts": charts
        }
        
        base_url = DEFAULT_WEB.rstrip("/") + "/apps/perfstack/?"
        query_string = urllib.parse.urlencode(params, safe='-_,:;')
        perfstack_url = base_url + query_string
        
        # Build login URL
        path_query = perfstack_url[len(DEFAULT_WEB.rstrip("/")):]
        login_url = f"{DEFAULT_WEB.rstrip('/')}/Orion/Login.aspx?ReturnUrl={urllib.parse.quote(path_query, safe='')}"
        
        print()
        print("🌐 Opening PerfStack with 7-day time window...")
        print(f"📊 Interface ID: {iface_id}")
        print(f"🔗 URL: {login_url}")
        print()
        print("📝 Steps:")
        print("   1. Log into SolarWinds")
        print("   2. PerfStack should load with 7-day data automatically")
        print("   3. Take your screenshot")
        print()
        
        # Open in browser
        webbrowser.open(login_url)
        print("✅ PerfStack opened with correct format - should show 7 days of data!")
        
        # Optional screenshot
        if args.screenshot:
            try:
                from tools import take_screenshot
                print()
                print("📷 Screenshot option enabled...")
                input("Press Enter after logging in and PerfStack loads to take screenshot...")
                
                # Generate screenshot filename
                safe_host = args.host.replace(".", "_").replace(":", "_")
                safe_interface = args.interface.replace("/", "_").replace("\\", "_")
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"perfstack_{safe_host}_{safe_interface}_{timestamp}"
                
                screenshot_path = take_screenshot(filename)
                print(f"✅ Screenshot saved: {screenshot_path}")
                
            except ImportError as e:
                print(f"⚠️  Screenshot failed: {e}")
                print("Install with: pip install mss")
            except Exception as e:
                print(f"⚠️  Screenshot failed: {e}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
