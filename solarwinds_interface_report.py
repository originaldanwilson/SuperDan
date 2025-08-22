#!/usr/bin/env python3
"""
SolarWinds Interface Usage Report Script
Retrieves interface usage data (bits used and percentage) for the past 7 days
without using the SolarWinds library, using direct REST API calls.
"""

import requests
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import urllib3
import argparse
import csv
from tabulate import tabulate

# Disable SSL warnings if needed (for self-signed certificates)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class SolarWindsAPI:
    def __init__(self, server_url: str, username: str, password: str, verify_ssl: bool = True):
        """
        Initialize SolarWinds API client
        
        Args:
            server_url: SolarWinds server URL (e.g., https://your-solarwinds-server)
            username: SolarWinds username
            password: SolarWinds password
            verify_ssl: Whether to verify SSL certificates
        """
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

    def _make_request(self, endpoint: str, method: str = 'GET', data: Dict = None) -> Dict:
        """
        Make HTTP request to SolarWinds API
        
        Args:
            endpoint: API endpoint
            method: HTTP method
            data: Request data for POST requests
            
        Returns:
            JSON response as dictionary
        """
        url = f"{self.server_url}/SolarWinds/InformationService/v3/Json/{endpoint}"
        
        try:
            if method.upper() == 'GET':
                response = self.session.get(url, verify=self.verify_ssl)
            elif method.upper() == 'POST':
                response = self.session.post(url, json=data, verify=self.verify_ssl)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            return response.json()
        
        except requests.exceptions.RequestException as e:
            print(f"Error making request to {url}: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response status: {e.response.status_code}")
                print(f"Response text: {e.response.text}")
            raise

    def get_interfaces(self, node_filter: str = None, interface_filter: str = None) -> List[Dict]:
        """
        Get network interfaces filtered by node and interface names
        
        Args:
            node_filter: Filter nodes by name pattern
            interface_filter: Filter interfaces by name pattern
            
        Returns:
            List of interface dictionaries
        """
        query = "Query"
        
        # Build query with filters
        base_query = """
            SELECT 
                i.InterfaceID, 
                i.NodeID, 
                i.Name, 
                i.Caption, 
                i.InterfaceAlias, 
                i.InterfaceType, 
                i.Speed, 
                i.Duplex,
                n.Caption as NodeName
            FROM Orion.NPM.Interfaces i
            JOIN Orion.Nodes n ON i.NodeID = n.NodeID
            WHERE i.Status = 1
        """
        
        conditions = []
        
        if node_filter:
            conditions.append(f"(UPPER(n.Caption) LIKE UPPER('%{node_filter}%') OR UPPER(n.SysName) LIKE UPPER('%{node_filter}%'))")
        
        if interface_filter:
            conditions.append(f"(UPPER(i.Name) LIKE UPPER('%{interface_filter}%') OR UPPER(i.Caption) LIKE UPPER('%{interface_filter}%'))")
        
        if conditions:
            base_query += " AND " + " AND ".join(conditions)
        
        data = {"query": base_query}
        
        try:
            result = self._make_request(query, 'POST', data)
            return result.get('results', [])
        except Exception as e:
            print(f"Error getting interfaces: {e}")
            return []

    def get_interface_statistics(self, interface_id: int, start_date: datetime, end_date: datetime) -> List[Dict]:
        """
        Get interface statistics for a specific time period
        
        Args:
            interface_id: Interface ID
            start_date: Start date for statistics
            end_date: End date for statistics
            
        Returns:
            List of statistics dictionaries
        """
        query = "Query"
        
        # Format dates for SolarWinds SWQL
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
                ORDER BY DateTime DESC
            """
        }
        
        try:
            result = self._make_request(query, 'POST', data)
            return result.get('results', [])
        except Exception as e:
            print(f"Error getting statistics for interface {interface_id}: {e}")
            return []

    def get_interface_details(self, interface_id: int) -> Dict:
        """
        Get detailed information about a specific interface
        
        Args:
            interface_id: Interface ID
            
        Returns:
            Interface details dictionary
        """
        query = "Query"
        data = {
            "query": f"""
                SELECT 
                    i.InterfaceID,
                    i.NodeID,
                    n.Caption as NodeName,
                    i.Name,
                    i.Caption,
                    i.InterfaceAlias,
                    i.InterfaceType,
                    i.Speed,
                    i.Duplex,
                    i.Status
                FROM Orion.NPM.Interfaces i
                JOIN Orion.Nodes n ON i.NodeID = n.NodeID
                WHERE i.InterfaceID = {interface_id}
            """
        }
        
        try:
            result = self._make_request(query, 'POST', data)
            results = result.get('results', [])
            return results[0] if results else {}
        except Exception as e:
            print(f"Error getting interface details for {interface_id}: {e}")
            return {}

def calculate_usage_summary(statistics: List[Dict], interface_speed: Optional[int] = None) -> Dict:
    """
    Calculate usage summary from statistics
    
    Args:
        statistics: List of statistics dictionaries
        interface_speed: Interface speed in bps (optional)
        
    Returns:
        Usage summary dictionary
    """
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
        # Handle bytes (convert from bits if needed)
        in_bytes = stat.get('InTotalBytes', 0) or 0
        out_bytes = stat.get('OutTotalBytes', 0) or 0
        
        total_in_bytes += in_bytes
        total_out_bytes += out_bytes
        
        # Handle percentage utilization
        in_percent = stat.get('InPercentUtil', 0) or 0
        out_percent = stat.get('OutPercentUtil', 0) or 0
        
        if in_percent > max_in_percent:
            max_in_percent = in_percent
        if out_percent > max_out_percent:
            max_out_percent = out_percent
        
        avg_in_percent += in_percent
        avg_out_percent += out_percent
        
        # Handle bits per second
        in_bps = stat.get('InBitsPerSec', 0) or 0
        out_bps = stat.get('OutBitsPerSec', 0) or 0
        
        if in_bps > max_in_bps:
            max_in_bps = in_bps
        if out_bps > max_out_bps:
            max_out_bps = out_bps
        
        valid_entries += 1
    
    # Calculate averages
    if valid_entries > 0:
        avg_in_percent = avg_in_percent / valid_entries
        avg_out_percent = avg_out_percent / valid_entries
    
    return {
        'total_in_bytes': total_in_bytes,
        'total_out_bytes': total_out_bytes,
        'total_bytes': total_in_bytes + total_out_bytes,
        'max_in_percent': max_in_percent,
        'max_out_percent': max_out_percent,
        'avg_in_percent': avg_in_percent,
        'avg_out_percent': avg_out_percent,
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

def generate_disr_dcsr_report(api: SolarWindsAPI, days: int = 7, output_format: str = 'table', 
                              output_file: Optional[str] = None) -> None:
    """
    Generate interface usage report specifically for DISR/DCSR switches and port-channels 5 & 25
    
    Args:
        api: SolarWinds API client
        days: Number of days to look back
        output_format: Output format ('table', 'csv', 'json')
        output_file: Output file path (optional)
    """
    print(f"Generating DISR/DCSR port-channel usage report for the past {days} days...")
    
    # Calculate date range
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    print(f"Date range: {start_date.strftime('%Y-%m-%d %H:%M')} to {end_date.strftime('%Y-%m-%d %H:%M')} UTC")
    
    # Get DISR/DCSR switches with port-channel interfaces
    print("Fetching DISR/DCSR switches and port-channel interfaces...")
    
    # First get DISR switches
    print("Searching for DISR switches...")
    disr_interfaces = api.get_interfaces(node_filter='DISR', interface_filter='port-channel')
    
    # Then get DCSR switches  
    print("Searching for DCSR switches...")
    dcsr_interfaces = api.get_interfaces(node_filter='DCSR', interface_filter='port-channel')
    
    # Combine all interfaces
    all_interfaces = disr_interfaces + dcsr_interfaces
    
    # Filter for specific port-channels (5 and 25)
    target_interfaces = []
    for iface in all_interfaces:
        interface_name = iface.get('Name', '').lower()
        interface_caption = iface.get('Caption', '').lower()
        
        # Check if it's port-channel 5 or 25
        if ('port-channel5' in interface_name or 'port-channel5' in interface_caption or
            'port-channel25' in interface_name or 'port-channel25' in interface_caption or
            'po5' in interface_name or 'po25' in interface_name):
            target_interfaces.append(iface)
    
    if not target_interfaces:
        print("No DISR/DCSR port-channel5 or port-channel25 interfaces found!")
        print("Available interfaces found:")
        for iface in all_interfaces[:10]:  # Show first 10 for debugging
            print(f"  - {iface.get('NodeName', 'Unknown')}: {iface.get('Name', 'Unknown')} ({iface.get('Caption', 'Unknown')})")
        return
    
    print(f"Found {len(target_interfaces)} target port-channel interfaces")
    for iface in target_interfaces:
        print(f"  - {iface.get('NodeName', 'Unknown')}: {iface.get('Name', 'Unknown')}")
    
    report_data = []
    
    # Process each interface
    for i, interface in enumerate(target_interfaces, 1):
        interface_id = interface['InterfaceID']
        interface_name = interface.get('Name', 'Unknown')
        interface_caption = interface.get('Caption', 'Unknown')
        node_name = interface.get('NodeName', 'Unknown')
        
        print(f"Processing interface {i}/{len(target_interfaces)}: {node_name} - {interface_name}")
        
        # Get detailed interface info
        details = api.get_interface_details(interface_id)
        speed = details.get('Speed', 0)
        
        # Get statistics
        statistics = api.get_interface_statistics(interface_id, start_date, end_date)
        
        # Calculate summary
        summary = calculate_usage_summary(statistics, speed)
        
        if summary and summary['data_points'] > 0:
            # Determine port-channel type
            pc_type = "Unknown"
            if 'port-channel5' in interface_name.lower() or 'po5' in interface_name.lower():
                pc_type = "Port-Channel 5"
            elif 'port-channel25' in interface_name.lower() or 'po25' in interface_name.lower():
                pc_type = "Port-Channel 25"
            
            report_data.append({
                'Switch': node_name,
                'Port-Channel': pc_type,
                'Interface': interface_name,
                'Description': interface_caption,
                'Speed': format_bps(speed) if speed else 'Unknown',
                'Total Data (In)': format_bytes(summary['total_in_bytes']),
                'Total Data (Out)': format_bytes(summary['total_out_bytes']),
                'Total Data': format_bytes(summary['total_bytes']),
                'Max Utilization (In)': f"{summary['max_in_percent']:.2f}%",
                'Max Utilization (Out)': f"{summary['max_out_percent']:.2f}%",
                'Avg Utilization (In)': f"{summary['avg_in_percent']:.2f}%",
                'Avg Utilization (Out)': f"{summary['avg_out_percent']:.2f}%",
                'Peak Speed (In)': format_bps(summary['max_in_bps']),
                'Peak Speed (Out)': format_bps(summary['max_out_bps']),
                'Data Points': summary['data_points']
            })
        else:
            print(f"  No data found for {node_name} - {interface_name}")
    
    if not report_data:
        print("No data found for any DISR/DCSR port-channel interfaces!")
        return
    
    # Sort by switch name and port-channel for better readability
    report_data.sort(key=lambda x: (x['Switch'], x['Port-Channel']))
    
    print(f"\nFound data for {len(report_data)} port-channel interfaces")
    
    # Output report
    if output_format.lower() == 'csv':
        output_csv(report_data, output_file)
    elif output_format.lower() == 'json':
        output_json(report_data, output_file)
    else:
        output_table(report_data, output_file)

def output_table(data: List[Dict], output_file: Optional[str] = None) -> None:
    """Output data as formatted table for DISR/DCSR switches"""
    if not data:
        return
    
    # Create table optimized for DISR/DCSR port-channel data
    table_data = []
    for row in data:
        table_data.append([
            row['Switch'][:15] + '...' if len(row['Switch']) > 15 else row['Switch'],
            row['Port-Channel'],
            row['Total Data'],
            row['Max Utilization (In)'],
            row['Max Utilization (Out)'],
            row['Avg Utilization (In)'],
            row['Avg Utilization (Out)'],
            row['Speed']
        ])
    
    headers = ['Switch', 'Port-Channel', 'Total Data', 'Max In %', 'Max Out %', 'Avg In %', 'Avg Out %', 'Speed']
    table = tabulate(table_data, headers=headers, tablefmt='grid')
    
    if output_file:
        with open(output_file, 'w') as f:
            f.write("DISR/DCSR Port-Channel Usage Report\n")
            f.write("=" * 50 + "\n\n")
            f.write(table)
        print(f"Report saved to {output_file}")
    else:
        print("\nDISR/DCSR Port-Channel Usage Report:")
        print("=" * 50)
        print(table)

def output_csv(data: List[Dict], output_file: Optional[str] = None) -> None:
    """Output data as CSV"""
    if not data:
        return
    
    filename = output_file or f'solarwinds_interface_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)
    
    print(f"CSV report saved to {filename}")

def output_json(data: List[Dict], output_file: Optional[str] = None) -> None:
    """Output data as JSON"""
    if not data:
        return
    
    filename = output_file or f'solarwinds_interface_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, default=str)
    
    print(f"JSON report saved to {filename}")

def main():
    parser = argparse.ArgumentParser(description='Generate DISR/DCSR port-channel usage report')
    parser.add_argument('--server', required=True, help='SolarWinds server URL')
    parser.add_argument('--username', required=True, help='SolarWinds username')
    parser.add_argument('--password', required=True, help='SolarWinds password')
    parser.add_argument('--days', type=int, default=7, help='Number of days to look back (default: 7)')
    parser.add_argument('--format', choices=['table', 'csv', 'json'], default='table', 
                       help='Output format (default: table)')
    parser.add_argument('--output', help='Output file path')
    parser.add_argument('--no-ssl-verify', action='store_true', help='Disable SSL certificate verification')
    
    args = parser.parse_args()
    
    try:
        # Initialize API client
        api = SolarWindsAPI(
            server_url=args.server,
            username=args.username,
            password=args.password,
            verify_ssl=not args.no_ssl_verify
        )
        
        # Generate DISR/DCSR port-channel report
        generate_disr_dcsr_report(
            api=api,
            days=args.days,
            output_format=args.format,
            output_file=args.output
        )
        
    except Exception as e:
        print(f"Error: {e}")
        return 1
    
    return 0

if __name__ == '__main__':
    exit(main())
