#!/usr/bin/env python3
"""
DISR/DCSR Port-Channel Monitor
Specialized script to monitor port-channel5 and port-channel25 on DISR and DCSR switches
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

class DisrDcsrMonitor:
    def __init__(self, server_url: str, username: str, password: str, verify_ssl: bool = True):
        """Initialize DISR/DCSR Monitor"""
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

    def find_target_interfaces(self) -> List[Dict]:
        """Find DISR/DCSR switches with port-channel5 and port-channel25"""
        query = "Query"
        data = {
            "query": """
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
                AND (
                    (UPPER(n.Caption) LIKE '%DISR%' OR UPPER(n.SysName) LIKE '%DISR%') OR
                    (UPPER(n.Caption) LIKE '%DCSR%' OR UPPER(n.SysName) LIKE '%DCSR%')
                )
                AND (
                    UPPER(i.Name) LIKE '%PORT-CHANNEL5%' OR 
                    UPPER(i.Name) LIKE '%PORT-CHANNEL25%' OR
                    UPPER(i.Name) LIKE '%PO5%' OR 
                    UPPER(i.Name) LIKE '%PO25%' OR
                    UPPER(i.Caption) LIKE '%PORT-CHANNEL5%' OR 
                    UPPER(i.Caption) LIKE '%PORT-CHANNEL25%'
                )
                ORDER BY n.Caption, i.Name
            """
        }
        
        try:
            result = self._make_request(query, 'POST', data)
            return result.get('results', [])
        except Exception as e:
            print(f"Error finding target interfaces: {e}")
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

    def calculate_port_channel_summary(self, statistics: List[Dict]) -> Dict:
        """Calculate comprehensive summary for port-channel interfaces"""
        if not statistics:
            return {}
        
        # Initialize counters
        total_in_bytes = 0
        total_out_bytes = 0
        max_in_percent = 0
        max_out_percent = 0
        avg_in_percent = 0
        avg_out_percent = 0
        max_in_bps = 0
        max_out_bps = 0
        
        # Track hourly peaks for better analysis
        hourly_peaks_in = []
        hourly_peaks_out = []
        
        valid_entries = 0
        
        for stat in statistics:
            # Bytes transferred
            in_bytes = stat.get('InTotalBytes', 0) or 0
            out_bytes = stat.get('OutTotalBytes', 0) or 0
            total_in_bytes += in_bytes
            total_out_bytes += out_bytes
            
            # Utilization percentages
            in_percent = stat.get('InPercentUtil', 0) or 0
            out_percent = stat.get('OutPercentUtil', 0) or 0
            
            max_in_percent = max(max_in_percent, in_percent)
            max_out_percent = max(max_out_percent, out_percent)
            avg_in_percent += in_percent
            avg_out_percent += out_percent
            
            # Bits per second
            in_bps = stat.get('InBitsPerSec', 0) or 0
            out_bps = stat.get('OutBitsPerSec', 0) or 0
            
            max_in_bps = max(max_in_bps, in_bps)
            max_out_bps = max(max_out_bps, out_bps)
            
            # Store for peak analysis
            if in_percent > 50:  # High utilization periods
                hourly_peaks_in.append(in_percent)
            if out_percent > 50:
                hourly_peaks_out.append(out_percent)
            
            valid_entries += 1
        
        # Calculate averages
        avg_in_percent = avg_in_percent / valid_entries if valid_entries > 0 else 0
        avg_out_percent = avg_out_percent / valid_entries if valid_entries > 0 else 0
        
        # Calculate 95th percentile for better capacity planning
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
            'high_util_periods_in': len(hourly_peaks_in),
            'high_util_periods_out': len(hourly_peaks_out),
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

def identify_port_channel_type(interface_name: str) -> str:
    """Identify the port-channel type from interface name"""
    name_lower = interface_name.lower()
    
    if 'port-channel5' in name_lower or name_lower.endswith('po5') or '/5' in name_lower:
        return "Port-Channel 5"
    elif 'port-channel25' in name_lower or name_lower.endswith('po25') or '/25' in name_lower:
        return "Port-Channel 25"
    elif 'po5' in name_lower:
        return "Port-Channel 5"
    elif 'po25' in name_lower:
        return "Port-Channel 25"
    else:
        return f"Port-Channel ({interface_name})"

def generate_disr_dcsr_report(monitor: DisrDcsrMonitor, days: int = 7, 
                              output_format: str = 'table', output_file: Optional[str] = None) -> None:
    """Generate specialized report for DISR/DCSR port-channels"""
    
    print(f"Generating DISR/DCSR Port-Channel Report for past {days} days")
    print("Target: port-channel5 and port-channel25 interfaces")
    print("=" * 60)
    
    # Calculate date range
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    print(f"Date range: {start_date.strftime('%Y-%m-%d %H:%M')} to {end_date.strftime('%Y-%m-%d %H:%M')} UTC")
    
    # Find target interfaces
    print("\nSearching for DISR/DCSR switches with port-channel5 and port-channel25...")
    interfaces = monitor.find_target_interfaces()
    
    if not interfaces:
        print("❌ No matching interfaces found!")
        print("Make sure:")
        print("  - DISR/DCSR switches are monitored in SolarWinds")
        print("  - Port-channel5 and port-channel25 interfaces exist")
        print("  - Interface names contain 'port-channel5', 'port-channel25', 'po5', or 'po25'")
        return
    
    print(f"✅ Found {len(interfaces)} matching interfaces:")
    for iface in interfaces:
        switch_type = "DISR" if "disr" in iface.get('NodeName', '').lower() else "DCSR"
        pc_type = identify_port_channel_type(iface.get('Name', ''))
        print(f"  - {iface.get('NodeName', 'Unknown')} ({switch_type}): {pc_type}")
    
    report_data = []
    
    # Process each interface
    print("\nProcessing interface statistics...")
    for i, interface in enumerate(interfaces, 1):
        interface_id = interface['InterfaceID']
        interface_name = interface.get('Name', 'Unknown')
        node_name = interface.get('NodeName', 'Unknown')
        speed = interface.get('Speed', 0)
        
        switch_type = "DISR" if "disr" in node_name.lower() else "DCSR"
        pc_type = identify_port_channel_type(interface_name)
        
        print(f"\n[{i}/{len(interfaces)}] Processing {node_name} - {pc_type}")
        
        # Get statistics
        statistics = monitor.get_interface_statistics(interface_id, start_date, end_date)
        
        if not statistics:
            print(f"  ⚠️  No statistics found for {pc_type}")
            continue
        
        print(f"  📊 Found {len(statistics)} data points")
        
        # Calculate summary
        summary = monitor.calculate_port_channel_summary(statistics)
        
        if summary and summary['data_points'] > 0:
            # Determine status based on utilization
            max_util = max(summary['max_in_percent'], summary['max_out_percent'])
            avg_util = max(summary['avg_in_percent'], summary['avg_out_percent'])
            
            if max_util > 80:
                status = "🔴 HIGH"
            elif max_util > 60:
                status = "🟡 MEDIUM"
            else:
                status = "🟢 LOW"
            
            report_data.append({
                'Switch': node_name,
                'Switch Type': switch_type,
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
                'High Util Periods (In)': summary['high_util_periods_in'],
                'High Util Periods (Out)': summary['high_util_periods_out'],
                'Data Points': summary['data_points']
            })
            
            print(f"  ✅ {status} - Max: {max_util:.1f}%, Avg: {avg_util:.1f}%")
        else:
            print(f"  ❌ No valid data for {pc_type}")
    
    if not report_data:
        print("\n❌ No data found for any DISR/DCSR port-channel interfaces!")
        return
    
    # Sort by switch type, then switch name, then port-channel
    report_data.sort(key=lambda x: (x['Switch Type'], x['Switch'], x['Port-Channel']))
    
    print(f"\n📈 Generated report for {len(report_data)} port-channel interfaces")
    
    # Output report
    if output_format.lower() == 'csv':
        output_csv_report(report_data, output_file, days)
    elif output_format.lower() == 'json':
        output_json_report(report_data, output_file, days)
    else:
        output_table_report(report_data, output_file, days)

def output_table_report(data: List[Dict], output_file: Optional[str] = None, days: int = 7) -> None:
    """Output specialized table for DISR/DCSR port-channels"""
    if not data:
        return
    
    # Create summary table
    table_data = []
    for row in data:
        table_data.append([
            row['Switch'][:12] + '...' if len(row['Switch']) > 12 else row['Switch'],
            row['Switch Type'],
            row['Port-Channel'].replace('Port-Channel ', 'PC'),
            row['Total Data'],
            row['Max Util (In)'],
            row['Max Util (Out)'],
            row['95th Percentile (In)'],
            row['95th Percentile (Out)'],
            row['Status'].split()[0]  # Just the emoji
        ])
    
    headers = ['Switch', 'Type', 'PC', 'Total Data', 'Max In%', 'Max Out%', '95th In%', '95th Out%', 'Status']
    table = tabulate(table_data, headers=headers, tablefmt='grid')
    
    # Create detailed summary
    summary_text = f"""
