from netmiko import ConnectHandler
from GetCreds import get_netmiko_creds
from tools import getScriptName, setupLogging
from openpyxl import Workbook
import re
import logging

def get_fex_and_native_counts(hostname, netmikoUser, passwd, ws):
    try:
        conn = ConnectHandler(
            device_type="cisco_nxos",
            host=hostname,
            username=netmikoUser,
            password=passwd
        )
        output = conn.send_command("show interface status", use_textfsm=False)
        conn.disconnect()

        counts = {}

        for line in output.splitlines():
            match = re.match(r"Eth(\d+)/(\d+)/(\d+)", line)
            if match and "connected" in line:
                slot = match.group(1)
                fex_or_native = match.group(2)

                # Native (chassis) interfaces are usually slot 1 and FEX are >100
                label = "native" if int(fex_or_native) < 100 else fex_or_native
                counts[label] = counts.get(label, 0) + 1

        for label, count in sorted(counts.items(), key=lambda x: (x[0] != "native", x[0])):
            ws.append([hostname, label, count])

    except Exception as e:
        logging.error(f"Failed to process {hostname}: {e}")

def auto_width(ws):
    for col in ws.columns:
        max_len = max(len(str(cell.value)) if cell.value else 0 for cell in col)
        ws.column_dimensions[col[0].column_letter].width = max_len + 2

def main():
    scriptName = getScriptName()
    setupLogging(scriptName)
    logging.info(f"{scriptName} started")

    netmikoUser, passwd, enable = get_netmiko_creds()

    switches = [
        "switch1.company.com",
        "switch2.company.com",
        # Add more here
    ]

    wb = Workbook()
    ws = wb.active
    ws.title = "fex_summary"
    ws.append(["switchname", "fex_number", "connected_ports"])
    ws.freeze_panes = "A2"

    for hostname in switches:
        get_fex_and_native_counts(hostname, netmikoUser, passwd, ws)

    auto_width(ws)
    outname = f"{scriptName}.xlsx"
    wb.save(outname)
    logging.info(f"Saved spreadsheet: {outname}")

if __name__ == "__main__":
    main()
