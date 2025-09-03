#!/usr/bin/env python3
# open_perfstack_playwright.py  (Option A: use installed Chrome/Edge)
import argparse, asyncio, ipaddress, sys, urllib.parse
from datetime import datetime, timedelta, timezone
import requests
from tools import get_ad_creds

DEFAULT_SWIS = "https://orionApi.company.com:17774"
DEFAULT_WEB  = "https://orion.company.com"
SWIS_QUERY_PATH = "/SolarWinds/InformationService/v3/Json/Query"
STATE_FILE = "state.json"

# -------- SWIS helpers --------
def swis_get(base_url, user, pwd, swql):
    url = base_url.rstrip("/") + SWIS_QUERY_PATH
    r = requests.get(url, params={"query": swql}, auth=(user, pwd), verify=False, timeout=30)
    r.raise_for_status()
    return r.json().get("results", [])

def looks_like_ip(s):
    try: ipaddress.ip_address(s); return True
    except: return False

def resolve_node_id(base_url, user, pwd, host):
    host_esc = host.replace("'", "''")
    if looks_like_ip(host):
        swql = f"SELECT TOP 1 NodeID FROM Orion.Nodes WHERE IPAddress='{host_esc}'"
    else:
        swql = (
            "SELECT TOP 1 NodeID FROM Orion.Nodes "
            f"WHERE Caption='{host_esc}' OR DNS='{host_esc}' OR NodeName='{host_esc}' OR SysName='{host_esc}'"
        )
    res = swis_get(base_url, user, pwd, swql)
    if not res: raise RuntimeError(f"No node match for '{host}'")
    return int(res[0]["NodeID"])

def resolve_iface_id(base_url, user, pwd, node_id, iface):
    needle = iface.replace("'", "''")
    swql = (
        "SELECT TOP 1 InterfaceID FROM Orion.NPM.Interfaces "
        f"WHERE NodeID={node_id} AND (Name LIKE '%{needle}%' OR Caption LIKE '%{needle}%')"
    )
    res = swis_get(base_url, user, pwd, swql)
    if not res: raise RuntimeError(f"No interface containing '{iface}' on NodeID {node_id}")
    return int(res[0]["InterfaceID"])

# -------- Time + URL helpers --------
def last_hours_window(hours):
    end = datetime.now(timezone.utc)
    start = end - timedelta(hours=hours)
    return start.strftime("%Y-%m-%dT%H:%M:%SZ"), end.strftime("%Y-%m-%dT%H:%M:%SZ")

def build_perfstack_url(iface_id, t_from, t_to):
    metrics = [
        f"Orion.NPM.Interfaces_{iface_id}-Orion.NPM.InterfaceTraffic.InAveragebps",
        f"Orion.NPM.Interfaces_{iface_id}-Orion.NPM.InterfaceTraffic.OutAveragebps",
    ]
    charts = "0_" + ",".join(metrics) + ";"
    qs = {"charts": charts, "timeFrom": t_from, "timeTo": t_to}
    return DEFAULT_WEB.rstrip("/") + "/apps/perfstack/?" + urllib.parse.urlencode(qs)

def build_login_url(perf_url):
    base = DEFAULT_WEB.rstrip("/")
    path_q = perf_url[len(base):]  # "/apps/perfstack/?..."
    return f"{base}/Orion/Login.aspx?ReturnUrl={urllib.parse.quote(path_q, safe='')}"

# -------- Playwright (use installed browser) --------
async def capture(login_url, perf_url, outfile, headed, browser_channel=None, exe_path=None):
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        launch_kwargs = {
            "headless": (not headed),
            "args": ["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-dev-shm-usage"],
        }
        if exe_path:
            launch_kwargs["executable_path"] = exe_path
        elif browser_channel:
            launch_kwargs["channel"] = browser_channel  # "chrome" or "msedge"

        browser = await p.chromium.launch(**launch_kwargs)

        ctx_args = {
            "viewport": {"width": 1600, "height": 900},
            "ignore_https_errors": True,
        }
        # Try to reuse cookies if they exist
        try:
            ctx_args["storage_state"] = STATE_FILE
        except Exception:
            pass

        context = await browser.new_context(**ctx_args)
        page = await context.new_page()

        # Go to login with ReturnUrl; if you’re already authenticated, it should redirect to PerfStack
        await page.goto(login_url, wait_until="domcontentloaded", timeout=45000)
        if "/apps/perfstack/" not in page.url:
            await page.goto(perf_url, wait_until="domcontentloaded", timeout=45000)

        await page.wait_for_load_state("networkidle", timeout=45000)
        try:
            await page.wait_for_selector("canvas, svg", timeout=15000)
        except Exception:
            pass

        await page.screenshot(path=outfile, full_page=True)
        await context.storage_state(path=STATE_FILE)  # persist cookies for next run
        await context.close()
        await browser.close()

# -------- main --------
def main():
    parser = argparse.ArgumentParser(description="Open SolarWinds PerfStack with installed Chrome/Edge, screenshot page.")
    parser.add_argument("--host", required=True, help="Hostname/DNS/IP (IP is most reliable).")
    parser.add_argument("--interface", required=True, help="Interface name/caption (e.g. Ethernet1/1).")
    parser.add_argument("--hours", type=int, default=168, help="Time window: last N hours (default 168 = 7 days).")
    parser.add_argument("--outfile", default="perfstack.png", help="Output PNG filename.")
    parser.add_argument("--headed", action="store_true", help="Show the browser (recommended for first run to log in).")
    # Option A flags:
    parser.add_argument("--browser", choices=["chrome", "msedge"], help="Use installed Chrome/Edge (no playwright install).")
    parser.add_argument("--exePath", help="Full path to Chrome/Edge executable (overrides --browser).")
    args = parser.parse_args()

    # SWIS calls use basic auth; certs are often self-signed
    requests.packages.urllib3.disable_warnings()
    user, pwd = get_ad_creds()

    try:
        node_id  = resolve_node_id(DEFAULT_SWIS, user, pwd, args.host)
        iface_id = resolve_iface_id(DEFAULT_SWIS, user, pwd, node_id, args.interface)
        t_from, t_to = last_hours_window(args.hours)
        perf_url  = build_perfstack_url(iface_id, t_from, t_to)
        login_url = build_login_url(perf_url)

        # Map --browser to Playwright channel
        browser_channel = None
        if args.exePath:
            browser_channel = None
        elif args.browser == "chrome":
            browser_channel = "chrome"
        elif args.browser == "msedge":
            browser_channel = "msedge"

        print(f"Opening PerfStack → {perf_url}")
        asyncio.run(capture(login_url, perf_url, args.outfile, args.headed,
                            browser_channel=browser_channel, exe_path=args.exePath))
        print(f"Saved screenshot: {args.outfile}\nCookies saved: {STATE_FILE}")
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
