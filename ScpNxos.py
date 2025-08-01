from netmiko import ConnectHandler, SCPConn
from getpass import getpass
import os

switch = {
    "device_type": "cisco_nxos",
    "host": "nxos_switch_ip",
    "username": "your_username",
    "password": getpass("Password: "),
}

local_file = "nxos.bin"
remote_path = "bootflash:nxos.bin"

def upload_file():
    # Ensure file exists
    if not os.path.exists(local_file):
        print(f"File {local_file} not found.")
        return

    # Connect to switch
    net_connect = ConnectHandler(**switch)

    # Open SCP connection
    scp_conn = SCPConn(net_connect)
    print(f"Uploading {local_file} to {remote_path} ...")
    scp_conn.scp_transfer_file(local_file, remote_path)
    scp_conn.close()
    print("Upload complete.")

    # Optionally verify
    output = net_connect.send_command("dir bootflash: | include nxos.bin")
    print(output)

    net_connect.disconnect()

if __name__ == "__main__":
    upload_file()
