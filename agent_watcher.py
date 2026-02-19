import os
import hashlib
import logging
import httpx
import json
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync
from tenacity import retry, stop_after_attempt, wait_fixed
import google.generativeai as genai

# --- 1. CONFIGURATION ---
TARGET_URL = os.environ["TARGET_URL"]
TARGET_SELECTOR = os.environ.get("TARGET_SELECTOR", "body")
DISCORD_WEBHOOK = os.environ["DISCORD_WEBHOOK"]
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
MEMORY_FILE = "last_run.txt"
IMAGE_FILE = "screenshot.png"

# --- 2. LOGGING SETUP ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- 3. UPGRADE 1: TRUE AI BRAIN ---
def summarize_with_ai(raw_text):
    """Uses AI to read the messy code and extract the actual updates."""
    if not GEMINI_API_KEY:
        return f"*(AI Summarization Disabled - Missing API Key)*\n\n{raw_text[:200]}..."
        
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"""
        The following text was just scraped from a website update (likely a movie or streaming site). 
        Please extract the newest additions, movies, or announcements. 
        Write a very short, exciting 1-2 sentence summary for a Discord alert. 
        Format it cleanly using bullet points if there are multiple items.
        
        Raw text:
        {raw_text[:2000]}
        """
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        logging.error(f"AI Brain failed: {e}")
        return f"Raw output:\n{raw_text[:200]}..."

# --- 4. UPGRADE 2 & 3: STEALTH & AUTO-RETRIES ---
# If the site fails to load, it will wait 30 seconds and try again, up to 3 times.
@retry(stop=stop_after_attempt(3), wait=wait_fixed(30))
def get_website_content():
    """Fetches the website using a stealth browser."""
    logging.info(f"Launching stealth browser to check {TARGET_URL}...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Setting a standard viewport to ensure mobile/desktop sites render properly
        context = browser.new_context(viewport={"width": 1920, "height": 1080})
        page = context.new_page()
        
        # Apply Stealth Mode to bypass Cloudflare/Bot-protection
        stealth_sync(page)
        
        try:
            page.goto(TARGET_URL, wait_until="networkidle", timeout=30000)
            page.wait_for_selector(TARGET_SELECTOR, timeout=15000)
            
            # Take screenshot of the target area
            locator = page.locator(TARGET_SELECTOR).first
            locator.screenshot(path=IMAGE_FILE)
            logging.info("📸 Stealth screenshot captured.")
            
            # Grab HTML
            html = page.content()
            soup = BeautifulSoup(html, 'html.parser')
            element = soup.select_one(TARGET_SELECTOR)
            
            if not element:
                raise Exception(f"Selector '{TARGET_SELECTOR}' not found on page.")
                
            return element.get_text(separator=" ", strip=True)
            
        finally:
            browser.close()

# --- 5. UPGRADE 4: PREMIUM DISCORD EMBEDS ---
def notify_discord(ai_summary):
    """Sends a professional, timestamped alert with the AI summary and image."""
    if not DISCORD_WEBHOOK:
        return
        
    current_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    
    payload = {
        "payload_json": json.dumps({
            "embeds": [{
                "title": "✨ New Content Detected!",
                "url": TARGET_URL, # Makes the title a clickable link
                "description": f"**AI Summary:**\n{ai_summary}",
                "color": 5763719, # Green
                "image": {
                    "url": f"attachment://{IMAGE_FILE}"
                },
                "footer": {
                    "text": f"Agent Watcher Pro • {current_time}"
                }
            }]
        })
    }
    
    try:
        with open(IMAGE_FILE, "rb") as f:
            files = {"file": (IMAGE_FILE, f, "image/png")}
            response = httpx.post(DISCORD_WEBHOOK, data=payload, files=files)
            response.raise_for_status()
            logging.info("🚀 Premium notification sent to Discord!")
    except Exception as e:
        logging.error(f"Failed to send Discord message: {e}")

# --- 6. CORE LOGIC ---
def main():
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r") as f:
            last_hash = f.read().strip()
    else:
        last_hash = ""
        logging.info("Creating initial baseline memory.")

    try:
        content = get_website_content()
    except Exception as e:
        logging.error(f"Bot failed after all retries: {e}")
        return

    current_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()

    if last_hash == "":
        logging.info("First run complete. Saving baseline.")
        with open(MEMORY_FILE, "w") as f:
            f.write(current_hash)
            
    elif current_hash != last_hash:
        logging.info("🚨 CHANGE DETECTED! Waking up AI Brain...")
        
        # Pass the messy text to Gemini to clean it up
        ai_summary = summarize_with_ai(content)
        notify_discord(ai_summary)
        
        with open(MEMORY_FILE, "w") as f:
            f.write(current_hash)
            
    else:
        logging.info("zzz No changes detected.")
        
    if os.path.exists(IMAGE_FILE):
        os.remove(IMAGE_FILE)

if __name__ == "__main__":
    main()
