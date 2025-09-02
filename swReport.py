#!/usr/bin/env python3
import argparse
import sys
import urllib.parse
import webbrowser
import requests
import json
from tools import get_ad_creds

SWIS_JSON = "/SolarWinds/InformationService/v3/Json/Query"

def swis_query(base_swis_url: str, user: str, pwd: str, swql: str, params: dict):
    url = base_swis_url.rstrip("/") + SWIS_JSON
    payload = {"query": swql, "parameters": params}
    r = requests.post(
        url,
        headers={"Content-Type": "application/json"},
        data=json.dumps(payload),
        auth=(user, pwd),
        verify=False
    )
    r.raise_for_status()
    return r.json().get("results", [])

def resolve_node_id(base_swis_url: str, user: str, pwd: str, hostname: str) -> int:
    swql = """
    SELECT TOP 1 NodeID
    FROM Orion.Nodes
    WHERE Caption=@name OR DNS=@name OR IPAddress=@name
    """
    res = swis_query(base_swis_url, user, pwd, swql, {"name": hostname})
    if not res:
        raise RuntimeError(f"No node match for '{hostname}'")
    return int(res[0]["NodeID"])

def resolve_interface_id(base_swis_url: str, user: str, pwd: str, node_id: int, if_name: str) -> int:
    swql = """
    SELECT InterfaceID, Name, Caption
    FROM Orion.NPM.Interfaces
    WHERE NodeID=@nid AND (Name LIKE @needle OR Caption LIKE @needle)
    """
    res = swis_query(base_swis_url, user, pwd, swql, {"nid": node_id, "needle": f"%{if_name}%"})
    if not res:
        raise RuntimeError(f"No interface match containing '{if_name}' on NodeID {node_id}")
    return int(res[0]["InterfaceID"])

def build_perfstack_url(base_web_url: str, iface_id: int, preset_time: str) -> str:
    # PerfStack metrics: In and Out bps
    metrics = [
        f"Orion.NPM.Interfaces_{iface_id}-Orion.NPM.InterfaceTraffic.InAveragebps",
        f"Orion.NPM.Interfaces_{iface_id}-Orion.NPM.InterfaceTraffic.OutAveragebps",
    ]
    charts = "0_" + ",".join(metrics) + ";"
    q = {
        "presetTime": preset_time,
        "charts": charts
    }
    return base_web_url.rstrip("/") + "/apps/perfstack/?" + urllib.parse.urlencode(q)

def main():
    ap = argparse.ArgumentParser(description="Open a SolarWinds PerfStack chart for an interface.")
    ap.add_argument("--host", required=True, help="Hostname/DNS/IP as it appears in SolarWinds.")
    ap.add_argument("--interface", required=True, help="Interface name/caption.")
    ap.add_argument("--webBase", default="https://orion.company.com", help="Base URL for SolarWinds web.")
    ap.add_argument("--swisBase", default="https://orion.company.com:17778", help="Base URL for SWIS REST.")
    ap.add_argument("--preset", default="last7days", help="PerfStack presetTime (e.g. last7days, last24hours).")
    args = ap.parse_args()

    username, password = get_ad_creds()

    try:
        node_id = resolve_node_id(args.swisBase, username, password, args.host)
        iface_id = resolve_interface_id(args.swisBase, username, password, node_id, args.interface)
        url = build_perfstack_url(args.webBase, iface_id, args.preset)
        print(f"Opening: {url}")
        webbrowser.open(url)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    requests.packages.urllib3.disable_warnings()
    main()