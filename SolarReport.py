#!/usr/bin/env python3
# open_perfstack_simple.py
# Minimal: SWIS lookup -> PerfStack URL (timeFrom/timeTo) -> open installed Edge/Chrome via Playwright -> screenshot
import argparse, asyncio, ipaddress, sys, urllib.parse, os
from datetime import datetime, timedelta, timezone
import requests
from tools import get_ad_creds

DEFAULT_SWIS = "https://orionApi.company.com:17774"
DEFAULT_WEB  = "https://orion.company.com"
SWIS_QUERY_PATH = "/SolarWinds/InformationService/v3/Json/Query"

DEFAULT_BROWSER = "msedge"       # default system browser (use --browser chrome to switch)
DEFAULT_STATE   = "state.json"   # cookie storage file

# ---------- SWIS helpers ----------
def swis_get(base_url, user, pwd, swql):
    url = base_url.rstrip("/") + SWIS_QUERY_PATH
    r = requests.get(url, params={"query": swql}, auth=(user, pwd), verify=False, timeout=30)
    r.raise_for_status()
    return r.json().get("results", [])

def looks_like_ip(s):
    try:
        ipaddress.ip_address(s)
        return True
    except ValueError:
        return False

def resolve_node_id(base_url, user, pwd, host):
    host_esc = host.replace("'", "''")
    if looks_like_ip(host):
        swql = f"SELECT TOP 1 NodeID FROM Orion.Nodes WHERE IPAddress='{host_esc}'"
    else:
        swql = ("SELECT TOP 1 NodeID FROM Orion.Nodes "
                f"WHERE Caption='{host_esc}' OR DNS='{host_esc}' OR NodeName='{host_esc}' OR SysName='{host_esc}'")
    res = swis_get(base_url, user, pwd, swql)
    if not res:
        raise RuntimeError(f"No node match for '{host}'")
    return int(res[0]["NodeID"])

def resolve_iface_id(base_url, user, pwd, node_id, iface):
    needle = iface.replace("'", "''")
    swql = ("SELECT TOP 1 InterfaceID FROM Orion.NPM.Interfaces "
            f"WHERE NodeID={node_id} AND (Name LIKE '%{needle}%' OR Caption LIKE '%{needle}%')")
    res = swis_get(base_url, user, pwd, swql)
    if not res:
        raise RuntimeError(f"No interface containing '{iface}' on NodeID {node_id}")
    return int(res[0]["InterfaceID"])

# ---------- Time + URLs ----------
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

# ---------- Playwright capture ----------
async def capture(login_url, perf_url, outfile, headed, state_path, browser_channel):
    from pathlib import Path
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        # Launch installed Edge/Chrome by channel (no playwright download needed)
        browser = await p.chromium.launch(channel=browser_channel, headless=(not headed))

        # Reuse cookies if present
        ctx_args = {"viewport": {"width": 1600, "height": 900}, "ignore_https_errors": True}
        sp = Path(state_path).expanduser().resolve()
        if sp.exists():
            ctx_args["storage_state"] = str(sp)

        context = await browser.new_context(**ctx_args)
        page = await context.new_page()

        # Clear sticky UI so URL timeFrom/timeTo is honored
        await page.goto("about:blank")
        try:
            await page.evaluate("localStorage.clear(); sessionStorage.clear();")
        except Exception:
            pass

        # Navigate via Login.aspx?ReturnUrl=... then always to exact PerfStack URL
        await page.goto(login_url, wait_until="domcontentloaded", timeout=45000)
        await page.goto(perf_url,  wait_until="domcontentloaded", timeout=45000)

        await page.wait_for_load_state("networkidle", timeout=45000)
        try:
            await page.wait_for_selector("canvas, svg", timeout=15000)
        except Exception:
            pass

        await page.screenshot(path=outfile, full_page=True)

        # Save cookies for next run
        sp.parent.mkdir(parents=True, exist_ok=True)
        await context.storage_state(path=str(sp))

        await context.close()
        await browser.close()

# ---------- main ----------
def main():
    parser = argparse.ArgumentParser(description="Open SolarWinds PerfStack (Edge/Chrome) and save a timestamped screenshot.")
    parser.add_argument("--host", required=True, help="Hostname/DNS/IP (IP is most reliable).")
    parser.add_argument("--interface", required=True, help="Interface name/caption (e.g., Ethernet1/1).")
    parser.add_argument("--hours", type=int, default=168, help="Time window in hours (default 168 = 7 days).")
    parser.add_argument("--outfile", default="perfstack.png", help="Base output filename (timestamp appended).")
    parser.add_argument("--headed", action="store_true", help="Show the browser window (use on first run to sign in).")
    parser.add_argument("--browser", choices=["msedge", "chrome"], default=DEFAULT_BROWSER,
                        help="Installed browser to use (default: msedge).")
    args = parser.parse_args()

    # Basic: trust self-signed SWIS certs
    requests.packages.urllib3.disable_warnings()

    # 1) Resolve IDs via SWIS with your AD creds
    ad_user, ad_pass = get_ad_creds()
    node_id  = resolve_node_id(DEFAULT_SWIS, ad_user, ad_pass, args.host)
    iface_id = resolve_iface_id(DEFAULT_SWIS, ad_user, ad_pass, node_id, args.interface)

    # 2) Build explicit time window & URLs
    t_from, t_to = last_hours_window(args.hours)
    perf_url  = build_perfstack_url(iface_id, t_from, t_to)
    login_url = build_login_url(perf_url)

    # 3) Make timestamped filename automatically
    stem, ext = os.path.splitext(args.outfile)
    stamped_out = f"{stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"

    print(f"Opening PerfStack → {perf_url}  (browser: {args.browser})")
    asyncio.run(capture(
        login_url=login_url,
        perf_url=perf_url,
        outfile=stamped_out,
        headed=args.headed,
        state_path=DEFAULT_STATE,
        browser_channel=args.browser
    ))
    print(f"Saved screenshot: {stamped_out}\nCookies saved in {DEFAULT_STATE}")

if __name__ == "__main__":
    main()
