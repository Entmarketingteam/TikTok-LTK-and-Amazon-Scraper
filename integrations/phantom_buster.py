import httpx
import asyncio
import logging
from config import PHANTOMBUSTER_API_KEY, PHANTOMBUSTER_BASE_URL

logger = logging.getLogger(__name__)


class PhantomBusterClient:
    """Client for PhantomBuster API.

    Used for:
    1. TikTok data extraction (supplement to Apify)
    2. Instagram profile enrichment for TikTok creators
    """

    def __init__(self):
        self.api_key = PHANTOMBUSTER_API_KEY
        self.base_url = PHANTOMBUSTER_BASE_URL
        self.headers = {
            "X-Phantombuster-Key": self.api_key,
            "Content-Type": "application/json",
        }

    async def launch_phantom(
        self, phantom_id: str, argument: dict
    ) -> dict:
        """Launch a PhantomBuster phantom and wait for results.

        Args:
            phantom_id: ID of the phantom to launch
            argument: Input arguments for the phantom

        Returns: Phantom run result or empty dict on failure.
        """
        if not self.api_key:
            logger.warning("PhantomBuster API key not configured")
            return {}

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                # Launch the phantom
                resp = await client.post(
                    f"{self.base_url}/agents/launch",
                    headers=self.headers,
                    json={"id": phantom_id, "argument": argument},
                )
                resp.raise_for_status()
                container_id = resp.json().get("containerId")

                if not container_id:
                    logger.error("PhantomBuster: no containerId returned")
                    return {}

                # Poll for completion
                for _ in range(60):
                    await asyncio.sleep(3)
                    status_resp = await client.get(
                        f"{self.base_url}/containers/fetch",
                        headers=self.headers,
                        params={"id": container_id},
                    )
                    status_resp.raise_for_status()
                    status_data = status_resp.json()
                    status = status_data.get("status")

                    if status == "finished":
                        return status_data
                    elif status in ("error", "stopped"):
                        logger.error(f"PhantomBuster run failed: {status}")
                        return {}

                logger.error("PhantomBuster run timed out")
                return {}
        except Exception as e:
            logger.error(f"PhantomBuster launch failed: {e}")
            return {}

    async def scrape_instagram_profile(
        self, phantom_id: str, instagram_urls: list[str]
    ) -> list[dict]:
        """Scrape Instagram profiles for enrichment data.

        Uses the Instagram Profile Scraper phantom.

        Args:
            phantom_id: Your Instagram Profile Scraper phantom ID
            instagram_urls: List of Instagram profile URLs to scrape

        Returns: List of enriched profile data dicts.
        """
        if not instagram_urls:
            return []

        result = await self.launch_phantom(
            phantom_id,
            {
                "spreadsheetUrl": None,
                "sessionCookie": None,
                "profileUrls": instagram_urls,
                "numberOfProfilesPerLaunch": len(instagram_urls),
            },
        )

        if not result:
            return []

        # Parse the result output
        output = result.get("output", "")
        # PhantomBuster typically returns a JSON lines or CSV result
        # The exact parsing depends on the phantom configuration
        return self._parse_phantom_output(result)

    async def scrape_tiktok_profiles(
        self, phantom_id: str, tiktok_urls: list[str]
    ) -> list[dict]:
        """Scrape TikTok profiles via PhantomBuster.

        Supplement to Apify — can extract additional data or be used
        as a fallback.

        Args:
            phantom_id: Your TikTok Profile Scraper phantom ID
            tiktok_urls: List of TikTok profile URLs

        Returns: List of profile data dicts.
        """
        if not tiktok_urls:
            return []

        result = await self.launch_phantom(
            phantom_id,
            {
                "spreadsheetUrl": None,
                "profileUrls": tiktok_urls,
                "numberOfProfilesPerLaunch": len(tiktok_urls),
            },
        )

        return self._parse_phantom_output(result) if result else []

    async def fetch_phantom_output(self, phantom_id: str) -> list[dict]:
        """Fetch the latest output from a phantom."""
        if not self.api_key:
            return []

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{self.base_url}/agents/fetch-output",
                    headers=self.headers,
                    params={"id": phantom_id},
                )
                resp.raise_for_status()
                return resp.json().get("output", [])
        except Exception as e:
            logger.warning(f"PhantomBuster fetch output failed: {e}")
            return []

    def _parse_phantom_output(self, result: dict) -> list[dict]:
        """Parse PhantomBuster phantom result into structured data."""
        output = result.get("resultObject")
        if isinstance(output, list):
            return output
        if isinstance(output, str):
            try:
                import json
                return json.loads(output)
            except Exception:
                pass
        return []

    async def health_check(self) -> bool:
        if not self.api_key:
            return False
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.base_url}/user",
                    headers=self.headers,
                )
                return resp.status_code == 200
        except Exception:
            return False
