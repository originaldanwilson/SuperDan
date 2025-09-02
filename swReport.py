#!/usr/bin/env python3
import argparse
import sys
import urllib.parse
import webbrowser
import requests
from tools import get_ad_creds

# Hard-coded endpoints
DEFAULT_SWIS = "https://orionApi.company.com:17774"
DEFAULT_WEB  = "https://orion.company.com"
SWIS_QUERY_PATH = "/SolarWinds/InformationService/v3/Json/Query"

def swisGet(baseUrl: str, user: str, pwd: str, swql: str, timeout: int = 30, verifySsl: bool = False):
    url = baseUrl.rstrip("/") + SWIS_QUERY_PATH
    r = requests.get(url, params={"query": swql}, auth=(user, pwd), timeout=timeout, verify=verifySsl)
    r.raise_for_status()
    data = r.json()
    return data.get("results", data.get("Results", []))

def resolveNodeId(baseUrl: str, user: str, pwd: str, host: str) -> int:
    # Match by Caption, DNS, or IP
    hostEsc = host.replace("'", "''")
    swql = (
        "SELECT TOP 1 NodeID "
        "FROM Orion.Nodes "
        f"WHERE Caption='{hostEsc}' OR DNS='{hostEsc}' OR IPAddress='{hostEsc}'"
    )
    res = swisGet(baseUrl, user, pwd, swql)
    if not res:
        raise RuntimeError(f"No node match for '{host}'")
    return int(res[0]["NodeID"])

def resolveInterfaceId(baseUrl: str, user: str, pwd: str, nodeId: int, iface: str) -> int:
    # Prefer exact (case-insensitive) Name/Caption; else first LIKE match
    needle = iface.replace("'", "''")
    swql = (
        "SELECT InterfaceID, Name, Caption "
        "FROM Orion.NPM.Interfaces "
        f"WHERE NodeID={nodeId} AND (Name LIKE '%{needle}%' OR Caption LIKE '%{needle}%') "
        "ORDER BY Name"
    )
    res = swisGet(baseUrl, user, pwd, swql)
    if not res:
        raise RuntimeError(f"No interface containing '{iface}' on NodeID {nodeId}")
    for row in res:
        n = (row.get("Name") or "").lower()
        c = (row.get("Caption") or "").lower()
        if n == iface.lower() or c == iface.lower():
            return int(row["InterfaceID"])
    return int(res[0]["InterfaceID"])

def buildPerfstackUrl(interfaceId: int, preset: str) -> str:
    metrics = [
        f"Orion.NPM.Interfaces_{interfaceId}-Orion.NPM.InterfaceTraffic.InAveragebps",
        f"Orion.NPM.Interfaces_{interfaceId}-Orion.NPM.InterfaceTraffic.OutAveragebps",
    ]
    chartsVal = "0_" + ",".join(metrics) + ";"
    qs = {"presetTime": preset, "charts": chartsVal}
    return DEFAULT_WEB.rstrip("/") + "/apps/perfstack/?" + urllib.parse.urlencode(qs)

def main():
    ap = argparse.ArgumentParser(description="Open a PerfStack chart for an interface (SWIS on 17774).")
    ap.add_argument("--host", required=True, help="Hostname/DNS/IP as shown in Orion.")
    ap.add_argument("--interface", required=True, help="Interface name/caption (e.g. Ethernet1/1).")
    ap.add_argument("--preset", default="last7days", help="PerfStack presetTime (e.g. last7days, last24hours).")
    ap.add_argument("--verifySSL", action="store_true", help="Enable TLS verification (default off).")
    ap.add_argument("--timeout", type=int, default=30, help="HTTP timeout seconds.")
    args = ap.parse_args()

    user, pwd = get_ad_creds()
    if not args.verifySSL:
        requests.packages.urllib3.disable_warnings()

    try:
        nodeId = resolveNodeId(DEFAULT_SWIS, user, pwd, args.host)
        ifaceId = resolveInterfaceId(DEFAULT_SWIS, user, pwd, nodeId, args.interface)
        url = buildPerfstackUrl(ifaceId, args.preset)
        print(f"Opening: {url}")
        webbrowser.open(url)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()