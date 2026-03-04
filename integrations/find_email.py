import httpx
import logging
from config import FIND_EMAIL_API_KEY, FIND_EMAIL_BASE_URL

logger = logging.getLogger(__name__)


class FindEmailClient:
    """Client for FindEmail/Findymail API.

    Used as a FALLBACK only — called when bio/Linktree scraping
    finds no email for a lead.
    """

    def __init__(self):
        self.api_key = FIND_EMAIL_API_KEY
        self.base_url = FIND_EMAIL_BASE_URL
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def find_email_by_name_and_domain(
        self, full_name: str, domain: str
    ) -> dict:
        """Find email by full name + company domain.

        Returns: {"email": "...", "verified": bool} or empty dict.
        """
        if not self.api_key:
            logger.warning("FindEmail API key not configured")
            return {}

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self.base_url}/search/name",
                    headers=self.headers,
                    json={"name": full_name, "domain": domain},
                )
                resp.raise_for_status()
                data = resp.json()

                if data.get("email"):
                    return {
                        "email": data["email"],
                        "verified": data.get("verified", False),
                        "source": "find_email",
                    }
                return {}
        except Exception as e:
            logger.warning(f"FindEmail lookup failed for {full_name}: {e}")
            return {}

    async def find_email_by_social(
        self, social_url: str
    ) -> dict:
        """Find email by social media profile URL.

        Works well for TikTok/Instagram profiles.
        Returns: {"email": "...", "verified": bool} or empty dict.
        """
        if not self.api_key:
            logger.warning("FindEmail API key not configured")
            return {}

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self.base_url}/search/social",
                    headers=self.headers,
                    json={"social_url": social_url},
                )
                resp.raise_for_status()
                data = resp.json()

                if data.get("email"):
                    return {
                        "email": data["email"],
                        "verified": data.get("verified", False),
                        "source": "find_email",
                    }
                return {}
        except Exception as e:
            logger.warning(f"FindEmail social lookup failed for {social_url}: {e}")
            return {}

    async def verify_email(self, email: str) -> bool:
        """Verify an email address is deliverable."""
        if not self.api_key:
            return False

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{self.base_url}/verify",
                    headers=self.headers,
                    json={"email": email},
                )
                resp.raise_for_status()
                data = resp.json()
                return data.get("is_valid", False)
        except Exception as e:
            logger.warning(f"FindEmail verify failed for {email}: {e}")
            return False

    async def health_check(self) -> bool:
        if not self.api_key:
            return False
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.base_url}/me",
                    headers=self.headers,
                )
                return resp.status_code == 200
        except Exception:
            return False
