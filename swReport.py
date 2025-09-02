#!/usr/bin/env python3
import argparse
import sys
import urllib.parse
import webbrowser
import requests
import ipaddress
from tools import get_ad_creds

# ---- Hard-coded endpoints ----
DEFAULT_SWIS = "https://orionApi.company.com:17774"
DEFAULT_WEB  = "https://orion.company.com"
SWIS_QUERY_PATH = "/SolarWinds/InformationService/v3/Json/Query"

# ---- SWIS GET helper ----
def swis_get(base_url: str, user: str, pwd: str, swql: str, timeout: int = 30, verify_ssl: bool = False):
    url = base_url.rstrip("/") + SWIS_QUERY_PATH
    r = requests.get(url, params={"query": swql}, auth=(user, pwd), timeout=timeout, verify=verify_ssl)
    r.raise_for_status()
    data = r.json()
    return data.get("results", data.get("Results", []))

# ---- Node resolution (robust) ----
def _looks_like_ip(text: str) -> bool:
    try:
        ipaddress.ip_address(text)
        return True
    except ValueError:
        return False

def resolve_node_id(base_url: str, user: str, pwd: str, host: str, show_candidates: bool = False) -> int:
    hostEsc = host.replace("'", "''")

    # If host is IP, go straight to IP exact match (fast & unambiguous)
    if _looks_like_ip(host):
        swql_ip = (
            "SELECT TOP 1 NodeID, Caption, DNS, NodeName, SysName, IPAddress "
            "FROM Orion.Nodes "
            f"WHERE IPAddress='{hostEsc}'"
        )
        res = swis_get(base_url, user, pwd, swql_ip)
        if not res:
            raise RuntimeError(f"No node with IP '{host}'")
        if show_candidates:
            print(f"Selected by IP: NodeID={res[0]['NodeID']} Caption={res[0].get('Caption')} DNS={res[0].get('DNS')} IP={res[0].get('IPAddress')}")
        return int(res[0]["NodeID"])

    # 1) Exact match across common name fields
    swql_exact = (
        "SELECT TOP 1 NodeID, Caption, DNS, NodeName, SysName, IPAddress "
        "FROM Orion.Nodes "
        f"WHERE Caption='{hostEsc}' OR DNS='{hostEsc}' OR NodeName='{hostEsc}' OR SysName='{hostEsc}'"
    )
    res = swis_get(base_url, user, pwd, swql_exact)
    if res:
        if show_candidates:
            print(f"Selected by exact: NodeID={res[0]['NodeID']} Caption={res[0].get('Caption')} DNS={res[0].get('DNS')} IP={res[0].get('IPAddress')}")
        return int(res[0]["NodeID"])

    # 2) Case-insensitive partial match across common fields
    swql_like = (
        "SELECT TOP 10 NodeID, Caption, DNS, NodeName, SysName, IPAddress "
        "FROM Orion.Nodes "
        f"WHERE UPPER(Caption)  LIKE UPPER('%{hostEsc}%') "
        f"   OR UPPER(DNS)      LIKE UPPER('%{hostEsc}%') "
        f"   OR UPPER(NodeName) LIKE UPPER('%{hostEsc}%') "
        f"   OR UPPER(SysName)  LIKE UPPER('%{hostEsc}%') "
        "ORDER BY Caption"
    )
    cand = swis_get(base_url, user, pwd, swql_like)
    if not cand:
        raise RuntimeError(f"No node match for '{host}'")

    # Choose best candidate (prefer exact lower-case match, else first)
    hostLower = host.lower()
    target = cand[0]
    for row in cand:
        for fld in ("Caption", "DNS", "NodeName", "SysName"):
            val = (row.get(fld) or "").lower()
            if val == hostLower:
                target = row
                break
    if show_candidates:
        print("Node candidates:")
        for r in cand:
            print(f"  NodeID={r['NodeID']} Caption={r.get('Caption')} DNS={r.get('DNS')} NodeName={r.get('NodeName')} SysName={r.get('SysName')} IP={r.get('IPAddress')}")
        print(f"Selected NodeID={target['NodeID']}")
    return int(target["NodeID"])

