import os
from dotenv import load_dotenv

load_dotenv()

# Server
PORT = int(os.getenv("PORT", 5000))

# Apify
APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN", "")
APIFY_TIKTOK_SCRAPER_ID = "clockworks/free-tiktok-scraper"
APIFY_BASE_URL = "https://api.apify.com/v2"

# SmartLead.AI
SMARTLEAD_API_KEY = os.getenv("SMARTLEAD_API_KEY", "")
SMARTLEAD_BASE_URL = "https://server.smartlead.ai/api/v1"

# FindEmail (findymail / similar)
FIND_EMAIL_API_KEY = os.getenv("FIND_EMAIL_API_KEY", "")
FIND_EMAIL_BASE_URL = os.getenv("FIND_EMAIL_BASE_URL", "https://app.findymail.com/api")

# Keywords Everywhere
KEYWORDS_EVERYWHERE_API_KEY = os.getenv("KEYWORDS_EVERYWHERE_API_KEY", "")
KEYWORDS_EVERYWHERE_BASE_URL = "https://api.keywordseverywhere.com/v1"

# PhantomBuster
PHANTOMBUSTER_API_KEY = os.getenv("PHANTOMBUSTER_API_KEY", "")
PHANTOMBUSTER_BASE_URL = "https://api.phantombuster.com/api/v2"

# Rate limiting
REQUEST_DELAY_SECONDS = 1.5
MAX_RETRIES = 3

# Lead scoring thresholds
LEAD_SCORE_AUTO_SEND = 75      # Score >= this → auto-push to SmartLead
LEAD_SCORE_REVIEW_MIN = 40     # Score >= this → queue for review
# Score < REVIEW_MIN → discard

# Lead scoring weights (out of 100 total)
WEIGHT_ENGAGEMENT = 35
WEIGHT_FOLLOWERS = 20
WEIGHT_BIO_KEYWORDS = 20
WEIGHT_CONTENT_RELEVANCE = 15
WEIGHT_RECENCY = 10
