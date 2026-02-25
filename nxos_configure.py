"""
NX-OS Switch Configurator
- Reads per-device command files from a commands/ directory
- Sends each command individually, checking for errors after every command
- Logs all output to per-device log files in a logs/ directory
- Stops immediately on error and reports which command failed

Usage:
    python nxos_configure.py CHG0002222222 [--commands-dir commands] [--logs-dir logs] [--dry-run]

Directory structure:
    commands/
      CHG0002222222/
        switch-core-01.txt
        switch-access-05.txt
      CHG0003333333/
        switch-dist-02.txt

Command file format (one command per line, blanks and # comments skipped).
Credentials are loaded from tools.py (get_netmiko_creds).
"""

import argparse
import os
import re
import sys
from pathlib import Path

try:
    from netmiko import ConnectHandler, NetmikoAuthenticationException, NetmikoTimeoutException
except ImportError:
    print("ERROR: netmiko is required. Install it with:  pip install netmiko")
    sys.exit(1)

from tools import get_netmiko_creds, get_netmiko_device_config, setupLogging

# NX-OS error patterns — add more as you encounter them
NXOS_ERROR_PATTERNS = [
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


# Initialize logger using tools.py — log file named after this script automatically
logger = setupLogging()


def check_for_errors(output: str) -> str | None:
    """Return the first matching error line, or None if clean."""
    for line in output.splitlines():
        for pattern in NXOS_ERROR_PATTERNS:
            if pattern.search(line):
                return line.strip()
    return None


def load_commands(filepath: Path) -> list[str]:
    """Load commands from a file, skipping blanks and comments."""
    commands = []
    with open(filepath, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if line and not line.startswith("#"):
                commands.append(line)
    return commands


def configure_device(
    hostname: str,
    commands: list[str],
    dry_run: bool = False,
) -> bool:
    """Configure a single device. Returns True on success, False on error."""

    logger.info(f"Starting configuration for {hostname} ({len(commands)} commands)")

    if dry_run:
        logger.info("DRY RUN — commands that would be sent:")
        for cmd in commands:
            logger.info(f"  {cmd}")
        return True

    # Build device params from tools.py, override type to nxos
    device_params = get_netmiko_device_config(hostname, device_type="cisco_nxos")

    try:
        conn = ConnectHandler(**device_params)
    except NetmikoAuthenticationException:
        logger.error(f"AUTHENTICATION FAILED for {hostname}")
        return False
    except NetmikoTimeoutException:
        logger.error(f"CONNECTION TIMED OUT for {hostname}")
        return False
    except Exception as e:
        logger.error(f"CONNECTION ERROR for {hostname}: {e}")
        return False

    logger.info(f"Connected to {hostname}")
    success = True

    try:
        # Enter config mode
        config_output = conn.config_mode()
        logger.debug(f"Entered config mode:\n{config_output}")

        for i, command in enumerate(commands, 1):
            logger.info(f"[{i}/{len(commands)}] Sending: {command}")
            output = conn.send_command_timing(
                command,
                strip_prompt=False,
                strip_command=False,
                delay_factor=2,
            )
            logger.info(f"COMMAND: {command}")
            logger.info(f"OUTPUT:\n{output}")

            error_line = check_for_errors(output)
            if error_line:
                logger.error(f"ERROR DETECTED on command {i}/{len(commands)}: {command}")
                logger.error(f"  Error: {error_line}")
                logger.error("Stopping — no further commands will be sent to this device.")
                success = False
                break

        # Exit config mode regardless
        exit_output = conn.exit_config_mode()
        logger.debug(f"Exited config mode:\n{exit_output}")

    except Exception as e:
        logger.error(f"UNEXPECTED ERROR during configuration: {e}")
        success = False
    finally:
        conn.disconnect()
        logger.info(f"Disconnected from {hostname}")

    if success:
        logger.info(f"All {len(commands)} commands completed successfully on {hostname}")

    return success


def main():
    parser = argparse.ArgumentParser(description="Configure NX-OS switches from per-device command files.")
    parser.add_argument("change_number", help="Change number (e.g. CHG0002222222)")
    parser.add_argument("--commands-dir", default="commands", help="Root commands directory (default: commands/)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be sent without connecting")
    parser.add_argument("--devices", nargs="*", help="Only configure these devices (by filename without .txt)")
    args = parser.parse_args()

    change = args.change_number
    commands_dir = Path(args.commands_dir) / change

    if not commands_dir.is_dir():
        logger.error(f"Change directory not found: {commands_dir}")
        logger.error(f"Create it and add one .txt file per device, e.g. {commands_dir}/switch1.txt")
        sys.exit(1)

    logger.info(f"Change: {change}")

    # Discover device files
    device_files = sorted(commands_dir.glob("*.txt"))
    if not device_files:
        logger.error(f"No .txt files found in {commands_dir}/")
        sys.exit(1)

    # Filter to specific devices if requested
    if args.devices:
        device_files = [f for f in device_files if f.stem in args.devices]
        if not device_files:
            logger.error(f"None of the specified devices found in {commands_dir}/")
            sys.exit(1)

    # Show what we found
    logger.info(f"Devices to configure ({len(device_files)}):")
    for df in device_files:
        cmds = load_commands(df)
        logger.info(f"  {df.stem:30s}  ({len(cmds)} commands)")

    # Process each device
    results = {}
    for df in device_files:
        hostname = df.stem
        commands = load_commands(df)
        if not commands:
            logger.warning(f"Skipping {hostname} — no commands in file")
            continue

        logger.info("=" * 60)
        ok = configure_device(hostname, commands, args.dry_run)
        results[hostname] = ok

        if not ok and not args.dry_run:
            logger.error(f"STOPPED on {hostname} due to error.")
            remaining = [f.stem for f in device_files if f.stem not in results]
            if remaining:
                logger.warning(f"Skipped devices: {', '.join(remaining)}")
            break

    # Summary
    logger.info("=" * 60)
    logger.info("SUMMARY:")
    for host, ok in results.items():
        status = "SUCCESS" if ok else "FAILED"
        logger.info(f"  {host:30s}  {status}")

    skipped = [f.stem for f in device_files if f.stem not in results]
    for host in skipped:
        logger.info(f"  {host:30s}  SKIPPED")

    if any(not ok for ok in results.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
