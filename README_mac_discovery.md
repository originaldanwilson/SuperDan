# MAC Discovery & DNS Resolution Tool

Collects locally learned MAC addresses from a Cisco NX-OS Layer 2 switch, resolves them to IP addresses via ARP on the Layer 3 switch, runs `nslookup`, and exports everything to Excel.

## Requirements

- Python 3
- `netmiko`, `openpyxl`
- `tools.py` (credentials and logging)

```
pip install netmiko openpyxl
```

## Usage

```
python mac_discovery.py <l2_switch> <l3_switch>
```

**Example:**

```
python mac_discovery.py dc-leaf-01 dc-spine-01
```

## What It Does

1. Connects to the **L2 switch** and runs `show mac address-table local`
2. Filters to only **dynamic** entries, excluding uplink/infrastructure ports (Eth1/25, Eth1/49–52, port-channel1, and any auto-discovered port-channels)
3. Connects to the **L3 switch** and runs `show ip arp` to map MAC → IP
4. Runs `nslookup` on each resolved IP for DNS names
5. Writes an Excel report with two sheets:
   - **MAC-ARP-DNS** – full data (MAC, VLAN, Port, IP, ARP Interface, DNS Name, switches)
   - **IP Addresses** – just the IPs in a single column for easy bulk copy

## Output

- Excel file: `mac_discovery_<l2_switch>_<timestamp>.xlsx`
- Log file: `logs/mac_discovery_<timestamp>.log`

## Excluded Interfaces

Edit the `EXCLUDE_INTERFACES` list near the top of `mac_discovery.py` to change which ports are skipped. Port-channel memberships are auto-discovered from the running config.

```python
EXCLUDE_INTERFACES = [
    "Eth1/25",
    "Eth1/49",
    "Eth1/50",
    "Eth1/51",
    "Eth1/52",
    "port-channel1",
]
```
