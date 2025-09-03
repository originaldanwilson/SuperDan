#!/usr/bin/env python3
# open_perfstack_playwright.py
import argparse
import asyncio
import ipaddress
import sys
import urllib.parse
from datetime import datetime, timedelta, timezone

import requests
from tools import get_ad_creds  # your helper for AD creds

# ---- Hard-coded endpoints ----
DEFAULT_SWIS = "https://orionApi.company.com:17774"
DEFAULT_WEB  = "https://orion.company.com"
SWIS_QUERY_PATH = "/SolarWinds/InformationService/v3/Json/Query"

# ---------------- SWIS helpers ----------------
def swis_get(base_url: str, user: str, pwd: str, swql: str, timeout: int, verify_ssl: bool):
    url = base_url.rstrip("/") + SWIS_QUERY_PATH
    r = requests.get(url, params={"query": swql}, auth=(user, pwd), timeout=timeout, verify=verify_ssl)
    r.raise_for_status()
    data = r.json()
    return data.get("results", data.get("Results", []))

def looks_like_ip(text: str) -> bool:
    try:
        ipaddress.ip_address(text)
        return True
    except ValueError:
        return False

def resolve_node_id(base_url: str, user: str, pwd: str, host: str, timeout: int, verify_ssl: bool) -> int:
    hostEsc = host.replace("'", "''")

    if looks_like_ip(host):
        swql_ip = (
            "SELECT TOP 1 NodeID, Caption, DNS, NodeName, SysName, IPAddress "
            "FROM Orion.Nodes "
            f"WHERE IPAddress='{hostEsc}'"
        )
        res = swis_get(base_url, user, pwd, swql_ip, timeout, verify_ssl)
        if not res:
            raise RuntimeError(f"No node with IP '{host}'")
        return int(res[0]["NodeID"])

    swql_exact = (
        "SELECT TOP 1 NodeID, Caption, DNS, NodeName, SysName, IPAddress "
        "FROM Orion.Nodes "
        f"WHERE Caption='{hostEsc}' OR DNS='{hostEsc}' OR NodeName='{hostEsc}' OR SysName='{hostEsc}'"
    )
    res = swis_get(base_url, user, pwd, swql_exact, timeout, verify_ssl)
    if res:
        return int(res[0]["NodeID"])

    swql_like = (
        "SELECT TOP 10 NodeID, Caption, DNS, NodeName, SysName, IPAddress "
        "FROM Orion.Nodes "
        f"WHERE UPPER(Caption)  LIKE UPPER('%{hostEsc}%') "
        f"   OR UPPER(DNS)      LIKE UPPER('%{hostEsc}%') "
        f"   OR UPPER(NodeName) LIKE UPPER('%{hostEsc}%') "
        f"   OR UPPER(SysName)  LIKE UPPER('%{hostEsc}%') "
        "ORDER BY Caption"
    )
    cand = swis_get(base_url, user, pwd, swql_like, timeout, verify_ssl)
    if not cand:
        raise RuntimeError(f"No node match for '{host}'")
    return int(cand[0]["NodeID"])

def resolve_interface_id(base_url: str, user: str, pwd: str, node_id: int, iface: str,
                         timeout: int, verify_ssl: bool, exact_only: bool) -> int:
    needle = iface.replace("'", "''")
    swql = (
        "SELECT TOP 20 InterfaceID, Name, Caption "
        "FROM Orion.NPM.Interfaces "
        f"WHERE NodeID={node_id} AND (Name LIKE '%{needle}%' OR Caption LIKE '%{needle}%') "
        "ORDER BY Name"
    )
    cand = swis_get(base_url, user, pwd, swql, timeout, verify_ssl)
    if not cand:
        raise RuntimeError(f"No interface containing '{iface}' on NodeID {node_id}")

    ifaceLower = iface.lower()
    for row in cand:
        n = (row.get("Name") or "").lower()
        c = (row.get("Caption") or "").lower()
        if n == ifaceLower or c == ifaceLower:
            return int(row["InterfaceID"])

    if exact_only:
        raise RuntimeError(f"No exact Name/Caption match for '{iface}' on NodeID {node_id}")

    return int(cand[0]["InterfaceID"])

# ---------------- Time + URLs ----------------
def last_hours_window(hours: int):
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=hours)
    return start.strftime("%Y-%m-%dT%H:%M:%SZ"), end.strftime("%Y-%m-%dT%H:%M:%SZ")

def build_perfstack_url(interface_id: int, time_from_iso: str, time_to_iso: str) -> str:
    metrics = [
        f"Orion.NPM.Interfaces_{interface_id}-Orion.NPM.InterfaceTraffic.InAveragebps",
        f"Orion.NPM.Interfaces_{interface_id}-Orion.NPM.InterfaceTraffic.OutAveragebps",
    ]
    charts_val = "0_" + ",".join(metrics) + ";"
    qs = {"charts": charts_val, "timeFrom": time_from_iso, "timeTo": time_to_iso}
    return DEFAULT_WEB.rstrip("/") + "/apps/perfstack/?" + urllib.parse.urlencode(qs)

def build_login_with_return(perfstack_full_url: str) -> str:
    # perfstack_full_url like "https://orion.company.com/apps/perfstack/?..."
    base = DEFAULT_WEB.rstrip("/")
    # ReturnUrl expects path+query, URL-encoded
    path_and_query = perfstack_full_url[len(base):]  # starts with /apps/perfstack/...
    return f"{base}/Orion/Login.aspx?ReturnUrl={urllib.parse.quote(path_and_query, safe='')}"

