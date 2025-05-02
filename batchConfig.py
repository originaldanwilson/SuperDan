import logging
from netmiko import ConnectHandler
from getUser import get_netmiko_creds

def run_config_batch(device_commands: dict, dry_run=False, device_type="cisco_nxos"):
    """
    Executes interface+description pairs or general command pairs on multiple switches.

    Args:
        device_commands (dict): {
            "switch1": {
                "interface ethernet1/22": "description to swiX",
                "interface ethernet1/23": "description to swiY"
            },
            ...
        }
        dry_run (bool): If True, prints commands instead of sending them.
        device_type (str): Netmiko device type. Default: 'cisco_nxos'.
    """
    username, password, enable = get_netmiko_creds()

    for switch, cmds in device_commands.items():
        if dry_run:
            print(f"\nDRY RUN: Would connect to {switch}")
            for cmd1, cmd2 in cmds.items():
                print(f"  Would send:")
                print(f"    {cmd1}")
                print(f"    {cmd2}")
                print(f"    exit")
            continue

        device = {
            "device_type": device_type,
            "host": switch,
            "username": username,
            "password": password,
        }

        try:
            print(f"Connecting to {switch}...")
            logging.info(f"Connecting to {switch}")
            with ConnectHandler(**device) as conn:
                cmd_list = []
                for cmd1, cmd2 in cmds.items():
                    cmd_list.extend([cmd1, cmd2, "exit"])
                conn.send_config_set(cmd_list)
                print(f"  {switch}: sent {len(cmds)} command blocks.")
                logging.info(f"{switch}: sent {len(cmds)} command blocks.")
        except Exception as e:
            print(f"  {switch}: FAILED - {e}")
            logging.error(f"{switch} failed: {e}")
