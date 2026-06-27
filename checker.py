import asyncio
import time
import random
import webbrowser as wb
from discord import send_discord_alert
from notification import send_alert

class RateLimitError(Exception):
    pass

def build_api_url(event_id: str, quantity: int) -> str:
    return (
        f"https://www.ticketmaster.ie/api/quickpicks/{event_id}/list"
        f"?sort=price&qty={quantity}&primary=true&resale=true"
    )

async def check_ticket_availability(context, event_id: str, quantity: int, first_run: bool) -> str:
    # Visit event page to establish session
    if first_run:
        event_url = f"https://www.ticketmaster.ie/event/{event_id}"
        page = await context.new_page()
        await page.goto(event_url, wait_until="networkidle")
        await page.close()

    # Fetch API after session is active
    api_url = build_api_url(event_id, quantity)
    response = await context.request.get(api_url)

    if response.status == 429:
        raise RateLimitError(f"429 Too Many Requests for {api_url}")
    if response.status != 200:
        raise RuntimeError(f"API returned {response.status} for {api_url}")

    data = await response.json()
    quantity_available = data.get("quantity", 0)
    picks = data.get("picks", [])
    return picks[0] if len(picks) > 0 else None

async def safe_check_ticket_availability(context, event_id: str, quantity: int, first_run: bool, retries=4, base_delay=1, max_delay=300) -> str:
    """
    Async safe wrapper with exponential backoff + jitter.
    - On RateLimitError (429) uses a longer backoff multiplier.
    - Uses asyncio.sleep (non-blocking).
    """
    for attempt in range(retries):
        try:
            return await check_ticket_availability(context, event_id, quantity, first_run)
        except RateLimitError as e:
            # stronger backoff on 429
            wait = min(max_delay, base_delay * (2 ** attempt) * 10 + random.uniform(0.5, 2.5))
            print(f"[RATE LIMIT] {e}. Backing off {wait:.1f}s (attempt {attempt+1}/{retries})")
            await asyncio.sleep(wait)
        except Exception as e:
            wait_time = 2 ** attempt + random.uniform(0.5, 1.5)
            print(f"[WARN] Attempt {attempt+1} failed: {e}. Retrying in {wait_time:.1f}s...")
            await asyncio.sleep(wait_time)
    print("[ERROR] All retry attempts failed. Assuming no tickets available.")
    return None

async def handle_ticket_status(is_available: bool, event_id: str, quantity: int, tid=None, context=None):
    event_url = f"https://secure.ticketmaster.ie/{event_id}/{tid}?qty={quantity}" if is_available else f"https://www.ticketmaster.ie/event/{event_id}"
    
    if is_available:
        print(f"✅ TICKETS AVAILABLE for event {event_id} (qty {quantity}) \n{event_url}\n")
        # message = f"✅ TICKETS AVAILABLE for event {event_id} (qty {quantity}) \n{event_url}"
        
        # page = await context.new_page()
        # await page.goto(event_url)
        # await page.wait_for_timeout(10000)
        wb.open(event_url, new=2)  # Open in a new tab if possible
    else:
        print("❌ No tickets\n")
        # message = f"❌ No tickets available for event {event_id} (qty {quantity})"

    send_alert("justin_tm_ep_alerts", event_url)
