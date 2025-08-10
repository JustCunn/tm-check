import time
import random
import webbrowser as wb
from discord import send_discord_alert

# @TODO: Send discord message after X failures
# 

def build_api_url(event_id: str, quantity: int) -> str:
    return (
        f"https://www.ticketmaster.ie/api/quickpicks/{event_id}/list"
        f"?sort=price&qty={quantity}&primary=false&resale=true"
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

    if response.status != 200:
        print(f"[ERROR] API returned {response.status} for {api_url}")
        return False

    data = await response.json()
    print(data)
    quantity_available = data.get("quantity", 0)
    picks = data.get("picks", [])

    return picks[0]['id'] if len(picks) > 0 else None

def safe_check_ticket_availability(context, event_id: str, quantity: int, first_run: bool, retries=3) -> str:
    for attempt in range(retries):
        try:
            return check_ticket_availability(context, event_id, quantity, first_run)
        except Exception as e:
            wait_time = 2 ** attempt + random.uniform(0.5, 1.5)
            print(f"[WARN] Attempt {attempt+1} failed: {e}. Retrying in {wait_time:.1f}s...")
            time.sleep(wait_time)
    print("[ERROR] All retry attempts failed. Assuming no tickets available.")
    return None

async def handle_ticket_status(is_available: bool, event_id: str, quantity: int, tid=None, context=None):
    event_url = f"https://secure.ticketmaster.ie/{event_id}/{tid}?qty={quantity}" if is_available else f"https://www.ticketmaster.ie/event/{event_id}"
    
    if is_available:
        print("✅ TICKETS AVAILABLE\n")
        message = f"✅ TICKETS AVAILABLE for event {event_id} (qty {quantity}) \n{event_url}"
        
        # Open the event page in a new browser tab when tickets are found
        # if context:
        #     page = await context.new_page()
        #     await page.goto(event_url, wait_until="networkidle")
        wb.open(event_url, new=2)  # Open in a new tab if possible
    else:
        print("❌ No tickets\n")
        message = f"❌ No tickets available for event {event_id} (qty {quantity})"

    send_discord_alert(message)
