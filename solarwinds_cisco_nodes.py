#!/usr/bin/env python3
"""
SolarWinds Orion - Cisco Node Inventory Report
Queries SolarWinds for Cisco nodes (excluding CUCM, null MachineType, and VMware ESX)
and exports results to CSV.
"""

import requests
import csv
import json
import os
import argparse
import urllib.parse
from datetime import datetime
from typing import Dict, List
import urllib3

# Disable SSL warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# SWQL query for Cisco nodes
CISCO_NODES_QUERY = """
SELECT DisplayName, IPAddress, MachineType, Status
FROM Orion.Nodes
WHERE UPPER(Vendor) = 'CISCO'
  AND MachineType <> 'Cisco Unified Communications Manager'
  AND MachineType IS NOT NULL
  AND MachineType <> 'VMWare ESX'
ORDER BY MachineType, DisplayName
""".strip()


class SolarWindsAPI:
    """SolarWinds Orion REST API client"""

    def __init__(self, server_url: str, username: str, password: str, verify_ssl: bool = False):
        self.server_url = server_url.rstrip('/')
        self.session = requests.Session()
        self.session.auth = (username, password)
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
        self.verify_ssl = verify_ssl

    def query(self, swql: str) -> List[Dict]:
        """
        Execute a SWQL query via the SolarWinds REST API.
        Uses GET with URL-encoded query parameter.

        Args:
            swql: The SWQL query string

        Returns:
            List of result dictionaries
        """
        encoded_query = urllib.parse.quote(swql)
        url = f"{self.server_url}/SolarWinds/InformationService/v3/Json/Query?query={encoded_query}"

        try:
            response = self.session.get(url, verify=self.verify_ssl)
            response.raise_for_status()
            data = response.json()
            return data.get('results', [])
        except requests.exceptions.RequestException as e:
            print(f"Error querying SolarWinds API: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"  Status: {e.response.status_code}")
                print(f"  Response: {e.response.text[:500]}")
            raise


def export_to_csv(results: List[Dict], output_file: str) -> None:
    """Write query results to a CSV file."""
    if not results:
        print("No results to export.")
        return

    fieldnames = list(results[0].keys())

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(f"Exported {len(results)} rows to {output_file}")


def print_summary(results: List[Dict]) -> None:
    """Print a summary of the query results."""
    if not results:
        return

    print(f"\n{'='*60}")
    print(f"  Cisco Node Inventory Summary")
    print(f"{'='*60}")
    print(f"  Total nodes: {len(results)}")

    # Count by MachineType
    type_counts = {}
    for row in results:
        mt = row.get('MachineType', 'Unknown')
        type_counts[mt] = type_counts.get(mt, 0) + 1

    print(f"  Unique MachineTypes: {len(type_counts)}")
    print(f"\n  Breakdown by MachineType:")
    for mt, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"    {mt}: {count}")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(
        description='Query SolarWinds Orion for Cisco node inventory and export to CSV'
    )
    parser.add_argument('--server', default=os.getenv('SOLARWINDS_SERVER'),
                        help='SolarWinds server URL (or set SOLARWINDS_SERVER env var)')
    parser.add_argument('--username', default=os.getenv('SOLARWINDS_USERNAME'),
                        help='SolarWinds username (or set SOLARWINDS_USERNAME env var)')
    parser.add_argument('--password', default=os.getenv('SOLARWINDS_PASSWORD'),
                        help='SolarWinds password (or set SOLARWINDS_PASSWORD env var)')
    parser.add_argument('--output', '-o',
                        default=f'cisco_nodes_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv',
                        help='Output CSV file path (default: cisco_nodes_YYYYMMDD_HHMMSS.csv)')
    parser.add_argument('--verify-ssl', action='store_true',
                        help='Enable SSL certificate verification (disabled by default)')
    parser.add_argument('--no-summary', action='store_true',
                        help='Skip printing the summary')

    args = parser.parse_args()

    # Validate required params
    if not args.server:
        parser.error("--server is required (or set SOLARWINDS_SERVER env var)")
    if not args.username:
        parser.error("--username is required (or set SOLARWINDS_USERNAME env var)")
    if not args.password:
        parser.error("--password is required (or set SOLARWINDS_PASSWORD env var)")

    # Initialize API client
    api = SolarWindsAPI(
        server_url=args.server,
        username=args.username,
        password=args.password,
        verify_ssl=args.verify_ssl
    )

    print(f"Querying SolarWinds at {args.server} for Cisco nodes...")
    print(f"SWQL:\n  {CISCO_NODES_QUERY.replace(chr(10), chr(10) + '  ')}\n")

    # Execute the query
    results = api.query(CISCO_NODES_QUERY)

    if not results:
        print("Query returned no results.")
        return 1

    # Print summary
    if not args.no_summary:
        print_summary(results)

    # Export to CSV
    export_to_csv(results, args.output)

    return 0


if __name__ == '__main__':
    exit(main())
