import logging
from datetime import datetime
from netmiko import ConnectHandler
from getCreds import get_netmiko_creds
import csv
from tools import getScriptName, setupLogging

def collect_data(switch, writer, summary_writer, netmikoUser, passwd):
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
        conn.send_command("terminal length 0")

        output = conn.send_command("show interface description", use_textfsm=True)
        connected_count = 0

        for entry in output:
            intf = entry.get("port", "")
            status = entry.get("status", "").lower()
            protocol = entry.get("protocol", "")
            desc = entry.get("description", "")

            writer.writerow([switch, intf, status, protocol, desc])

            intf_lower = intf.lower()
            desc_lower = desc.lower()
            if (
                status == "up"
                and protocol == "up"
                and not intf_lower.startswith("lo")
                and not intf_lower.startswith("mgmt")
                and "uplink" not in desc_lower
            ):
                connected_count += 1

        summary_writer.writerow([switch, connected_count])
        logging.info(f"{switch}: {connected_count} ports fully up with valid interface description")
        conn.disconnect()

    except Exception as e:
        logging.error(f"Failed to query {switch}: {e}")

def main():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    script_name = getScriptName()
    setupLogging(script_name, timestamp)

    nxos_switches = ["sw1", "sw2", "sw3", "sw4"]
    netmikoUser, passwd = get_netmiko_creds()

    interfaces_file = f"{script_name}_interfaces_{timestamp}.csv"
    summary_file = f"{script_name}_summary_{timestamp}.csv"

    with open(interfaces_file, "w", newline="") as f_intf, open(summary_file, "w", newline="") as f_summary:
        writer = csv.writer(f_intf)
        summary_writer = csv.writer(f_summary)

        writer.writerow(["Switch", "Interface", "Status", "Protocol", "Description"])
        summary_writer.writerow(["Switch", "Connected Ports"])

        for switch in nxos_switches:
            collect_data(switch, writer, summary_writer, netmikoUser, passwd)

    print(f"Interface data saved to: {interfaces_file}")
    print(f"Summary data saved to: {summary_file}")

if __name__ == "__main__":
    main()
