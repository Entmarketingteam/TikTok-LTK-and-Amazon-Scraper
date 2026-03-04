import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pipeline.orchestrator import PipelineLead
from integrations.smartlead import SmartLeadClient

logger = logging.getLogger(__name__)


@dataclass
class ReviewItem:
    """A lead waiting for manual review before outreach."""
    id: int
    lead: PipelineLead
    added_at: str = ""
    status: str = "pending"  # pending, approved, rejected


class ReviewQueue:
    """In-memory review queue for medium-score leads.

    High-score leads get auto-pushed to SmartLead.
    Medium-score leads land here for manual review.
    Approved leads get pushed to SmartLead.
    Rejected leads are discarded.
    """

    def __init__(self):
        self._queue: list[ReviewItem] = []
        self._next_id = 1
        self.smartlead = SmartLeadClient()

    def add(self, lead: PipelineLead) -> ReviewItem:
        """Add a lead to the review queue."""
        item = ReviewItem(
            id=self._next_id,
            lead=lead,
            added_at=datetime.now(timezone.utc).isoformat(),
            status="pending",
        )
        self._queue.append(item)
        self._next_id += 1
        return item

    def add_batch(self, leads: list[PipelineLead]) -> list[ReviewItem]:
        """Add multiple leads to the review queue."""
        return [self.add(lead) for lead in leads]

    def get_all(self, status: str | None = None) -> list[ReviewItem]:
        """Get all review items, optionally filtered by status."""
        if status:
            return [item for item in self._queue if item.status == status]
        return list(self._queue)

    def get_by_id(self, item_id: int) -> ReviewItem | None:
        """Get a single review item by ID."""
        for item in self._queue:
            if item.id == item_id:
                return item
        return None

    async def approve(self, item_id: int, niche: str) -> dict:
        """Approve a lead and push to SmartLead."""
        item = self.get_by_id(item_id)
        if not item:
            return {"error": "Item not found"}
        if item.status != "pending":
            return {"error": f"Item already {item.status}"}

        lead = item.lead
        if not lead.outreach_email:
            return {"error": "Lead has no email"}

        # Push to SmartLead
        campaign_id = await self.smartlead.find_or_create_campaign(niche)
        if not campaign_id:
            return {"error": "Failed to find/create SmartLead campaign"}

        name_parts = (lead.display_name or lead.username).split(maxsplit=1)
        first_name = name_parts[0] if name_parts else lead.username
        last_name = name_parts[1] if len(name_parts) > 1 else ""

        result = await self.smartlead.add_lead_to_campaign(
            campaign_id=campaign_id,
            email=lead.outreach_email,
            first_name=first_name,
            last_name=last_name,
            custom_fields={
                "tiktok_username": f"@{lead.username}",
                "tiktok_url": lead.profile_url,
                "follower_count": str(lead.follower_count),
                "lead_score": str(lead.score.total_score if lead.score else 0),
                "bio": lead.bio[:500] if lead.bio else "",
            },
        )

        item.status = "approved"
        lead.pushed_to_smartlead = True
        lead.smartlead_campaign_id = campaign_id

        return {"success": True, "campaign_id": campaign_id}

    def reject(self, item_id: int) -> dict:
        """Reject a lead (discard from outreach)."""
        item = self.get_by_id(item_id)
        if not item:
            return {"error": "Item not found"}
        if item.status != "pending":
            return {"error": f"Item already {item.status}"}

        item.status = "rejected"
        item.lead.tier = "discard"
        return {"success": True}

    def clear_resolved(self) -> int:
        """Remove approved and rejected items from the queue."""
        before = len(self._queue)
        self._queue = [item for item in self._queue if item.status == "pending"]
        return before - len(self._queue)

    def stats(self) -> dict:
        """Get queue statistics."""
        return {
            "total": len(self._queue),
            "pending": sum(1 for i in self._queue if i.status == "pending"),
            "approved": sum(1 for i in self._queue if i.status == "approved"),
            "rejected": sum(1 for i in self._queue if i.status == "rejected"),
        }
