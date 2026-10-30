#!/usr/bin/env python3
"""
vtp_audit.py  —  Catalyst Switch VTP Audit

Connects concurrently to Catalyst switches, collects:
    show vtp status
    show vtp interface
    show vtp counters

Generates an Excel workbook with four sheets:
    VTP Status    — one row per device, colour-coded by mode
    VTP Traffic   — devices with non-zero inbound VTP advertisements
    VTP Interfaces— per-interface VTP enable state
    Summary       — mode counts and traffic overview

Usage:
    python vtp_audit.py --devices switches.txt
    python vtp_audit.py --devices switches.txt --workers 30 --output my_report.xlsx

Input file:  comma-delimited hostnames or IPs, any number of lines.
             Lines beginning with # are ignored.

Author: SuperDan Environment
"""

import argparse
import logging
import re
import sys
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from netmiko import ConnectHandler
from netmiko.exceptions import NetmikoAuthenticationException, NetmikoTimeoutException

try:
    from openpyxl import Workbook
    from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.table import Table, TableStyleInfo
except ImportError:
    print("ERROR: openpyxl not found.  pip install openpyxl")
    sys.exit(1)

try:
    from tools import get_netmiko_creds, setupLogging, getScriptName, save_file_and_set_permissions
except ImportError:
    print("WARNING: tools.py not found — falling back to interactive credential prompt.")
    import getpass

    def get_netmiko_creds():
        user   = input("SSH Username: ").strip()
        passwd = getpass.getpass("SSH Password: ")
        enable = getpass.getpass("Enable Secret (press Enter to skip): ")
        return user, passwd, enable

    def setupLogging(script_name=None, timestamp=None):
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s  %(levelname)-8s  %(message)s",
            handlers=[logging.StreamHandler(sys.stdout)],
        )

    def getScriptName():
        return os.path.splitext(os.path.basename(sys.argv[0]))[0]

    def save_file_and_set_permissions(path, **_):
        os.chmod(path, 0o664)


# ─────────────────────────────────────────────────────────────────────────────
#  Colour palette (openpyxl hex, no leading #)
# ─────────────────────────────────────────────────────────────────────────────
FILL = {
    "header":      PatternFill("solid", fgColor="2E4057"),   # dark blue-grey
    "server":      PatternFill("solid", fgColor="FF6B6B"),   # red   — VTP Server
    "client":      PatternFill("solid", fgColor="FFD166"),   # amber — VTP Client
    "transparent": PatternFill("solid", fgColor="A8D5A2"),   # green — Transparent
    "off":         PatternFill("solid", fgColor="A0C4FF"),   # blue  — Off
    "unknown":     PatternFill("solid", fgColor="D3D3D3"),   # grey  — error / unknown
    "warning":     PatternFill("solid", fgColor="FFD166"),   # amber — traffic warning
    "alt_row":     PatternFill("solid", fgColor="F5F5F5"),   # very light grey
}

HEADER_FONT  = Font(bold=True, color="FFFFFF", size=11)
BOLD_FONT    = Font(bold=True)
CENTER       = Alignment(horizontal="center", vertical="center", wrap_text=True)
LEFT         = Alignment(horizontal="left",   vertical="center", wrap_text=True)
THIN_BORDER  = Border(
    bottom=Side(style="thin", color="CCCCCC"),
    right=Side(style="thin",  color="CCCCCC"),
)


# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _re(pattern, text, default=""):
    m = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
    return m.group(1).strip() if m else default


def _int(val, default=0):
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def mode_fill(mode: str) -> PatternFill:
    key = mode.lower().replace(" ", "")
    if "server"      in key: return FILL["server"]
    if "client"      in key: return FILL["client"]
    if "transparent" in key: return FILL["transparent"]
    if "off"         in key: return FILL["off"]
    return FILL["unknown"]


# ─────────────────────────────────────────────────────────────────────────────
#  Parsing  (raw text → dicts, no external TextFSM files required)
# ─────────────────────────────────────────────────────────────────────────────

