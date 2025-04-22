from netmiko import ConnectHandler
from getUser import get_netmiko_creds
from openpyxl import Workbook
from tools import getScriptName, setupLogging
import logging

def get_cdp_neighbors(device, ws, netmikoUser, passwd):
    try:
        conn = ConnectHandler(
            device_type="cisco_nxos",
            host=device["host"],
            username=netmikoUser,
            password=passwd
        )
        output = conn.send_command("show cdp neighbors", use_textfsm=True)
        conn.disconnect()

        if isinstance(output, list):
            for neighbor in output:
                neighbor_name = neighbor.get("neighbor", "unknown")
                local_intf = neighbor.get("local_interface", "unknown")
                remote_intf = neighbor.get("port", "unknown")
                ws.append([device["host"], local_intf, neighbor_name, remote_intf])
        else:
            logging.warning(f"No structured output for {device['host']}")
    except Exception as e:
        logging.error(f"Failed to connect to {device['host']}: {e}")

def auto_width(ws):
    for col in ws.columns:
        max_length = 0
        col_letter = col[0].column_letter
        for cell in col:
            try:
                if cell.value:
                    max_length = max(max_length, len(str(cell.value)))
            except:
                pass
        ws.column_dimensions[col_letter].width = max_length + 2

def main():
    scriptName = getScriptName()
    setupLogging(scriptName)
    logging.info(f"{scriptName} started")

    netmikoUser, passwd = get_netmiko_creds()

    nxos_switches = [
        {"host": "10.0.0.1"},
        {"host": "10.0.0.2"},
        {"host": "10.0.0.3"},
        # Add more NX-OS switches here
    ]

    wb = Workbook()
    ws = wb.active
    ws.title = "cdp_neighbors"
    ws.append(["switch", "port", "neighbor switch", "neighbor port"])
    ws.freeze_panes = "A2"

    for device in nxos_switches:
        get_cdp_neighbors(device, ws, netmikoUser, passwd)

    auto_width(ws)

    xlsx_name = f"{scriptName}.xlsx"
    wb.save(xlsx_name)
    logging.info(f"CDP neighbor spreadsheet saved: {xlsx_name}")

if __name__ == "__main__":
    main()
