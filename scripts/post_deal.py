"""
MadhuVenke Moments - Automated Deals Poster
Runs on GitHub Actions (Morning 9:30 AM & Night 7:30 PM IST)
"""

import os
import re
import sys
import json
import urllib.request
import urllib.parse

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "@madhuvenkedeals").strip()
AMAZON_TAG = os.environ.get("AMAZON_TAG", "").strip()

if not BOT_TOKEN:
    print("Error: TELEGRAM_BOT_TOKEN is required!")
    sys.exit(1)

FOOTER = (
    "\n\n━━━━━━━━━━━━━━━━━━━━━━\n"
    "🔥 Join MadhuVenke Deals: @madhuvenkedeals\n"
    "💬 WhatsApp Channel: https://whatsapp.com/channel/0029Vb9EERsHFxOsnGsEI71r\n"
    "🛍️ Our Recommended Gear: https://madhuvenke.github.io/.productslinks/"
)

def fetch_latest_deal():
    sources = ["https://t.me/s/deals", "https://t.me/s/lootdeals"]
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    for source in sources:
        try:
            req = urllib.request.Request(source, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8", errors="ignore")

            # Find all message elements
            msg_blocks = re.findall(
                r'<div class="tgme_widget_message_wrap[^>]*>([\s\S]*?)</div>\s*</div>\s*</div>',
                html
            )

            for block in reversed(msg_blocks):
                # Check for photo
                photo_match = re.search(r'background-image:url\(\'([^\']+)\'\)', block)
                photo_url = photo_match.group(1) if photo_match else None

                # Check for text
                text_match = re.search(r'<div class="tgme_widget_message_text[^>]*>([\s\S]*?)</div>', block)
                if not text_match:
                    continue

                raw_text = text_match.group(1)

                # Ensure it has a shopping link
                if not any(k in raw_text.lower() for k in ["amazon", "amzn", "flipkart", "fkrt", "myntra", "ajio", "http"]):
                    continue

                # Clean HTML tags to readable text
                clean_text = raw_text.replace("<br/>", "\n").replace("<br>", "\n")
                clean_text = re.sub(r'<a href="([^"]+)"[^>]*>([^<]*)</a>', r'\1', clean_text)
                clean_text = re.sub(r'<[^>]+>', ' ', clean_text).strip()

                # Clean other channels' watermark/mentions
                clean_text = re.sub(r'@[a-zA-Z0-9_]+', '', clean_text)
                clean_text = re.sub(r't\.me/[a-zA-Z0-9_]+', '', clean_text)
                clean_text = re.sub(r'Join.*?(?=\n|$)', '', clean_text, flags=re.IGNORECASE).strip()

                # If Amazon tag provided, append tag
                if AMAZON_TAG:
                    clean_text = re.sub(
                        r'(https?://(?:www\.)?amazon\.in/[^\s]+)',
                        lambda m: m.group(1) + ("&tag=" if "?" in m.group(1) else "?tag=") + AMAZON_TAG,
                        clean_text
                    )

                final_text = clean_text + FOOTER

                return {
                    "photo": photo_url,
                    "text": final_text
                }
        except Exception as e:
            print(f"Error reading from {source}: {e}")

    return None

def send_to_telegram(deal):
    base_url = f"https://api.telegram.org/bot{BOT_TOKEN}/"

    if deal.get("photo"):
        endpoint = base_url + "sendPhoto"
        payload = {
            "chat_id": CHAT_ID,
            "photo": deal["photo"],
            "caption": deal["text"][:1024]
        }
    else:
        endpoint = base_url + "sendMessage"
        payload = {
            "chat_id": CHAT_ID,
            "text": deal["text"][:4096]
        }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(endpoint, data=data, headers={"Content-Type": "application/json"})

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            if res.get("ok"):
                print("Successfully posted deal to Telegram!")
                return True
            else:
                print(f"Telegram API response: {res}")
                return False
    except Exception as e:
        print(f"Error sending message to Telegram: {e}")
        return False

def main():
    print(f"Fetching latest deal for {CHAT_ID}...")
    deal = fetch_latest_deal()
    if not deal:
        print("No valid deal found in current feeds.")
        sys.exit(0)

    print("Posting deal to Telegram channel...")
    success = send_to_telegram(deal)
    if success:
        print("All done!")
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
