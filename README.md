[![Website Watcher](https://github.com/Clovie8/AI-Agent-for-web-monitoring/actions/workflows/watcher.yml/badge.svg)](https://github.com/Clovie8/AI-Agent-for-web-monitoring/actions/workflows/watcher.yml)

# AI-Agent-for-web-monitoring
Headless AI Agent for web monitoring. Detects content updates with precision selectors and syncs alerts to Discord Webhooks. 'Set and forget' architecture.


# 🎬 Multi-Agent Pro: AI-Powered Web Scraper

An intelligent, fully autonomous multi-site web scraper that monitors movie/TV streaming websites for new content. It leverages **Google's Gemini 2.5 Flash AI** to generate smart summaries, extracts TMDB metadata, and sends rich notifications directly to Discord using a headless browser.

Fully automated to run completely free in the background using **GitHub Actions**.

## ✨ Key Features

* **🧠 Gemini 2.5 Flash Integration:** Doesn't just scrape text. The AI brain reads the website updates and uses its internal knowledge base to automatically append estimated **TMDB Ratings, Release Years, and Genres** to the alerts.
* **🥷 Playwright Stealth V2:** Bypasses modern anti-bot protection (like Cloudflare) by simulating real human browser behavior and fingerprints.
* **📸 Smart Screenshots & Lazy Loading:** Automatically scrolls newly detected elements into view and waits for lazy-loaded high-resolution movie posters to download before snapping a picture.
* **🥷 The "Popup Assassin":** Includes custom error-handled logic to auto-select languages (e.g., Kinyarwanda) and automatically dismiss disruptive "Continue" overlays before scanning the page.
* **🛡️ Bulletproof Failsafes:** * Uses the `tenacity` library to Auto-Retry up to 3 times if a website is loading too slowly (`domcontentloaded` targeting).
  * Implements `git pull --rebase` to automatically resolve Git collision errors if code is edited while the bot is running.
  * Features a hard-coded GitHub Actions failsafe that pings Discord with a direct log link if the entire workflow crashes.
* **⏰ 100% Autopilot:** Runs on a strict 30-minute `cron` schedule via GitHub Actions, processing timezone conversions to Central Africa Time (CAT) dynamically.

## 🛠️ Tech Stack

* **Language:** Python 3.12+
* **Browser Automation:** Playwright (`sync_playwright`), `playwright-stealth`
* **Parsing:** BeautifulSoup4 (`bs4`)
* **AI Provider:** Google GenAI (`google-genai`)
* **Infrastructure:** GitHub Actions (Ubuntu-latest)
* **Notifications:** Discord Webhooks (`httpx`)

## 🚀 Setup & Installation

### 1. Repository Secrets
To run this securely, you must configure the following in your GitHub repository under **Settings > Secrets and variables > Actions**:
* `DISCORD_WEBHOOK`: Your full Discord channel webhook URL.
* `GEMINI_API_KEY`: Your active Google AI Studio API key.

### 2. Configure Your Targets
Add the websites and specific CSS selectors you want to monitor in the `sites.json` file. 

Example configuration:
```json
[
  {
    "url": "[https://www.cinebeta.net/reba/tvshows/](https://www.cinebeta.net/reba/tvshows/)",
    "selector": "article.item.tvshows"
  },
  {
    "url": "[https://www.rebamovie.com/filme-na-serie](https://www.rebamovie.com/filme-na-serie)",
    "selector": "[data-testid^='movie-card-']"
  }
] 
```
### 3. How Memory Works

The bot uses a ```memory.json``` file to store SHA-256 hashes of the scraped content.

* On its first run, it establishes a "baseline" and stays quiet.
* On subsequent runs, if the new hash doesn't match the saved hash, the AI wakes up, processes the new text, alerts Discord, and updates the memory file.
* To force a test alert: Manually edit a hash inside ```memory.json``` to the word ```"test"``` and trigger the workflow.

## 🚦 Automation Failsafe

This workflow runs automatically every 30 minutes. If a critical failure occurs (e.g., API key expires, major code syntax error), the GitHub Action is configured with an if: failure() step to bypass standard operations and send an emergency red alert to Discord with a direct link to the failing run log.
