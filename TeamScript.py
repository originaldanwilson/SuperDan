import json
import sys
import os
from tools import getScriptName, setupLogging
from batchConfig import run_config_batch

def print_usage(script_name):
    print(f"""
Usage:
  python {script_name} [input_file.json] [--dry-run]

Options:
  input_file.json   JSON file with device command map (default: s.json)
  --dry-run         Show commands that would be sent, but do not execute
  -h, --help        Show this help message
""")

def main():
    scriptName = getScriptName()
    setupLogging(scriptName)

    if "-h" in sys.argv or "--help" in sys.argv:
        print_usage(scriptName)
        sys.exit(0)

    dry_run = "--dry-run" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]

    input_file = args[0] if args else "s.json"

    if not os.path.isfile(input_file):
        logging.error(f"Input file '{input_file}' not found.")
        print(f"ERROR: Input file '{input_file}' not found.")
        sys.exit(1)

    try:
        with open(input_file) as f:
            device_commands = json.load(f)
    except Exception as e:
        logging.error(f"Failed to parse JSON from '{input_file}': {e}")
        print(f"ERROR: Invalid JSON in '{input_file}'")
        sys.exit(1)

    run_config_batch(device_commands, dry_run=dry_run)

if __name__ == "__main__":
    main()