def parse_vtp_status(output: str) -> dict:
    """Parse 'show vtp status' output into a dict."""
    return {
        "vtp_version":   _re(r"VTP [Vv]ersion\s+running\s*:\s*(\S+)", output)
                         or _re(r"VTP [Vv]ersion\s*:\s*(\S+)", output),
        "vtp_mode":      _re(r"VTP [Oo]perating [Mm]ode\s*:\s*(.+)", output)
                         or _re(r"VTP [Mm]ode\s*:\s*(.+)", output, "Unknown"),
        "vtp_domain":    _re(r"VTP [Dd]omain [Nn]ame\s*:\s*(\S*)", output, "(none)"),
        "config_rev":    _re(r"[Cc]onfiguration [Rr]evision\s*:\s*(\d+)", output, "0"),
        "max_vlans":     _re(r"[Mm]aximum [Vv]LANs.*?:\s*(\d+)", output, ""),
        "existing_vlans":_re(r"[Nn]umber of existing [Vv]LANs\s*:\s*(\d+)", output, ""),
        "pruning_mode":  _re(r"VTP [Pp]runing [Mm]ode\s*:\s*(\S+)", output, ""),
        "v2_mode":       _re(r"VTP V2 [Mm]ode\s*:\s*(\S+)", output, ""),
    }


def parse_vtp_interfaces(output: str) -> list:
    """Parse 'show vtp interface' → list of {interface, vtp_status}."""
    results = []
    # Typical line: "GigabitEthernet1/0/1    enabled"
    for line in output.splitlines():
        m = re.match(r"^\s*((?:Gi|Fa|Te|Hu|Po|Vl|Et)\S+)\s+(enabled|disabled)\s*$",
                     line, re.IGNORECASE)
        if m:
            results.append({"interface": m.group(1), "vtp_status": m.group(2).lower()})
    return results


def parse_vtp_counters(output: str) -> dict:
    """Parse 'show vtp counters' → dict of counter values."""
    return {
        "summary_sent":    _int(_re(r"Summary advertisements sent\s*:\s*(\d+)", output)),
        "summary_rcvd":    _int(_re(r"Summary advertisements received\s*:\s*(\d+)", output)),
        "subset_sent":     _int(_re(r"Subset advertisements sent\s*:\s*(\d+)", output)),
        "subset_rcvd":     _int(_re(r"Subset advertisements received\s*:\s*(\d+)", output)),
        "request_sent":    _int(_re(r"Request advertisements sent\s*:\s*(\d+)", output)),
        "request_rcvd":    _int(_re(r"Request advertisements received\s*:\s*(\d+)", output)),
        "rev_errors":      _int(_re(r"Number of config revision errors\s*:\s*(\d+)", output)),
        "digest_errors":   _int(_re(r"Number of config digest errors\s*:\s*(\d+)", output)),
    }


# ─────────────────────────────────────────────────────────────────────────────
#  Device collection (runs in thread pool)
# ─────────────────────────────────────────────────────────────────────────────

def collect_device(device: dict, credentials: dict) -> dict:
    """
    Connect to one device and collect all VTP data.
    device = {"name": hostname, "host": ip}
    Returns a result dict — never raises; errors go into result['error'].
    """
    logger = logging.getLogger(__name__)
    name = device["name"]
    host = device["host"]
    logger.info(f"Connecting to {name} ({host})")

    result = {
        "name":       name,
        "host":       host,
        "status":     "Failed",
        "error":      "",
        "vtp_status": {},
        "interfaces": [],
        "counters":   {},
    }

    device_params = {
        "device_type":    "cisco_ios",
        "host":           host,
        "username":       credentials["username"],
        "password":       credentials["password"],
        "secret":         credentials["secret"],
        "timeout":        30,
        "session_timeout":60,
        "auth_timeout":   20,
        "fast_cli":       False,
    }

    try:
        conn = ConnectHandler(**device_params)
        try:
            conn.enable()
        except Exception:
            pass  # Some devices don't need enable or it auto-enables

        status_raw   = conn.send_command("show vtp status",    use_textfsm=False)
        intf_raw     = conn.send_command("show vtp interface",  use_textfsm=False)
        counter_raw  = conn.send_command("show vtp counters",  use_textfsm=False)
        conn.disconnect()

        result["vtp_status"] = parse_vtp_status(status_raw)
        result["interfaces"] = parse_vtp_interfaces(intf_raw)
        result["counters"]   = parse_vtp_counters(counter_raw)
        result["status"]     = "OK"
        logger.info(f"{name} ({host})  →  {result['vtp_status'].get('vtp_mode', '?')}")

    except NetmikoAuthenticationException as e:
        result["error"] = f"Auth failed: {e}"
        logger.error(f"{host}: {result['error']}")
    except NetmikoTimeoutException as e:
        result["error"] = f"Timeout: {e}"
        logger.warning(f"{host}: {result['error']}")
    except Exception as e:
        result["error"] = str(e)
        logger.error(f"{host}: {result['error']}")

    return result


