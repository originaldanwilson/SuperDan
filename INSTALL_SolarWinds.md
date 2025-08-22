# SolarWinds Scripts Installation Guide

## Quick Installation

### On Ubuntu/Debian Systems:
```bash
# Install system packages
sudo apt update
sudo apt install -y python3-requests python3-urllib3 python3-tabulate

# Clone the repository
git clone https://github.com/originaldanwilson/SuperDan.git
cd SuperDan

# Make scripts executable
chmod +x *.py
```

### On Other Systems (using virtual environment):
```bash
# Clone the repository
git clone https://github.com/originaldanwilson/SuperDan.git
cd SuperDan

# Create virtual environment
python3 -m venv solarwinds-env
source solarwinds-env/bin/activate

# Install dependencies
pip install requests urllib3 tabulate

# Make scripts executable
chmod +x *.py
```

## Dependencies

The SolarWinds monitoring scripts require:
- **Python 3.6+**
- **requests** - For HTTP API calls
- **urllib3** - For SSL handling
- **tabulate** - For formatted table output

## Quick Test

Test the installation with:
```bash
python3 disr_dcsr_portchannel_monitor.py --help
```

You should see the help message without any import errors.

## Usage Examples

### DISR/DCSR Port-Channel Monitor:
```bash
# Basic usage
python3 disr_dcsr_portchannel_monitor.py \
    --server https://your-solarwinds.com \
    --username your-user \
    --password your-pass

# Generate CSV report
python3 disr_dcsr_portchannel_monitor.py \
    --server https://your-solarwinds.com \
    --username your-user \
    --password your-pass \
    --format csv \
    --output weekly_report.csv

# 14-day analysis
python3 disr_dcsr_portchannel_monitor.py \
    --server https://your-solarwinds.com \
    --username your-user \
    --password your-pass \
    --days 14
```

### Using Environment Variables (Recommended):
```bash
export SOLARWINDS_SERVER=https://your-solarwinds.com
export SOLARWINDS_USERNAME=your-username
export SOLARWINDS_PASSWORD=your-password

python3 run_disr_dcsr_report.py
```

## Troubleshooting

### "No module named 'tabulate'"
```bash
# Ubuntu/Debian
sudo apt install python3-tabulate

# Or in virtual environment
pip install tabulate
```

### "No module named 'requests'"
```bash
# Ubuntu/Debian
sudo apt install python3-requests

# Or in virtual environment
pip install requests
```

### SSL Certificate Issues
Add `--no-ssl-verify` flag if using self-signed certificates:
```bash
python3 disr_dcsr_portchannel_monitor.py \
    --server https://your-solarwinds.com \
    --username your-user \
    --password your-pass \
    --no-ssl-verify
```

### Permission Issues
Make scripts executable:
```bash
chmod +x disr_dcsr_portchannel_monitor.py run_disr_dcsr_report.py
```

## Security Notes

- Use environment variables for credentials instead of command-line arguments
- Consider using API tokens if supported by your SolarWinds version
- Ensure HTTPS is used for API connections
- Store credentials securely and rotate them regularly
