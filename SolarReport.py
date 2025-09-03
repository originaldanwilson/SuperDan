#!/usr/bin/env python3
# Use installed Chrome/Edge via Playwright to open SolarWinds PerfStack and save a screenshot.
import argparse, asyncio, ipaddress, sys, urllib.parse, os
from datetime import datetime, timedelta, timezone
import requests
from tools import get_ad_creds  # your helper

# ---- Hard-coded endpoints (adjust to your env) ----
DEFAULT_SWIS = "https://orionApi.company.com:17774"
DEFAULT_WEB  = "https://orion.company.com"
SWIS_QUERY_PATH = "/SolarWinds/InformationService/v3/Json/Query"

# ---------------- SWIS helpers ----------------
def swis_get(base_url: str, user: str, pwd: str, swql: str):
    url = base_url.rstrip("/") + SWIS_QUERY_PATH
    r = requests.get(url, params={"query": swql}, auth=(user, pwd), verify=False, timeout=30)
    r.raise_for_status()
    data = r.json()
    return data.get("results", data.get("Results", []))

def looks_like_ip(text: str) -> bool:
    try:
        ipaddress.ip_address(text); return True
    except ValueError:
        return False

def resolve_node_id(base_url: str, user: str, pwd: str, host: str) -> int:
    host_esc = host.replace("'", "''")
    if looks_like_ip(host):
        swql = f"SELECT TOP 1 NodeID FROM Orion.Nodes WHERE IPAddress='{host_esc}'"
    else:
        swql = (
            "SELECT TOP 1 NodeID FROM Orion.Nodes "
            f"WHERE Caption='{host_esc}' OR DNS='{host_esc}' OR NodeName='{host_esc}' OR SysName='{host_esc}'"
        )
    res = swis_get(base_url, user, pwd, swql)
    if not res:
        raise RuntimeError(f"No node match for '{host}'")
    return int(res[0]["NodeID"])

def resolve_iface_id(base_url: str, user: str, pwd: str, node_id: int, iface: str) -> int:
    needle = iface.replace("'", "''")
    swql = (
        "SELECT TOP 1 InterfaceID FROM Orion.NPM.Interfaces "
        f"WHERE NodeID={node_id} AND (Name LIKE '%{needle}%' OR Caption LIKE '%{needle}%')"
    )
    res = swis_get(base_url, user, pwd, swql)
    if not res:
        raise RuntimeError(f"No interface containing '{iface}' on NodeID {node_id}")
    return int(res[0]["InterfaceID"])

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

def build_login_url(perf_url: str) -> str:
    base = DEFAULT_WEB.rstrip("/")
    path_q = perf_url[len(base):]  # "/apps/perfstack/?..."
    return f"{base}/Orion/Login.aspx?ReturnUrl={urllib.parse.quote(path_q, safe='')}"

# ---------------- Playwright capture (Option A) ----------------
async def capture(login_url: str, perf_url: str, outfile: str, headed: bool,
                  browser_channel: str | None = None, exe_path: str | None = None,
                  state_path: str = "state.json"):
    from pathlib import Path
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        launch_kwargs = {
            "headless": (not headed),
            "args": ["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-dev-shm-usage"],
        }
        if exe_path:
            launch_kwargs["executable_path"] = exe_path
        elif browser_channel:  # "chrome" or "msedge"
            launch_kwargs["channel"] = browser_channel

        browser = await p.chromium.launch(**launch_kwargs)

        # Only load cookies if the file actually exists
        ctx_args = {
            "viewport": {"width": 1600, "height": 900},
            "ignore_https_errors": True,
        }
        sp = Path(state_path).expanduser().resolve()
        if sp.exists():
            ctx_args["storage_state"] = str(sp)

        context = await browser.new_context(**ctx_args)
        page = await context.new_page()

        # Navigate (login with ReturnUrl → PerfStack)
        await page.goto(login_url, wait_until="domcontentloaded", timeout=45000)
        if "/apps/perfstack/" not in page.url:
            await page.goto(perf_url, wait_until="domcontentloaded", timeout=45000)

        await page.wait_for_load_state("networkidle", timeout=45000)
        try:
            await page.wait_for_selector("canvas, svg", timeout=15000)
        except Exception:
            pass

        await page.screenshot(path=outfile, full_page=True)

        # Ensure folder exists, then save cookies
        sp.parent.mkdir(parents=True, exist_ok=True)
        await context.storage_state(path=str(sp))

        await context.close()
        await browser.close()

# ---------------- main ----------------
def main():
    parser = argparse.ArgumentParser(
        description="Open SolarWinds PerfStack with installed Chrome/Edge and save a screenshot."
    )
    parser.add_argument("--host", required=True, help="Hostname/DNS/IP (IP is most reliable).")
    parser.add_argument("--interface", required=True, help="Interface name/caption (e.g. Ethernet1/1).")
    parser.add_argument("--hours", type=int, default=168, help="Time window: last N hours (default 168 = 7 days).")
    parser.add_argument("--outfile", default="perfstack.png", help="Output PNG filename.")
    parser.add_argument("--headed", action="store_true", help="Show the browser (recommended for first run).")
    # Installed browser options (no playwright install needed):
    parser.add_argument("--browser", choices=["chrome", "msedge"], help="Use installed Chrome/Edge channel.")
    parser.add_argument("--exePath", help="Full path to Chrome/Edge executable (overrides --browser).")
    # Cookie storage:
    parser.add_argument("--state", default="state.json", help="Path to cookie storage file (default: state.json).")
    args = parser.parse_args()

    # SWIS often has self-signed certs
    requests.packages.urllib3.disable_warnings()
    username, password = get_ad_creds()

    try:
        node_id  = resolve_node_id(DEFAULT_SWIS, username, password, args.host)
        iface_id = resolve_iface_id(DEFAULT_SWIS, username, password, node_id, args.interface)
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
        asyncio.run(
            capture(
                login_url=login_url,
                perf_url=perf_url,
                outfile=args.outfile,
                headed=args.headed,
                browser_channel=browser_channel,
                exe_path=args.exePath,
                state_path=args.state,
            )
        )
        print(f"Saved screenshot: {args.outfile}\nCookies saved: {args.state}")
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
