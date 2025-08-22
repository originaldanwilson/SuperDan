#!/usr/bin/env python3
"""
Direct DISR/DCSR Port-Channel Monitor
Fast version that directly targets known switches and port-channels
No searching required - configure your switch names directly
"""

import requests
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import urllib3
import argparse
import csv
from tabulate import tabulate

# Disable SSL warnings if needed
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# CONFIGURATION: Update these with your actual switch names
DEFAULT_SWITCHES = {
    'DISR': [
        'your-disr-switch-1',  # Replace with actual DISR switch names
        'your-disr-switch-2',
    ],
    'DCSR': [
        'your-dcsr-switch-1',  # Replace with actual DCSR switch names
        'your-dcsr-switch-2',
    ]
}

DEFAULT_PORT_CHANNELS = [5, 25]  # Port-channel numbers to monitor

class DirectSolarWindsMonitor:
    def __init__(self, server_url: str, username: str, password: str, verify_ssl: bool = True):
        """Initialize Direct SolarWinds Monitor"""
        self.server_url = server_url.rstrip('/')
        self.username = username
        self.password = password
        self.verify_ssl = verify_ssl
        self.session = requests.Session()
        self.session.auth = (username, password)
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })

    def _make_request(self, endpoint: str, method: str = 'POST', data: Dict = None) -> Dict:
        """Make HTTP request to SolarWinds API"""
        url = f"{self.server_url}/SolarWinds/InformationService/v3/Json/{endpoint}"
        
        try:
            response = self.session.post(url, json=data, verify=self.verify_ssl)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error making request to {url}: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response status: {e.response.status_code}")
                print(f"Response text: {e.response.text}")
            raise

    def get_switch_interfaces(self, switch_names: List[str], port_channels: List[int]) -> List[Dict]:
        """Get specific port-channel interfaces from known switches"""
        query = "Query"
        
        # Build switch name conditions
        switch_conditions = []
        for switch in switch_names:
            switch_conditions.append(f"UPPER(n.Caption) LIKE UPPER('%{switch}%') OR UPPER(n.SysName) LIKE UPPER('%{switch}%')")
        
        # Build port-channel conditions
        pc_conditions = []
        for pc in port_channels:
            pc_conditions.extend([
                f"UPPER(i.Name) LIKE UPPER('%PORT-CHANNEL{pc}%')",
                f"UPPER(i.Name) LIKE UPPER('%PO{pc}%')",
                f"UPPER(i.Caption) LIKE UPPER('%PORT-CHANNEL{pc}%')"
            ])
        
        switch_clause = " OR ".join(switch_conditions)
        pc_clause = " OR ".join(pc_conditions)
        
        data = {
            "query": f"""
                SELECT 
                    i.InterfaceID,
                    i.NodeID,
                    i.Name,
                    i.Caption,
                    i.InterfaceAlias,
                    i.Speed,
                    n.Caption as NodeName,
                    n.SysName as SystemName
                FROM Orion.NPM.Interfaces i
                JOIN Orion.Nodes n ON i.NodeID = n.NodeID
                WHERE i.Status = 1
                AND ({switch_clause})
                AND ({pc_clause})
                ORDER BY n.Caption, i.Name
            """
        }
        
        try:
            result = self._make_request(query, 'POST', data)
            return result.get('results', [])
        except Exception as e:
            print(f"Error getting switch interfaces: {e}")
            return []

    def get_interface_statistics(self, interface_id: int, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Get interface statistics for the specified time period"""
        query = "Query"
        
        start_str = start_date.strftime('%Y-%m-%dT%H:%M:%S.000Z')
        end_str = end_date.strftime('%Y-%m-%dT%H:%M:%S.000Z')
        
        data = {
            "query": f"""
                SELECT 
                    DateTime,
                    InterfaceID,
                    InBitsPerSec,
                    OutBitsPerSec,
                    InPercentUtil,
                    OutPercentUtil,
                    InTotalBytes,
                    OutTotalBytes
                FROM Orion.NPM.InterfaceTraffic 
                WHERE InterfaceID = {interface_id} 
                AND DateTime >= '{start_str}' 
                AND DateTime <= '{end_str}'
                ORDER BY DateTime ASC
            """
        }
        
        try:
            result = self._make_request(query, 'POST', data)
            return result.get('results', [])
        except Exception as e:
            print(f"Error getting statistics for interface {interface_id}: {e}")
            return []

    def calculate_summary(self, statistics: List[Dict]) -> Dict:
        """Calculate usage summary from statistics"""
        if not statistics:
            return {}
        
        total_in_bytes = 0
        total_out_bytes = 0
        max_in_percent = 0
        max_out_percent = 0
        avg_in_percent = 0
        avg_out_percent = 0
        max_in_bps = 0
        max_out_bps = 0
        
        valid_entries = 0
        
        for stat in statistics:
            in_bytes = stat.get('InTotalBytes', 0) or 0
            out_bytes = stat.get('OutTotalBytes', 0) or 0
            total_in_bytes += in_bytes
            total_out_bytes += out_bytes
            
            in_percent = stat.get('InPercentUtil', 0) or 0
            out_percent = stat.get('OutPercentUtil', 0) or 0
            
            max_in_percent = max(max_in_percent, in_percent)
            max_out_percent = max(max_out_percent, out_percent)
            avg_in_percent += in_percent
            avg_out_percent += out_percent
            
            in_bps = stat.get('InBitsPerSec', 0) or 0
            out_bps = stat.get('OutBitsPerSec', 0) or 0
            
            max_in_bps = max(max_in_bps, in_bps)
            max_out_bps = max(max_out_bps, out_bps)
            
            valid_entries += 1
        
        avg_in_percent = avg_in_percent / valid_entries if valid_entries > 0 else 0
        avg_out_percent = avg_out_percent / valid_entries if valid_entries > 0 else 0
        
        # Calculate 95th percentile
        sorted_in_util = sorted([s.get('InPercentUtil', 0) or 0 for s in statistics])
        sorted_out_util = sorted([s.get('OutPercentUtil', 0) or 0 for s in statistics])
        
        percentile_95_index = int(len(sorted_in_util) * 0.95)
        percentile_95_in = sorted_in_util[percentile_95_index] if sorted_in_util else 0
        percentile_95_out = sorted_out_util[percentile_95_index] if sorted_out_util else 0
        
        return {
            'total_in_bytes': total_in_bytes,
            'total_out_bytes': total_out_bytes,
            'total_bytes': total_in_bytes + total_out_bytes,
            'max_in_percent': max_in_percent,
            'max_out_percent': max_out_percent,
            'avg_in_percent': avg_in_percent,
            'avg_out_percent': avg_out_percent,
            'percentile_95_in': percentile_95_in,
            'percentile_95_out': percentile_95_out,
            'max_in_bps': max_in_bps,
            'max_out_bps': max_out_bps,
            'data_points': valid_entries
        }

def format_bytes(bytes_value: int) -> str:
    """Format bytes into human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB', 'PB']:
        if bytes_value < 1024.0:
            return f"{bytes_value:.2f} {unit}"
        bytes_value /= 1024.0
    return f"{bytes_value:.2f} EB"

def format_bps(bps_value: int) -> str:
    """Format bits per second into human readable format"""
    for unit in ['bps', 'Kbps', 'Mbps', 'Gbps', 'Tbps']:
        if bps_value < 1000.0:
            return f"{bps_value:.2f} {unit}"
        bps_value /= 1000.0
    return f"{bps_value:.2f} Pbps"

def identify_switch_type(node_name: str) -> str:
    """Identify switch type from node name"""
    name_upper = node_name.upper()
    if 'DISR' in name_upper:
        return 'DISR'
    elif 'DCSR' in name_upper:
        return 'DCSR'
    else:
        return 'Unknown'

def identify_port_channel_type(interface_name: str) -> str:
    """Identify the port-channel type from interface name"""
    name_lower = interface_name.lower()
    
    if 'port-channel5' in name_lower or 'po5' in name_lower:
        return "Port-Channel 5"
    elif 'port-channel25' in name_lower or 'po25' in name_lower:
        return "Port-Channel 25"
    else:
        return f"Port-Channel ({interface_name})"

def generate_direct_report(monitor: DirectSolarWindsMonitor, switches: Dict[str, List[str]], 
                          port_channels: List[int], days: int = 7, 
                          output_format: str = 'table', output_file: Optional[str] = None) -> None:
    """Generate direct report for specified switches and port-channels"""
    
    print(f"🎯 Direct DISR/DCSR Port-Channel Report ({days} days)")
    print("=" * 60)
    
    # Show configuration
    total_switches = sum(len(sw_list) for sw_list in switches.values())
    print(f"📋 Configuration:")
    print(f"   - DISR switches: {len(switches.get('DISR', []))}")
    print(f"   - DCSR switches: {len(switches.get('DCSR', []))}")
    print(f"   - Port-channels: {', '.join(map(str, port_channels))}")
    print(f"   - Total targets: {total_switches} switches")
    
    # Calculate date range
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    print(f"📅 Date range: {start_date.strftime('%Y-%m-%d %H:%M')} to {end_date.strftime('%Y-%m-%d %H:%M')} UTC")
    
    report_data = []
    
    # Process each switch type
    for switch_type, switch_list in switches.items():
        if not switch_list:
            continue
            
        print(f"\n🔍 Querying {switch_type} switches: {', '.join(switch_list)}")
        
        # Get interfaces for this switch type
        interfaces = monitor.get_switch_interfaces(switch_list, port_channels)
        
        if not interfaces:
            print(f"   ⚠️  No interfaces found for {switch_type} switches")
            continue
        
        print(f"   ✅ Found {len(interfaces)} interfaces")
        
        # Process each interface
        for i, interface in enumerate(interfaces, 1):
            interface_id = interface['InterfaceID']
            interface_name = interface.get('Name', 'Unknown')
            node_name = interface.get('NodeName', 'Unknown')
            speed = interface.get('Speed', 0)
            
            actual_switch_type = identify_switch_type(node_name)
            pc_type = identify_port_channel_type(interface_name)
            
            print(f"   [{i}/{len(interfaces)}] {node_name} - {pc_type}")
            
            # Get statistics
            statistics = monitor.get_interface_statistics(interface_id, start_date, end_date)
            
            if not statistics:
                print(f"      ⚠️  No statistics found")
                continue
            
            print(f"      📊 {len(statistics)} data points")
            
            # Calculate summary
            summary = monitor.calculate_summary(statistics)
            
            if summary and summary['data_points'] > 0:
                # Determine status
                max_util = max(summary['max_in_percent'], summary['max_out_percent'])
                
                if max_util > 80:
                    status = "🔴 HIGH"
                elif max_util > 60:
                    status = "🟡 MEDIUM"
                else:
                    status = "🟢 LOW"
                
                report_data.append({
                    'Switch': node_name,
                    'Switch Type': actual_switch_type,
                    'Port-Channel': pc_type,
                    'Interface Name': interface_name,
                    'Speed': format_bps(speed) if speed else 'Unknown',
                    'Status': status,
                    'Total Data (In)': format_bytes(summary['total_in_bytes']),
                    'Total Data (Out)': format_bytes(summary['total_out_bytes']),
                    'Total Data': format_bytes(summary['total_bytes']),
                    'Max Util (In)': f"{summary['max_in_percent']:.1f}%",
                    'Max Util (Out)': f"{summary['max_out_percent']:.1f}%",
                    'Avg Util (In)': f"{summary['avg_in_percent']:.1f}%",
                    'Avg Util (Out)': f"{summary['avg_out_percent']:.1f}%",
                    '95th Percentile (In)': f"{summary['percentile_95_in']:.1f}%",
                    '95th Percentile (Out)': f"{summary['percentile_95_out']:.1f}%",
                    'Peak Speed (In)': format_bps(summary['max_in_bps']),
                    'Peak Speed (Out)': format_bps(summary['max_out_bps']),
                    'Data Points': summary['data_points']
                })
                
                print(f"      ✅ {status} - Max: {max_util:.1f}%")
            else:
                print(f"      ❌ No valid data")
    
    if not report_data:
        print("\n❌ No data found for any interfaces!")
        return
    
    # Sort results
    report_data.sort(key=lambda x: (x['Switch Type'], x['Switch'], x['Port-Channel']))
    
    print(f"\n📈 Generated report for {len(report_data)} interfaces")
    
    # Output report
    if output_format.lower() == 'csv':
        output_csv_report(report_data, output_file, days)
    elif output_format.lower() == 'json':
        output_json_report(report_data, output_file, days)
    else:
        output_table_report(report_data, output_file, days)

def output_table_report(data: List[Dict], output_file: Optional[str] = None, days: int = 7) -> None:
    """Output table report"""
    if not data:
        return
    
    table_data = []
    for row in data:
        table_data.append([
            row['Switch'][:12] + '...' if len(row['Switch']) > 12 else row['Switch'],
            row['Switch Type'],
            row['Port-Channel'].replace('Port-Channel ', 'PC'),
            row['Total Data'],
            row['Max Util (In)'],
            row['Max Util (Out)'],
            row['Status'].split()[0]  # Just the emoji
        ])
    
    headers = ['Switch', 'Type', 'Port-Channel', 'Total Data', 'Max In%', 'Max Out%', 'Status']
    table = tabulate(table_data, headers=headers, tablefmt='grid')
    
    summary_text = f"""
Direct DISR/DCSR Port-Channel Report ({days} days)
{'=' * 55}

Summary:
- Total interfaces: {len(data)}
- DISR interfaces: {len([d for d in data if d['Switch Type'] == 'DISR'])}
- DCSR interfaces: {len([d for d in data if d['Switch Type'] == 'DCSR'])}
- PC5 interfaces: {len([d for d in data if 'Port-Channel 5' in d['Port-Channel']])}
- PC25 interfaces: {len([d for d in data if 'Port-Channel 25' in d['Port-Channel']])}

{table}

Status: 🟢 LOW (<60%) | 🟡 MEDIUM (60-80%) | 🔴 HIGH (>80%)
"""
    
    if output_file:
        with open(output_file, 'w') as f:
            f.write(summary_text)
        print(f"\n📄 Report saved to {output_file}")
    else:
        print(summary_text)

def output_csv_report(data: List[Dict], output_file: Optional[str] = None, days: int = 7) -> None:
    """Output CSV report"""
    if not data:
        return
    
    filename = output_file or f'direct_disr_dcsr_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)
    
    print(f"📄 CSV report saved to {filename}")

def output_json_report(data: List[Dict], output_file: Optional[str] = None, days: int = 7) -> None:
    """Output JSON report"""
    if not data:
        return
    
    filename = output_file or f'direct_disr_dcsr_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, default=str)
    
    print(f"📄 JSON report saved to {filename}")

def main():
    parser = argparse.ArgumentParser(
        description='Direct DISR/DCSR port-channel usage report (no search required)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 disr_dcsr_direct_monitor.py --server https://sw.local --username user --password pass
  python3 disr_dcsr_direct_monitor.py --server https://sw.local --username user --password pass --format csv
  
Configuration:
  Edit the DEFAULT_SWITCHES dictionary at the top of this script to specify your switch names.
        """
    )
    
    parser.add_argument('--server', required=True, help='SolarWinds server URL')
    parser.add_argument('--username', required=True, help='SolarWinds username')
    parser.add_argument('--password', required=True, help='SolarWinds password')
    parser.add_argument('--days', type=int, default=7, help='Number of days to analyze (default: 7)')
    parser.add_argument('--format', choices=['table', 'csv', 'json'], default='table', 
                       help='Output format (default: table)')
    parser.add_argument('--output', help='Output file path')
    parser.add_argument('--no-ssl-verify', action='store_true', 
                       help='Disable SSL certificate verification')
    parser.add_argument('--switches', help='JSON string with switch configuration (overrides defaults)')
    parser.add_argument('--port-channels', nargs='+', type=int, default=DEFAULT_PORT_CHANNELS,
                       help='Port-channel numbers to monitor (default: 5 25)')
    
    args = parser.parse_args()
    
    # Parse switch configuration
    switches = DEFAULT_SWITCHES
    if args.switches:
        try:
            switches = json.loads(args.switches)
        except json.JSONDecodeError:
            print("❌ Invalid JSON format for --switches parameter")
            return 1
    
    # Check if default configuration is being used
    if switches == DEFAULT_SWITCHES and all('your-' in switch for switch_list in switches.values() for switch in switch_list):
        print("⚠️  WARNING: Using default switch configuration!")
        print("   Please edit the DEFAULT_SWITCHES dictionary in this script")
        print("   or use the --switches parameter to specify your switch names.")
        print()
    
    try:
        print("🎯 Initializing Direct DISR/DCSR Monitor...")
        
        monitor = DirectSolarWindsMonitor(
            server_url=args.server,
            username=args.username,
            password=args.password,
            verify_ssl=not args.no_ssl_verify
        )
        
        generate_direct_report(
            monitor=monitor,
            switches=switches,
            port_channels=args.port_channels,
            days=args.days,
            output_format=args.format,
            output_file=args.output
        )
        
        print("\n✅ Direct report completed!")
        
    except KeyboardInterrupt:
        print("\n⏹️  Operation cancelled")
        return 1
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return 1
    
    return 0

if __name__ == '__main__':
    exit(main())
