# NX-OS Configuration Manager

A comprehensive Python solution for automating Cisco NX-OS switch configuration using Netmiko, with advanced error handling, logging, and Excel reporting capabilities.

## Features

- **Netmiko-based connectivity** to Cisco NX-OS switches
- **Interface-level error handling** - skips failed interfaces and continues with others
- **Before/after configuration comparison** for each interface
- **Comprehensive logging** with both console and file output
- **Excel spreadsheet generation** showing detailed results
- **Credential management** through tools.py
- **IOS-to-NX-OS command conversion** utility

## Files Overview

### Main Scripts
- **`nxos_config_manager.py`** - Main configuration management class
- **`run_nxos_config_example.py`** - Example usage script
- **`create_nxos_config.py`** - Converts IOS commands to NX-OS format
- **`tools.py`** - Enhanced with logging and credential management functions

### Configuration Files
- **`nxos_config.txt`** - NX-OS configuration commands (auto-generated)
- **`testconfig1c.txt`** - Original IOS configuration file
- **`nxos_requirements.txt`** - Python package requirements

## Installation

1. **Install required packages:**
   ```bash
   pip install -r nxos_requirements.txt
   ```

2. **Update credentials in tools.py:**
   ```python
   netmikoUser = "your_username"    # Replace with actual username
   passwd = "your_password"         # Replace with actual password
   enable = "your_enable_secret"    # Replace with enable secret
   ```

## Usage

### Quick Start

1. **Create or convert your configuration file:**
   ```bash
   python3 create_nxos_config.py
   ```
   This creates `nxos_config.txt` with NX-OS commands.

2. **Update device list in your script:**
   ```python
   device_list = [
       "192.168.1.100",
       "192.168.1.101",
       "switch01.example.com"
   ]
   ```

3. **Run the configuration manager:**
   ```bash
   python3 run_nxos_config_example.py
   ```

### Advanced Usage

```python
from nxos_config_manager import NXOSConfigManager

# Initialize with configuration file and device list
manager = NXOSConfigManager("nxos_config.txt", device_list)

# Process all devices
manager.process_devices()

# Generate detailed Excel report
report_file = manager.generate_spreadsheet_report()

# Print summary
manager.print_summary()
```

## Configuration File Format

The configuration file should contain NX-OS commands in the following format:

```
vlan 10
  name User_Data
vlan 110
  name Voice

interface Ethernet1/1
  description Access Port
  switchport mode access
  switchport access vlan 10
  spanning-tree port type edge
  no shutdown

interface Ethernet1/2
  description Trunk Port
  switchport mode trunk
  switchport trunk allowed vlan 10,110
  no shutdown
```

## Error Handling

The script provides robust error handling at multiple levels:

### Device Level
- Connection failures are logged and the script continues with other devices
- Authentication errors are captured and reported
- Timeout issues are handled gracefully

### Interface Level
- Failed interface configurations don't stop the entire process
- Each interface error is logged with details
- Script continues with remaining interfaces

### Example Error Scenarios
- **Invalid interface names** - Script logs the error and continues
- **Configuration syntax errors** - Captured per interface
- **Device unreachable** - Device marked as failed, script continues

## Logging

The solution provides comprehensive logging:

### Log Locations
- **Console output** - Real-time status and progress
- **Log files** - Stored in `logs/` directory with timestamps
- **Excel reports** - Detailed spreadsheet with all results

### Log Levels
- **INFO** - General progress and status
- **WARNING** - Interface configuration failures
- **ERROR** - Device connection failures and critical errors
- **DEBUG** - Detailed technical information

## Excel Report Structure

The generated Excel file contains multiple sheets:

### Summary Sheet
- Device-level success/failure status
- Interface count summaries
- Configuration save status
- Timestamps for all operations

### Interface Details Sheet
- Per-interface configuration results
- Success/failure status for each interface
- Commands applied to each interface
- Before/after configuration availability

### Failed Interfaces Sheet
- Detailed error information for failed interfaces
- Error messages and troubleshooting information
- Commands that failed to apply

### Before-After Comparison Sheet
- Complete before and after configurations
- Interface status comparisons
- Applied commands for successful interfaces

## Credential Security

### Best Practices
1. **Never commit credentials to version control**
2. **Use environment variables in production:**
   ```python
   import os
   netmikoUser = os.getenv('NETWORK_USERNAME')
   passwd = os.getenv('NETWORK_PASSWORD')
   ```
3. **Consider using credential vaults** for enterprise deployments
4. **Restrict file permissions** on tools.py:
   ```bash
   chmod 600 tools.py
   ```

## Troubleshooting

### Common Issues

#### Import Errors
```
Error: netmiko library not found
```
**Solution:** `pip install netmiko`

#### Connection Failures
```
Connection timeout for 192.168.1.100
```
**Solutions:**
- Verify device IP address is correct
- Check network connectivity
- Ensure SSH is enabled on the device
- Verify credentials

#### Configuration Errors
```
Failed to configure interface Ethernet1/99
```
**Solutions:**
- Check if interface exists on the device
- Verify command syntax for NX-OS
- Review device logs for specific errors

### Debug Mode
Enable debug logging for detailed troubleshooting:

```python
manager = NXOSConfigManager(config_file, device_list)
manager.logger.setLevel(logging.DEBUG)
```

## IOS to NX-OS Conversion

The `create_nxos_config.py` script automatically converts common IOS commands to NX-OS equivalents:

### Automatic Conversions
- `interface GigabitEthernet1/0/1` → `interface Ethernet1/1`
- `spanning-tree portfast` → `spanning-tree port type edge`
- `switchport trunk encapsulation dot1q` → (removed - not needed in NX-OS)

### Manual Review Required
Some commands may need manual review after conversion:
- Complex interface range configurations
- Advanced QoS settings
- Routing protocol configurations

## Performance Considerations

### Timeouts
- Default connection timeout: 120 seconds
- Session timeout: 300 seconds
- Configurable via device configuration dictionary

### Large Deployments
- Process devices in batches for very large deployments
- Use threading for parallel device processing (advanced)
- Monitor memory usage with large configuration files

## Support and Maintenance

### Regular Maintenance
1. **Update netmiko regularly** for latest device support
2. **Review logs periodically** for recurring issues
3. **Backup configuration files** before major changes
4. **Test with lab devices** before production deployment

### Extending the Solution
The modular design allows easy extension:
- Add new device types by modifying device_type parameter
- Extend reporting with additional Excel sheets
- Add custom validation logic for specific environments

## License

This tool is provided as-is for network automation purposes. Please ensure compliance with your organization's security policies and change management procedures.
