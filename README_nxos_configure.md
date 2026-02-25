# NX-OS Switch Configurator (nxos_configure.py)

A Python script for pushing configuration commands to Cisco NX-OS switches, organized by change number. Commands are sent one at a time with error detection — if anything goes wrong, the script stops immediately and tells you exactly what failed.

## Prerequisites

- Python 3.10+
- netmiko (`pip install netmiko`)
- `tools.py` (included in this repo — provides credentials, logging, and device config)

## Directory Structure

Command files are organized by change number under a `commands/` directory. Each `.txt` file is named after the switch hostname or IP:

```
commands/
  CHG0002222222/
    switch-core-01.txt
    switch-access-05.txt
  CHG0003333333/
    switch-dist-02.txt
```

## Command File Format

One NX-OS command per line. Blank lines and lines starting with `#` are skipped.

```
# Configure access ports
interface Ethernet1/1
  switchport mode access
  switchport access vlan 100
  no shutdown

interface Ethernet1/2
  switchport mode access
  switchport access vlan 200
  no shutdown
```

## Usage

### Basic Run

```
python nxos_configure.py CHG0002222222
```

Reads all `.txt` files from `commands/CHG0002222222/`, connects to each device, and sends commands one by one. Credentials come from `tools.py` (`get_netmiko_creds`).

### Dry Run (no connections made)

```
python nxos_configure.py CHG0002222222 --dry-run
```

Shows which devices would be configured and what commands would be sent, without actually connecting.

### Target Specific Devices

```
python nxos_configure.py CHG0002222222 --devices switch-core-01 switch-access-05
```

Only configures the listed devices (filenames without `.txt`).

### Custom Commands Directory

```
python nxos_configure.py CHG0002222222 --commands-dir my_commands
```

Looks for command files in `my_commands/CHG0002222222/` instead of the default `commands/`.

## Error Handling

The script checks every command response for NX-OS error patterns including:

- `% Invalid command`
- `% Incomplete command`
- `% Ambiguous command`
- `% Permission denied`
- `Syntax error`
- `% Interface is in Layer-X mode`
- `% Port-channel already exists`
- `% Requested config change not allowed`
- `VLAN(s) not available`
- And more (see `NXOS_ERROR_PATTERNS` in the script)

When an error is detected:
1. The exact error and failed command are logged
2. No further commands are sent to that device
3. Remaining devices are skipped
4. A summary is printed showing what succeeded, failed, and was skipped

## Logging

Logging is handled by `setupLogging()` from `tools.py`. Logs go to both the console and a timestamped file in `logs/`:

```
logs/nxos_configure_20260225_235500.log
```

All commands and their full output are logged, along with connection events and errors.

## Credentials

Credentials are managed in `tools.py` via `get_netmiko_creds()` and `get_netmiko_device_config()`. Update the values in `tools.py` before running:

```python
netmikoUser = "your_username"
passwd = "your_password"
enable = "your_enable_secret"
```

## Quick Reference

| Command | Description |
|---------|-------------|
| `python nxos_configure.py CHG123` | Run change CHG123 |
| `python nxos_configure.py CHG123 --dry-run` | Preview without connecting |
| `python nxos_configure.py CHG123 --devices sw1 sw2` | Only configure sw1 and sw2 |
| `python nxos_configure.py CHG123 --commands-dir other` | Use alternate commands dir |
