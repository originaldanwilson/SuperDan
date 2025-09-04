#!/usr/bin/env python3
"""
Attach to a running Chrome/Edge (CDP) and screenshot a SolarWinds PerfStack view
Updated with working SolarWinds format: presetTime=last7Days and proper chart format
"""
import argparse, asyncio, urllib.parse, os, ipaddress, requests
from datetime import datetime
from tools import get_ad_creds

DEFAULT_SWIS = "https://orionApi.company.com:17774"
DEFAULT_WEB  = "https://orion.company.com"
SWIS_QUERY   = "/SolarWinds/InformationService/v3/Json/Query"

def looks_like_ip(s):
    try: ipaddress.ip_address(s); return True
    except ValueError: return False

def swis_get(base, user, pwd, swql):
    url = base.rstrip("/") + SWIS_QUERY
    r = requests.get(url, params={"query": swql}, auth=(user, pwd), verify=False, timeout=30)
    r.raise_for_status()
    return r.json().get("results", [])

def resolve_node_id(base, user, pwd, host):
    h = host.replace("'", "''")
    if looks_like_ip(host):
        swql = f"SELECT TOP 1 NodeID FROM Orion.Nodes WHERE IPAddress='{h}'"
    else:
        swql = ("SELECT TOP 1 NodeID FROM Orion.Nodes "
                f"WHERE Caption='{h}' OR DNS='{h}' OR NodeName='{h}' OR SysName='{h}'")
    res = swis_get(base, user, pwd, swql)
    if not res: raise RuntimeError(f"No node match for '{host}'")
    return int(res[0]["NodeID"])

def resolve_iface_id(base, user, pwd, node_id, iface):
    n = iface.replace("'", "''")
    # Try exact match first
    swql = ("SELECT TOP 1 InterfaceID FROM Orion.NPM.Interfaces "
            f"WHERE NodeID={node_id} AND (Name='{n}' OR Caption='{n}')")
    res = swis_get(base, user, pwd, swql)
    
    # If no exact match, fall back to substring match with warning
    if not res:
        print(f"⚠️  No exact match for '{iface}', trying substring match...")
        swql = ("SELECT TOP 1 InterfaceID FROM Orion.NPM.Interfaces "
                f"WHERE NodeID={node_id} AND (Name LIKE '%{n}%' OR Caption LIKE '%{n}%')")
        res = swis_get(base, user, pwd, swql)
    
    if not res: raise RuntimeError(f"No interface containing '{iface}' on NodeID {node_id}")
    return int(res[0]["InterfaceID"])

def hours_to_preset(hours):
    """Convert hours to SolarWinds preset time string"""
    presets = {
        1: "last1Hour",
        2: "last2Hours", 
        4: "last4Hours",
        8: "last8Hours",
        12: "last12Hours",
        24: "last24Hours",
        48: "last2Days",
        72: "last3Days",
        168: "last7Days",  # 7 days - this is the working format!
        336: "last2Weeks", # 14 days  
        720: "last30Days", # 30 days
        2160: "last90Days" # 90 days
    }
    
    # Find closest preset
    if hours in presets:
        return presets[hours]
    
    # Find closest match
    closest = min(presets.keys(), key=lambda x: abs(x - hours))
    preset = presets[closest]
    
    if closest != hours:
        print(f"⚠️  No exact preset for {hours} hours, using closest: {preset} ({closest} hours)")
    
    return preset

def build_perfstack_url(web_base, iface_id, hours):
    """Build PerfStack URL using the ACTUAL working SolarWinds format"""
    # Convert hours to SolarWinds preset format
    preset_time = hours_to_preset(hours)
    
    # Use the ACTUAL working format from browser testing
    metrics = [
        f"0_Orion.NPM.Interfaces_{iface_id}-Orion.NPM.InterfaceTraffic.InAveragebps",
        f"0_Orion.NPM.Interfaces_{iface_id}-Orion.NPM.InterfaceTraffic.OutAveragebps"
    ]
    charts = ",".join(metrics)  # Comma-separated, no semicolon
    
    print(f"🔗 URL parameters:")
    print(f"   presetTime: {preset_time} ({hours} hours)")
    print(f"   charts:     {charts}")
    
    params = {
        "presetTime": preset_time,
        "charts": charts
    }
    
    return web_base.rstrip("/") + "/apps/perfstack/?" + urllib.parse.urlencode(params)

async def attach_and_shot(cdp_url, target_url, outfile, width=1600, height=900):
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(cdp_url)
        ctx = browser.contexts[0] if browser.contexts else await browser.new_context(
            viewport={"width": width, "height": height},
            ignore_https_errors=True
        )
        page = await ctx.new_page()
        # Go to the exact PerfStack URL (explicit timeFrom/timeTo)
        await page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_load_state("networkidle", timeout=60000)
        try:
            await page.wait_for_selector("canvas, svg", timeout=20000)
        except:
            pass
        await page.screenshot(path=outfile, full_page=True)
        await browser.close()  # only detaches; the real browser stays open

def main():
    ap = argparse.ArgumentParser(description="Attach to a running Chrome/Edge (CDP) and screenshot PerfStack.")
    ap.add_argument("--host", required=True, help="Hostname/DNS/IP in Orion (IP is most reliable).")
    ap.add_argument("--interface", required=True, help="Interface name/caption (e.g. Ethernet1/1).")
    ap.add_argument("--hours", type=int, default=168, help="Time window in hours (default 168=7 days).")
    ap.add_argument("--outfile", default="perfstack.png", help="Base output file name (timestamp appended).")
    ap.add_argument("--cdp", default="http://localhost:9222", help="CDP endpoint from --remote-debugging-port.")
    args = ap.parse_args()

    requests.packages.urllib3.disable_warnings()
    user, pwd = get_ad_creds()

    print(f"🔍 Resolving node: {args.host}")
    node_id  = resolve_node_id(DEFAULT_SWIS, user, pwd, args.host)
    print(f"   NodeID: {node_id}")
    
    print(f"🔍 Resolving interface: {args.interface}")
    iface_id = resolve_iface_id(DEFAULT_SWIS, user, pwd, node_id, args.interface)
    print(f"   InterfaceID: {iface_id}")
    
    print(f"🕐 Building PerfStack URL for {args.hours} hours...")
    url = build_perfstack_url(DEFAULT_WEB, iface_id, args.hours)

    stem, ext = os.path.splitext(args.outfile)
    stamped = f"{stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
    
    print()
    print(f"📷 Taking screenshot...")
    print(f"   CDP: {args.cdp}")
    print(f"   URL: {url}")
    print(f"   File: {stamped}")
    print()
    
    asyncio.run(attach_and_shot(args.cdp, url, stamped))
    print(f"✅ Screenshot saved: {stamped}")

if __name__ == "__main__":
    main()
