"""
NX-OS Switch Configurator
Sends commands to NX-OS switches one at a time, stops on any error.

Usage:  python nxos_configure.py CHG0002222222

Put command files in:  commands/<change_number>/<switch_hostname>.txt
One command per line.  Lines starting with # are skipped.
Credentials come from tools.py.
Log file goes to logs/nxos_configure_<timestamp>.log
"""

import re
import sys
from pathlib import Path
from netmiko import ConnectHandler
from tools import netmikoUser, passwd, enable, setupLogging

logger = setupLogging()

# NX-OS error patterns
ERROR_PATTERNS = [
    re.compile(r"% Invalid", re.IGNORECASE),
    re.compile(r"% Incomplete command", re.IGNORECASE),
    re.compile(r"% Ambiguous command", re.IGNORECASE),
    re.compile(r"% Permission denied", re.IGNORECASE),
    re.compile(r"ERROR:", re.IGNORECASE),
    re.compile(r"% Cannot", re.IGNORECASE),
    re.compile(r"Syntax error", re.IGNORECASE),
    re.compile(r"% Bad IP address", re.IGNORECASE),
    re.compile(r"% Port is not a member", re.IGNORECASE),
    re.compile(r"% Port-channel already exists", re.IGNORECASE),
    re.compile(r"% Interface is in Layer-\d+ mode", re.IGNORECASE),
    re.compile(r"% Requested config change not allowed", re.IGNORECASE),
    re.compile(r"VLAN\(s\) not available", re.IGNORECASE),
]


def check_for_errors(output):
    for line in output.splitlines():
        for pattern in ERROR_PATTERNS:
            if pattern.search(line):
                return line.strip()
    return None


def load_commands(filepath):
    commands = []
    with open(filepath, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if line and not line.startswith("#") and line != "!":
                commands.append(line)
    return commands


def configure_device(hostname, commands):
    """Connect, send commands one by one, stop on error. Returns True/False."""
    logger.info(f"Connecting to {hostname} ({len(commands)} commands)")

    try:
        conn = ConnectHandler(
            device_type="cisco_nxos",
            host=hostname,
            username=netmikoUser,
            password=passwd,
            secret=enable,
        )
    except Exception as e:
        logger.error(f"Failed to connect to {hostname}: {e}")
        return False

    logger.info(f"Connected to {hostname}")
    success = True

    try:
        conn.config_mode()
        for i, command in enumerate(commands, 1):
            logger.info(f"[{i}/{len(commands)}] {command}")
            output = conn.send_command_timing(command, strip_prompt=False, strip_command=False)
            logger.info(f"OUTPUT:\n{output}")

            error = check_for_errors(output)
            if error:
                logger.error(f"FAILED on command {i}/{len(commands)}: {command}")
                logger.error(f"  {error}")
                success = False
                break

        conn.exit_config_mode()
    except Exception as e:
        logger.error(f"Unexpected error on {hostname}: {e}")
        success = False
    finally:
        conn.disconnect()
        logger.info(f"Disconnected from {hostname}")

    if success:
        logger.info(f"All {len(commands)} commands OK on {hostname}")
    return success


def main():
    if len(sys.argv) != 2:
        print("Usage:  python nxos_configure.py CHG0002222222")
        sys.exit(1)

    change = sys.argv[1]
    commands_dir = Path("commands") / change

    if not commands_dir.is_dir():
        logger.error(f"Directory not found: {commands_dir}")
        sys.exit(1)

    device_files = sorted(commands_dir.glob("*.txt"))
    if not device_files:
        logger.error(f"No .txt files in {commands_dir}")
        sys.exit(1)

    logger.info(f"Change: {change} — {len(device_files)} device(s)")
    for df in device_files:
        logger.info(f"  {df.stem}  ({len(load_commands(df))} commands)")

    # Configure each device, stop on first failure
    results = {}
    for df in device_files:
        hostname = df.stem
        commands = load_commands(df)
        if not commands:
            logger.warning(f"Skipping {hostname} — empty file")
            continue

        ok = configure_device(hostname, commands)
        results[hostname] = ok
        if not ok:
            remaining = [f.stem for f in device_files if f.stem not in results]
            if remaining:
                logger.warning(f"Skipped: {', '.join(remaining)}")
            break

    # Summary
    logger.info("SUMMARY:")
    for host, ok in results.items():
        logger.info(f"  {host}: {'SUCCESS' if ok else 'FAILED'}")
    for f in device_files:
        if f.stem not in results:
            logger.info(f"  {f.stem}: SKIPPED")

    if any(not v for v in results.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
