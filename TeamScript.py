import json
import sys
from tools import getScriptName, setupLogging
from batchConfig import run_config_batch

def main():
    scriptName = getScriptName()
    setupLogging(scriptName)

    dry_run = "--dry-run" in sys.argv

    with open("s.json") as f:
        device_commands = json.load(f)

    run_config_batch(device_commands, dry_run=dry_run)

if __name__ == "__main__":
    main()
