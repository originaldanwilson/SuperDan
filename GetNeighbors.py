from netmiko import ConnectHandler
from getUser import get_netmiko_creds
from tools import getScriptName, setupLogging
import logging

def collect_cdp_raw(hostname, netmikoUser, passwd, outfile):
    try:
        conn = ConnectHandler(
            device_type="cisco_nxos",
            host=hostname,
            username=netmikoUser,
            password=passwd
        )

        for intf in ["eth1/21", "eth1/22"]:
            cmd = f"show cdp neighbors interface {intf}"
            output = conn.send_command(cmd, use_textfsm=False)

            outfile.write(f"\n----- {hostname} {intf} -----\n")
            outfile.write(output + "\n")

        conn.disconnect()

    except Exception as e:
        logging.error(f"Failed to connect to {hostname}: {e}")

def main():
    scriptName = getScriptName()
    setupLogging(scriptName)
    logging.info(f"{scriptName} started")

    netmikoUser, passwd = get_netmiko_creds()

    nxos_switches = [
        "switch1.company.com",
        "switch2.company.com",
        "switch3.company.com",
        # Add more DNS names here
    ]

    with open(f"{scriptName}_output.txt", "w") as outfile:
        for hostname in nxos_switches:
            collect_cdp_raw(hostname, netmikoUser, passwd, outfile)

    logging.info(f"Raw CDP output saved to {scriptName}_output.txt")

if __name__ == "__main__":
    main()
