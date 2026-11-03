"""
MadhuVenke Moments - Smart Automated Deals Engine
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
MAX_DEALS  = int(os.environ.get("MAX_DEALS", "2")) # Up to 2 new deals per 15-min run

FOOTER = (
    "\n\n━━━━━━━━━━━━━━━━━━━━━━\n"
    "🔥 Join MadhuVenke Deals: @madhuvenkedeals\n"
    "💬 WhatsApp Channel: https://whatsapp.com/channel/0029Vb9EERsHFxOsnGsEI71r\n"
    "🛍️ Our Recommended Gear: https://madhuvenke.github.io/.productslinks/"
)

def get_already_posted_keys(channel_handle):
    """Fetches the latest messages from the public channel to prevent duplicates."""
    clean_handle = channel_handle.replace("@", "").strip()
    url = f"https://t.me/s/{clean_handle}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    posted = set()

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            page_html = resp.read().decode("utf-8", errors="ignore")

        # 1. Extract previous product URLs
        urls = re.findall(r'href=["\'](https?://[^\s"\'<>]+)["\']', page_html)
        for u in urls:
            base = u.split("?")[0].replace("https://", "").replace("http://", "").strip().lower()
            if base and not any(k in base for k in ["madhuvenke", "whatsapp.com", "t.me", "telegram.org"]):
                posted.add(base)

        # 2. Extract first 30 chars of post titles
        titles = re.findall(r'<div class="tgme_widget_message_text[^>]*>([\s\S]*?)</div>', page_html)
        for t in titles:
            clean = re.sub(r'<[^>]+>', '', t).replace("🔥", "").strip()
            first_line = clean.split("\n")[0].strip()[:35].lower()
            if first_line:
                posted.add(first_line)

    except Exception as e:
        print(f"Notice: Could not load channel history: {e}")

    return posted

def is_shopping_url(url):
    u = url.lower()
    if any(k in u for k in ["t.me", "telegram.org", "whatsapp.com", "instagram.com", "bit.ly"]):
        return False
    return any(k in u for k in ["amazon", "amzn", "flipkart", "fkrt", "myntra", "ajio", "croma", "boat-lifestyle", "nykaa", "tatacliq", "jiomart", "meesho"]) or "http" in u

def format_prasad_style(raw_text, amazon_tag):
    t = html.unescape(raw_text)

    seen = set()
    links = []

    def ext_link(m):
        url = m.group(1).strip().replace("&amp;", "&")
        if not is_shopping_url(url):
            return ""

        # Inject user affiliate tag for Amazon links
        if "amazon.in" in url:
            if "tag=" in url:
                url = re.sub(r'tag=[a-zA-Z0-9_-]+', f'tag={amazon_tag}', url)
            else:
                url += ("&" if "?" in url else "?") + f"tag={amazon_tag}"

        if url not in seen:
            seen.add(url)
            links.append(url)
        return ""

    # Extract shopping links
    t = re.sub(r'<a\s+[^>]*href=["\']([^"\']+)["\'][^>]*>([\s\S]*?)</a>', ext_link, t)
    t = t.replace("<br/>", "\n").replace("<br>", "\n")
    t = re.sub(r'<[^>]+>', '', t)
    t = re.sub(r'@[a-zA-Z0-9_]+', '', t)
    t = re.sub(r't\.me/[a-zA-Z0-9_]+', '', t)
    t = re.sub(r'Join.*?(?=\n|$)', '', t, flags=re.IGNORECASE)

    raw_lines = [l.strip() for l in t.split("\n") if l.strip() and l.strip() not in ["🛒", "👉", "🔥", "⚡"]]
    if not raw_lines and not links:
        return None

    title = raw_lines[0] if raw_lines else "Special Loot Deal"
    if not title.startswith("🔥"):
        title = f"🔥🔥 {title}"

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
    return "\n".join(post_parts), links[0] if links else None

def fetch_fresh_deals(already_posted, limit=2):
    sources = [
        "https://t.me/s/deals",
        "https://t.me/s/lootdeals",
        "https://t.me/s/prasadtech_deals"
    ]
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

    deals = []
    current_run_keys = set()

    for source in sources:
        try:
            req = urllib.request.Request(source, headers=headers)
            with urllib.request.urlopen(req, timeout=12) as resp:
                page_html = resp.read().decode("utf-8", errors="ignore")

            msg_blocks = re.findall(
                r'<div class="tgme_widget_message_wrap[^>]*>([\s\S]*?)</div>\s*</div>\s*</div>',
                page_html
            )

            for block in reversed(msg_blocks):
                # 1. Check shopping link
                link_match = re.search(r'href=["\'](https?://[^\s"\'<>]+)["\']', block)
                if not link_match:
                    continue
                raw_url = link_match.group(1)
                if not is_shopping_url(raw_url):
                    continue

                base_key = raw_url.split("?")[0].replace("https://", "").replace("http://", "").strip().lower()

                # Deduplication check
                if base_key in already_posted or base_key in current_run_keys:
                    continue

                # 2. Extract Message Text
                text_match = re.search(r'<div class="tgme_widget_message_text[^>]*>([\s\S]*?)</div>', block)
                if not text_match:
                    continue

                formatted = format_prasad_style(text_match.group(1), AMAZON_TAG)
                if not formatted:
                    continue
                formatted_text, primary_link = formatted

                # 3. Product Photo Extraction (with Amazon fallback)
                photo_match = re.search(r'class="tgme_widget_message_photo_wrap"[^>]*style="[^"]*background-image:url\(\'([^\']+)\'\)', block)
                if not photo_match:
                    photo_match = re.search(r'background-image:url\(\'([^\']+)\'\)', block)

                photo_url = photo_match.group(1) if photo_match else None
                if photo_url and ("emoji" in photo_url or "sticker" in photo_url or "avatar" in photo_url):
                    photo_url = None
                if photo_url and photo_url.startswith("//"):
                    photo_url = "https:" + photo_url

                # If no photo in feed, but Amazon link, extract Amazon product image
                if not photo_url and primary_link and "amazon.in" in primary_link:
                    asin_m = re.search(r'/(?:dp|gp/product)/([A-Z0-9]{10})', primary_link)
                    if asin_m:
                        photo_url = f"https://images-eu.ssl-images-amazon.com/images/P/{asin_m.group(1)}.01.LZZZZZZZ.jpg"

                current_run_keys.add(base_key)
                deals.append({
                    "photo": photo_url,
                    "text": formatted_text
                })

                if len(deals) >= limit:
                    return deals
        except Exception as e:
            print(f"Notice: Reading from {source}: {e}")

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

    # Fallback to rich text message
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

    print(f"Checking for recent posts in {CHAT_ID} to prevent duplicates...")
    already_posted = get_already_posted_keys(CHAT_ID)
    print(f"Found {len(already_posted)} recent posts in channel history.")

    print(f"Scanning for NEW flash loot deals...")
    fresh_deals = fetch_fresh_deals(already_posted, limit=MAX_DEALS)

    if not fresh_deals:
        print("✅ Channel is up-to-date! No new flash deals dropped in the last 15 minutes.")
        sys.exit(0)

    print(f"Found {len(fresh_deals)} BRAND NEW deals! Posting to {CHAT_ID}...")
    sent = 0
    for deal in fresh_deals:
        ok = send_to_telegram(deal)
        if ok:
            sent += 1
        time.sleep(2.5) # Pause between messages

    print(f"Done! Successfully posted {sent} fresh deals.")

if __name__ == "__main__":
    main()
