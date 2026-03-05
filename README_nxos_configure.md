# NX-OS Switch Configurator (nxos_configure.py)

Sends commands to Cisco NX-OS switches one at a time, stops on any error.

## Setup

1. `pip install netmiko`
2. Set your credentials in `tools.py` (`netmikoUser`, `passwd`, `enable`)

## Usage

```
python nxos_configure.py CHG0002222222
```

That's it. It reads all `.txt` files from `commands/CHG0002222222/` and configures each switch.

## File Layout

```
commands/
  CHG0002222222/
    switch-core-01.txt
    switch-access-05.txt
```

Each `.txt` file is named after the switch hostname or IP. One NX-OS command per line. Lines starting with `#` are skipped.

Example `commands/CHG0002222222/switch-core-01.txt`:
```
# Configure access ports
interface Ethernet1/1
  switchport mode access
  switchport access vlan 100
  no shutdown
```

## What It Does

- Connects to each switch using creds from `tools.py`
- Enters config mode, sends commands one by one
- Checks every response for NX-OS errors (invalid command, syntax error, wrong port mode, etc.)
- **Stops immediately** on the first error and reports what failed
- Skips remaining devices after a failure
- Logs everything to console and `logs/nxos_configure_<timestamp>.log`
- Prints a summary at the end (SUCCESS / FAILED / SKIPPED)
