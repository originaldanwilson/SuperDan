#!/usr/bin/env python3
"""
Example configuration and usage for SolarWinds interface report script
"""

import os
from solarwinds_interface_report import SolarWindsAPI, generate_report

# Example configuration
SOLARWINDS_CONFIG = {
    'server_url': 'https://your-solarwinds-server.com',
    'username': 'your-username',
    'password': 'your-password',  # Consider using environment variables
    'verify_ssl': True  # Set to False for self-signed certificates
}

def example_usage():
    """Example of how to use the script programmatically"""
    
    # Method 1: Using environment variables (recommended for security)
    server = os.getenv('SOLARWINDS_SERVER')
    username = os.getenv('SOLARWINDS_USERNAME')
    password = os.getenv('SOLARWINDS_PASSWORD')
    
    if all([server, username, password]):
        api = SolarWindsAPI(server, username, password)
        
        # Generate report for past 7 days
        generate_report(api, days=7, output_format='table')
        
        # Generate CSV report for past 30 days
        generate_report(api, days=30, output_format='csv', 
                       output_file='monthly_report.csv')
        
        # Generate filtered report for specific interfaces
        generate_report(api, days=7, output_format='json',
                       interface_filter='GigabitEthernet')
    
    else:
        print("Please set environment variables:")
        print("export SOLARWINDS_SERVER=https://your-server.com")
        print("export SOLARWINDS_USERNAME=your-username")
        print("export SOLARWINDS_PASSWORD=your-password")

def quick_report_example():
    """Quick example for immediate use"""
    
    # Direct configuration (less secure)
    api = SolarWindsAPI(
        server_url='https://your-solarwinds-server.com',
        username='your-username',
        password='your-password',
        verify_ssl=False  # Only if using self-signed certificates
    )
    
    # Generate simple table report
    generate_report(api)

if __name__ == '__main__':
    example_usage()
