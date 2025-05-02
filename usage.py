def printUsage(script_name, description="", usage_string=""):
    print(f"\nUsage:\n  python {script_name} [input_file.json] [--dry-run]\n")
    if description:
        print(f"Description:\n  {description}\n")
    if usage_string:
        print("Options:")
        print(usage_string)
    else:
        print("""Options:
  input_file.json   JSON file with device command map (default: s.json)
  --dry-run         Show commands that would be sent, but do not execute
  -h, --help        Show this help message""")
    print("")
