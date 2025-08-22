#!/usr/bin/env python3
"""
Configuration file for DISR/DCSR Direct Monitor
Edit the switches list below with your actual switch names
"""

# Your SolarWinds server configuration
SOLARWINDS_CONFIG = {
    'server': 'https://your-solarwinds-server.com',
    'username': 'your-username', 
    'password': 'your-password',
    'verify_ssl': False  # Set to True if you have valid SSL certificates
}

# Your DISR/DCSR switches - EDIT THESE WITH YOUR ACTUAL SWITCH NAMES
SWITCHES = {
    'DISR': [
        # Add your DISR switch names here (partial names work)
        'DISR-SW-01',
        'DISR-SW-02',
        # 'Add more DISR switches...',
    ],
    'DCSR': [
        # Add your DCSR switch names here (partial names work)
        'DCSR-SW-01', 
        'DCSR-SW-02',
        # 'Add more DCSR switches...',
    ]
}

# Port-channel numbers to monitor
PORT_CHANNELS = [5, 25]

# Report settings
REPORT_DAYS = 7  # Number of days to analyze
OUTPUT_FORMAT = 'table'  # 'table', 'csv', or 'json'

if __name__ == '__main__':
    """
    Run this file directly to test your configuration
    """
    import json
    from disr_dcsr_direct_monitor import DirectSolarWindsMonitor, generate_direct_report
    
    print("🔧 DISR/DCSR Configuration Test")
    print("=" * 40)
    print(f"Server: {SOLARWINDS_CONFIG['server']}")
    print(f"Username: {SOLARWINDS_CONFIG['username']}")
    print(f"SSL Verify: {SOLARWINDS_CONFIG['verify_ssl']}")
    print()
    
    print("📋 Switch Configuration:")
    for switch_type, switch_list in SWITCHES.items():
        print(f"  {switch_type}: {len(switch_list)} switches")
        for switch in switch_list:
            print(f"    - {switch}")
    print()
    
    print(f"🔌 Port-channels: {', '.join(map(str, PORT_CHANNELS))}")
    print(f"📅 Report period: {REPORT_DAYS} days")
    print(f"📊 Output format: {OUTPUT_FORMAT}")
    print()
    
    # Check for placeholder values
    has_placeholders = (
        'your-' in SOLARWINDS_CONFIG['server'] or
        'your-' in SOLARWINDS_CONFIG['username'] or
        any('your-' in switch for switch_list in SWITCHES.values() for switch in switch_list)
    )
    
    if has_placeholders:
        print("⚠️  WARNING: Configuration contains placeholder values!")
        print("   Please edit this file with your actual:")
        print("   - SolarWinds server URL") 
        print("   - Username and password")
        print("   - Switch names")
        print()
        print("💡 TIP: Switch names can be partial matches")
        print("   For example, 'DISR-CORE' will match 'DISR-CORE-01'")
    else:
        print("✅ Configuration looks good!")
        print()
        
        # Option to run the report
        try:
            response = input("🚀 Run report now? (y/N): ")
            if response.lower() in ['y', 'yes']:
                print("\n🔌 Connecting to SolarWinds...")
                
                monitor = DirectSolarWindsMonitor(
                    server_url=SOLARWINDS_CONFIG['server'],
                    username=SOLARWINDS_CONFIG['username'], 
                    password=SOLARWINDS_CONFIG['password'],
                    verify_ssl=SOLARWINDS_CONFIG['verify_ssl']
                )
                
                generate_direct_report(
                    monitor=monitor,
                    switches=SWITCHES,
                    port_channels=PORT_CHANNELS,
                    days=REPORT_DAYS,
                    output_format=OUTPUT_FORMAT
                )
        except KeyboardInterrupt:
            print("\n👋 Cancelled by user")
        except Exception as e:
            print(f"\n❌ Error: {e}")
