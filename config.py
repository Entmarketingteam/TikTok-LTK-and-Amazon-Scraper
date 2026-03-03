import os
from dotenv import load_dotenv

load_dotenv()

APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN", "")
APIFY_TIKTOK_SCRAPER_ID = "clockworks/free-tiktok-scraper"
APIFY_BASE_URL = "https://api.apify.com/v2"

PORT = int(os.getenv("PORT", 5000))

# Rate limiting
REQUEST_DELAY_SECONDS = 1.5
MAX_RETRIES = 3
