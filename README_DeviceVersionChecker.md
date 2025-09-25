# Device Version Checker

This script connects to Cisco IOS and IOS XE devices via SSH using Netmiko, collects version information, and generates an Excel report with conditional formatting.

## Required Files

1. **devices.csv** - Contains device information with columns:
   - `devicename,ipAddr,deviceGroup,deviceType`
   - Device types: `cisco_ios` or `cisco_ios_xe` only

2. **known_good_versions.csv** - Contains known good versions with columns:
   - `device_type,version`

## Setup

1. Make sure you have the required Python libraries:
   ```bash
   pip install netmiko openpyxl
   ```

2. Update your credentials in `tools.py` (netmikoUser, passwd, enable)

3. Create your `devices.csv` file using the sample format in `devices_sample.csv`

4. Update `known_good_versions.csv` with your approved versions

## Usage

```bash
python3 DeviceVersionChecker.py
```

## Output

- Excel report with device version information
- Devices with versions below known good versions are highlighted in YELLOW
- Summary statistics printed to console
- Log files in the `logs/` directory

## CSV File Formats

### devices.csv
```
devicename,ipAddr,deviceGroup,deviceType
sw01-access,192.168.1.10,Access,cisco_ios
rtr01-core,192.168.1.30,Core,cisco_ios_xe
```

### known_good_versions.csv
```
device_type,version
cisco_ios,15.2.4.S7
cisco_ios,15.1.4.M12
cisco_ios_xe,16.12.14
cisco_ios_xe,17.3.8
cisco_ios_xe,16.9.8
cisco_ios_xe,17.6.6
cisco_ios_xe,16.6.10
```

## Version Train Matching

The script intelligently matches device versions to appropriate known good versions based on version trains:

- **Same Train Match**: Device running 16.12.5 will be compared against known good 16.12.14
- **Different Train**: Device running 17.3.2 will be compared against known good 17.3.8
- **No Train Match**: If no matching train is found, uses first available version for reference

Example: Device with IOS XE 16.12.8 → Compared against 16.12.14 → Result: "Below" (highlighted yellow)

## Features

- **Smart Device Detection**: Automatically detects IOS XE devices even when CSV lists them as cisco_ios
- **Version Train Matching**: Finds appropriate known good version for the same major.minor train (e.g., 16.12.x matches 16.12.14)
- **Multiple Good Versions**: Supports multiple known good versions per device type for different version trains
- **Automatic Version Extraction**: Parses version from 'show version' output for both IOS and IOS XE
- **Version Comparison**: Compares current vs known good (Below/Match/Above)
- **Excel Report**: Conditional formatting with yellow highlighting for devices needing updates
- **Dual Device Type Tracking**: Shows both detected device type and CSV device type in report
- **Error Handling**: Comprehensive logging and connection error handling
- **Connection Timeout**: Robust timeout and retry logic
