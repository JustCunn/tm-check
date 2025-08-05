import requests
import os

def send_discord_alert(message: str):
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        print("[WARN] Discord webhook URL not set (DISCORD_WEBHOOK_URL). Skipping alert.")
        return

    try:
        response = requests.post(
            webhook_url,
            json={"content": f"{message}"},
            timeout=10
        )
        if response.status_code != 204:
            print(f"[ERROR] Failed to send Discord alert: {response.status_code} {response.text}")
    except Exception as e:
        print(f"[ERROR] Discord webhook failed: {e}")