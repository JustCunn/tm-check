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
    
    args = parser.parse_args()

    print(f"🎫 Starting Ticket Checker for event: {args.event_id}, qty: {args.quantity}")
    print(f"⏱ Polling every {args.interval} seconds. Press Ctrl+C to stop.\n")

    async with Stealth().use_async(async_playwright()) as playwright:
        unsuccessful_count = 0
        browser = await playwright.chromium.launch(
            headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/115.0.0.0 Safari/537.36"
            ),
            locale='en-US',
            storage_state=None,
        )
        
        # await context.add_init_script("""
        # Object.defineProperty(navigator, 'webdriver', {
        # get: () => undefined
        # });
        # """)


        # Open sign-in page at startup
        # login_page = await context.new_page()
        # await login_page.goto("https://auth.ticketmaster.com/as/authorization.oauth2?client_id=3896bb8a93ef.web.ticketmaster.ie&response_type=code&scope=openid%20profile%20phone%20email%20tm&redirect_uri=https://identity.ticketmaster.ie/exchange&visualPresets=tmeu&lang=en-ie&placementId=mytmlogin&hideLeftPanel=false&integratorId=prd1741.iccp&intSiteToken=tm-ie&TMUO=east_ViXnHNSPR5RmT27B9srfbKTs22oqNn+qjKJaymaZwE8=&deviceId=rj6sXuJ%2F983HycrJyMXGy8jLxss5CFX%2Fdioypg&doNotTrack=true&disableAutoOptIn=false", wait_until="networkidle")
        # print("Please sign in to Ticketmaster in the opened browser window...")

        first_run = True
        try:
            while True:
                res = await safe_check_ticket_availability(context, args.event_id, args.quantity, first_run)
                is_available = res is not None and res is not False
                first_run = False

                if is_available:
                    unsuccessful_count = 0
                else:
                    unsuccessful_count += 1


                if unsuccessful_count % 10 == 0:
                    unsuccessful_count = 0
                    await handle_ticket_status(is_available, args.event_id, args.quantity, res, context)
                elif is_available:
                    await handle_ticket_status(is_available, args.event_id, args.quantity, context)
                else:
                    print("❌ No tickets")

                await asyncio.sleep(args.interval + random.uniform(-5, 5))
        
        except KeyboardInterrupt:
            print("\n[INFO] Stopped by user.")
        finally:
            try:
                await context.close()
                await browser.close()
                print("[INFO] Browser closed cleanly.")
            except Exception as e:
                print(f"[WARN] Cleanup failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())
