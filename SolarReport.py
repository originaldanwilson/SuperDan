#!/usr/bin/env python3
# open_perfstack_playwright.py (installed Chrome/Edge; autofill login; optional persistent profile)
import argparse, asyncio, ipaddress, sys, urllib.parse, os
from datetime import datetime, timedelta, timezone
import requests
from tools import get_ad_creds

DEFAULT_SWIS = "https://orionApi.company.com:17774"
DEFAULT_WEB  = "https://orion.company.com"
SWIS_QUERY_PATH = "/SolarWinds/InformationService/v3/Json/Query"

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
        swql = ("SELECT TOP 1 NodeID FROM Orion.Nodes "
                f"WHERE Caption='{host_esc}' OR DNS='{host_esc}' OR NodeName='{host_esc}' OR SysName='{host_esc}'")
    res = swis_get(base_url, user, pwd, swql)
    if not res: raise RuntimeError(f"No node match for '{host}'")
    return int(res[0]["NodeID"])

def resolve_iface_id(base_url, user, pwd, node_id, iface):
    needle = iface.replace("'", "''")
    swql = ("SELECT TOP 1 InterfaceID FROM Orion.NPM.Interfaces "
            f"WHERE NodeID={node_id} AND (Name LIKE '%{needle}%' OR Caption LIKE '%{needle}%')")
    res = swis_get(base_url, user, pwd, swql)
    if not res: raise RuntimeError(f"No interface containing '{iface}' on NodeID {node_id}")
    return int(res[0]["InterfaceID"])

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

# ---------- Playwright helpers ----------
LOGIN_USER_SELECTORS = [
    "input[name*='User']", "input[name*='Username']",
    "input[id*='User']",   "input[id*='Username']",
    "input[type='text']"
]
LOGIN_PASS_SELECTORS = [
    "input[name*='Pass']", "input[name*='Password']",
    "input[id*='Pass']",   "input[id*='Password']",
    "input[type='password']"
]
SUBMIT_SELECTORS = ["input[type='submit']", "button[type='submit']", "button[name*='Login']"]

async def find_first(page, selectors):
    for sel in selectors:
        el = await page.query_selector(sel)
        if el:
            return el
    return None

async def submit_login_form(page, username_str, password_str, timeout_ms):
    user_el = await find_first(page, LOGIN_USER_SELECTORS)
    pass_el = await find_first(page, LOGIN_PASS_SELECTORS)
    if not pass_el:
        return False  # no form present

    if user_el:
        await user_el.fill(username_str)
    await pass_el.fill(password_str)

    submit_el = await find_first(page, SUBMIT_SELECTORS)
    if submit_el:
        await submit_el.click()
    else:
        await pass_el.press("Enter")

    # Wait for either a navigation or an error message
    try:
        await page.wait_for_load_state("networkidle", timeout=timeout_ms)
    except Exception:
        pass

    # Basic heuristic: if we still see a password field, assume it failed
    still_login = await find_first(page, LOGIN_PASS_SELECTORS)
    return not bool(still_login)

