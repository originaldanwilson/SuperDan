from netmiko import ConnectHandler, SCPConn
from tools import get_netmiko_creds
import os

# Input variables
switch_ip = "nxos_switch_ip"
local_file = "nxos.bin"
remote_file = "bootflash:nxos.bin"

def upload_nxos_image():
    if not os.path.exists(local_file):
        print(f"File '{local_file}' not found.")
        return

    username, password = get_netmiko_creds()

    device = {
        "device_type": "cisco_nxos",
        "host": switch_ip,
        "username": username,
        "password": password,
    }

    net_connect = ConnectHandler(**device)
    scp_conn = SCPConn(net_connect)

    print(f"Uploading {local_file} to {remote_file} on {switch_ip} ...")
    scp_conn.scp_transfer_file(local_file, remote_file)
    scp_conn.close()
    print("Upload complete.")

    verify = net_connect.send_command(f"dir bootflash: | include {os.path.basename(remote_file)}")
    print("Verification:\n", verify)

    net_connect.disconnect()

if __name__ == "__main__":
    upload_nxos_image()
