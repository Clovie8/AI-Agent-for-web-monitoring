import os
import hashlib
import logging
import httpx
import json
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# --- CONFIGURATION ---
TARGET_URL = os.environ["TARGET_URL"]
TARGET_SELECTOR = os.environ.get("TARGET_SELECTOR", "body")
DISCORD_WEBHOOK = os.environ["DISCORD_WEBHOOK"]
MEMORY_FILE = "last_run.txt"
IMAGE_FILE = "screenshot.png"

# --- LOGGING ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_website_content():
    """Fetches the website, grabs the text, and takes a picture."""
    logging.info(f"Launching browser to check {TARGET_URL}...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        try:
            page.goto(TARGET_URL, wait_until="networkidle", timeout=30000)
            page.wait_for_selector(TARGET_SELECTOR, timeout=10000)
            
            # 1. Take a picture of the specific element and save it
            locator = page.locator(TARGET_SELECTOR).first
            locator.screenshot(path=IMAGE_FILE)
            logging.info("Screenshot captured successfully.")
            
            # 2. Grab the HTML for text comparison
            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')
            element = soup.select_one(TARGET_SELECTOR)
            
            if not element:
                return None
                
            return element.get_text(separator=" ", strip=True)
            
        except Exception as e:
            logging.error(f"Error fetching site: {e}")
            return None
        finally:
            browser.close()

def notify_discord(new_text):
    """Sends a simple text alert WITH the picture attached."""
    if not DISCORD_WEBHOOK:
        return
        
    # We use a special Discord format to attach a local file to an embed
    payload = {
        "payload_json": json.dumps({
            "embeds": [{
                "title": "🚨 Website Updated!",
                "description": f"New content was just added to **{TARGET_URL}**\n\n**Quick summary:**\n{new_text[:150]}...",
                "color": 5763719,
                "image": {
                    "url": f"attachment://{IMAGE_FILE}" # Links the uploaded image here
                },
                "footer": {"text": "Visual Watcher Agent"}
            }]
        })
    }
    
    # Open the image we just saved and send it in the HTTP request
    try:
        with open(IMAGE_FILE, "rb") as f:
            files = {"file": (IMAGE_FILE, f, "image/png")}
            response = httpx.post(DISCORD_WEBHOOK, data=payload, files=files)
            response.raise_for_status()
            logging.info("Notification with image sent to Discord!")
    except Exception as e:
        logging.error(f"Failed to send Discord message: {e}")

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
        
    # Clean up the image file so it doesn't stay in the repository
    if os.path.exists(IMAGE_FILE):
        os.remove(IMAGE_FILE)

if __name__ == "__main__":
    main()
