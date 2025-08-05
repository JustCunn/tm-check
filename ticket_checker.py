import argparse
import random
from checker import handle_ticket_status
import asyncio
import argparse
from playwright.async_api import async_playwright
from checker import safe_check_ticket_availability, handle_ticket_status

async def main():
    parser = argparse.ArgumentParser(description="Ticketmaster Ticket Checker")
    parser.add_argument("event_id", help="Ticketmaster Event ID")
    parser.add_argument("quantity", type=int, help="Number of tickets to check for")
    parser.add_argument(
        "--interval", type=int, default=60, help="Polling interval in seconds (default: 60)"
    )
    parser.add_argument(
    "--consec-fails", type=int, default=10, help="The number of consecutive unsuccessful searches until alert"
    )
    
    args = parser.parse_args()

    print(f"🎫 Starting Ticket Checker for event: {args.event_id}, qty: {args.quantity}")
    print(f"⏱ Polling every {args.interval} seconds. Press Ctrl+C to stop.\n")

    async with async_playwright() as playwright:
        unsuccessful_count = 0
        try:
            while True:
                is_available = await safe_check_ticket_availability(playwright, args.event_id, args.quantity)

                if is_available:
                    unsuccessful_count = 0
                else:
                    unsuccessful_count += 1


                if unsuccessful_count % 10 == 0:
                  unsuccessful_count = 0
                  handle_ticket_status(is_available, args.event_id, args.quantity)
                elif is_available:
                  handle_ticket_status(is_available, args.event_id, args.quantity)
                else:
                    print("❌ No tickets")

                await asyncio.sleep(args.interval + random.uniform(-5, 5))
        except KeyboardInterrupt:
            print("\n🛑 Stopped by user.")

if __name__ == "__main__":
    asyncio.run(main())
