def save_all_configs(device_list: list, device_type="cisco_nxos"):
    """
    Connects to each switch and saves the running config to startup-config.

    Args:
        device_list (list): List of switch hostnames or IPs
        device_type (str): Netmiko device type (default 'cisco_nxos')
    """
    username, password, enable = get_netmiko_creds()

    for switch in device_list:
        device = {
            "device_type": device_type,
            "host": switch,
            "username": username,
            "password": password,
        }
        try:
            print(f"Connecting to {switch} to save config...")
            with ConnectHandler(**device) as conn:
                conn.save_config()
                print(f"  {switch}: startup-config saved.")
                logging.info(f"{switch}: startup-config saved.")
        except Exception as e:
            print(f"  {switch}: FAILED to save config - {e}")
            logging.error(f"{switch} failed during save: {e}")
