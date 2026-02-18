import os
import time
import logging
import hashlib
import threading
import schedule
import httpx
from flask import Flask
from bs4 import BeautifulSoup

# --- 1. CONFIGURATION (Load from Environment Variables) ---
# We use os.getenv so you can change settings in Render without touching code
TARGET_URL = os.getenv("TARGET_URL", "https://example.com") 
TARGET_SELECTOR = os.getenv("TARGET_SELECTOR", "body") 
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK", "")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", "10")) # Minutes

# --- 2. LOGGING SETUP (Professional & Clean) ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("WatcherBot")

# --- 3. THE WATCHER AGENT ---
class WebsiteWatcher:
    def __init__(self):
        self.last_hash = None
        # Disguise as a standard Chrome browser on Windows
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

    def fetch_and_hash(self):
        """Downloads the site and returns a hash of the specific section."""
        try:
            with httpx.Client(timeout=15.0) as client:
                response = client.get(TARGET_URL, headers=self.headers)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                element = soup.select_one(TARGET_SELECTOR)
                
                if not element:
                    logger.warning(f"⚠️ Selector '{TARGET_SELECTOR}' not found on page.")
                    return None, None

                # Clean text: remove extra whitespace to avoid false positives
                content_text = element.get_text(separator=" ", strip=True)
                content_hash = hashlib.sha256(content_text.encode('utf-8')).hexdigest()
                
                return content_hash, content_text

        except httpx.RequestError as e:
            logger.error(f"❌ Network Error: {e}")
            return None, None
        except Exception as e:
            logger.error(f"❌ Unexpected Error: {e}")
            return None, None

    def check(self):
        logger.info(f"🔍 Checking target: {TARGET_URL}")
        current_hash, current_text = self.fetch_and_hash()

        if not current_hash:
            return # Skip if fetch failed

        # LOGIC: Handling the 'First Run' vs 'Change'
        if self.last_hash is None:
            self.last_hash = current_hash
            logger.info("✅ Baseline established. Monitoring for changes...")
            # We DO NOT notify here to prevent spam on Render restarts.
        
        elif current_hash != self.last_hash:
            logger.info("🚨 CONTENT CHANGE DETECTED!")
            self.notify(current_text)
            self.last_hash = current_hash # Update memory
        
        else:
            logger.info("zzz No changes detected.")

    def notify(self, content_snippet):
        if not DISCORD_WEBHOOK:
            logger.warning("⚠️ Change detected, but no Discord Webhook URL set!")
            return

        # Create a rich Discord Embed
        payload = {
            "embeds": [{
                "title": "🔔 New Content Detected!",
                "description": f"Change detected at **{TARGET_URL}**",
                "color": 5763719, # Green
                "fields": [
                    {
                        "name": "Preview",
                        "value": f"```\n{content_snippet[:250]}...\n```"
                    }
                ],
                "footer": {"text": "Render Watcher Bot • 2026"}
            }]
        }
        
        try:
            httpx.post(DISCORD_WEBHOOK, json=payload)
            logger.info("📨 Notification sent to Discord.")
        except Exception as e:
            logger.error(f"❌ Failed to send Discord alert: {e}")

# --- 4. BACKGROUND SCHEDULER ---
def run_scheduler():
    bot = WebsiteWatcher()
    
    # Run once immediately on startup to set baseline
    bot.check()
    
    # Schedule the loop
    schedule.every(CHECK_INTERVAL).minutes.do(bot.check)
    
    logger.info(f"⏱️ Scheduler started. Checking every {CHECK_INTERVAL} minutes.")
    
    while True:
        schedule.run_pending()
        time.sleep(1)

# --- 5. FLASK SERVER (For UptimeRobot) ---
app = Flask(__name__)

# Start the watcher in a background thread
# daemon=True means it shuts down when the main app shuts down
threading.Thread(target=run_scheduler, daemon=True).start()

@app.route('/')
def home():
    return "<h1>🤖 Watcher is Active</h1><p>Status: Running</p>", 200

if __name__ == "__main__":
    # Render assigns the port automatically
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
