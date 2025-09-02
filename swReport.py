#!/usr/bin/env python3
import argparse
import webbrowser
from tools import get_ad_creds

def load_reports(file_path="reports.txt"):
    try:
        with open(file_path, "r") as f:
            return [line.strip() for line in f if line.strip() and not line.startswith("#")]
    except FileNotFoundError:
        return []

def main():
    parser = argparse.ArgumentParser(description="Open a SolarWinds report in the browser using AD creds.")
    parser.add_argument("report_id", nargs="?", help="SolarWinds report name or ID (e.g. Interfaces_Utilization)")
    parser.add_argument("--baseUrl", default="https://solarwinds.company.com/Orion/Report.aspx",
                        help="Base URL to SolarWinds report.aspx")
    parser.add_argument("--listFile", default="reports.txt",
                        help="Text file containing report IDs (one per line).")
    args = parser.parse_args()

    username, _ = get_ad_creds()

    report_id = args.report_id
    if not report_id:
        reports = load_reports(args.listFile)
        if not reports:
            print("No report specified and no reports.txt found.")
            return
        print("Available reports:")
        for i, r in enumerate(reports, start=1):
            print(f"{i}: {r}")
        choice = input("Choose report number: ").strip()
        try:
            idx = int(choice) - 1
            report_id = reports[idx]
        except (ValueError, IndexError):
            print("Invalid choice.")
            return

    report_url = f"{args.baseUrl}?Report={report_id}&User={username}"
    print(f"Opening: {report_url}")
    webbrowser.open(report_url)

if __name__ == "__main__":
    main()