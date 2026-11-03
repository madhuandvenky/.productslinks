"""
MadhuVenke Moments - Automated Deals Poster
Runs on GitHub Actions (Morning 9:30 AM & Night 7:30 PM IST)
"""

import os
import re
import sys
import json
import html
import urllib.request
import urllib.parse

BOT_TOKEN  = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID    = os.environ.get("TELEGRAM_CHAT_ID", "@madhuvenkedeals").strip()
AMAZON_TAG = os.environ.get("AMAZON_TAG", "madhuvenke-21").strip()

if not BOT_TOKEN:
    print("❌ Error: TELEGRAM_BOT_TOKEN is missing!")
    sys.exit(1)

FOOTER = (
    "\n\n━━━━━━━━━━━━━━━━━━━━━━\n"
    "🔥 Join MadhuVenke Deals: @madhuvenkedeals\n"
    "💬 WhatsApp Channel: https://whatsapp.com/channel/0029Vb9EERsHFxOsnGsEI71r\n"
    "🛍️ Our Recommended Gear: https://madhuvenke.github.io/.productslinks/"
)

def clean_deal_html(raw_html, amazon_tag):
    t = html.unescape(raw_html)
    seen_urls = set()
    links = []

    def extract_link(m):
        url = m.group(1).strip().replace("&amp;", "&")
        anchor_text = re.sub(r'<[^>]+>', '', m.group(2)).strip()

        # Inject user affiliate tag for Amazon links
        if "amazon.in" in url:
            if "tag=" in url:
                url = re.sub(r'tag=[a-zA-Z0-9_-]+', f'tag={amazon_tag}', url)
            else:
                url += ("&" if "?" in url else "?") + f"tag={amazon_tag}"

        if url not in seen_urls:
            seen_urls.add(url)
            label = anchor_text if anchor_text else "Buy Link"
            links.append((label, url))
        return " "

    # Extract all hyperlinks
    t = re.sub(r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>([\s\S]*?)</a>', extract_link, t)

    # Clean formatting and watermarks
    t = t.replace("<br/>", "\n").replace("<br>", "\n")
    t = re.sub(r'<[^>]+>', '', t)
    t = re.sub(r'@[a-zA-Z0-9_]+', '', t)
    t = re.sub(r't\.me/[a-zA-Z0-9_]+', '', t)
    t = re.sub(r'Join.*?(?=\n|$)', '', t, flags=re.IGNORECASE)

    # Remove orphan emojis left behind
    lines = []
    for line in t.split("\n"):
        line_clean = line.strip()
        if line_clean in ["🛒", "👉", "🔥", "⚡", ""]:
            continue
        lines.append(line_clean)

    body = "\n".join(lines)

    # Append clean, clickable buy links with your tag
    if links:
        body += "\n\n" + "\n".join([f"🛒 {label}: {url}" for label, url in links])

    return body

def fetch_latest_deal():
    sources = ["https://t.me/s/deals", "https://t.me/s/lootdeals"]
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    for source in sources:
        try:
            req = urllib.request.Request(source, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                page_html = resp.read().decode("utf-8", errors="ignore")

            msg_blocks = re.findall(
                r'<div class="tgme_widget_message_wrap[^>]*>([\s\S]*?)</div>\s*</div>\s*</div>',
                page_html
            )

            for block in reversed(msg_blocks):
                photo_match = re.search(r'class="tgme_widget_message_photo_wrap"[^>]*style="[^"]*background-image:url\(\'([^\']+)\'\)', block)
                if not photo_match:
                    photo_match = re.search(r'background-image:url\(\'([^\']+)\'\)', block)

                photo_url = photo_match.group(1) if photo_match else None
                if photo_url and ("emoji" in photo_url or "sticker" in photo_url or "avatar" in photo_url):
                    photo_url = None
                if photo_url and photo_url.startswith("//"):
                    photo_url = "https:" + photo_url

                text_match = re.search(r'<div class="tgme_widget_message_text[^>]*>([\s\S]*?)</div>', block)
                if not text_match:
                    continue

                raw_text = text_match.group(1)
                if not any(k in raw_text.lower() for k in ["amazon", "amzn", "flipkart", "fkrt", "myntra", "ajio", "http"]):
                    continue

                clean_text = clean_deal_html(raw_text, AMAZON_TAG)
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

    # Send with photo if available
    if deal.get("photo"):
        try:
            endpoint = base_url + "sendPhoto"
            payload = {
                "chat_id": CHAT_ID,
                "photo": deal["photo"],
                "caption": deal["text"][:1024]
            }
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(endpoint, data=data, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                if res.get("ok"):
                    print("✅ Successfully posted deal with photo to Telegram!")
                    return True
        except Exception as e:
            print(f"Photo send failed ({e}), falling back to text...")

    # Fallback to text message
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
                print("✅ Successfully posted deal to Telegram!")
                return True
            else:
                print(f"❌ Telegram API response: {res}")
                return False
    except Exception as e:
        print(f"❌ Error sending message to Telegram: {e}")
        return False

def main():
    print(f"Fetching latest deal for {CHAT_ID}...")
    deal = fetch_latest_deal()
    if not deal:
        print("No valid deal found.")
        sys.exit(0)

    print("Posting deal to Telegram channel...")
    success = send_to_telegram(deal)
    if success:
        print("All done!")
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
