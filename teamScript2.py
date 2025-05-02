import logging
from datetime import datetime
from netmiko import ConnectHandler
from getCreds import get_netmiko_creds

def run_config_batch(device_commands: dict, dry_run=False, device_type="cisco_nxos"):
    """
    Executes a batch of configuration commands on multiple switches.

    Enforces consistent input format:
    - Either all values are dicts (pair format), or all are lists (command list format).

    Args:
        device_commands (dict): Dictionary keyed by switch name.
        dry_run (bool): If True, only prints commands without executing.
        device_type (str): Netmiko device type (default 'cisco_nxos').
    """
    username, password, enable = get_netmiko_creds()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")

    # Determine and enforce input format
    formats = set(type(v) for v in device_commands.values())
    if len(formats) > 1:
        logging.error("Mixed input formats detected: must be all dicts or all lists.")
        print("ERROR: Mixed input formats detected. Use only one format across all switches.")
        return

    input_type = formats.pop()
    is_dict_format = input_type is dict
    is_list_format = input_type is list

    if not (is_dict_format or is_list_format):
        logging.error("Unsupported input structure.")
        print("ERROR: Unsupported input structure. Must be dict-of-pairs or list-of-commands.")
        return

    for switch, cmds in device_commands.items():
        if is_list_format:
            cmd_list = cmds
        elif is_dict_format:
            cmd_list = []
            for cmd1, cmd2 in cmds.items():
                cmd_list.extend([cmd1, cmd2, "exit"])
        else:
            continue  # Shouldn't happen

        if dry_run:
            print(f"\nDRY RUN: Would connect to {switch}")
            for cmd in cmd_list:
                print(f"  {cmd}")
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
                conn.send_config_set(cmd_list)
                print(f"  {switch}: sent {len(cmd_list)} lines.")
                logging.info(f"{switch}: sent {len(cmd_list)} config lines.")
        except Exception as e:
            print(f"  {switch}: FAILED - {e}")
            logging.error(f"{switch} failed: {e}")
