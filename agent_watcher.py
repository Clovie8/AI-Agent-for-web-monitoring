import os
import hashlib
import logging
import httpx
import json
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth 
from tenacity import retry, stop_after_attempt, wait_fixed
from google import genai # <-- The brand new import

# --- 1. CONFIGURATION ---
DISCORD_WEBHOOK = os.environ["DISCORD_WEBHOOK"]
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
SITES_FILE = "sites.json"
MEMORY_FILE = "memory.json" 
IMAGE_FILE = "screenshot.png"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

# --- 2. AI BRAIN (Updated for the new google-genai library) ---
def summarize_with_ai(raw_text):
    if not GEMINI_API_KEY:
        return f"*(AI Disabled)*\n\n{raw_text[:200]}..."
    try:
        # The new V2 connection method
        client = genai.Client(api_key=GEMINI_API_KEY)
        prompt = f"Summarize these website updates in 1-2 exciting sentences for Discord. Use bullets if multiple items.\n\nRaw text:\n{raw_text[:2000]}"
        
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt,
        )
        return response.text.strip()
    except Exception as e:
        logging.error(f"AI Brain failed: {e}")
        return f"Raw output:\n{raw_text[:200]}..."

# --- 3. FETCHING ENGINE ---
@retry(stop=stop_after_attempt(3), wait=wait_fixed(30))
def get_website_content(page, url, selector):
    logging.info(f"Checking {url} ...")
    page.goto(url, wait_until="networkidle", timeout=30000)
    page.wait_for_selector(selector, timeout=15000)
    
    locator = page.locator(selector).first
    
    # --- NEW: FIX FOR BLACK IMAGES ---
    # 1. Scroll the movie card into view to trigger Lazy Loading
    locator.scroll_into_view_if_needed()
    # 2. Wait 2 seconds for the poster to actually download
    page.wait_for_timeout(2000) 
    # ---------------------------------
    
    locator.screenshot(path=IMAGE_FILE)
    
    html = page.content()
    soup = BeautifulSoup(html, 'html.parser')
    element = soup.select_one(selector)
    
    if not element:
        raise Exception(f"Selector '{selector}' not found.")
        
    return element.get_text(separator=" ", strip=True)

# --- 4. DISCORD NOTIFIER ---
def notify_discord(url, ai_summary):
    if not DISCORD_WEBHOOK:
        return
        
    current_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    payload = {
        "payload_json": json.dumps({
            "embeds": [{
                "title": "✨ New Content Detected!",
                "url": url,
                "description": f"**AI Summary:**\n{ai_summary}",
                "color": 5763719,
                "image": {"url": f"attachment://{IMAGE_FILE}"},
                "footer": {"text": f"Multi-Agent Pro • {current_time}"}
            }]
        })
    }
    
    try:
        with open(IMAGE_FILE, "rb") as f:
            files = {"file": (IMAGE_FILE, f, "image/png")}
            httpx.post(DISCORD_WEBHOOK, data=payload, files=files)
            logging.info(f"🚀 Alert sent for {url}!")
    except Exception as e:
        logging.error(f"Failed to send Discord message: {e}")

# --- 5. THE MAIN LOOP ---
def main():
    with open(SITES_FILE, "r") as f:
        sites = json.load(f)

    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r") as f:
            memory = json.load(f)
    else:
        memory = {}
        logging.info("Creating initial multi-site memory.")

    memory_changed = False

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1920, "height": 1080})
        page = context.new_page()
        
        stealth = Stealth()
        stealth.apply_stealth_sync(page)

        for site in sites:
            target_url = site["url"]
            target_selector = site["selector"]
            
            try:
                content = get_website_content(page, target_url, target_selector)
                current_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
                last_hash = memory.get(target_url, "")

                if last_hash == "":
                    logging.info(f"First run for {target_url}. Saving baseline.")
                    memory[target_url] = current_hash
                    memory_changed = True
                    
                elif current_hash != last_hash:
                    logging.info(f"🚨 CHANGE DETECTED on {target_url}! Waking AI...")
                    ai_summary = summarize_with_ai(content)
                    notify_discord(target_url, ai_summary)
                    
                    memory[target_url] = current_hash
                    memory_changed = True
                else:
                    logging.info(f"zzz No changes for {target_url}.")
                    
            except Exception as e:
                logging.error(f"❌ Failed to process {target_url}: {e}")
                
            if os.path.exists(IMAGE_FILE):
                os.remove(IMAGE_FILE)

        browser.close()

    if memory_changed:
        with open(MEMORY_FILE, "w") as f:
            json.dump(memory, f, indent=4)

if __name__ == "__main__":
    main()
