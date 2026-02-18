import os
import hashlib
import logging
import httpx
from bs4 import BeautifulSoup

# --- CONFIGURATION ---
TARGET_URL = os.environ["TARGET_URL"]
TARGET_SELECTOR = os.environ.get("TARGET_SELECTOR", "body")
DISCORD_WEBHOOK = os.environ["DISCORD_WEBHOOK"]
MEMORY_FILE = "last_run.txt"

# --- LOGGING ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_website_content():
    """Fetches and cleans the website content."""
    headers = {
        "User-Agent": "Mozilla/5.0 (GitHubActions/1.0; +https://github.com/)"
    }
    try:
        response = httpx.get(TARGET_URL, headers=headers, timeout=20.0)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        element = soup.select_one(TARGET_SELECTOR)
        
        if not element:
            logging.warning(f"Selector '{TARGET_SELECTOR}' not found.")
            return None
            
        # Get clean text to avoid false positives from HTML spacing changes
        return element.get_text(separator=" ", strip=True)
        
    except Exception as e:
        logging.error(f"Error fetching site: {e}")
        return None

def notify_discord(new_text):
    """Sends the alert to Discord."""
    if not DISCORD_WEBHOOK:
        return
        
    payload = {
        "embeds": [{
            "title": "🚨 New Content Detected!",
            "description": f"Change detected at **{TARGET_URL}**",
            "color": 5763719, # Green
            "fields": [
                {
                    "name": "Preview",
                    "value": f"```\n{new_text[:250]}...\n```"
                }
            ],
            "footer": {"text": "GitHub Watcher Agent"}
        }]
    }
    httpx.post(DISCORD_WEBHOOK, json=payload)

def main():
    # 1. Read the previous state (Memory)
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r") as f:
            last_hash = f.read().strip()
    else:
        last_hash = ""
        logging.info("No memory file found. Creating baseline.")

    # 2. Fetch current state
    content = get_website_content()
    if not content:
        return # Exit if site is down

    current_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()

    # 3. Compare
    if last_hash == "":
        # First run ever - just save the hash, don't spam
        logging.info("First run. Saving baseline.")
        with open(MEMORY_FILE, "w") as f:
            f.write(current_hash)
            
    elif current_hash != last_hash:
        logging.info("CHANGE DETECTED! Sending notification...")
        notify_discord(content)
        
        # Save the new hash to memory
        with open(MEMORY_FILE, "w") as f:
            f.write(current_hash)
            
    else:
        logging.info("No changes detected.")

if __name__ == "__main__":
    main()
