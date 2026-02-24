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
Credentials are prompted interactively (same creds used for all devices).
"""

import argparse
import getpass
import os
import re
import sys
from datetime import datetime
from pathlib import Path

try:
    from netmiko import ConnectHandler, NetmikoAuthenticationException, NetmikoTimeoutException
except ImportError:
    print("ERROR: netmiko is required. Install it with:  pip install netmiko")
    sys.exit(1)

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


class DeviceLogger:
    """Handles per-device timestamped logging to file and console."""

    def __init__(self, hostname: str, logs_dir: Path):
        logs_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.logfile = logs_dir / f"{hostname}_{timestamp}.log"
        self._fh = open(self.logfile, "w", encoding="utf-8")
        self.hostname = hostname

    def log(self, message: str, also_print: bool = False):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"[{ts}] {message}"
        self._fh.write(entry + "\n")
        self._fh.flush()
        if also_print:
            print(entry)

    def log_output(self, command: str, output: str):
        self.log(f"COMMAND: {command}")
        self.log(f"OUTPUT:\n{output}")

    def close(self):
        self._fh.close()


def configure_device(
    hostname: str,
    commands: list[str],
    username: str,
    password: str,
    logs_dir: Path,
    dry_run: bool = False,
) -> bool:
    """Configure a single device. Returns True on success, False on error."""

    logger = DeviceLogger(hostname, logs_dir)
    logger.log(f"Starting configuration for {hostname} ({len(commands)} commands)", also_print=True)

    if dry_run:
        logger.log("DRY RUN — commands that would be sent:", also_print=True)
        for cmd in commands:
            logger.log(f"  {cmd}", also_print=True)
        logger.close()
        return True

    device_params = {
        "device_type": "cisco_nxos",
        "host": hostname,
        "username": username,
        "password": password,
        "timeout": 30,
        "session_log": str(logger.logfile.with_suffix(".session.log")),
    }

    try:
        conn = ConnectHandler(**device_params)
    except NetmikoAuthenticationException:
        logger.log(f"AUTHENTICATION FAILED for {hostname}", also_print=True)
        logger.close()
        return False
    except NetmikoTimeoutException:
        logger.log(f"CONNECTION TIMED OUT for {hostname}", also_print=True)
        logger.close()
        return False
    except Exception as e:
        logger.log(f"CONNECTION ERROR for {hostname}: {e}", also_print=True)
        logger.close()
        return False

    logger.log(f"Connected to {hostname}", also_print=True)
    success = True

    try:
        # Enter config mode
        config_output = conn.config_mode()
        logger.log(f"Entered config mode:\n{config_output}")

        for i, command in enumerate(commands, 1):
            logger.log(f"[{i}/{len(commands)}] Sending: {command}", also_print=True)
            output = conn.send_command_timing(
                command,
                strip_prompt=False,
                strip_command=False,
                delay_factor=2,
            )
            logger.log_output(command, output)

            error_line = check_for_errors(output)
            if error_line:
                logger.log(
                    f"ERROR DETECTED on command {i}/{len(commands)}: {command}",
                    also_print=True,
                )
                logger.log(f"  Error: {error_line}", also_print=True)
                logger.log("Stopping — no further commands will be sent to this device.", also_print=True)
                success = False
                break

        # Exit config mode regardless
        exit_output = conn.exit_config_mode()
        logger.log(f"Exited config mode:\n{exit_output}")

    except Exception as e:
        logger.log(f"UNEXPECTED ERROR during configuration: {e}", also_print=True)
        success = False
    finally:
        conn.disconnect()
        logger.log(f"Disconnected from {hostname}", also_print=True)

    if success:
        logger.log(f"All {len(commands)} commands completed successfully on {hostname}", also_print=True)

    logger.close()
    return success


def main():
    parser = argparse.ArgumentParser(description="Configure NX-OS switches from per-device command files.")
    parser.add_argument("change_number", help="Change number (e.g. CHG0002222222)")
    parser.add_argument("--commands-dir", default="commands", help="Root commands directory (default: commands/)")
    parser.add_argument("--logs-dir", default="logs", help="Root logs directory (default: logs/)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be sent without connecting")
    parser.add_argument("--devices", nargs="*", help="Only configure these devices (by filename without .txt)")
    args = parser.parse_args()

    change = args.change_number
    commands_dir = Path(args.commands_dir) / change
    logs_dir = Path(args.logs_dir) / change

    if not commands_dir.is_dir():
        print(f"ERROR: Change directory not found: {commands_dir}")
        print(f"Create it and add one .txt file per device, e.g. {commands_dir}/switch1.txt")
        sys.exit(1)

    print(f"Change: {change}")

    # Discover device files
    device_files = sorted(commands_dir.glob("*.txt"))
    if not device_files:
        print(f"ERROR: No .txt files found in {commands_dir}/")
        sys.exit(1)

    # Filter to specific devices if requested
    if args.devices:
        device_files = [f for f in device_files if f.stem in args.devices]
        if not device_files:
            print(f"ERROR: None of the specified devices found in {commands_dir}/")
            sys.exit(1)

    # Show what we found
    print(f"\nDevices to configure ({len(device_files)}):")
    for df in device_files:
        cmds = load_commands(df)
        print(f"  {df.stem:30s}  ({len(cmds)} commands)")

    if not args.dry_run:
        print()
        username = input("Username: ")
        password = getpass.getpass("Password: ")
        print()
    else:
        username = password = ""

    # Process each device
    results = {}
    for df in device_files:
        hostname = df.stem
        commands = load_commands(df)
        if not commands:
            print(f"Skipping {hostname} — no commands in file")
            continue

        print(f"\n{'='*60}")
        ok = configure_device(hostname, commands, username, password, logs_dir, args.dry_run)
        results[hostname] = ok

        if not ok and not args.dry_run:
            print(f"\n*** STOPPED on {hostname} due to error. ***")
            remaining = [f.stem for f in device_files if f.stem not in results]
            if remaining:
                print(f"Skipped devices: {', '.join(remaining)}")
            break

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY:")
    for host, ok in results.items():
        status = "SUCCESS" if ok else "FAILED"
        print(f"  {host:30s}  {status}")

    skipped = [f.stem for f in device_files if f.stem not in results]
    for host in skipped:
        print(f"  {host:30s}  SKIPPED")

    print(f"\nLogs saved to: {logs_dir.resolve()}")

    if any(not ok for ok in results.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
