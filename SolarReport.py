#!/usr/bin/env python3
import argparse, asyncio, ipaddress, sys, urllib.parse
from datetime import datetime, timedelta, timezone
import requests
from tools import get_ad_creds

DEFAULT_SWIS = "https://orionApi.company.com:17774"
DEFAULT_WEB  = "https://orion.company.com"
SWIS_QUERY_PATH = "/SolarWinds/InformationService/v3/Json/Query"
STATE_FILE = "state.json"

def swis_get(base_url, user, pwd, swql):
    url = base_url.rstrip("/") + SWIS_QUERY_PATH
    r = requests.get(url, params={"query": swql}, auth=(user, pwd), verify=False)
    r.raise_for_status()
    return r.json().get("results", [])

def resolve_node_id(base_url, user, pwd, host):
    if looks_like_ip(host):
        swql = f"SELECT TOP 1 NodeID FROM Orion.Nodes WHERE IPAddress='{host}'"
    else:
        swql = f"SELECT TOP 1 NodeID FROM Orion.Nodes WHERE Caption='{host}' OR DNS='{host}' OR NodeName='{host}' OR SysName='{host}'"
    res = swis_get(base_url, user, pwd, swql)
    if not res: raise RuntimeError(f"No node for {host}")
    return int(res[0]["NodeID"])

def resolve_iface_id(base_url, user, pwd, node_id, iface):
    swql = f"SELECT TOP 1 InterfaceID FROM Orion.NPM.Interfaces WHERE NodeID={node_id} AND (Name LIKE '%{iface}%' OR Caption LIKE '%{iface}%')"
    res = swis_get(base_url, user, pwd, swql)
    if not res: raise RuntimeError(f"No interface {iface}")
    return int(res[0]["InterfaceID"])

def looks_like_ip(text):
    try: ipaddress.ip_address(text); return True
    except: return False

def last_hours_window(hours):
    end = datetime.now(timezone.utc); start = end - timedelta(hours=hours)
    return start.strftime("%Y-%m-%dT%H:%M:%SZ"), end.strftime("%Y-%m-%dT%H:%M:%SZ")

def build_perfstack_url(iface_id, t_from, t_to):
    metrics = [
        f"Orion.NPM.Interfaces_{iface_id}-Orion.NPM.InterfaceTraffic.InAveragebps",
        f"Orion.NPM.Interfaces_{iface_id}-Orion.NPM.InterfaceTraffic.OutAveragebps",
    ]
    charts = "0_" + ",".join(metrics) + ";"
    qs = {"charts": charts, "timeFrom": t_from, "timeTo": t_to}
    return DEFAULT_WEB + "/apps/perfstack/?" + urllib.parse.urlencode(qs)

def build_login_url(perf_url):
    path_q = perf_url[len(DEFAULT_WEB):]
    return DEFAULT_WEB + "/Orion/Login.aspx?ReturnUrl=" + urllib.parse.quote(path_q, safe="")

async def capture(login_url, perf_url, outfile, headed):
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        ctx_args = {
            "viewport": {"width": 1600, "height": 900},
            "ignore_https_errors": True,
        }
        # reuse cookies if present
        try: ctx_args["storage_state"] = STATE_FILE
        except: pass
        browser = await p.chromium.launch(headless=(not headed))
        context = await browser.new_context(**ctx_args)
        page = await context.new_page()
        await page.goto(login_url, wait_until="domcontentloaded")
        # if already logged in, Orion redirects straight to perfstack
        if "/apps/perfstack/" not in page.url:
            await page.goto(perf_url, wait_until="domcontentloaded")
        await page.wait_for_load_state("networkidle")
        try: await page.wait_for_selector("canvas, svg", timeout=10000)
        except: pass
        await page.screenshot(path=outfile, full_page=True)
        await context.storage_state(path=STATE_FILE)  # save cookies
        await context.close(); await browser.close()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", required=True)
    ap.add_argument("--interface", required=True)
    ap.add_argument("--hours", type=int, default=168)
    ap.add_argument("--outfile", default="perfstack.png")
    ap.add_argument("--headed", action="store_true", help="Show browser (first run)")
    args = ap.parse_args()

    user,pwd = get_ad_creds()
    requests.packages.urllib3.disable_warnings()

    node_id = resolve_node_id(DEFAULT_SWIS, user, pwd, args.host)
    iface_id = resolve_iface_id(DEFAULT_SWIS, user, pwd, node_id, args.interface)
    t_from, t_to = last_hours_window(args.hours)
    perf_url = build_perfstack_url(iface_id, t_from, t_to)
    login_url = build_login_url(perf_url)
    print(f"Opening PerfStack for {args.host} {args.interface}, saving {args.outfile}")
    asyncio.run(capture(login_url, perf_url, args.outfile, args.headed))

if __name__ == "__main__":
    main()
