import httpx
import asyncio
import logging
from config import APIFY_API_TOKEN, APIFY_TIKTOK_SCRAPER_ID, APIFY_BASE_URL

logger = logging.getLogger(__name__)


class ApifyTikTokClient:
    """Client for Apify's Clockworks TikTok Scraper."""

    def __init__(self):
        self.token = APIFY_API_TOKEN
        self.base_url = APIFY_BASE_URL
        self.actor_id = APIFY_TIKTOK_SCRAPER_ID

    async def search_videos(
        self, keyword: str, max_videos: int = 20, date_range: int = 7
    ) -> list[dict]:
        """Search TikTok videos by keyword using Apify actor."""
        run_input = {
            "searchQueries": [keyword],
            "maxProfilesPerQuery": 0,
            "resultsPerPage": min(max_videos, 100),
            "shouldDownloadCovers": False,
            "shouldDownloadVideos": False,
            "shouldDownloadSlideshowImages": False,
        }

        return await self._run_actor(run_input)

    async def scrape_profile(self, username: str) -> list[dict]:
        """Scrape a single TikTok profile."""
        clean_username = username.lstrip("@")
        profile_urls = [f"https://www.tiktok.com/@{clean_username}"]

        run_input = {
            "profiles": profile_urls,
            "resultsPerPage": 10,
            "shouldDownloadCovers": False,
            "shouldDownloadVideos": False,
            "shouldDownloadSlideshowImages": False,
        }

        return await self._run_actor(run_input)

    async def _run_actor(self, run_input: dict) -> list[dict]:
        """Run an Apify actor and wait for results."""
        url = f"{self.base_url}/acts/{self.actor_id}/runs"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}",
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            # Start the actor run
            resp = await client.post(url, json=run_input, headers=headers)
            resp.raise_for_status()
            run_data = resp.json()["data"]
            run_id = run_data["id"]

            logger.info(f"Apify actor run started: {run_id}")

            # Poll for completion
            status_url = f"{self.base_url}/actor-runs/{run_id}"
            for _ in range(60):  # max 5 minutes of polling
                await asyncio.sleep(5)
                status_resp = await client.get(status_url, headers=headers)
                status_resp.raise_for_status()
                status = status_resp.json()["data"]["status"]

                if status == "SUCCEEDED":
                    break
                elif status in ("FAILED", "ABORTED", "TIMED-OUT"):
                    logger.error(f"Apify actor run failed with status: {status}")
                    return []
            else:
                logger.error("Apify actor run timed out waiting for results")
                return []

            # Fetch results from the dataset
            dataset_id = status_resp.json()["data"]["defaultDatasetId"]
            dataset_url = f"{self.base_url}/datasets/{dataset_id}/items"
            dataset_resp = await client.get(
                dataset_url, headers=headers, params={"format": "json"}
            )
            dataset_resp.raise_for_status()
            return dataset_resp.json()

    async def health_check(self) -> bool:
        """Check if the Apify token is valid."""
        if not self.token:
            return False
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self.base_url}/users/me",
                    headers={"Authorization": f"Bearer {self.token}"},
                )
                return resp.status_code == 200
        except Exception:
            return False
