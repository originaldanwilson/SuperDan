import logging
import csv
from datetime import datetime
from netmiko import ConnectHandler
from tools import getScriptName, setupLogging, get_netmiko_creds

def collect_interface_names(switch, writer, netmikoUser, passwd):
    device = {
        "device_type": "cisco_nxos",
        "host": switch,
        "username": netmikoUser,
        "password": passwd,
        "secret": passwd
    }

    try:
        logging.info(f"Connecting to {switch}")
        conn = ConnectHandler(**device)
        conn.enable()

        output = conn.send_command("show interface description", use_textfsm=True)
        conn.disconnect()

        if isinstance(output, list):
            for entry in output:
                intf = entry.get("port", "")
                desc = entry.get("description", "")
                if intf:
                    writer.writerow([switch, intf, desc])
            logging.info(f"{switch}: found {len(output)} interfaces")
        else:
            logging.warning(f"{switch}: TextFSM parse failed, got raw string")

    except Exception as e:
        logging.error(f"Failed to query {switch}: {e}")

def main():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    scriptName = getScriptName()
    setupLogging(scriptName, timestamp)
    logging.info(f"{scriptName} started")

    netmikoUser, passwd, enable = get_netmiko_creds()

    nxos_switches = [
        "switch1",
        "switch2",
        # Add your 5596 hostnames or IPs here
    ]

    outfile = f"{scriptName}_{timestamp}.csv"
    with open(outfile, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Switch", "Interface", "Description"])

        for switch in nxos_switches:
            collect_interface_names(switch, writer, netmikoUser, passwd)

    print(f"Interface data saved to: {outfile}")

if __name__ == "__main__":
    main()
