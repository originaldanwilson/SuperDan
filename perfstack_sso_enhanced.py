#!/usr/bin/env python3
"""
Enhanced SolarWinds PerfStack SSO Handler
Improved version with multiple SSO authentication methods

NOTE: This script has known issues after format updates.
USE INSTEAD:
- perfstack_simple.py (recommended)
- perfstack_windows.py (with file output options) 
- perfstackAttachShot.py (with screenshot capture)
"""

import argparse
import asyncio
import ipaddress
import json
import os
import sys
import time
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from tools import get_ad_creds

# Configuration
DEFAULT_SWIS = "https://orionApi.company.com:17774"
DEFAULT_WEB = "https://orion.company.com"
SWIS_QUERY_PATH = "/SolarWinds/InformationService/v3/Json/Query"

# Browser configurations
BROWSER_CONFIGS = {
    'chrome': {
        'executable': None,  # Use system Chrome
        'args': [
            '--disable-blink-features=AutomationControlled',
            '--no-sandbox',
            '--disable-dev-shm-usage',
            '--disable-web-security',
            '--disable-features=VizDisplayCompositor',
            '--ignore-certificate-errors',
            '--ignore-ssl-errors',
            '--allow-running-insecure-content'
        ]
    },
    'msedge': {
        'executable': None,  # Use system Edge
        'args': [
            '--disable-blink-features=AutomationControlled',
            '--no-sandbox', 
            '--disable-dev-shm-usage',
            '--disable-web-security',
            '--ignore-certificate-errors',
            '--ignore-ssl-errors'
        ]
    }
}

class SolarWindsSSO:
    def __init__(self, swis_base=DEFAULT_SWIS, web_base=DEFAULT_WEB):
        self.swis_base = swis_base
        self.web_base = web_base
        self.session = requests.Session()
        self.session.verify = False
        requests.packages.urllib3.disable_warnings()

    def swis_query(self, user, password, swql):
        """Execute SWIS query with authentication"""
        url = self.swis_base.rstrip("/") + SWIS_QUERY_PATH
        try:
            r = self.session.get(
                url, 
                params={"query": swql}, 
                auth=(user, password), 
                timeout=30
            )
            r.raise_for_status()
            return r.json().get("results", [])
        except Exception as e:
            print(f"SWIS query error: {e}")
            return []

    def resolve_node_id(self, user, password, host):
        """Resolve hostname/IP to NodeID"""
        host_esc = host.replace("'", "''")
        
        if self._looks_like_ip(host):
            swql = f"SELECT TOP 1 NodeID FROM Orion.Nodes WHERE IPAddress='{host_esc}'"
        else:
            swql = (
                "SELECT TOP 1 NodeID FROM Orion.Nodes "
                f"WHERE Caption='{host_esc}' OR DNS='{host_esc}' "
                f"OR NodeName='{host_esc}' OR SysName='{host_esc}'"
            )
        
        results = self.swis_query(user, password, swql)
        if not results:
            raise RuntimeError(f"No node found for '{host}'")
        
        return int(results[0]["NodeID"])

    def resolve_interface_id(self, user, password, node_id, interface):
        """Resolve interface name to InterfaceID"""
        iface_esc = interface.replace("'", "''")
        # Try exact match first
        swql = (
            "SELECT TOP 1 InterfaceID FROM Orion.NPM.Interfaces "
            f"WHERE NodeID={node_id} AND "
            f"(Name='{iface_esc}' OR Caption='{iface_esc}')"
        )
        
        results = self.swis_query(user, password, swql)
        
        # If no exact match, fall back to substring match with warning
        if not results:
            print(f"⚠️  No exact match for '{interface}', trying substring match...")
            swql = (
                "SELECT TOP 1 InterfaceID FROM Orion.NPM.Interfaces "
                f"WHERE NodeID={node_id} AND "
                f"(Name LIKE '%{iface_esc}%' OR Caption LIKE '%{iface_esc}%')"
            )
            results = self.swis_query(user, password, swql)
        
        if not results:
            raise RuntimeError(f"No interface containing '{interface}' on NodeID {node_id}")
        
        return int(results[0]["InterfaceID"])

    def _looks_like_ip(self, s):
        """Check if string looks like an IP address"""
        try:
            ipaddress.ip_address(s)
            return True
        except ValueError:
            return False

    def hours_to_preset(self, hours):
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

    def build_time_window(self, hours):
        """Build time window for PerfStack"""
        end = datetime.now(timezone.utc)
        start = end - timedelta(hours=hours)
        return (
            start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            end.strftime("%Y-%m-%dT%H:%M:%SZ")
        )

    def build_perfstack_url(self, interface_id, hours=168):
        """Build PerfStack URL using the actual working SolarWinds format"""
        # Convert hours to SolarWinds preset format  
        preset_time = self.hours_to_preset(hours)
        
        # Use the ACTUAL working format from browser testing
        metrics = [
            f"0_Orion.NPM.Interfaces_{interface_id}-Orion.NPM.InterfaceTraffic.InAveragebps",
            f"0_Orion.NPM.Interfaces_{interface_id}-Orion.NPM.InterfaceTraffic.OutAveragebps"
        ]
        charts = ",".join(metrics)  # Comma-separated, no semicolon
        
        params = {
            "presetTime": preset_time,
            "charts": charts
        }
        
        return self.web_base.rstrip("/") + "/apps/perfstack/?" + urllib.parse.urlencode(params)

    def build_login_url(self, return_url):
        """Build login URL with return path"""
        base = self.web_base.rstrip("/")
        if return_url.startswith(base):
            path_query = return_url[len(base):]
        else:
            path_query = return_url
        
        return f"{base}/Orion/Login.aspx?ReturnUrl={urllib.parse.quote(path_query, safe='')}"


