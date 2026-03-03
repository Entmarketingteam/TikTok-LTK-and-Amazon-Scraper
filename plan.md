# TikTok Scraper & Profile Email Search — Implementation Plan

## Overview
Web-based TikTok scraper that searches trending videos by keyword via **Apify's Clockworks TikTok Scraper**, discovers creator profiles, and extracts emails from bios + Linktree/bio-link pages (one layer deep). Built with FastAPI + vanilla JS frontend.

---

## Architecture

```
TikTok-LTK-and-Amazon-Scraper/
├── requirements.txt            # Python dependencies
├── .gitignore
├── .env.example                # APIFY_API_TOKEN placeholder
├── config.py                   # Central config (Apify token, settings)
├── main.py                     # FastAPI app + uvicorn entry point
├── scrapers/
│   └── tiktok/
│       ├── apify_client.py     # Apify actor runner (search & profile)
│       ├── profile_scraper.py  # Parse Apify results, orchestrate email extraction
│       ├── email_extractor.py  # Regex email extraction + obfuscation handling
│       └── link_scraper.py     # Deep-scrape Linktree/bio links for emails
├── models/
│   └── profile.py              # Pydantic models (TikTokVideo, TikTokProfile, requests)
├── exporters/
│   └── csv_exporter.py         # CSV export for videos & profiles
├── templates/
│   └── index.html              # Web UI template
└── static/
    ├── style.css               # Dark theme TikTok-inspired UI
    └── app.js                  # Frontend logic (search, modals, email scan)
```

---

## Features Built

### 1. Video Search (via Apify)
- Keyword search with configurable date range (7/30/90 days)
- Configurable result count (10-100 videos)
- Video cards with cover images, author info, engagement stats
- Click-to-expand video modal with full stats + TikTok link
- Auto-discovers unique creator profiles from results

### 2. Profile Email Finder
- Single profile lookup by username
- Extracts emails directly from TikTok bio text
- Regex handles obfuscated emails ("name [at] gmail [dot] com")
- Filters false positives (example@example.com, etc.)

### 3. Deep Linktree/Bio Link Scraping
- Detects 15+ link-in-bio services (linktr.ee, beacons.ai, stan.store, etc.)
- Follows bio links one layer deep via HTTP
- Scrapes page text, mailto: links, and raw HTML for emails
- Concurrent scraping with asyncio for speed

### 4. Batch Email Scan
- "Scan All Profiles for Emails" button after video search
- Iterates all discovered creators, runs profile + deep scrape on each
- Results displayed in a table (username, bio emails, linktree emails)

### 5. CSV Export
- Export video results to CSV
- Export email scan results to CSV (username, bio, emails, linktree emails)

---

## Tech Stack

| Component | Choice | Why |
|-----------|--------|-----|
| Backend | FastAPI | Async-native, fast, auto-docs |
| Data Source | Apify Clockworks TikTok Scraper | Reliable TikTok data without direct scraping |
| HTTP Client | httpx (async) | HTTP/2, async, clean API |
| Deep Scraping | BeautifulSoup4 + httpx | Parse Linktree pages for emails |
| Data Models | Pydantic v2 | Validation, serialization |
| Frontend | Vanilla HTML/CSS/JS | Zero build step, ships as static files |
| Styling | Custom dark theme | TikTok-inspired gradient branding |

---

## How to Run

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set Apify token
cp .env.example .env
# Edit .env and add your APIFY_API_TOKEN

# 3. Run the server
python main.py

# 4. Open http://localhost:5000
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Web UI |
| POST | `/api/search` | Search TikTok videos by keyword |
| POST | `/api/profile` | Scrape single profile + emails |
| POST | `/api/scan-emails` | Batch scan profiles for emails |
| GET | `/api/export/videos` | Download last video results as CSV |
| GET | `/api/export/emails` | Download last email results as CSV |
| GET | `/api/health` | Health check + Apify connection status |
