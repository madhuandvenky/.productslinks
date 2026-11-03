"""
MadhuVenke Moments - Automated Deals Poster (Prasad Tech Style)
Runs every hour on GitHub Actions
Posts top 5 fresh loot deals to @madhuvenkedeals
"""

import os
import re
import sys
import json
import time
import html
import urllib.request
import urllib.parse

BOT_TOKEN  = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID    = os.environ.get("TELEGRAM_CHAT_ID", "@madhuvenkedeals").strip()
AMAZON_TAG = os.environ.get("AMAZON_TAG", "madhuvenke-21").strip()
DEAL_COUNT = int(os.environ.get("DEAL_COUNT", "5")) # Top 5 deals every hour

FOOTER = (
    "\n\n━━━━━━━━━━━━━━━━━━━━━━\n"
    "🔥 Join MadhuVenke Deals: @madhuvenkedeals\n"
    "💬 WhatsApp Channel: https://whatsapp.com/channel/0029Vb9EERsHFxOsnGsEI71r\n"
    "🛍️ Our Recommended Gear: https://madhuvenke.github.io/.productslinks/"
)

def format_prasad_style(raw_text, amazon_tag):
    t = html.unescape(raw_text)

    # Extract and tag links
    seen = set()
    links = []
    def ext_link(m):
        url = m.group(1).strip().replace("&amp;", "&")
        if "amazon.in" in url:
            if "tag=" in url:
                url = re.sub(r'tag=[a-zA-Z0-9_-]+', f'tag={amazon_tag}', url)
            else:
                url += ("&" if "?" in url else "?") + f"tag={amazon_tag}"
        if url not in seen and not url.startswith("https://t.me"):
            seen.add(url)
            links.append(url)
        return ""

    t = re.sub(r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>([\s\S]*?)</a>', ext_link, t)
    t = t.replace("<br/>", "\n").replace("<br>", "\n")
    t = re.sub(r'<[^>]+>', '', t)
    t = re.sub(r'@[a-zA-Z0-9_]+', '', t)
    t = re.sub(r't\.me/[a-zA-Z0-9_]+', '', t)
    t = re.sub(r'Join.*?(?=\n|$)', '', t, flags=re.IGNORECASE)

    raw_lines = [l.strip() for l in t.split("\n") if l.strip() and l.strip() not in ["🛒", "👉", "🔥", "⚡"]]
    if not raw_lines and not links:
        return None

    # Title with fire emojis
    title = raw_lines[0] if raw_lines else "Special Loot Deal"
    if not title.startswith("🔥"):
        title = f"🔥🔥 {title}"

    # Price / Highlights / Offers
    other_lines = []
    for l in raw_lines[1:]:
        if any(w in l.lower() for w in ["price", "mrp", "deal", "offer", "discount", "lowest", "coupon", "bank", "₹", "rs."]):
            other_lines.append(l)

    post_parts = [title]
    if other_lines:
        post_parts.append("\n" + "\n".join(other_lines))

    if links:
        post_parts.append(f"\n🛒 Buy Here: {links[0]}")

    post_parts.append(FOOTER)
    return "\n".join(post_parts)

def fetch_latest_deals(limit=5):
    sources = [
        "https://t.me/s/prasadtech_deals",
        "https://t.me/s/deals",
        "https://t.me/s/lootdeals"
    ]
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    deals = []
    seen_urls = set()

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
                # Product Photo
                photo_match = re.search(r'class="tgme_widget_message_photo_wrap"[^>]*style="[^"]*background-image:url\(\'([^\']+)\'\)', block)
                if not photo_match:
                    photo_match = re.search(r'background-image:url\(\'([^\']+)\'\)', block)

                photo_url = photo_match.group(1) if photo_match else None
                if photo_url and ("emoji" in photo_url or "sticker" in photo_url or "avatar" in photo_url):
                    photo_url = None
                if photo_url and photo_url.startswith("//"):
                    photo_url = "https:" + photo_url

                # Message Text
                text_match = re.search(r'<div class="tgme_widget_message_text[^>]*>([\s\S]*?)</div>', block)
                if not text_match:
                    continue

                raw_text = text_match.group(1)
                if not any(k in raw_text.lower() for k in ["amazon", "amzn", "flipkart", "fkrt", "myntra", "ajio", "http"]):
                    continue

                # Deduplicate by primary link
                first_link = re.search(r'href=["\']([^"\']+)["\']', raw_text)
                if first_link:
                    base_link = first_link.group(1).split("?")[0]
                    if base_link in seen_urls:
                        continue
                    seen_urls.add(base_link)

                formatted_text = format_prasad_style(raw_text, AMAZON_TAG)
                if not formatted_text:
                    continue

                deals.append({
                    "photo": photo_url,
                    "text": formatted_text
                })

                if len(deals) >= limit:
                    return deals
        except Exception as e:
            print(f"Error reading from {source}: {e}")

    return deals

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
                else:
                    print(f"Photo response: {res}")
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
    if not BOT_TOKEN:
        print("❌ Error: TELEGRAM_BOT_TOKEN is missing!")
        sys.exit(1)

    print(f"Fetching top {DEAL_COUNT} deals for {CHAT_ID}...")
    deals = fetch_latest_deals(limit=DEAL_COUNT)
    if not deals:
        print("No valid deals found.")
        sys.exit(0)

    print(f"Found {len(deals)} deals. Posting to Telegram channel...")
    sent = 0
    for i, deal in enumerate(deals):
        ok = send_to_telegram(deal)
        if ok:
            sent += 1
        time.sleep(2.5) # Pause 2.5s between messages

    print(f"Done! Successfully posted {sent}/{len(deals)} deals to {CHAT_ID}.")
    if sent == 0:
        sys.exit(1)

if __name__ == "__main__":
    main()