# ─────────────────────────────────────────────────────────────────────────────
#  Excel helpers
# ─────────────────────────────────────────────────────────────────────────────

def _header_row(ws, headers: list, row: int = 1):
    for col, h in enumerate(headers, 1):
        c = ws.cell(row=row, column=col, value=h)
        c.fill      = FILL["header"]
        c.font      = HEADER_FONT
        c.alignment = CENTER
        c.border    = THIN_BORDER


def _autowidth(ws, min_w: int = 10, max_w: int = 45):
    for col in ws.columns:
        best = min_w
        for cell in col:
            if cell.value is not None:
                best = min(max(best, len(str(cell.value)) + 2), max_w)
        ws.column_dimensions[get_column_letter(col[0].column)].width = best


def _style_data_row(ws, row: int, ncols: int, fill: PatternFill = None):
    bg = fill or (FILL["alt_row"] if row % 2 == 0 else None)
    for col in range(1, ncols + 1):
        c = ws.cell(row=row, column=col)
        if bg:
            c.fill = bg
        c.alignment = CENTER
        c.border    = THIN_BORDER


# ─────────────────────────────────────────────────────────────────────────────
#  Sheet builders
# ─────────────────────────────────────────────────────────────────────────────

def build_status_sheet(ws, results: list):
    """Sheet 1 — VTP Status (one row per device)."""
    headers = [
        "Hostname", "IP Address", "VTP Mode", "VTP Domain", "VTP Version",
        "Config Revision", "Existing VLANs", "Max VLANs",
        "Pruning", "V2 Mode", "Status", "Error",
    ]
    _header_row(ws, headers)
    ws.freeze_panes = "A2"

    for r_idx, res in enumerate(results, 2):
        s = res["vtp_status"]
        mode = s.get("vtp_mode", "Unknown") if res["status"] == "OK" else "N/A"
        row_fill = mode_fill(mode) if res["status"] == "OK" else FILL["unknown"]

        values = [
            res["name"],
            res["host"],
            mode,
            s.get("vtp_domain", ""),
            s.get("vtp_version", ""),
            s.get("config_rev", ""),
            s.get("existing_vlans", ""),
            s.get("max_vlans", ""),
            s.get("pruning_mode", ""),
            s.get("v2_mode", ""),
            res["status"],
            res["error"],
        ]
        for c_idx, val in enumerate(values, 1):
            cell = ws.cell(row=r_idx, column=c_idx, value=val)
            cell.fill      = row_fill
            cell.alignment = CENTER
            cell.border    = THIN_BORDER

    _autowidth(ws)


