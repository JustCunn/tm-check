import requests

# Your unique secret key from the Pushcut app

def send_alert(topic, dynamic_url):
    requests.post(f"https://ntfy.sh/{topic}",
        data="There is a ticket available!".encode('utf-8'),
        headers={
            "Title": "Ticket Alert!",
            "Click": dynamic_url, # This makes the notification clickable
            "Priority": "high"
        })

if __name__ == "__main__":
    send_alert("justin_tm_ep_alerts", "https://www.google.com")