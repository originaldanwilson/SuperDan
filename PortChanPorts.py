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
            current_pc = parts[1]  # Po10
        elif current_pc and re.search(r'(Eth\d+/\d+(/\d+)?)', line):
            interfaces = re.findall(r'(Eth\d+/\d+(/\d+)?)', line)
            for match in interfaces:
                portchannel_map[match[0]] = current_pc
    return portchannel_map

def correlate_neighbors(device):
    logging.info(f"Connecting to {device['host']}")
    try:
        conn = ConnectHandler(**device)
        conn.enable()

        cdp_output = conn.send_command("show cdp neighbors", use_textfsm=True)
        pc_output = conn.send_command("show port-channel summary", use_textfsm=False)
        conn.disconnect()
    except Exception as e:
        logging.error(f"{device['host']}: {e}")
        return []

    portchannel_map = parse_portchannel_summary(pc_output)

    results = []
    for entry in cdp_output:
        local_intf = entry['local_port']
        results.append({
            'Local Interface': local_intf,
            'Port-Channel': portchannel_map.get(local_intf, '---'),
            'Neighbor': entry['destination_host'],
            'Neighbor Port': entry['port_id']
        })
    return results

def write_multi_sheet_excel(all_data, filename):
    wb = Workbook()
    first = True
    for device_name, rows in all_data.items():
        if first:
            ws = wb.active
            ws.title = device_name[:31]
            first = False
        else:
            ws = wb.create_sheet(title=device_name[:31])

        headers = ['Local Interface', 'Port-Channel', 'Neighbor', 'Neighbor Port']
        ws.append(headers)
        for col in ws[1]:
            col.font = Font(bold=True)

        for row in rows:
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
    scriptName = getScriptName()
    setupLogging(scriptName, timestamp)

    netmikoUser, passwd, enable = get_netmiko_creds()

    devices = [
        {'device_type': 'cisco_nxos', 'host': '10.0.0.1'},
        {'device_type': 'cisco_nxos', 'host': '10.0.0.2'},
        # Add more devices as needed
    ]
    for device in devices:
        device['username'] = netmikoUser
        device['password'] = passwd
        device['secret'] = enable

    all_data = {}
    for device in devices:
        device_name = device['host']
        data = correlate_neighbors(device)
        if data:
            all_data[device_name] = data

    if all_data:
        excel_file = f"cdp_pc_multi_{timestamp}.xlsx"
        write_multi_sheet_excel(all_data, excel_file)

if __name__ == "__main__":
    main()