def build_traffic_sheet(ws, results: list):
    """Sheet 2 — devices with non-zero inbound VTP advertisements."""
    headers = [
        "Hostname", "IP Address", "VTP Mode",
        "Summary Rcvd", "Subset Rcvd", "Request Rcvd",
        "Summary Sent", "Subset Sent",
        "Rev Errors", "Digest Errors",
        "Has Inbound Traffic",
    ]
    _header_row(ws, headers)
    ws.freeze_panes = "A2"

    traffic_rows = []
    for res in results:
        if res["status"] != "OK":
            continue
        c   = res["counters"]
        rcvd = c.get("summary_rcvd", 0) + c.get("subset_rcvd", 0) + c.get("request_rcvd", 0)
        traffic_rows.append((res, rcvd))

    # Sort: rows with traffic first
    traffic_rows.sort(key=lambda x: x[1], reverse=True)

    for r_idx, (res, rcvd) in enumerate(traffic_rows, 2):
        c    = res["counters"]
        mode = res["vtp_status"].get("vtp_mode", "")
        has_traffic = "YES" if rcvd > 0 else "no"
        row_fill = FILL["warning"] if rcvd > 0 else None

        values = [
            res["name"],
            res["host"],
            mode,
            c.get("summary_rcvd", 0),
            c.get("subset_rcvd",  0),
            c.get("request_rcvd", 0),
            c.get("summary_sent", 0),
            c.get("subset_sent",  0),
            c.get("rev_errors",   0),
            c.get("digest_errors",0),
            has_traffic,
        ]
        for c_idx, val in enumerate(values, 1):
            cell = ws.cell(row=r_idx, column=c_idx, value=val)
            if row_fill:
                cell.fill = row_fill
            elif r_idx % 2 == 0:
                cell.fill = FILL["alt_row"]
            cell.alignment = CENTER
            cell.border    = THIN_BORDER

    _autowidth(ws)


def build_interface_sheet(ws, results: list):
    """Sheet 3 — per-interface VTP state (only enabled interfaces)."""
    headers = ["Hostname", "IP Address", "VTP Mode", "Interface", "VTP State"]
    _header_row(ws, headers)
    ws.freeze_panes = "A2"

    r_idx = 2
    for res in results:
        if res["status"] != "OK":
            continue
        mode = res["vtp_status"].get("vtp_mode", "")
        for intf in res["interfaces"]:
            if intf["vtp_status"] != "enabled":
                continue        # only show enabled interfaces
            values = [res["name"], res["host"], mode, intf["interface"], intf["vtp_status"]]
            for c_idx, val in enumerate(values, 1):
                cell = ws.cell(row=r_idx, column=c_idx, value=val)
                cell.fill      = FILL["alt_row"] if r_idx % 2 == 0 else None
                cell.alignment = CENTER
                cell.border    = THIN_BORDER
            r_idx += 1

    if r_idx == 2:
        ws.cell(row=2, column=1, value="No VTP-enabled interfaces found.").alignment = LEFT

    _autowidth(ws)


def build_summary_sheet(ws, results: list):
    """Sheet 4 — mode counts, traffic summary, failure list."""
    ws.freeze_panes = "A1"

    # ── Mode count table ──────────────────────────────────────────────────
    mode_counts: dict = {}
    traffic_count = 0
    failed = []

    for res in results:
        if res["status"] != "OK":
            failed.append(res)
            continue
        mode = res["vtp_status"].get("vtp_mode", "Unknown").strip()
        mode_counts[mode] = mode_counts.get(mode, 0) + 1
        c = res["counters"]
        rcvd = c.get("summary_rcvd", 0) + c.get("subset_rcvd", 0)
        if rcvd > 0:
            traffic_count += 1

    # Title
    title_cell = ws.cell(row=1, column=1, value="VTP Audit — Summary")
    title_cell.font      = Font(bold=True, size=14, color="2E4057")
    title_cell.alignment = LEFT
    ws.merge_cells("A1:C1")

    # Sub-header: mode counts
    row = 3
    ws.cell(row=row, column=1, value="VTP Mode Distribution").font = BOLD_FONT
    row += 1
    for col, h in enumerate(["VTP Mode", "Device Count", "% of Total"], 1):
        c = ws.cell(row=row, column=col, value=h)
        c.fill      = FILL["header"]
        c.font      = HEADER_FONT
        c.alignment = CENTER
    row += 1

    total_ok = sum(mode_counts.values())
    for mode, count in sorted(mode_counts.items(), key=lambda x: -x[1]):
        pct = f"{count / total_ok * 100:.1f}%" if total_ok else "—"
        vals = [mode, count, pct]
        for col, val in enumerate(vals, 1):
            cell = ws.cell(row=row, column=col, value=val)
            cell.fill      = mode_fill(mode)
            cell.alignment = CENTER
            cell.border    = THIN_BORDER
        row += 1

    # Totals row
    ws.cell(row=row, column=1, value="TOTAL").font = BOLD_FONT
    ws.cell(row=row, column=2, value=total_ok).font = BOLD_FONT
    ws.cell(row=row, column=2).alignment = CENTER
    row += 2

    # Traffic summary
    ws.cell(row=row, column=1, value="VTP Traffic Summary").font = BOLD_FONT
    row += 1
    for label, val in [
        ("Devices with inbound VTP advertisements",  traffic_count),
        ("Devices with NO inbound VTP advertisements", total_ok - traffic_count),
        ("Failed / unreachable devices",              len(failed)),
        ("Total devices attempted",                   len(results)),
    ]:
        ws.cell(row=row, column=1, value=label).alignment = LEFT
        ws.cell(row=row, column=2, value=val).alignment   = CENTER
        if val > 0 and "Failed" in label:
            ws.cell(row=row, column=2).fill = FILL["server"]
        row += 1

    row += 1

    # Failed devices list
    if failed:
        ws.cell(row=row, column=1, value="Failed Devices").font = BOLD_FONT
        row += 1
        for col, h in enumerate(["Hostname", "IP Address", "Error"], 1):
            c = ws.cell(row=row, column=col, value=h)
            c.fill = FILL["header"]; c.font = HEADER_FONT; c.alignment = CENTER
        row += 1
        for res in failed:
            ws.cell(row=row, column=1, value=res["name"]).alignment  = LEFT
            ws.cell(row=row, column=2, value=res["host"]).alignment  = LEFT
            ws.cell(row=row, column=3, value=res["error"]).alignment = LEFT
            for col in range(1, 4):
                ws.cell(row=row, column=col).fill = FILL["unknown"]
            row += 1

    ws.column_dimensions["C"].width = 50

    ws.column_dimensions["A"].width = 42
    ws.column_dimensions["B"].width = 18
    ws.column_dimensions["C"].width = 14


