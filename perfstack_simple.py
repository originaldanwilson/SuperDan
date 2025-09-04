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
        
        # Build simple PerfStack URL with just the interface metrics
        metrics = [
            f"Orion.NPM.Interfaces_{iface_id}-Orion.NPM.InterfaceTraffic.InAveragebps",
            f"Orion.NPM.Interfaces_{iface_id}-Orion.NPM.InterfaceTraffic.OutAveragebps"
        ]
        charts = "0_" + ",".join(metrics) + ";"
        
        # Just the basic PerfStack URL - no time parameters
        params = {"charts": charts}
        
        base_url = DEFAULT_WEB.rstrip("/") + "/apps/perfstack/?"
        query_string = urllib.parse.urlencode(params, safe='-_,:;')
        perfstack_url = base_url + query_string
        
        # Build login URL
        path_query = perfstack_url[len(DEFAULT_WEB.rstrip("/")):]
        login_url = f"{DEFAULT_WEB.rstrip('/')}/Orion/Login.aspx?ReturnUrl={urllib.parse.quote(path_query, safe='')}"
        
        print()
        print("🌐 Opening PerfStack (no time parameters)...")
        print(f"📊 Interface ID: {iface_id}")
        print(f"🔗 URL: {login_url}")
        print()
        print("📝 Manual steps:")
        print("   1. Log into SolarWinds")
        print("   2. Wait for PerfStack to load")
        print("   3. Manually change time frame to 7 days using the dropdown")
        print("   4. Take your screenshot")
        print()
        
        # Open in browser
        webbrowser.open(login_url)
        print("✅ PerfStack opened in browser - manually adjust time frame to 7 days")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
