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
    dash_count = 0

    for line in output.splitlines():
        if re.match(r'^-+$', line.strip()):
            dash_count += 1
            continue

        if dash_count < 2:
            continue

        line = line.strip()

        # Look for a line that starts a new port-channel group like:
        # "10     Po1(SU)     LACP       Eth1/22(P)  Eth1/33(P)"
        po_line_match = re.match(r'^\d+\s+(Po\d+\w+)', line)
        if po_line_match:
            # Extract Po ID with status, e.g. Po1(SU)
            current_pc = po_line_match.group(1)

        if current_pc:
            # Find all interfaces like Eth1/22(P)
            matches = re.findall(r'(Eth\d+/\d+(?:/\d+)?)[\s]*(\w)', line)
            for intf, flag in matches:
                portchannel_map[intf] = f"{current_pc} ({flag})"

    return portchannel_map




def parse_portchannel_summary(output):
    portchannel_map = {}
    current_pc = None
    dash_count = 0

    for line in output.splitlines():
        if re.match(r'^-+$', line.strip()):
            dash_count += 1
            continue

        if dash_count < 2:
            continue

        line = line.strip()

        # New Po line with optional members
        po_match = re.match(r'^\d+\s+(Po\d+)', line)
        if po_match:
            current_pc = po_match.group(1)

        # Always look for interfaces, even on same line as Po or wrapped line
        if current_pc:
            matches = re.findall(r'(Eth\d+/\d+(?:/\d+)?)[\s]*(\w)', line)
            for intf, status in matches:
                portchannel_map[intf] = f"{current_pc} ({status})"

    return portchannel_map





    






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
