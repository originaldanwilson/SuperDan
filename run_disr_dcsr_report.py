#!/usr/bin/env python3
"""
Simple runner script for DISR/DCSR port-channel monitoring
Configure your credentials here and run this script directly
"""

import os
from disr_dcsr_portchannel_monitor import DisrDcsrMonitor, generate_disr_dcsr_report

def run_report():
    """Run DISR/DCSR port-channel report with your configuration"""
    
    # Configuration - Update these values
    SOLARWINDS_SERVER = "https://your-solarwinds-server.com"
    USERNAME = "your-username"
    PASSWORD = "your-password"
    
    # Or use environment variables (more secure)
    server = os.getenv('SOLARWINDS_SERVER', SOLARWINDS_SERVER)
    username = os.getenv('SOLARWINDS_USERNAME', USERNAME)
    password = os.getenv('SOLARWINDS_PASSWORD', PASSWORD)
    
    print("🔌 DISR/DCSR Port-Channel Monitor")
    print("=" * 40)
    print(f"Server: {server}")
    print(f"Username: {username}")
    print("Targeting: DISR/DCSR switches")
    print("Interfaces: port-channel5 and port-channel25")
    print()
    
    try:
        # Initialize monitor
        monitor = DisrDcsrMonitor(
            server_url=server,
            username=username,
            password=password,
            verify_ssl=False  # Set to True if you have valid SSL certificates
        )
        
        # Generate 7-day report (table format)
        print("📊 Generating 7-day usage report...")
        generate_disr_dcsr_report(monitor, days=7, output_format='table')
        
        # Optionally generate CSV for detailed analysis
        print("\n📋 Generating CSV report for detailed analysis...")
        generate_disr_dcsr_report(monitor, days=7, output_format='csv', 
                                 output_file='disr_dcsr_weekly_report.csv')
        
        print("\n✅ Reports completed successfully!")
        print("Check 'disr_dcsr_weekly_report.csv' for detailed data")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\nTroubleshooting:")
        print("1. Check your SolarWinds server URL")
        print("2. Verify username and password")
        print("3. Ensure DISR/DCSR switches are monitored")
        print("4. Confirm port-channel5 and port-channel25 exist")

if __name__ == '__main__':
    run_report()