# ─────────────────────────────────────────────────────────────────────────────
#  File loading / argument parsing
# ─────────────────────────────────────────────────────────────────────────────

# Keywords that identify a Catalyst switch in the description field
CATALYST_KEYWORDS = ["catalyst", "9300", "9400", "9500", "9200", "9600"]

# Keywords that identify a router — these are excluded even if a Catalyst
# keyword also matches (e.g. a Catalyst ISR description)
ROUTER_KEYWORDS   = ["router", " isr", " asr", "c8", "c11", "c29", "4331",
                     "4351", "4431", "4451", "891", "892", "896"]


def _is_catalyst(description: str) -> bool:
    """Return True if description looks like a Catalyst switch, not a router."""
    desc = description.lower()
    if any(kw in desc for kw in ROUTER_KEYWORDS):
        return False
    return any(kw in desc for kw in CATALYST_KEYWORDS)


def load_hosts(path: str) -> list:
    """
    Parse a SolarWinds-style CSV export:
        switchname.company.com, switchIP, description, 1

    Returns a list of dicts: [{"name": hostname, "host": ip}, ...]
    Only rows whose description matches a Catalyst switch are included.
    Lines beginning with # are skipped.
    """
    if not os.path.exists(path):
        print(f"ERROR: device file not found: {path}")
        sys.exit(1)

    hosts    = []
    skipped  = 0
    errors   = 0

    with open(path) as fh:
        for lineno, raw in enumerate(fh, 1):
            line = raw.strip()
            if not line or line.startswith("#"):
                continue

            parts = [p.strip() for p in line.split(",")]

            if len(parts) < 2:
                logging.warning(f"Line {lineno}: too few columns, skipping: {line}")
                errors += 1
                continue

            hostname    = parts[0]
            ip          = parts[1]
            description = parts[2] if len(parts) > 2 else ""

            if not hostname or not ip:
                logging.warning(f"Line {lineno}: missing hostname or IP, skipping.")
                errors += 1
                continue

            if description and not _is_catalyst(description):
                logging.debug(f"Skipping {hostname} — description does not match Catalyst: {description!r}")
                skipped += 1
                continue

            hosts.append({"name": hostname, "host": ip})

    if skipped:
        print(f"  Filtered out {skipped} non-Catalyst devices based on description.")
    if errors:
        print(f"  Skipped {errors} malformed lines.")

    if not hosts:
        print(f"ERROR: no qualifying Catalyst hosts found in {path}")
        sys.exit(1)

    return hosts