class PlaywrightSSO:
    def __init__(self, browser_type='msedge', headless=True):
        self.browser_type = browser_type
        self.headless = headless
        self.viewport = {"width": 1600, "height": 900}

    async def capture_with_persistent_profile(self, login_url, target_url, output_file, 
                                            profile_dir, wait_for_auth=True):
        """
        Most reliable method: Use persistent browser profile for SSO
        """
        from playwright.async_api import async_playwright
        
        print(f"🔐 Using persistent profile: {profile_dir}")
        
        async with async_playwright() as p:
            try:
                # Launch persistent context (keeps cookies, auth state)
                context = await p.chromium.launch_persistent_context(
                    user_data_dir=profile_dir,
                    channel=self.browser_type,
                    headless=self.headless,
                    viewport=self.viewport,
                    ignore_https_errors=True,
                    args=BROWSER_CONFIGS[self.browser_type]['args']
                )
                
                page = await context.new_page()
                
                # Navigate to login first
                print(f"🌐 Navigating to login: {login_url}")
                await page.goto(login_url, wait_until="domcontentloaded", timeout=60000)
                
                if wait_for_auth:
                    await self._wait_for_authentication(page)
                
                # Navigate to target PerfStack URL
                print(f"📊 Loading PerfStack: {target_url}")
                await page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
                await page.wait_for_load_state("networkidle", timeout=60000)
                
                # Wait for charts to load
                await self._wait_for_charts(page)
                
                # Take screenshot
                print(f"📷 Taking screenshot: {output_file}")
                await page.screenshot(path=output_file, full_page=True)
                
                await context.close()
                return True
                
            except Exception as e:
                print(f"❌ Error with persistent profile: {e}")
                return False

    async def capture_with_state_file(self, login_url, target_url, output_file, 
                                    state_file, manual_auth=False):
        """
        Alternative method: Use state.json for session persistence
        """
        from playwright.async_api import async_playwright
        
        print(f"🔐 Using state file: {state_file}")
        
        async with async_playwright() as p:
            try:
                browser = await p.chromium.launch(
                    channel=self.browser_type,
                    headless=self.headless,
                    args=BROWSER_CONFIGS[self.browser_type]['args']
                )
                
                # Load existing state if available
                context_args = {
                    "viewport": self.viewport,
                    "ignore_https_errors": True
                }
                
                state_path = Path(state_file)
                if state_path.exists():
                    print("📁 Loading existing authentication state...")
                    context_args["storage_state"] = str(state_path)
                
                context = await browser.new_context(**context_args)
                page = await context.new_page()
                
                # Clear any sticky UI state
                await page.goto("about:blank")
                await page.evaluate("""
                    try {
                        localStorage.clear();
                        sessionStorage.clear();
                    } catch (e) {
                        console.log('Could not clear storage:', e);
                    }
                """)
                
                # Navigate to login
                print(f"🌐 Navigating to login: {login_url}")
                await page.goto(login_url, wait_until="domcontentloaded", timeout=60000)
                
                if manual_auth and not state_path.exists():
                    print("⏳ Please complete authentication in the browser...")
                    print("   Press Enter when authentication is complete...")
                    input()
                
                # Navigate to PerfStack
                print(f"📊 Loading PerfStack: {target_url}")
                await page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
                await page.wait_for_load_state("networkidle", timeout=60000)
                
                # Wait for charts
                await self._wait_for_charts(page)
                
                # Screenshot
                print(f"📷 Taking screenshot: {output_file}")
                await page.screenshot(path=output_file, full_page=True)
                
                # Save state
                print(f"💾 Saving authentication state...")
                state_path.parent.mkdir(parents=True, exist_ok=True)
                await context.storage_state(path=str(state_path))
                
                await context.close()
                await browser.close()
                return True
                
            except Exception as e:
                print(f"❌ Error with state file method: {e}")
                return False

    async def capture_with_cdp_attach(self, cdp_endpoint, target_url, output_file):
        """
        Alternative method: Attach to running browser via CDP
        """
        from playwright.async_api import async_playwright
        
        print(f"🔗 Attaching to CDP endpoint: {cdp_endpoint}")
        
        try:
            async with async_playwright() as p:
                browser = await p.chromium.connect_over_cdp(cdp_endpoint)
                
                # Use existing context or create new one
                if browser.contexts:
                    context = browser.contexts[0]
                    page = await context.new_page()
                else:
                    context = await browser.new_context(
                        viewport=self.viewport,
                        ignore_https_errors=True
                    )
                    page = await context.new_page()
                
                print(f"📊 Loading PerfStack: {target_url}")
                await page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
                await page.wait_for_load_state("networkidle", timeout=60000)
                
                await self._wait_for_charts(page)
                
                print(f"📷 Taking screenshot: {output_file}")
                await page.screenshot(path=output_file, full_page=True)
                
                # Don't close browser - just detach
                await browser.close()
                return True
                
        except Exception as e:
            print(f"❌ Error with CDP attach: {e}")
            return False

    async def _wait_for_authentication(self, page):
        """Wait for user to complete authentication"""
        print("⏳ Waiting for authentication...")
        
        # Check if we're still on login page after a delay
        await asyncio.sleep(2)
        current_url = page.url
        
        if 'login' in current_url.lower():
            print("🔐 Please complete authentication in the browser...")
            
            # Wait for navigation away from login
            try:
                await page.wait_for_function(
                    "() => !window.location.href.toLowerCase().includes('login')",
                    timeout=120000
                )
                print("✅ Authentication completed")
            except:
                print("⚠️  Authentication timeout - continuing anyway...")
        else:
            print("✅ Already authenticated")

    async def _wait_for_charts(self, page):
        """Wait for PerfStack charts to load"""
        print("📈 Waiting for charts to load...")
        
        try:
            # Wait for chart elements
            await page.wait_for_selector("canvas, svg, .chart", timeout=30000)
            
            # Additional wait for chart rendering
            await asyncio.sleep(3)
            
            print("✅ Charts loaded")
        except:
            print("⚠️  Chart loading timeout - taking screenshot anyway...")