async def capture(login_url, perf_url, outfile, headed, browser_channel=None, exe_path=None,
                  state_path="state.json", ad_user=None, ad_pass=None, domain_hint=None):
    """
    - If state file exists, reuse it.
    - Otherwise, go to Login.aspx?ReturnUrl=... and try autofill with multiple username formats.
    - After success, save cookies (state file). If --userDataDir is used (persistent profile), no state file is needed.
    """
    from pathlib import Path
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        # Choose launch mode: persistent (user profile) or regular
        # If --userDataDir provided, use a persistent context (best for SSO)
        persistent = False
        launch_kwargs = {
            "headless": (not headed),
            "args": ["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-dev-shm-usage"],
        }
        if exe_path:
            launch_kwargs["executable_path"] = exe_path
        elif browser_channel:
            launch_kwargs["channel"] = browser_channel

        browser = None
        context = None

        user_data_dir = os.environ.get("PW_USER_DATA_DIR", "")  # we’ll set from CLI below
        if user_data_dir:
            persistent = True
            # Persistent context keeps cookies in the OS profile folder
            browser = await p.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                **launch_kwargs,
                viewport={"width": 1600, "height": 900},
                ignore_https_errors=True
            )
            page = await browser.new_page()
        else:
            browser = await p.chromium.launch(**launch_kwargs)
            ctx_args = {"viewport": {"width":1600,"height":900}, "ignore_https_errors": True}
            sp = Path(state_path).expanduser().resolve()
            if sp.exists():
                ctx_args["storage_state"] = str(sp)
            context = await browser.new_context(**ctx_args)
            page = await context.new_page()

        # Navigate to login-with-return
        await page.goto(login_url, wait_until="domcontentloaded", timeout=45000)

        # If a login form is present, try AD creds in common formats
        # Build candidate usernames
        user_variants = []
        if ad_user:
            # If they gave DOMAIN\user or user@domain, keep as-is and add alternatives
            u = ad_user
            if "\\" in u:
                dom, name = u.split("\\", 1)
                user_variants = [u, f"{name}@{dom}", name]
            elif "@" in u:
                name, dom = u.split("@", 1)
                user_variants = [u, f"{dom}\\{name}", name]
            else:
                if domain_hint:
                    user_variants = [f"{ad_user}@{domain_hint}", f"{domain_hint}\\{ad_user}", ad_user]
                else:
                    user_variants = [ad_user]

        logged_in = False
        for uv in user_variants or [ad_user]:
            ok = await submit_login_form(page, uv, ad_pass or "", timeout_ms=20000)
            # If we landed on perfstack, we're good
            if "/apps/perfstack/" in page.url:
                logged_in = True
                break
            # If no form anymore, assume logged in (redirect might be pending)
            pf = await find_first(page, LOGIN_PASS_SELECTORS)
            if not pf:
                logged_in = True
                break

        # If still not on perfstack, try to go directly once
        if "/apps/perfstack/" not in page.url:
            await page.goto(perf_url, wait_until="domcontentloaded", timeout=45000)

        await page.wait_for_load_state("networkidle", timeout=45000)
        try:
            await page.wait_for_selector("canvas, svg", timeout=15000)
        except Exception:
            pass

        await page.screenshot(path=outfile, full_page=True)

        # Save cookies only in non-persistent mode
        if not persistent:
            from pathlib import Path
            sp = Path(state_path).expanduser().resolve()
            sp.parent.mkdir(parents=True, exist_ok=True)
            await context.storage_state(path=str(sp))

        # Close contexts/browsers
        if context:
            await context.close()
        if browser:
            await browser.close()

def main():
    parser = argparse.ArgumentParser(description="Open SolarWinds PerfStack with installed Chrome/Edge; screenshot page.")
    parser.add_argument("--host", required=True, help="Hostname/DNS/IP (IP is most reliable).")
    parser.add_argument("--interface", required=True, help="Interface name/caption (e.g. Ethernet1/1).")
    parser.add_argument("--hours", type=int, default=168, help="Time window: last N hours (default 168 = 7 days).")
    parser.add_argument("--outfile", default="perfstack.png", help="Output PNG filename.")
    parser.add_argument("--headed", action="store_true", help="Show the browser window.")
    # Installed browser choice
    parser.add_argument("--browser", choices=["chrome", "msedge"], help="Use installed Chrome/Edge channel.")
    parser.add_argument("--exePath", help="Full path to Chrome/Edge executable (overrides --browser).")
    # Cookie storage (non-persistent)
    parser.add_argument("--state", default="state.json", help="Path to cookie storage file.")
    # Persistent profile (best for SSO) — set a user data dir (enables launch_persistent_context)
    parser.add_argument("--userDataDir", help="Use a persistent browser profile at this path (skips state.json).")
    # Optional domain hint if your AD username is just 'user' (not user@domain)
    parser.add_argument("--domain", help="Domain hint for login (e.g., company.com or COMPANY).")
    args = parser.parse_args()

    # SWIS often has self-signed certs
    requests.packages.urllib3.disable_warnings()
    ad_user, ad_pass = get_ad_creds()

    try:
        node_id  = resolve_node_id(DEFAULT_SWIS, ad_user, ad_pass, args.host)
        iface_id = resolve_iface_id(DEFAULT_SWIS, ad_user, ad_pass, node_id, args.interface)
        t_from, t_to = last_hours_window(args.hours)
        perf_url  = build_perfstack_url(iface_id, t_from, t_to)
        login_url = build_login_url(perf_url)

        # Map browser channel
        browser_channel = None
        if args.exePath:
            browser_channel = None
        elif args.browser == "chrome":
            browser_channel = "chrome"
        elif args.browser == "msedge":
            browser_channel = "msedge"

        # If userDataDir is provided, pass it via env var (simple handoff to capture())
        if args.userDataDir:
            os.environ["PW_USER_DATA_DIR"] = args.userDataDir

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
                ad_user=ad_user,
                ad_pass=ad_pass,
                domain_hint=args.domain,
            )
        )
        if args.userDataDir:
            print(f"Saved screenshot: {args.outfile}\nProfile (cookies) persisted in: {args.userDataDir}")
        else:
            print(f"Saved screenshot: {args.outfile}\nCookies saved: {args.state}")
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()

