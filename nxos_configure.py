"""
NX-OS Switch Configurator
Sends commands to NX-OS switches.  Each device stops on its first error.
Devices are configured concurrently by default; use --serial for the
original one-at-a-time, stop-on-first-failure behavior.

Usage:
    python nxos_configure.py CHG0002222222
    python nxos_configure.py CHG0002222222 --workers 16
    python nxos_configure.py CHG0002222222 --serial

Put command files in:  commands/<change_number>/<switch_hostname>.txt
One command per line.  Lines starting with # are skipped.
Credentials come from tools.py.
Log file goes to logs/nxos_configure_<timestamp>.log
"""

import argparse
import logging
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from netmiko import ConnectHandler
from tools import get_netmiko_creds, getScriptName, setupLogging

scriptName = getScriptName()
timestamp = datetime.now().strftime('%Y%m%d_%H%M')
log_path = setupLogging(scriptName, timestamp)
logger = logging.getLogger(__name__)
netmikoUser, passwd, enable = get_netmiko_creds()

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
    """Connect, send commands one by one, stop on error.

    Returns a tuple (success, output_lines).  output_lines is a list of
    strings that the caller is expected to print as a single block so
    multi-threaded runs don't interleave per-device output.
    """
    output_lines = [f"\nWorking on {hostname} ({len(commands)} commands)..."]
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
        output_lines.append(f"  *** FAILED to connect to {hostname}: {e}")
        logger.error(f"Failed to connect to {hostname}: {e}")
        return False, output_lines

    logger.info(f"Connected to {hostname}")
    success = True

    try:
        conn.config_mode()
        for i, command in enumerate(commands, 1):
            output_lines.append(f"  [{i}/{len(commands)}] {command}")
            logger.info(f"[{i}/{len(commands)}] {command}")
            output = conn.send_command_timing(command, strip_prompt=False, strip_command=False)
            logger.info(f"OUTPUT:\n{output}")

            error = check_for_errors(output)
            if error:
                output_lines.append(f"  *** ERROR on command {i}: {error}")
                logger.error(f"FAILED on command {i}/{len(commands)}: {command}")
                logger.error(f"  {error}")
                success = False
                break

        conn.exit_config_mode()
    except Exception as e:
        output_lines.append(f"  *** Unexpected error: {e}")
        logger.error(f"Unexpected error on {hostname}: {e}")
        success = False
    finally:
        try:
            conn.disconnect()
        except Exception as e:
            logger.warning(f"Error during disconnect from {hostname}: {e}")
        logger.info(f"Disconnected from {hostname}")

    if success:
        output_lines.append(f"  Completed {hostname} successfully.")
        logger.info(f"All {len(commands)} commands OK on {hostname}")
    else:
        output_lines.append(f"  *** {hostname} FAILED.")
    return success, output_lines


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Push NX-OS configuration to one or more switches.",
    )
    parser.add_argument(
        "change",
        help="Change number / directory name under commands/ (e.g. CHG0002222222)",
    )
    parser.add_argument(
        "-w", "--workers",
        type=int,
        default=8,
        help="Maximum number of devices to configure concurrently (default: 8).",
    )
    parser.add_argument(
        "--serial",
        action="store_true",
        help="Run devices one at a time and stop on the first failure "
             "(original behavior).",
    )
    args = parser.parse_args(argv)
    if args.workers < 1:
        parser.error("--workers must be >= 1")
    if args.serial:
        args.workers = 1
    return args


def run_serial(device_jobs):
    """Original one-at-a-time, stop-on-first-failure behavior.

    device_jobs is a list of (hostname, commands) tuples.
    Returns (results_dict, not_attempted_list).
    """
    results = {}
    not_attempted = []
    for idx, (hostname, commands) in enumerate(device_jobs):
        ok, output_lines = configure_device(hostname, commands)
        for line in output_lines:
            print(line)
        results[hostname] = ok
        if not ok:
            print(f"  *** Stopping. {len(device_jobs) - idx - 1} device(s) not attempted.")
            not_attempted = [h for h, _ in device_jobs[idx + 1:]]
            break
    return results, not_attempted


def run_parallel(device_jobs, workers):
    """Configure devices concurrently using a thread pool.

    device_jobs is a list of (hostname, commands) tuples.
    Returns (results_dict, not_attempted_list).  not_attempted is always
    empty in parallel mode — every job is submitted.
    """
    results = {}
    print(f"\nRunning {len(device_jobs)} device(s) with up to {workers} concurrent worker(s)...")
    logger.info(f"Running {len(device_jobs)} device(s) with up to {workers} concurrent worker(s)")

    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_host = {
            executor.submit(configure_device, hostname, commands): hostname
            for hostname, commands in device_jobs
        }
        for future in as_completed(future_to_host):
            hostname = future_to_host[future]
            try:
                ok, output_lines = future.result()
            except Exception as e:
                # Should be rare — configure_device catches its own errors.
                ok = False
                output_lines = [f"\n  *** Unhandled error on {hostname}: {e}"]
                logger.exception(f"Unhandled error on {hostname}")
            # Print this device's full block as a single, uninterrupted chunk.
            for line in output_lines:
                print(line)
            results[hostname] = ok
    return results, []


def main():
    args = parse_args()
    change = args.change
    commands_dir = Path("commands") / change

    if not commands_dir.is_dir():
        logger.error(f"Directory not found: {commands_dir}")
        sys.exit(1)

    device_files = sorted(commands_dir.glob("*.txt"))
    if not device_files:
        logger.error(f"No .txt files in {commands_dir}")
        sys.exit(1)

    mode = "serial" if args.serial else f"parallel (workers={args.workers})"
    print(f"\nChange: {change} — {len(device_files)} device(s) — mode: {mode}")
    logger.info(f"Change: {change} — {len(device_files)} device(s) — mode: {mode}")

    # Build the job list, splitting out empty files as 'skipped' up front.
    device_jobs = []
    skipped = []
    for df in device_files:
        hostname = df.stem
        commands = load_commands(df)
        if not commands:
            print(f"  Skipping {hostname} — empty file")
            logger.warning(f"Skipping {hostname} — empty file")
            skipped.append(hostname)
            continue
        print(f"  {hostname}  ({len(commands)} commands)")
        logger.info(f"  {hostname}  ({len(commands)} commands)")
        device_jobs.append((hostname, commands))

    if not device_jobs:
        print("\nNothing to do — all command files were empty.")
        logger.warning("Nothing to do — all command files were empty.")
        sys.exit(1)

    if args.serial:
        results, not_attempted = run_serial(device_jobs)
    else:
        results, not_attempted = run_parallel(device_jobs, args.workers)

    skipped.extend(not_attempted)

    # Summary
    succeeded = [h for h, ok in results.items() if ok]
    failed = [h for h, ok in results.items() if not ok]

    print(f"\n{'='*60}")
    print(f"SUMMARY for {change}")
    print(f"{'='*60}")
    if succeeded:
        print(f"  SUCCEEDED: {', '.join(sorted(succeeded))}")
    if failed:
        print(f"  FAILED:    {', '.join(sorted(failed))}")
    if skipped:
        print(f"  SKIPPED:   {', '.join(sorted(skipped))}")
    print(f"\n  Log file:  {log_path}")
    print(f"{'='*60}")

    logger.info("SUMMARY:")
    for host, ok in results.items():
        logger.info(f"  {host}: {'SUCCESS' if ok else 'FAILED'}")
    for host in skipped:
        logger.info(f"  {host}: SKIPPED")

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