def main():
    parser = argparse.ArgumentParser(
        description="Enhanced SolarWinds PerfStack with improved SSO handling",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
SSO Methods (in order of reliability):
  1. --profile DIR    : Use persistent browser profile (best for SSO)
  2. --state FILE     : Use state.json file for session persistence  
  3. --cdp ENDPOINT   : Attach to running browser via CDP
  4. --manual         : Interactive authentication with state saving

Examples:
  # Best for SSO - persistent profile
  python3 perfstack_sso_enhanced.py --host 10.1.1.1 --interface Gi0/1 --profile ./browser_profile
  
  # Interactive first-time setup
  python3 perfstack_sso_enhanced.py --host router01 --interface Ethernet1/1 --manual --headed
  
  # Attach to running browser
  python3 perfstack_sso_enhanced.py --host switch01 --interface Po5 --cdp http://localhost:9222
        """
    )
    
    # Required arguments
    parser.add_argument("--host", required=True, 
                       help="Hostname/IP/DNS name (IP most reliable)")
    parser.add_argument("--interface", required=True, 
                       help="Interface name (e.g., GigabitEthernet0/1, Po5)")
    
    # Optional arguments
    parser.add_argument("--hours", type=int, default=168,
                       help="Time window in hours (default: 168 = 7 days)")
    parser.add_argument("--output", default="perfstack.png",
                       help="Output filename (timestamp will be added)")
    parser.add_argument("--browser", choices=['chrome', 'msedge'], default='msedge',
                       help="Browser to use (default: msedge)")
    parser.add_argument("--headed", action="store_true",
                       help="Show browser window (useful for debugging)")
    
    # SSO method arguments
    sso_group = parser.add_mutually_exclusive_group()
    sso_group.add_argument("--profile", 
                          help="Use persistent browser profile directory (most reliable)")
    sso_group.add_argument("--state", default="solarwinds_state.json",
                          help="State file for session persistence (default: solarwinds_state.json)")
    sso_group.add_argument("--cdp", 
                          help="CDP endpoint to attach to running browser (e.g., http://localhost:9222)")
    sso_group.add_argument("--manual", action="store_true",
                          help="Manual authentication with state saving")
    
    args = parser.parse_args()
    
    try:
        # Initialize SolarWinds API client
        sw = SolarWindsSSO(DEFAULT_SWIS, DEFAULT_WEB)
        
        # Get credentials
        print("🔑 Getting credentials...")
        user, password = get_ad_creds()
        
        # Resolve node and interface
        print(f"🔍 Resolving node: {args.host}")
        node_id = sw.resolve_node_id(user, password, args.host)
        print(f"   NodeID: {node_id}")
        
        print(f"🔍 Resolving interface: {args.interface}")
        iface_id = sw.resolve_interface_id(user, password, node_id, args.interface)
        print(f"   InterfaceID: {iface_id}")
        
        # Build PerfStack URL with working format
        print(f"🕐 Building PerfStack URL for {args.hours} hours...")
        perfstack_url = sw.build_perfstack_url(iface_id, args.hours)
        login_url = sw.build_login_url(perfstack_url)
        print(f"🌐 PerfStack URL: {perfstack_url}")
        
        # Create timestamped output filename
        stem, ext = os.path.splitext(args.output)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"{stem}_{args.host}_{args.interface}_{timestamp}{ext}"
        
        # Initialize Playwright SSO handler
        pw_sso = PlaywrightSSO(args.browser, headless=not args.headed)
        
        # Choose SSO method
        success = False
        
        if args.profile:
            print("🎯 Using persistent profile method...")
            success = await pw_sso.capture_with_persistent_profile(
                login_url, perfstack_url, output_file, args.profile
            )
            
        elif args.cdp:
            print("🎯 Using CDP attach method...")
            success = await pw_sso.capture_with_cdp_attach(
                args.cdp, perfstack_url, output_file
            )
            
        else:
            print("🎯 Using state file method...")
            success = await pw_sso.capture_with_state_file(
                login_url, perfstack_url, output_file, 
                args.state, manual_auth=args.manual
            )
        
        if success:
            print(f"✅ Screenshot saved: {output_file}")
            
            # Show file with permissions (if tools.py has the function)
            try:
                from tools import print_file_with_permissions
                print_file_with_permissions(output_file)
            except ImportError:
                pass
                
        else:
            print("❌ Screenshot failed")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n⏹️  Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) == 1:
        # Show help if no arguments provided
        main_parser = argparse.ArgumentParser(
            description="Enhanced SolarWinds PerfStack with improved SSO handling"
        )
        main_parser.print_help()
        sys.exit(1)
    
    asyncio.run(main())
