import httpx
import logging
from config import SMARTLEAD_API_KEY, SMARTLEAD_BASE_URL

logger = logging.getLogger(__name__)


class SmartLeadClient:
    """Client for SmartLead.AI API.

    Handles:
    - Pushing qualified leads into campaigns
    - Auto-creating campaigns for new niches
    - Managing lead status (auto-send vs review queue)
    """

    def __init__(self):
        self.api_key = SMARTLEAD_API_KEY
        self.base_url = SMARTLEAD_BASE_URL

    def _params(self, extra: dict | None = None) -> dict:
        params = {"api_key": self.api_key}
        if extra:
            params.update(extra)
        return params

    async def list_campaigns(self) -> list[dict]:
        """List all SmartLead campaigns."""
        if not self.api_key:
            logger.warning("SmartLead API key not configured")
            return []

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{self.base_url}/campaigns",
                    params=self._params(),
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.error(f"SmartLead list campaigns failed: {e}")
            return []

    async def create_campaign(self, name: str) -> dict:
        """Create a new SmartLead campaign.

        Auto-creates campaigns for new niches when no matching
        campaign exists.

        Returns: {"id": int, "name": str, ...} or empty dict.
        """
        if not self.api_key:
            return {}

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self.base_url}/campaigns/create",
                    params=self._params(),
                    json={"name": name},
                )
                resp.raise_for_status()
                data = resp.json()
                logger.info(f"SmartLead campaign created: {data.get('id')} - {name}")
                return data
        except Exception as e:
            logger.error(f"SmartLead create campaign failed: {e}")
            return {}

    async def find_or_create_campaign(self, niche: str) -> int | None:
        """Find an existing campaign for a niche, or create one.

        Naming convention: "TikTok Outreach - {niche}"

        Returns: campaign_id or None.
        """
        campaign_name = f"TikTok Outreach - {niche.title()}"

        # Check existing campaigns
        campaigns = await self.list_campaigns()
        for c in campaigns:
            if c.get("name", "").lower() == campaign_name.lower():
                logger.info(f"Found existing campaign: {c['id']} - {campaign_name}")
                return c.get("id")

        # Create new campaign
        new_campaign = await self.create_campaign(campaign_name)
        return new_campaign.get("id")

    async def add_lead_to_campaign(
        self,
        campaign_id: int,
        email: str,
        first_name: str = "",
        last_name: str = "",
        custom_fields: dict | None = None,
    ) -> dict:
        """Add a single lead to a SmartLead campaign.

        custom_fields can include:
        - tiktok_username, follower_count, engagement_score,
          lead_score, bio, profile_url, etc.

        Returns: API response dict.
        """
        if not self.api_key:
            return {}

        lead_data = {
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
        }

        if custom_fields:
            lead_data["custom_fields"] = custom_fields

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self.base_url}/campaigns/{campaign_id}/leads",
                    params=self._params(),
                    json={"lead_list": [lead_data]},
                )
                resp.raise_for_status()
                data = resp.json()
                logger.info(f"Lead added to campaign {campaign_id}: {email}")
                return data
        except Exception as e:
            logger.error(f"SmartLead add lead failed: {e}")
            return {}

    async def add_leads_batch(
        self, campaign_id: int, leads: list[dict]
    ) -> dict:
        """Add multiple leads to a campaign in one request.

        Each lead dict should have: email, first_name, last_name,
        and optionally custom_fields.
        """
        if not self.api_key or not leads:
            return {}

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{self.base_url}/campaigns/{campaign_id}/leads",
                    params=self._params(),
                    json={"lead_list": leads},
                )
                resp.raise_for_status()
                data = resp.json()
                logger.info(
                    f"Batch added {len(leads)} leads to campaign {campaign_id}"
                )
                return data
        except Exception as e:
            logger.error(f"SmartLead batch add failed: {e}")
            return {}

    async def get_campaign_leads(self, campaign_id: int, offset: int = 0, limit: int = 100) -> list[dict]:
        """Get leads from a campaign (for review queue)."""
        if not self.api_key:
            return []

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{self.base_url}/campaigns/{campaign_id}/leads",
                    params=self._params({"offset": offset, "limit": limit}),
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.error(f"SmartLead get leads failed: {e}")
            return []

    async def update_lead_status(
        self, campaign_id: int, lead_id: int, status: str
    ) -> dict:
        """Update a lead's status (for review queue approval/rejection)."""
        if not self.api_key:
            return {}

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self.base_url}/campaigns/{campaign_id}/leads/{lead_id}/status",
                    params=self._params(),
                    json={"status": status},
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.error(f"SmartLead update lead status failed: {e}")
            return {}

    async def health_check(self) -> bool:
        if not self.api_key:
            return False
        try:
            campaigns = await self.list_campaigns()
            return isinstance(campaigns, list)
        except Exception:
            return False
