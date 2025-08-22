# SolarWinds Interface Usage Report

This Python script generates interface usage reports from SolarWinds NPM without using the SolarWinds library. It uses direct REST API calls to retrieve interface traffic statistics, bits used, and utilization percentages for the past 7 days (configurable).

## Features

- **No SolarWinds Library Required**: Uses direct REST API calls
- **Multiple Output Formats**: Table, CSV, and JSON output
- **Flexible Time Ranges**: Configurable number of days to look back
- **Interface Filtering**: Filter by interface name or description
- **Comprehensive Data**: Shows bytes transferred, utilization percentages, and peak speeds
- **SSL Support**: Handles both verified and self-signed certificates
- **Human-Readable Output**: Formats bytes and speeds in readable units

## Installation

1. Install Python dependencies:
```bash
pip install requests urllib3 tabulate
```

2. Make the script executable:
```bash
chmod +x solarwinds_interface_report.py
```

## Usage

### Command Line Interface

Basic usage:
```bash
python solarwinds_interface_report.py --server https://your-solarwinds-server.com --username your-username --password your-password
```

Advanced options:
```bash
# Generate CSV report for past 30 days
python solarwinds_interface_report.py \
    --server https://your-solarwinds-server.com \
    --username your-username \
    --password your-password \
    --days 30 \
    --format csv \
    --output monthly_report.csv

# Filter interfaces containing "GigabitEthernet"
python solarwinds_interface_report.py \
    --server https://your-solarwinds-server.com \
    --username your-username \
    --password your-password \
    --filter GigabitEthernet

# Disable SSL verification for self-signed certificates
python solarwinds_interface_report.py \
    --server https://your-solarwinds-server.com \
    --username your-username \
    --password your-password \
    --no-ssl-verify
```

### Using Environment Variables (Recommended)

For security, set credentials as environment variables:
```bash
export SOLARWINDS_SERVER=https://your-solarwinds-server.com
export SOLARWINDS_USERNAME=your-username
export SOLARWINDS_PASSWORD=your-password

# Then run the script programmatically
python solarwinds_config_example.py
```

### Command Line Options

- `--server`: SolarWinds server URL (required)
- `--username`: SolarWinds username (required)
- `--password`: SolarWinds password (required)
- `--days`: Number of days to look back (default: 7)
- `--format`: Output format - table, csv, or json (default: table)
- `--output`: Output file path (optional)
- `--filter`: Filter interfaces by name or description
- `--no-ssl-verify`: Disable SSL certificate verification

## Sample Output

### Table Format
```
+------------------+---------------+-------------+-----------+------------+-----------+------------+
| Node             | Interface     | Total Data  | Max In %  | Max Out %  | Avg In %  | Avg Out %  |
+==================+===============+=============+===========+============+===========+============+
| router-01        | Gi0/1         | 125.67 GB   | 85.23%    | 78.91%     | 45.12%    | 38.77%     |
| switch-02        | Fa0/24        | 45.23 MB    | 12.45%    | 8.93%      | 3.21%     | 2.15%      |
+------------------+---------------+-------------+-----------+------------+-----------+------------+
```

### CSV Format
Contains all detailed columns including:
- Node name
- Interface name and description
- Interface speed
- Total data in/out/combined
- Maximum and average utilization percentages
- Peak speeds
- Number of data points

### JSON Format
Structured data suitable for further processing or integration with other tools.

## Programmatic Usage

```python
from solarwinds_interface_report import SolarWindsAPI, generate_report

# Initialize API client
api = SolarWindsAPI(
    server_url='https://your-solarwinds-server.com',
    username='your-username',
    password='your-password'
)

# Generate report
generate_report(
    api=api,
    days=7,
    output_format='table',
    interface_filter='GigabitEthernet'
)
```

## Data Retrieved

The script retrieves and calculates:

- **Interface Information**: Name, description, speed, node details
- **Traffic Data**: Bytes in/out, bits per second in/out
- **Utilization**: Percentage utilization in/out
- **Statistics**: Maximum and average values over the time period
- **Totals**: Total bytes transferred during the period

## API Endpoints Used

The script uses SolarWinds SWQL (SolarWinds Query Language) to query:
- `Orion.NPM.Interfaces`: Interface configuration data
- `Orion.NPM.InterfaceTraffic`: Traffic statistics and utilization
- `Orion.Nodes`: Node information

## Requirements

- Python 3.6+
- SolarWinds NPM with API access enabled
- Valid SolarWinds user account with appropriate permissions
- Network connectivity to SolarWinds server

## Troubleshooting

### SSL Certificate Issues
If you encounter SSL certificate errors with self-signed certificates, use the `--no-ssl-verify` flag.

### Authentication Issues
Ensure your SolarWinds user has appropriate permissions to access the Information Service and query interface data.

### No Data Returned
- Check that interfaces are monitored and have traffic data
- Verify the time range includes periods with network activity
- Ensure interface status is up (Status = 1)

### Connection Issues
- Verify the server URL is correct and accessible
- Check firewall settings allow connections to the SolarWinds API port (typically 17778)
- Confirm the SolarWinds Information Service is running

## Security Considerations

- Use environment variables for credentials instead of command-line arguments
- Consider using API tokens if supported by your SolarWinds version
- Ensure HTTPS is used for API connections
- Store credentials securely and rotate them regularly