def parse_args():
    p = argparse.ArgumentParser(
        description="Audit VTP configuration on Catalyst switches.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  python vtp_audit.py --devices switches.txt
  python vtp_audit.py --devices switches.txt --workers 30 --output vtp_report.xlsx
""",
    )
    p.add_argument("--devices",  required=True, metavar="FILE",
                   help="Comma-delimited text file of switch hostnames/IPs")
    p.add_argument("--workers",  type=int, default=20, metavar="N",
                   help="Concurrent SSH threads (default: 20)")
    p.add_argument("--output",   default=None, metavar="FILE",
                   help="Output XLSX filename (default: auto-generated with timestamp)")
    return p.parse_args()


# ─────────────────────────────────────────────────────────────────────────────
#  Main
# ─────────────────────────────────────────────────────────────────────────────

def main():
    script_name = getScriptName()
    timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
    setupLogging(script_name, timestamp)
    logger = logging.getLogger(__name__)
    args   = parse_args()

    hosts = load_hosts(args.devices)
    logger.info(f"Loaded {len(hosts)} hosts from {args.devices}")

    user, passwd, enable = get_netmiko_creds()
    credentials = {"username": user, "password": passwd, "secret": enable}

    # ── Concurrent collection ─────────────────────────────────────────────
    results     = []
    done        = 0
    total       = len(hosts)
    workers     = min(args.workers, total)

    logger.info(f"Starting collection with {workers} concurrent workers …")

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(collect_device, d, credentials): d for d in hosts}
        for future in as_completed(futures):
            done += 1
            res = future.result()
            results.append(res)
            pct = done / total * 100
            print(f"  [{done:>4}/{total}  {pct:5.1f}%]  {res['name']:<35}  {res['host']:<16}  {res['status']}"
                  + (f"  ({res['vtp_status'].get('vtp_mode', '')})" if res['status'] == 'OK' else f"  {res['error'][:50]}"),
                  flush=True)

    # ── Sort results by hostname for consistent output ────────────────────
    results.sort(key=lambda r: r["name"].lower())

    # ── Build workbook ────────────────────────────────────────────────────
    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = args.output or f"vtp_audit_{ts}.xlsx"

    wb = Workbook()

    ws_status = wb.active
    ws_status.title = "VTP Status"
    build_status_sheet(ws_status, results)

    ws_traffic = wb.create_sheet("VTP Traffic")
    build_traffic_sheet(ws_traffic, results)

    ws_intf = wb.create_sheet("VTP Interfaces")
    build_interface_sheet(ws_intf, results)

    ws_summary = wb.create_sheet("Summary")
    build_summary_sheet(ws_summary, results)

    # Put Summary first
    wb.move_sheet("Summary", offset=-(len(wb.sheetnames) - 1))

    wb.save(out_file)
    save_file_and_set_permissions(out_file)

    # ── Console summary ───────────────────────────────────────────────────
    ok      = [r for r in results if r["status"] == "OK"]
    failed  = [r for r in results if r["status"] != "OK"]
    modes: dict = {}
    for r in ok:
        m = r["vtp_status"].get("vtp_mode", "Unknown")
        modes[m] = modes.get(m, 0) + 1

    print(f"\n{'='*60}")
    print(f"  VTP Audit Complete — {len(results)} devices")
    print(f"{'='*60}")
    print(f"  Successful  : {len(ok)}")
    print(f"  Failed      : {len(failed)}")
    print(f"\n  VTP Mode Breakdown:")
    for mode, count in sorted(modes.items(), key=lambda x: -x[1]):
        print(f"    {mode:<20}  {count:>4}")
    traffic = sum(
        1 for r in ok
        if r["counters"].get("summary_rcvd", 0)
           + r["counters"].get("subset_rcvd", 0) > 0
    )
    print(f"\n  Devices seeing inbound VTP traffic : {traffic}")
    print(f"\n  Report : {out_file}")
    print(f"{'='*60}\n")

    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
