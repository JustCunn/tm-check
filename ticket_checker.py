import argparse
from cmath import log
import random
from checker import handle_ticket_status
import asyncio
import argparse
from playwright.async_api import async_playwright
from checker import safe_check_ticket_availability, handle_ticket_status
import playwright_stealth
from playwright_stealth import Stealth
import os, shutil

chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
user_data_dir = os.path.expanduser("~/Library/Application Support/Google/Chrome")

original_profile = os.path.expanduser("~/Library/Application Support/Google/Chrome")
temp_profile = "/tmp/playwright_profile2"

# small UA sample — expand as needed
UA_POOL = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
]

# Basic stealth init script to reduce common webdriver fingerprints
STEALTH_INIT_JS = """
// navigator.webdriver, languages, plugins, userAgent tweaks
Object.defineProperty(navigator, 'webdriver', {get: () => false});
Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
Object.defineProperty(navigator, 'plugins', {get: () => [1,2,3,4,5]});
window.__injected_user_agent = '%s';
Object.defineProperty(navigator, 'userAgent', {get: () => window.__injected_user_agent});
"""  # %s will be replaced with chosen UA

async def create_context(playwright, proxy_server=None, user_agent=None):
    launch_kwargs = dict(
        user_data_dir=temp_profile,
        headless=False,
        executable_path=chrome_path,
        args=["--no-first-run", "--no-default-browser-check", "--disable-extensions", "--disable-sync"],
        timeout=20000,
    )
    if proxy_server:
        launch_kwargs["proxy"] = {"server": proxy_server}
    # pass minimal UA override as an arg to chromium (helps some checks)
    if user_agent:
        launch_kwargs["args"].append(f'--user-agent={user_agent}')

    context = await playwright.chromium.launch_persistent_context(**launch_kwargs)

    # set header and init script to override navigator properties early
    if user_agent:
        try:
            await context.set_extra_http_headers({"user-agent": user_agent})
        except Exception:
            pass
        try:
            await context.add_init_script(STEALTH_INIT_JS % user_agent)
        except Exception:
            pass

    return context

async def main():
    parser = argparse.ArgumentParser(description="Ticketmaster Ticket Checker")
    parser.add_argument("event_id", help="Ticketmaster Event ID")
    parser.add_argument("quantity", type=int, help="Number of tickets to check for")
    parser.add_argument(
        "--interval", type=int, default=60, help="Polling interval in seconds (default: 60)"
    )
    parser.add_argument(
        "--proxy", type=str, help="Proxy URL to use for requests (optional, e.g., 'http://user:pass@proxyserver:port')"
    )
    parser.add_argument(
    "--consec-fails", type=int, default=10, help="The number of consecutive unsuccessful searches until alert"
    )
    parser.add_argument(
    "--auth", action=argparse.BooleanOptionalAction, help="Open auth page for manual sign-in at startup"
    )
    
    args = parser.parse_args()

    proxies = []
    if args.proxy:
        proxies = [p.strip() for p in args.proxy.split(",") if p.strip()]

    print(f"🎫 Starting Ticket Checker for event: {args.event_id}, qty: {args.quantity}")
    print(f"⏱ Polling every {args.interval} seconds. Press Ctrl+C to stop.\n")

    # Create a minimal temp profile if original doesn't exist (avoid copying a full real profile)
    if not os.path.exists(temp_profile):
        if os.path.exists(original_profile):
            try:
                shutil.copytree(original_profile, temp_profile)
            except Exception as e:
                print(f"[WARN] Could not copy original profile ({e}), creating empty profile dir")
                os.makedirs(temp_profile, exist_ok=True)
        else:
            os.makedirs(temp_profile, exist_ok=True)

    async with async_playwright() as playwright:
        unsuccessful_count = 0
        backoff_multiplier = 1
        proxy_index = 0

        # choose UA and proxy for initial context
        chosen_ua = random.choice(UA_POOL)
        chosen_proxy = proxies[proxy_index] if proxies else None

        try:
            context = await create_context(playwright, proxy_server=chosen_proxy, user_agent=chosen_ua)

            if args.auth:
                login_page = await context.new_page()
                await login_page.goto("https://auth.ticketmaster.com/...", wait_until="networkidle")
                print("Please sign in to Ticketmaster in the opened browser window...")
                await asyncio.sleep(90)

            first_run = True
            try:
                while True:
                    res = await safe_check_ticket_availability(context, args.event_id, args.quantity, first_run)
                    is_available = res is not None and res is not False
                    first_run = False

                    if is_available:
                        unsuccessful_count = 0
                        backoff_multiplier = 1
                    else:
                        unsuccessful_count += 1

                    # call handler correctly
                    if unsuccessful_count % 10 == 0 and unsuccessful_count != 0:
                        unsuccessful_count = 0
                        await handle_ticket_status(is_available, args.event_id, args.quantity, res['id'] if res is not None else None, context)
                    elif is_available:
                        await handle_ticket_status(is_available, args.event_id, args.quantity, res['id'] if res is not None else None, context)
                    else:
                        print("❌ No tickets")

                    # rotate proxy/UA after too many consecutive fails (example strategy)
                    if unsuccessful_count >= args.consec_fails and proxies:
                        print("[ROTATE] Too many fails, rotating proxy/UA and increasing backoff")
                        unsuccessful_count = 0
                        backoff_multiplier = min(backoff_multiplier * 2, 16)
                        # close current context and create a new one with next proxy + UA
                        try:
                            await context.close()
                        except Exception:
                            pass
                        proxy_index = (proxy_index + 1) % len(proxies)
                        chosen_proxy = proxies[proxy_index]
                        chosen_ua = random.choice(UA_POOL)
                        context = await create_context(playwright, proxy_server=chosen_proxy, user_agent=chosen_ua)

                    # Adaptive backoff and jitter (unchanged idea)
                    sleep_base = args.interval * backoff_multiplier
                    sleep_interval = min(max(5, sleep_base + random.uniform(-5, 5)), 3600)
                    await asyncio.sleep(sleep_interval)
            
            except KeyboardInterrupt:
                print("\n[INFO] Stopped by user.")
            finally:
                try:
                    await context.close()
                except Exception:
                    pass
                print("[INFO] Browser closed cleanly.")
        except Exception as e:
            print(f"[ERROR] Failed to start browser/context: {e}")


if __name__ == "__main__":
    asyncio.run(main())
