import logging
from datetime import datetime
from netmiko import ConnectHandler
from tools import getScriptName, setupLogging, get_netmiko_creds

def get_interface_names(switch, netmikoUser, passwd):
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
            names = [entry.get("port", "") for entry in output if entry.get("port")]
            logging.info(f"{switch}: found {len(names)} interfaces")
            return names
        else:
            logging.warning(f"{switch}: TextFSM parse failed, got raw string")
            return []

    except Exception as e:
        logging.error(f"Failed to query {switch}: {e}")
        return []

def main():
    scriptName = getScriptName()
    setupLogging(scriptName)
    logging.info(f"{scriptName} started")

    netmikoUser, passwd, enable = get_netmiko_creds()

    nxos_switches = [
        "switch1",
        "switch2",
        # Add your 5596 hostnames or IPs here
    ]

    for switch in nxos_switches:
        names = get_interface_names(switch, netmikoUser, passwd)
        print(f"\n--- {switch} ---")
        for name in names:
            print(name)

if __name__ == "__main__":
    main()
