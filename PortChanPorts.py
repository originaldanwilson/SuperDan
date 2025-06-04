from netmiko import ConnectHandler
from GetCreds import get_netmiko_creds
from tools import setupLogging
from datetime import datetime
import logging
import re
from openpyxl import Workbook
from openpyxl.styles import Font

def parse_portchannel_summary(output):
    portchannel_map = {}
    current_pc = None

    for line in output.splitlines():
        if line.startswith('Group') or 'Flags' in line:
            continue
        if re.match(r'^\d+\s+Po\d+', line):
            parts = line.split()
            current_pc = parts[1]  # e.g., Po10
        elif current_pc and re.search(r'(Eth\d+/\d+(/\d+)?)', line):
            interfaces = re.findall(r'(Eth\d+/\d+(/\d+)?)', line)
            for match in interfaces:
                portchannel_map[match[0]] = current_pc
    return portchannel_map

def correlate_neighbors(device):
    logging.info(f"Connecting to {device['host']}")
    conn = ConnectHandler(**device)
    conn.enable()

    cdp_output = conn.send_command("show cdp neighbors", use_textfsm=True)
    pc_output = conn.send_command("show port-channel summary", use_textfsm=False)

    portchannel_map = parse_portchannel_summary(pc_output)

    correlated = []
    for entry in cdp_output:
        local_intf = entry['local_port']
        neighbor = entry['destination_host']
        remote_port = entry['port_id']
        port_channel = portchannel_map.get(local_intf, "---")

        correlated.append({
            'Local Interface': local_intf,
            'Port-Channel': port_channel,
            'Neighbor': neighbor,
            'Neighbor Port': remote_port
        })

    conn.disconnect()
    return correlated

def write_to_excel(data, filename):
    wb = Workbook()
    ws = wb.active
    ws.title = "CDP_PortChannel"

    headers = ['Local Interface', 'Port-Channel', 'Neighbor', 'Neighbor Port']
    ws.append(headers)

    for col in ws[1]:
        col.font = Font(bold=True)

    for row in data:
        ws.append([
            row['Local Interface'],
            row['Port-Channel'],
            row['Neighbor'],
            row['Neighbor Port']
        ])

    wb.save(filename)
    logging.info(f"Saved Excel report: {filename}")

def main():
    timestamp = datetime.now().strftime('%Y%m%d_%H%M')
    setupLogging('nxos_cdp_pc_excel', timestamp)

    netmikoUser, passwd, enable = get_netmiko_creds()
    device = {
        'device_type': 'cisco_nxos',
        'host': '10.0.0.1',  # Replace with actual device IP
        'username': netmikoUser,
        'password': passwd,
        'secret': enable,
    }

    results = correlate_neighbors(device)
    excel_filename = f"cdp_pc_report_{device['host']}_{timestamp}.xlsx"
    write_to_excel(results, excel_filename)

if __name__ == "__main__":
    main()
