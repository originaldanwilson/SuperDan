from netmiko import ConnectHandler
from getUser import get_netmiko_creds
from openpyxl import Workbook
import logging

def get_cdp_neighbors(device, ws):
    try:
        connection = ConnectHandler(**device)
        output = connection.send_command("show cdp neighbors", use_textfsm=True)
        connection.disconnect()

        if isinstance(output, list):
            for neighbor in output:
                neighbor_name = neighbor.get("neighbor", "unknown")
                local_intf = neighbor.get("local_interface", "unknown")
                remote_intf = neighbor.get("port", "unknown")
                ws.append([device['host'], local_intf, neighbor_name, remote_intf])
        else:
            logging.warning(f"No structured output for {device['host']}")
    except Exception as e:
        logging.error(f"Failed to connect to {device['host']}: {e}")

def main():
    netmikoUser, passwd = get_netmiko_creds()
    switches = [
        {"device_type": "cisco_ios", "host": "10.0.0.1", "username": netmikoUser, "password": passwd},
        # Add more devices here
    ]

    wb = Workbook()
    ws = wb.active
    ws.title = "cdp_neighbors"
    ws.append(["switch", "port", "neighbor switch", "neighbor port"])

    for device in switches:
        get_cdp_neighbors(device, ws)

    wb.save("cdp_neighbors.xlsx")

if __name__ == "__main__":
    main()
