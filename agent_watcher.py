import os
import hashlib
import logging
import httpx
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# --- CONFIGURATION ---
TARGET_URL = os.environ["TARGET_URL"]
TARGET_SELECTOR = os.environ.get("TARGET_SELECTOR", "body")
DISCORD_WEBHOOK = os.environ["DISCORD_WEBHOOK"]
MEMORY_FILE = "last_run.txt"

# --- LOGGING ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_website_content():
    """Fetches the website using a real browser to render Javascript."""
    logging.info(f"Launching browser to check {TARGET_URL}...")
    
    with sync_playwright() as p:
        # Launch an invisible Chromium browser
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        try:
            # Go to the site and wait until the network is quiet (JS has loaded)
            page.goto(TARGET_URL, wait_until="networkidle", timeout=30000)
            
            # Extra safety: wait for your specific selector to appear on the screen
            page.wait_for_selector(TARGET_SELECTOR, timeout=10000)
            
            # Now grab the fully rendered HTML
            html = page.content()
            
            soup = BeautifulSoup(html, 'html.parser')
            element = soup.select_one(TARGET_SELECTOR)
            
            if not element:
                logging.warning(f"Selector '{TARGET_SELECTOR}' not found after JS loaded.")
                return None
                
            return element.get_text(separator=" ", strip=True)
            
        except Exception as e:
            logging.error(f"Error fetching site: {e}")
            return None
        finally:
            browser.close()

def notify_discord(new_text):
    """Sends the alert to Discord."""
    if not DISCORD_WEBHOOK:
        return
        
    payload = {
        "embeds": [{
            "title": "🚨 New Content Detected!",
            "description": f"Change detected at **{TARGET_URL}**",
            "color": 5763719,
            "fields": [
                {
                    "name": "Preview",
                    "value": f"```\n{new_text[:250]}...\n```"
                }
            ],
            "footer": {"text": "GitHub Watcher Agent (JS Enabled)"}
        }]
    }
    httpx.post(DISCORD_WEBHOOK, json=payload)

def main():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r") as f:
            last_hash = f.read().strip()
    else:
        last_hash = ""
        logging.info("No memory file found. Creating baseline.")

    content = get_website_content()
    if not content:
        return 

    current_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()

    if last_hash == "":
        logging.info("First run. Saving baseline.")
        with open(MEMORY_FILE, "w") as f:
            f.write(current_hash)
            
    elif current_hash != last_hash:
        logging.info("CHANGE DETECTED! Sending notification...")
        notify_discord(content)
        
        with open(MEMORY_FILE, "w") as f:
            f.write(current_hash)
            
    else:
        logging.info("No changes detected.")

if __name__ == "__main__":
    main()
