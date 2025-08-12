# IP Address Categorizer

This script categorizes individual IP addresses based on network ranges (CIDR notation) and labels them as either "msft" or "zx".

## Requirements

Install the required Python packages:
```bash
pip install -r requirements.txt
```

## Input Files

### 1. Network Ranges CSV File
- Should contain network ranges in CIDR notation (e.g., 150.171.32.0/22)
- Should have a column indicating whether each range is "msft" or "zx"
- The script will auto-detect column names

Example CSV format:
```csv
network,category
150.171.32.0/22,msft
192.168.1.0/24,zx
10.0.0.0/8,msft
```

### 2. IP Addresses XLSX File  
- Can contain multiple sheets
- Each sheet should have a column with individual IP addresses
- The script will combine all sheets and remove duplicates
- Expected to contain ~65,000 IP addresses across all sheets

## Usage

```bash
python ip_categorizer.py <network_ranges.csv> <ip_addresses.xlsx> <output_file>
```

Examples:
```bash
# Output to CSV
python ip_categorizer.py networks.csv addresses.xlsx results.csv

# Output to XLSX
python ip_categorizer.py networks.csv addresses.xlsx results.xlsx
```

## Output

The output file will contain two columns:
- `ip_address`: The individual IP address
- `category`: Either "msft", "zx", or "uncategorized"

## Features

- **Automatic column detection**: The script will try to identify which columns contain network ranges and categories
- **Multi-sheet support**: Processes all sheets in the XLSX file automatically  
- **Duplicate removal**: Removes duplicate IP addresses while preserving order
- **Progress tracking**: Shows progress for large datasets
- **Error handling**: Continues processing even if some IPs or networks are invalid
- **Flexible output**: Supports both CSV and XLSX output formats

## Performance

The script can handle:
- ~40 network ranges
- ~65,000 individual IP addresses
- Processing typically takes a few seconds to minutes depending on data size

## Troubleshooting

If the script can't find the right columns, it will display:
- Available column names
- Sample data from the file

This helps you identify the correct format or rename columns as needed.
