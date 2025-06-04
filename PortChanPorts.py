from netmiko import ConnectHandler
from GetCreds import get_netmiko_creds
from tools import getScriptName, setupLogging
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Font
import logging
import re

def parse_portchannel_summary(output):
    portchannel_map = {}
    current_pc = None
    for line in output.splitlines():
        if line.startswith('Group') or 'Flags' in line:
            continue
        if re.match(r'^\d+\s+Po\d+', line):
            parts = line.split()
            current_pc = parts[1]
        elif current_pc and re.search(r'(Eth\d+/\d+(/\d+)?)', line):
            interfaces = re.findall(r'(Eth\d+/\d+(/\d+)?)', line)
            for match in interfaces:
                portchannel_map[match[0]] = current_pc
    return portchannel_map

def correlate_neighbors(hostname, netmikoUser, passwd, enable):
    logging.info(f"Connecting to {hostname}")
    try:
        conn = ConnectHandler(
            device_type='cisco_nxos',
            host=hostname,
            username=netmikoUser,
            password=passwd,
            secret=enable
        )
        conn.enable()
        cdp_output = conn.send_command("show cdp neighbors", use_textfsm=True)
        pc_output = conn.send_command("show port-channel summary", use_textfsm=False)
        conn.disconnect()
    except Exception as e:
        logging.error(f"{hostname}: {e}")
        return []

    portchannel_map = parse_portchannel_summary(pc_output)
results = []
for entry in cdp_output:
    local_intf = entry['local_interface']
    results.append({
        'Hostname': hostname,
        'Local Interface': local_intf,
        'Port-Channel': portchannel_map.get(local_intf, '---'),
        'Neighbor': entry['neighbor_name'],
        'Neighbor Port': entry['neighbor_interface'],
        'Platform': entry.get('platform', '---')
    })
    results = []
    for entry in cdp_output:
        local_intf = entry['local_port']
        results.append({
            'Hostname': hostname,
            'Local Interface': local_intf,
            'Port-Channel': portchannel_map.get(local_intf, '---'),
            'Neighbor': entry['destination_host'],
            'Neighbor Port': entry['port_id']
        })
    return results

def write_flat_excel(all_rows, filename):
    wb = Workbook()
    ws = wb.active
    ws.title = "CDP_PortChannels"

    headers = ['Hostname', 'Local Interface', 'Port-Channel', 'Neighbor', 'Neighbor Port']
    ws.append(headers)
    for col in ws[1]:
        col.font = Font(bold=True)

    for row in all_rows:
        ws.append([
            row['Hostname'],
            row['Local Interface'],
            row['Port-Channel'],
            row['Neighbor'],
            row['Neighbor Port']
        ])

    ws.freeze_panes = "A2"
    wb.save(filename)
    logging.info(f"Saved Excel report: {filename}")

def main():
    timestamp = datetime.now().strftime('%Y%m%d_%H%M')
    scriptName = getScriptName()
    setupLogging(scriptName, timestamp)

    netmikoUser, passwd, enable = get_netmiko_creds()
    devices = ["switchzz1", "switzz2", "switchAPAC44"]

    all_rows = []
    for hostname in devices:
        rows = correlate_neighbors(hostname, netmikoUser, passwd, enable)
        all_rows.extend(rows)

    if all_rows:
        output_file = f"cdp_pc_flat_{timestamp}.xlsx"
        write_flat_excel(all_rows, output_file)

if __name__ == "__main__":
    main()
