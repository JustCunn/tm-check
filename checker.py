import time
import random
from discord import send_discord_alert

# @TODO: Send discord message after X failures
# 

def build_api_url(event_id: str, quantity: int) -> str:
    return (
        f"https://www.ticketmaster.ie/api/quickpicks/{event_id}/list"
        f"?sort=price&offset=0&qty={quantity}&primary=true&resale=true&tids=000000000001"
    )

async def check_ticket_availability(playwright, event_id: str, quantity: int) -> bool:
    browser = await playwright.chromium.launch(headless=True)
    context = await browser.new_context()

    # Visit event page to establish session
    event_url = f"https://www.ticketmaster.ie/event/{event_id}"
    page = await context.new_page()
    await page.goto(event_url, wait_until="networkidle")

    # Fetch API after session is active
    api_url = build_api_url(event_id, quantity)
    response = await context.request.get(api_url)

    if response.status != 200:
        print(f"[ERROR] API returned {response.status} for {api_url}")
        await browser.close()
        return False

    data = await response.json()
    print(data)
    quantity_available = data.get("quantity", 0)
    picks = data.get("picks", [])

    await browser.close()
    return quantity_available > 0 or len(picks) > 0

def safe_check_ticket_availability(playwright, event_id: str, quantity: int, retries=3) -> bool:
    for attempt in range(retries):
        try:
            return check_ticket_availability(playwright, event_id, quantity)
        except Exception as e:
            wait_time = 2 ** attempt + random.uniform(0.5, 1.5)
            print(f"[WARN] Attempt {attempt+1} failed: {e}. Retrying in {wait_time:.1f}s...")
            time.sleep(wait_time)
    print("[ERROR] All retry attempts failed. Assuming no tickets available.")
    return False

def handle_ticket_status(is_available: bool, event_id: str, quantity: int):
    # Placeholder for alerting/notification logic
    if is_available:
        print("✅ TICKETS AVAILABLE\n")
        message = f"✅ TICKETS AVAILABLE for event {event_id} (qty {quantity}) \nhttps://www.ticketmaster.ie/event/{event_id}"
    else:
        print("❌ No tickets\n")
        message = f"❌ No tickets available for event {event_id} (qty {quantity})"

    send_discord_alert(message)
