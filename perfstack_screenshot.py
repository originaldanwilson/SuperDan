#!/usr/bin/env python3
"""
Launch system browser and screenshot SolarWinds PerfStack with working format
Uses Selenium with system-installed browsers (no browser installation needed)
Uses proven working format: presetTime=last7Days with proper chart format
"""
import argparse, time, urllib.parse, os, ipaddress, requests
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

def screenshot_with_selenium(login_url, perfstack_url, outfile, width=1600, height=900, headless=True, browser="chrome"):
    """Take screenshot using Selenium with system browsers"""
    try:
        from selenium import webdriver
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.chrome.options import Options as ChromeOptions
        from selenium.webdriver.firefox.options import Options as FirefoxOptions
        from selenium.webdriver.edge.options import Options as EdgeOptions
    except ImportError:
        print("❌ Selenium not installed. Install with: pip install selenium")
        return False
    
    driver = None
    try:
        # Set up browser options
        if browser.lower() == "chrome":
            options = ChromeOptions()
            if headless:
                options.add_argument("--headless")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--ignore-certificate-errors")
            options.add_argument("--ignore-ssl-errors")
            options.add_argument(f"--window-size={width},{height}")
            driver = webdriver.Chrome(options=options)
            
        elif browser.lower() == "firefox":
            options = FirefoxOptions()
            if headless:
                options.add_argument("--headless")
            options.add_argument(f"--width={width}")
            options.add_argument(f"--height={height}")
            driver = webdriver.Firefox(options=options)
            
        elif browser.lower() == "edge":
            options = EdgeOptions()
            if headless:
                options.add_argument("--headless")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument(f"--window-size={width},{height}")
            driver = webdriver.Edge(options=options)
        else:
            print(f"❌ Unsupported browser: {browser}")
            return False
        
        # Set window size
        driver.set_window_size(width, height)
        
        # Navigate to login URL
        print(f"🔑 Navigating to login page...")
        driver.get(login_url)
        
        # Wait for login or manual intervention
        print(f"⏳ Waiting for login... (you may need to authenticate manually)")
        if not headless:
            input("Press Enter after logging in...")
        else:
            # Try to detect login automatically
            try:
                WebDriverWait(driver, 30).until(
                    EC.any_of(
                        EC.presence_of_element_located((By.CLASS_NAME, "sw-header")),
                        EC.presence_of_element_located((By.CLASS_NAME, "orion-header")),
                        EC.presence_of_element_located((By.ID, "main-content"))
                    )
                )
                print(f"✅ Login detected, proceeding to PerfStack...")
            except:
                print(f"⚠️  Login timeout - continuing anyway...")
        
        # Navigate to PerfStack URL
        print(f"📊 Loading PerfStack...")
        driver.get(perfstack_url)
        
        # Wait for page to load
        time.sleep(5)
        
        # Wait for chart elements
        print(f"📊 Waiting for charts to load...")
        try:
            WebDriverWait(driver, 20).until(
                EC.any_of(
                    EC.presence_of_element_located((By.TAG_NAME, "canvas")),
                    EC.presence_of_element_located((By.TAG_NAME, "svg")),
                    EC.presence_of_element_located((By.CLASS_NAME, "chart"))
                )
            )
            # Additional wait for chart rendering
            time.sleep(3)
            print(f"✅ Charts loaded")
        except:
            print(f"⚠️  Chart loading timeout - taking screenshot anyway...")
        
        # Take screenshot
        print(f"📷 Taking screenshot...")
        driver.save_screenshot(outfile)
        
        return True
        
    except Exception as e:
        print(f"❌ Screenshot failed: {e}")
        return False
        
    finally:
        if driver:
            driver.quit()

def main():
    ap = argparse.ArgumentParser(description="Screenshot SolarWinds PerfStack using system browsers (Selenium).")
    ap.add_argument("--host", required=True, help="Hostname/DNS/IP in Orion (IP is most reliable).")
    ap.add_argument("--interface", required=True, help="Interface name/caption (e.g. Ethernet1/1).")
    ap.add_argument("--hours", type=int, default=168, help="Time window in hours (default 168=7 days).")
    ap.add_argument("--outfile", default="perfstack.png", help="Base output file name (timestamp appended).")
    ap.add_argument("--headed", action="store_true", help="Show browser window (useful for login/debugging).")
    ap.add_argument("--browser", choices=["chrome", "firefox", "edge"], default="chrome", help="Browser to use (default: chrome).")
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
    print(f"   Browser: {args.browser} ({'headed' if args.headed else 'headless'})")
    print()
    
    success = screenshot_with_selenium(
        login_url, perfstack_url, stamped,
        args.width, args.height, headless=not args.headed, browser=args.browser
    )
    
    if success:
        print(f"✅ Screenshot saved: {stamped}")
    else:
        print(f"❌ Screenshot failed")
        exit(1)

if __name__ == "__main__":
    main()
