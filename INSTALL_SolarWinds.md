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

### On Red Hat/CentOS/RHEL Systems:
```bash
# Install system packages
sudo yum install -y python3 python3-requests python3-urllib3
# OR on newer versions:
# sudo dnf install -y python3 python3-requests python3-urllib3

# Clone the repository
git clone https://github.com/originaldanwilson/SuperDan.git
cd SuperDan

# Install tabulate (usually not available as system package)
python -m pip install --user tabulate
# OR if you have pip3:
# pip3 install --user tabulate

# Make scripts executable
chmod +x *.py
```

### Using Python Module Method (Works on all systems):
```bash
# Clone the repository
git clone https://github.com/originaldanwilson/SuperDan.git
cd SuperDan

# Install dependencies using python -m pip (most reliable method)
python -m pip install --user requests urllib3 tabulate
# OR with python3 if python points to Python 2:
# python3 -m pip install --user requests urllib3 tabulate

# Make scripts executable
chmod +x *.py
```

### Using Virtual Environment (Recommended for isolation):
```bash
# Clone the repository
git clone https://github.com/originaldanwilson/SuperDan.git
cd SuperDan

# Create virtual environment
python -m venv solarwinds-env
# OR: python3 -m venv solarwinds-env

# Activate virtual environment
source solarwinds-env/bin/activate

# Install dependencies
python -m pip install requests urllib3 tabulate

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

# Red Hat/CentOS/RHEL (tabulate usually not available as system package)
python -m pip install --user tabulate

# Or in virtual environment
python -m pip install tabulate

# If pip command not found, use:
python -m pip install --user tabulate
```

### "No module named 'requests'"
```bash
# Ubuntu/Debian
sudo apt install python3-requests

# Red Hat/CentOS/RHEL
sudo yum install python3-requests
# OR: sudo dnf install python3-requests

# Or using pip module method
python -m pip install --user requests

# Or in virtual environment
python -m pip install requests
```

### "pip: command not found"
```bash
# Use the python module method instead:
python -m pip install --user tabulate requests urllib3

# Or with python3 if python points to Python 2:
python3 -m pip install --user tabulate requests urllib3

# Install pip if needed (Red Hat/CentOS/RHEL):
sudo yum install python3-pip
# OR: sudo dnf install python3-pip
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
