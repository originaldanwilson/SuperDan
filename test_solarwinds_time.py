#!/usr/bin/env python3
"""
Test different time formats with SolarWinds PerfStack
Try to determine which format works best
"""

import argparse
import sys
import webbrowser
from datetime import datetime, timedelta, timezone
import urllib.parse
from tools import get_ad_creds
from perfstack_windows import WindowsPerfStackSolution

DEFAULT_SWIS = "https://orionApi.company.com:17774"
DEFAULT_WEB = "https://orion.company.com"

def test_time_formats(host, interface, hours=168, interface_id=None):
    """Test different time format approaches"""
    
    print(f"🧪 Testing Time Formats for SolarWinds PerfStack")
    print("=" * 55)
    
    if not interface_id:
        # Get interface ID first
        sw = WindowsPerfStackSolution(DEFAULT_SWIS, DEFAULT_WEB)
        user, password = get_ad_creds()
        
        print(f"🔍 Resolving node: {host}")
        node_id = sw.resolve_node_id(user, password, host)
        print(f"   NodeID: {node_id}")
        
        print(f"🔍 Resolving interface: {interface}")
        interface_id = sw.resolve_interface_id(user, password, node_id, interface)
        print(f"   InterfaceID: {interface_id}")
        print()
    
    # Calculate times
    now = datetime.now(timezone.utc)
    start = now - timedelta(hours=hours)
    
    print(f"⏰ Time Window: {hours} hours")
    print(f"   Start: {start}")
    print(f"   End:   {now}")
    print()
    
    # Test different formats
    time_formats = [
        {
            'name': 'ISO with Z (current)',
            'start': start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            'end': now.strftime("%Y-%m-%dT%H:%M:%SZ")
        },
        {
            'name': 'ISO with milliseconds', 
            'start': start.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            'end': now.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        },
        {
            'name': 'Epoch milliseconds',
            'start': str(int(start.timestamp() * 1000)),
            'end': str(int(now.timestamp() * 1000))
        },
        {
            'name': 'Simple date-time',
            'start': start.strftime("%Y-%m-%d %H:%M:%S"),
            'end': now.strftime("%Y-%m-%d %H:%M:%S")
        }
    ]
    
    metrics = [
        f"Orion.NPM.Interfaces_{interface_id}-Orion.NPM.InterfaceTraffic.InAveragebps",
        f"Orion.NPM.Interfaces_{interface_id}-Orion.NPM.InterfaceTraffic.OutAveragebps"
    ]
    charts = "0_" + ",".join(metrics) + ";"
    
    for i, fmt in enumerate(time_formats, 1):
        print(f"🌐 Format {i}: {fmt['name']}")
        print(f"   Start: {fmt['start']}")
        print(f"   End:   {fmt['end']}")
        
        # Build URL
        params = {
            "charts": charts,
            "timeFrom": fmt['start'],
            "timeTo": fmt['end']
        }
        
        base_url = DEFAULT_WEB.rstrip("/") + "/apps/perfstack/?"
        
        # Test different URL encoding approaches
        query_string = urllib.parse.urlencode(params, safe='-_,:;')
        full_url = base_url + query_string
        
        # Build login URL
        path_query = full_url[len(DEFAULT_WEB.rstrip("/")):]
        login_url = f"{DEFAULT_WEB.rstrip('/')}/Orion/Login.aspx?ReturnUrl={urllib.parse.quote(path_query, safe='')}"
        
        print(f"   URL: {login_url}")
        
        # Offer to open this format
        choice = input(f"   ❓ Open Format {i} in browser? (y/n/q): ").lower().strip()
        if choice == 'y':
            print(f"   🌐 Opening Format {i}...")
            webbrowser.open(login_url)
            input("   📊 Press Enter after checking if the time window is correct...")
        elif choice == 'q':
            print("   ⏹️  Quitting test...")
            break
        print()

def main():
    parser = argparse.ArgumentParser(description="Test SolarWinds time formats")
    parser.add_argument("--host", required=True, help="Hostname/IP")
    parser.add_argument("--interface", required=True, help="Interface name")
    parser.add_argument("--hours", type=int, default=168, help="Hours (default: 168)")
    parser.add_argument("--interface-id", type=int, help="Skip resolution, use this InterfaceID")
    
    args = parser.parse_args()
    
    try:
        test_time_formats(args.host, args.interface, args.hours, args.interface_id)
    except KeyboardInterrupt:
        print("\n⏹️  Test cancelled")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