# ---- Interface resolution (robust) ----
def resolve_interface_id(base_url: str, user: str, pwd: str, node_id: int, iface: str,
                         exact_only: bool = False, show_candidates: bool = False) -> int:
    needle = iface.replace("'", "''")

    # Fetch a small candidate set
    swql = (
        "SELECT TOP 20 InterfaceID, Name, Caption "
        "FROM Orion.NPM.Interfaces "
        f"WHERE NodeID={node_id} AND (Name LIKE '%{needle}%' OR Caption LIKE '%{needle}%') "
        "ORDER BY Name"
    )
    cand = swis_get(base_url, user, pwd, swql)
    if not cand:
        raise RuntimeError(f"No interface containing '{iface}' on NodeID {node_id}")

    ifaceLower = iface.lower()

    # Exact (case-insensitive) first
    for row in cand:
        n = (row.get("Name") or "").lower()
        c = (row.get("Caption") or "").lower()
        if n == ifaceLower or c == ifaceLower:
            if show_candidates:
                print(f"Selected interface by exact: InterfaceID={row['InterfaceID']} Name={row.get('Name')} Caption={row.get('Caption')}")
            return int(row["InterfaceID"])

    if exact_only:
        raise RuntimeError(f"No exact Name/Caption match for '{iface}' on NodeID {node_id}")

    # Else use first contains() hit (already filtered by LIKE)
    row = cand[0]
    if show_candidates:
        print("Interface candidates:")
        for r in cand:
            print(f"  InterfaceID={r['InterfaceID']} Name={r.get('Name')} Caption={r.get('Caption')}")
        print(f"Selected InterfaceID={row['InterfaceID']}")
    return int(row["InterfaceID"])

# ---- PerfStack URL ----
def build_perfstack_url(interface_id: int, preset: str) -> str:
    metrics = [
        f"Orion.NPM.Interfaces_{interface_id}-Orion.NPM.InterfaceTraffic.InAveragebps",
        f"Orion.NPM.Interfaces_{interface_id}-Orion.NPM.InterfaceTraffic.OutAveragebps",
    ]
    charts_val = "0_" + ",".join(metrics) + ";"
    qs = {"presetTime": preset, "charts": charts_val}
    return DEFAULT_WEB.rstrip("/") + "/apps/perfstack/?" + urllib.parse.urlencode(qs)

# ---- main ----
def main():
    ap = argparse.ArgumentParser(description="Open a PerfStack chart for an interface (robust lookup via SWIS 17774).")
    ap.add_argument("--host", required=True, help="Hostname/DNS/IP as shown in Orion (IP is most reliable).")
    ap.add_argument("--interface", required=True, help="Interface name/caption (e.g. Ethernet1/1).")
    ap.add_argument("--preset", default="last7days", help="PerfStack presetTime (e.g., last7days, last24hours).")
    ap.add_argument("--exactInterface", action="store_true", help="Require exact interface Name/Caption match.")
    ap.add_argument("--showCandidates", action="store_true", help="Print candidates before choosing.")
    ap.add_argument("--verifySSL", action="store_true", help="Enable TLS verification (default off).")
    ap.add_argument("--timeout", type=int, default=30, help="HTTP timeout seconds.")
    args = ap.parse_args()

    user, pwd = get_ad_creds()
    if not args.verifySSL:
        requests.packages.urllib3.disable_warnings()

    try:
        node_id = resolve_node_id(DEFAULT_SWIS, user, pwd, args.host, show_candidates=args.showCandidates)
        iface_id = resolve_interface_id(DEFAULT_SWIS, user, pwd, node_id, args.interface,
                                        exact_only=args.exactInterface, show_candidates=args.showCandidates)
        url = build_perfstack_url(iface_id, args.preset)
        print(f"Opening: {url}")
        webbrowser.open(url)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()