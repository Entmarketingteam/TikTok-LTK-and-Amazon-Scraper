import httpx
import logging
from config import KEYWORDS_EVERYWHERE_API_KEY, KEYWORDS_EVERYWHERE_BASE_URL

logger = logging.getLogger(__name__)


class KeywordsEverywhereClient:
    """Client for Keywords Everywhere API.

    Used to analyze niche/content relevance of search keywords
    and validate that the keyword/niche has real search volume.
    """

    def __init__(self):
        self.api_key = KEYWORDS_EVERYWHERE_API_KEY
        self.base_url = KEYWORDS_EVERYWHERE_BASE_URL
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }

    async def get_keyword_data(self, keywords: list[str], country: str = "us") -> list[dict]:
        """Get search volume, CPC, and competition for keywords.

        Returns list of:
        {
            "keyword": str,
            "vol": int,         # monthly search volume
            "cpc": float,       # cost per click
            "competition": float,  # 0-1 competition score
            "trend": list       # monthly trend data
        }
        """
        if not self.api_key:
            logger.warning("Keywords Everywhere API key not configured")
            return []

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self.base_url}/get_keyword_data",
                    headers=self.headers,
                    json={
                        "dataSource": "gkp",
                        "kw": keywords,
                        "country": country,
                        "currency": "USD",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                return data.get("data", [])
        except Exception as e:
            logger.warning(f"Keywords Everywhere lookup failed: {e}")
            return []

    async def get_related_keywords(self, keyword: str, country: str = "us") -> list[dict]:
        """Get related keywords for a search term.

        Useful for expanding niche searches and finding
        related creator audiences.
        """
        if not self.api_key:
            return []

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self.base_url}/get_related_keywords",
                    headers=self.headers,
                    json={
                        "kw": keyword,
                        "country": country,
                        "currency": "USD",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                return data.get("data", [])
        except Exception as e:
            logger.warning(f"Keywords Everywhere related lookup failed: {e}")
            return []

    async def get_trend_data(self, keywords: list[str], country: str = "us") -> list[dict]:
        """Get Google Trends data for keywords.

        Helps determine if a niche is trending up or down.
        """
        if not self.api_key:
            return []

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self.base_url}/get_trend_data",
                    headers=self.headers,
                    json={
                        "kw": keywords,
                        "country": country,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                return data.get("data", [])
        except Exception as e:
            logger.warning(f"Keywords Everywhere trend lookup failed: {e}")
            return []

    async def analyze_niche(self, keyword: str) -> dict:
        """Analyze a niche keyword for outreach viability.

        Returns a summary with volume, competition, trend direction,
        and related keywords to expand the search.
        """
        keyword_data = await self.get_keyword_data([keyword])
        related = await self.get_related_keywords(keyword)

        result = {
            "keyword": keyword,
            "volume": 0,
            "cpc": 0.0,
            "competition": 0.0,
            "trend_direction": "unknown",
            "related_keywords": [],
            "viable": False,
        }

        if keyword_data:
            kd = keyword_data[0]
            result["volume"] = kd.get("vol", 0)
            result["cpc"] = kd.get("cpc", {}).get("value", 0.0) if isinstance(kd.get("cpc"), dict) else kd.get("cpc", 0.0)
            result["competition"] = kd.get("competition", 0.0)
            # Viable if there's real search volume
            result["viable"] = result["volume"] > 100

        if related:
            result["related_keywords"] = [
                r.get("keyword", "") for r in related[:10]
            ]

        return result

    async def health_check(self) -> bool:
        if not self.api_key:
            return False
        try:
            data = await self.get_keyword_data(["test"])
            return True
        except Exception:
            return False
