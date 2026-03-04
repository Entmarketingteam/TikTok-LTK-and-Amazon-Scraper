import os
import logging

logger = logging.getLogger(__name__)

# ── Doppler Integration ──────────────────────────────────────────
# Doppler is the primary secrets provider. Secrets are fetched at
# startup and cached. Falls back to environment variables / .env
# only if Doppler is unavailable.
#
# Setup:
#   1. pip install doppler-sdk
#   2. Set DOPPLER_TOKEN env var (service token from Doppler dashboard)
#      OR run `doppler setup` in this directory to configure CLI auth
#   3. All secrets are pulled automatically — no .env file needed
# ─────────────────────────────────────────────────────────────────

_secrets: dict[str, str] = {}


def _load_doppler_secrets() -> dict[str, str]:
    """Load all secrets from Doppler. Returns empty dict on failure."""
    # Method 1: Doppler SDK with a service token
    doppler_token = os.getenv("DOPPLER_TOKEN", "")
    if doppler_token:
        try:
            from doppler_sdk import DopplerSDK
            sdk = DopplerSDK()
            sdk.set_access_token(doppler_token)

            # Fetch all secrets for the configured project/config
            response = sdk.secrets.list(
                project=os.getenv("DOPPLER_PROJECT", "tiktok-scraper"),
                config=os.getenv("DOPPLER_CONFIG", "dev"),
            )

            secrets = {}
            if response and hasattr(response, "secrets"):
                for key, val in response.secrets.items():
                    if hasattr(val, "computed"):
                        secrets[key] = val.computed
                    elif isinstance(val, dict) and "computed" in val:
                        secrets[key] = val["computed"]

            if secrets:
                logger.info(f"Doppler: loaded {len(secrets)} secrets via SDK")
                return secrets
        except Exception as e:
            logger.warning(f"Doppler SDK failed: {e}")

    # Method 2: Doppler CLI (if `doppler` is installed and configured)
    try:
        import subprocess
        import json
        result = subprocess.run(
            ["doppler", "secrets", "download", "--no-file", "--format", "json"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            secrets = json.loads(result.stdout)
            logger.info(f"Doppler: loaded {len(secrets)} secrets via CLI")
            return secrets
    except FileNotFoundError:
        logger.info("Doppler CLI not installed, skipping")
    except Exception as e:
        logger.warning(f"Doppler CLI failed: {e}")

    # Method 3: Fall back to .env file
    try:
        from dotenv import load_dotenv
        load_dotenv()
        logger.info("Doppler unavailable, fell back to .env")
    except ImportError:
        pass

    return {}


def _get(key: str, default: str = "") -> str:
    """Get a secret from Doppler first, then env vars."""
    return _secrets.get(key, os.getenv(key, default))


# Load secrets at import time
_secrets = _load_doppler_secrets()

# ── Server ───────────────────────────────────────────────────────
PORT = int(_get("PORT", "5000"))

# ── Apify ────────────────────────────────────────────────────────
APIFY_API_TOKEN = _get("APIFY_API_TOKEN")
APIFY_TIKTOK_SCRAPER_ID = "clockworks/free-tiktok-scraper"
APIFY_BASE_URL = "https://api.apify.com/v2"

# ── SmartLead.AI ─────────────────────────────────────────────────
SMARTLEAD_API_KEY = _get("SMARTLEAD_API_KEY")
SMARTLEAD_BASE_URL = "https://server.smartlead.ai/api/v1"

# ── FindEmail ────────────────────────────────────────────────────
FIND_EMAIL_API_KEY = _get("FIND_EMAIL_API_KEY")
FIND_EMAIL_BASE_URL = _get("FIND_EMAIL_BASE_URL", "https://app.findymail.com/api")

# ── Keywords Everywhere ──────────────────────────────────────────
KEYWORDS_EVERYWHERE_API_KEY = _get("KEYWORDS_EVERYWHERE_API_KEY")
KEYWORDS_EVERYWHERE_BASE_URL = "https://api.keywordseverywhere.com/v1"

# ── PhantomBuster ────────────────────────────────────────────────
PHANTOMBUSTER_API_KEY = _get("PHANTOMBUSTER_API_KEY")
PHANTOMBUSTER_BASE_URL = "https://api.phantombuster.com/api/v2"

# ── Rate Limiting ────────────────────────────────────────────────
REQUEST_DELAY_SECONDS = 1.5
MAX_RETRIES = 3

# ── Lead Scoring Thresholds ──────────────────────────────────────
LEAD_SCORE_AUTO_SEND = int(_get("LEAD_SCORE_AUTO_SEND", "75"))
LEAD_SCORE_REVIEW_MIN = int(_get("LEAD_SCORE_REVIEW_MIN", "40"))

# ── Lead Scoring Weights (out of 100) ────────────────────────────
WEIGHT_ENGAGEMENT = int(_get("WEIGHT_ENGAGEMENT", "35"))
WEIGHT_FOLLOWERS = int(_get("WEIGHT_FOLLOWERS", "20"))
WEIGHT_BIO_KEYWORDS = int(_get("WEIGHT_BIO_KEYWORDS", "20"))
WEIGHT_CONTENT_RELEVANCE = int(_get("WEIGHT_CONTENT_RELEVANCE", "15"))
WEIGHT_RECENCY = int(_get("WEIGHT_RECENCY", "10"))