# ---------------- Playwright flow ----------------
async def login_then_land(page, login_with_return_url: str, username: str, password: str, timeout_ms: int):
    await page.goto(login_with_return_url, wait_until="domcontentloaded", timeout=timeout_ms)

    # Try to locate a username/password form (ASP.NET patterns)
    user_selectors = [
        "input[name*='User']", "input[name*='Username']",
        "input[id*='User']",   "input[id*='Username']",
        "input[type='text']"
    ]
    pass_selectors = [
        "input[name*='Pass']", "input[name*='Password']",
        "input[id*='Pass']",   "input[id*='Password']",
        "input[type='password']"
    ]

    user_el = None
    for sel in user_selectors:
        user_el = await page.query_selector(sel)
        if user_el: break

    pass_el = None
    for sel in pass_selectors:
        pass_el = await page.query_selector(sel)
        if pass_el: break

    if pass_el:
        if user_el:
            await user_el.fill(username)
        await pass_el.fill(password)
        submit = await page.query_selector("input[type='submit'], button[type='submit']")
        if submit:
            await submit.click()
        else:
            await pass_el.press("Enter")
        await page.wait_for_load_state("networkidle", timeout=timeout_ms)

async def open_and_capture(login_url: str, perf_url: str, username: str, password: str, outfile: str,
                           headless: bool, width: int, height: int,
                           wait_selector: str, nav_timeout_ms: int, verify_ssl: bool,
                           load_state: str | None = None, save_state: str | None = None):
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        ctx_args = {
            "viewport": {"width": width, "height": height},
            "ignore_https_errors": (not verify_ssl),
        }
        if load_state:
            ctx_args["storage_state"] = load_state
        context = await browser.new_context(**ctx_args)
        page = await context.new_page()

        # Hit login with ReturnUrl and authenticate if needed
        await login_then_land(page, login_url, username, password, nav_timeout_ms)

        # If we didn’t land on /apps/perfstack (SSO quirks), go directly
        if "/apps/perfstack/" not in page.url:
            await page.goto(perf_url, wait_until="domcontentloaded", timeout=nav_timeout_ms)

        await page.wait_for_load_state("networkidle", timeout=nav_timeout_ms)

        # Wait for chart elements then capture
        try:
            await page.wait_for_selector(wait_selector, timeout=nav_timeout_ms)
        except Exception:
            pass

        await page.screenshot(path=outfile, full_page=True)

        if save_state:
            await context.storage_state(path=save_state)

        await context.close()
        await browser.close()

# ---------------- main ----------------
def main():
    ap = argparse.ArgumentParser(description="Open SolarWinds PerfStack via Playwright and capture a screenshot.")
    ap.add_argument("--host", required=True, help="Hostname/DNS/IP as in Orion (IP is safest).")
    ap.add_argument("--interface", required=True, help="Interface name/caption (e.g. Ethernet1/1).")
    ap.add_argument("--hours", type=int, default=168, help="Last N hours (default 168 = 7 days).")
    ap.add_argument("--exactInterface", action="store_true", help="Require exact interface name/caption.")
    ap.add_argument("--outfile", default="perfstack.png", help="Output PNG filename.")
    ap.add_argument("--width", type=int, default=1600, help="Viewport width.")
    ap.add_argument("--height", type=int, default=900, help="Viewport height.")
    ap.add_argument("--waitSelector", default="canvas, svg", help="CSS selector to wait for before screenshot.")
    ap.add_argument("--timeoutMs", type=int, default=30000, help="Navigation/selector timeout in ms.")
    ap.add_argument("--headed", action="store_true", help="Run browser in headed mode (visible).")
    ap.add_argument("--verifySSL", action="store_true", help="Verify TLS to SWIS/Orion (default off).")
    ap.add_argument("--swisTimeout", type=int, default=30, help="SWIS HTTP timeout seconds.")
    ap.add_argument("--loadState", help="Playwright storage state to load (skip login).")
    ap.add_argument("--saveState", help="Save storage state after run (reuse next time).")
    args = ap.parse_args()

    username, password = get_ad_creds()

    # SWIS often uses self-signed certs; default verify off
    if not args.verifySSL:
        requests.packages.urllib3.disable_warnings()

    try:
        node_id = resolve_node_id(DEFAULT_SWIS, username, password, args.host, args.swisTimeout, args.verifySSL)
        iface_id = resolve_interface_id(DEFAULT_SWIS, username, password, node_id, args.interface,
                                        args.swisTimeout, args.verifySSL, args.exactInterface)

        t_from, t_to = last_hours_window(args.hours)
        perf_url = build_perfstack_url(iface_id, t_from, t_to)
        login_url = build_login_with_return(perf_url)

        print(f"Navigating via ReturnUrl → {perf_url}")
        asyncio.run(
            open_and_capture(
                login_url=login_url,
                perf_url=perf_url,
                username=username,
                password=password,
                outfile=args.outfile,
                headless=(not args.headed),
                width=args.width,
                height=args.height,
                wait_selector=args.waitSelector,
                nav_timeout_ms=args.timeoutMs,
                verify_ssl=args.verifySSL,
                load_state=args.loadState,
                save_state=args.saveState,
            )
        )
        print(f"Saved screenshot: {args.outfile}")
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