DISR/DCSR Port-Channel Usage Report ({days} days)
{'=' * 55}

Summary:
- Total interfaces analyzed: {len(data)}
- DISR switches: {len([d for d in data if d['Switch Type'] == 'DISR'])}
- DCSR switches: {len([d for d in data if d['Switch Type'] == 'DCSR'])}
- Port-Channel 5 interfaces: {len([d for d in data if 'Port-Channel 5' in d['Port-Channel']])}
- Port-Channel 25 interfaces: {len([d for d in data if 'Port-Channel 25' in d['Port-Channel']])}

{table}

Utilization Status Legend:
🟢 LOW    - Max utilization < 60%
🟡 MEDIUM - Max utilization 60-80%
🔴 HIGH   - Max utilization > 80%
"""
    
    if output_file:
        with open(output_file, 'w') as f:
            f.write(summary_text)
        print(f"\n📄 Report saved to {output_file}")
    else:
        print(summary_text)

def output_csv_report(data: List[Dict], output_file: Optional[str] = None, days: int = 7) -> None:
    """Output CSV report with timestamp"""
    if not data:
        return
    
    filename = output_file or f'disr_dcsr_portchannel_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        # Add header with metadata
        f.write(f"# DISR/DCSR Port-Channel Usage Report\n")
        f.write(f"# Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# Period: {days} days\n")
        f.write(f"# Interfaces: {len(data)}\n")
        f.write("\n")
        
        writer = csv.DictWriter(f, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)
    
    print(f"📄 CSV report saved to {filename}")

def output_json_report(data: List[Dict], output_file: Optional[str] = None, days: int = 7) -> None:
    """Output JSON report with metadata"""
    if not data:
        return
    
    filename = output_file or f'disr_dcsr_portchannel_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    
    report_metadata = {
        'report_type': 'DISR/DCSR Port-Channel Usage Report',
        'generated_at': datetime.now().isoformat(),
        'period_days': days,
        'interface_count': len(data),
        'disr_count': len([d for d in data if d['Switch Type'] == 'DISR']),
        'dcsr_count': len([d for d in data if d['Switch Type'] == 'DCSR']),
        'pc5_count': len([d for d in data if 'Port-Channel 5' in d['Port-Channel']]),
        'pc25_count': len([d for d in data if 'Port-Channel 25' in d['Port-Channel']]),
        'data': data
    }
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(report_metadata, f, indent=2, default=str)
    
    print(f"📄 JSON report saved to {filename}")

def main():
    parser = argparse.ArgumentParser(
        description='Generate DISR/DCSR port-channel5 and port-channel25 usage report',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python disr_dcsr_portchannel_monitor.py --server https://solarwinds.company.com --username admin --password pass123
  python disr_dcsr_portchannel_monitor.py --server https://sw.local --username user --password pass --days 14 --format csv
  python disr_dcsr_portchannel_monitor.py --server https://sw.local --username user --password pass --output report.txt
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
    
    args = parser.parse_args()
    
    try:
        print("🔌 Initializing DISR/DCSR Port-Channel Monitor...")
        
        # Initialize monitor
        monitor = DisrDcsrMonitor(
            server_url=args.server,
            username=args.username,
            password=args.password,
            verify_ssl=not args.no_ssl_verify
        )
        
        # Generate report
        generate_disr_dcsr_report(
            monitor=monitor,
            days=args.days,
            output_format=args.format,
            output_file=args.output
        )
        
        print("\n✅ Report generation completed!")
        
    except KeyboardInterrupt:
        print("\n⏹️  Operation cancelled by user")
        return 1
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return 1
    
    return 0

if __name__ == '__main__':
    exit(main())
