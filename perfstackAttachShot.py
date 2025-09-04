#!/usr/bin/env python3
"""
Launch browser and screenshot SolarWinds PerfStack with working format
No CDP attachment needed - launches its own browser window
Uses proven working format: presetTime=last7Days with proper chart format
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

def build_login_url(web_base, perfstack_url):
    """Build login URL with return path"""
    base = web_base.rstrip("/")
    if perfstack_url.startswith(base):
        path_query = perfstack_url[len(base):]
    else:
        path_query = perfstack_url
    
    return f"{base}/Orion/Login.aspx?ReturnUrl={urllib.parse.quote(path_query, safe='')}"

async def screenshot_perfstack(login_url, perfstack_url, outfile, width=1600, height=900, headless=True):
    """Launch new browser, login, and take PerfStack screenshot"""
    from playwright.async_api import async_playwright
    
    async with async_playwright() as p:
        # Launch new browser instance
        browser = await p.chromium.launch(
            headless=headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--ignore-certificate-errors',
                '--ignore-ssl-errors'
            ]
        )
        
        context = await browser.new_context(
            viewport={"width": width, "height": height},
            ignore_https_errors=True
        )
        
        page = await context.new_page()
        
        try:
            # Navigate to login URL first
            print(f"🔑 Navigating to login page...")
            await page.goto(login_url, wait_until="domcontentloaded", timeout=60000)
            
            # Wait for user to login (check for SolarWinds elements)
            print(f"⏳ Waiting for login... (you may need to authenticate manually)")
            
            # Try to detect if we're logged in by looking for SolarWinds elements
            try:
                await page.wait_for_selector(".sw-header, .orion-header, #main-content", timeout=30000)
                print(f"✅ Login detected, proceeding to PerfStack...")
            except:
                print(f"⚠️  Login timeout - continuing anyway...")
            
            # Navigate to PerfStack URL
            print(f"📊 Loading PerfStack...")
            await page.goto(perfstack_url, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_load_state("networkidle", timeout=60000)
            
            # Wait for chart elements to load
            print(f"📊 Waiting for charts to load...")
            try:
                await page.wait_for_selector("canvas, svg, .chart", timeout=30000)
                # Additional wait for chart rendering
                await asyncio.sleep(3)
                print(f"✅ Charts loaded")
            except:
                print(f"⚠️  Chart loading timeout - taking screenshot anyway...")
            
            # Take screenshot
            print(f"📷 Taking screenshot...")
            await page.screenshot(path=outfile, full_page=True)
            
        finally:
            await browser.close()

def main():
    ap = argparse.ArgumentParser(description="Launch browser and screenshot SolarWinds PerfStack with working format.")
    ap.add_argument("--host", required=True, help="Hostname/DNS/IP in Orion (IP is most reliable).")
    ap.add_argument("--interface", required=True, help="Interface name/caption (e.g. Ethernet1/1).")
    ap.add_argument("--hours", type=int, default=168, help="Time window in hours (default 168=7 days).")
    ap.add_argument("--outfile", default="perfstack.png", help="Base output file name (timestamp appended).")
    ap.add_argument("--headed", action="store_true", help="Show browser window (useful for login/debugging).")
    ap.add_argument("--width", type=int, default=1600, help="Browser window width (default: 1600).")
    ap.add_argument("--height", type=int, default=900, help="Browser window height (default: 900).")
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
    perfstack_url = build_perfstack_url(DEFAULT_WEB, iface_id, args.hours)
    login_url = build_login_url(DEFAULT_WEB, perfstack_url)
    
    stem, ext = os.path.splitext(args.outfile)
    stamped = f"{stem}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
    
    print()
    print(f"📷 Taking PerfStack screenshot...")
    print(f"   PerfStack URL: {perfstack_url}")
    print(f"   Login URL: {login_url}")
    print(f"   Output file: {stamped}")
    print(f"   Browser mode: {'headed' if args.headed else 'headless'}")
    print()
    
    asyncio.run(screenshot_perfstack(
        login_url, perfstack_url, stamped, 
        args.width, args.height, headless=not args.headed
    ))
    print(f"✅ Screenshot saved: {stamped}")

if __name__ == "__main__":
    main()
