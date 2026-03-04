import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

from models.profile import TikTokVideo, TikTokProfile
from scoring.lead_scorer import score_lead, LeadScore
from scrapers.tiktok.profile_scraper import (
    search_videos,
    scrape_profile_with_emails,
    extract_unique_profiles,
)
from integrations.find_email import FindEmailClient
from integrations.phantom_buster import PhantomBusterClient
from integrations.keywords_everywhere import KeywordsEverywhereClient
from integrations.smartlead import SmartLeadClient

logger = logging.getLogger(__name__)


@dataclass
class PipelineLead:
    """A lead flowing through the pipeline with all enrichment data."""
    username: str
    display_name: str = ""
    bio: str = ""
    profile_url: str = ""
    avatar_url: str = ""
    follower_count: int = 0
    like_count: int = 0
    video_count: int = 0

    # Best video stats (used for scoring)
    best_play_count: int = 0
    best_like_count: int = 0
    best_comment_count: int = 0
    best_share_count: int = 0
    best_video_text: str = ""
    best_video_created_at: str = ""

    # Emails found at each stage
    bio_emails: list[str] = field(default_factory=list)
    linktree_emails: list[str] = field(default_factory=list)
    find_email_result: str = ""
    instagram_emails: list[str] = field(default_factory=list)

    # Final email chosen for outreach
    outreach_email: str = ""

    # Enrichment
    instagram_handle: str = ""
    instagram_followers: int = 0
    instagram_bio: str = ""

    # Scoring
    score: LeadScore | None = None
    tier: str = "pending"  # pending, auto_send, review, discard, sent

    # Pipeline state
    smartlead_campaign_id: int | None = None
    pushed_to_smartlead: bool = False
    pipeline_errors: list[str] = field(default_factory=list)


@dataclass
class PipelineResult:
    """Result of a full pipeline run."""
    keyword: str
    started_at: str = ""
    completed_at: str = ""
    niche_analysis: dict = field(default_factory=dict)
    total_videos_found: int = 0
    total_creators_found: int = 0
    total_leads_scored: int = 0
    auto_send_count: int = 0
    review_count: int = 0
    discard_count: int = 0
    emails_found: int = 0
    pushed_to_smartlead: int = 0
    leads: list[PipelineLead] = field(default_factory=list)


class PipelineOrchestrator:
    """Orchestrates the full scrape → score → enrich → outreach pipeline.

    Flow:
    1. Analyze niche (Keywords Everywhere)
    2. Search TikTok videos (Apify)
    3. Extract unique creators
    4. Scrape each creator's profile + bio emails + Linktree deep scrape
    5. FindEmail fallback for creators with no email
    6. PhantomBuster Instagram enrichment
    7. Score each lead (engagement-heavy)
    8. Auto-send high-score leads to SmartLead
    9. Queue medium-score leads for review
    10. Discard low-score leads
    """

    def __init__(self):
        self.find_email = FindEmailClient()
        self.phantom = PhantomBusterClient()
        self.keywords = KeywordsEverywhereClient()
        self.smartlead = SmartLeadClient()

    async def run(
        self,
        keyword: str,
        max_videos: int = 20,
        date_range: int = 7,
        custom_bio_keywords: list[str] | None = None,
        instagram_phantom_id: str = "",
        auto_push_to_smartlead: bool = True,
    ) -> PipelineResult:
        """Run the full pipeline end-to-end."""

        result = PipelineResult(
            keyword=keyword,
            started_at=datetime.now(timezone.utc).isoformat(),
        )

        # ── Step 1: Niche Analysis ──────────────────────────────────
        logger.info(f"[Pipeline] Step 1: Analyzing niche '{keyword}'")
        result.niche_analysis = await self.keywords.analyze_niche(keyword)

        # ── Step 2: Search TikTok Videos ────────────────────────────
        logger.info(f"[Pipeline] Step 2: Searching TikTok for '{keyword}'")
        videos = await search_videos(keyword, max_videos, date_range)
        result.total_videos_found = len(videos)

        if not videos:
            logger.warning("[Pipeline] No videos found, aborting")
            result.completed_at = datetime.now(timezone.utc).isoformat()
            return result

        # ── Step 3: Extract Unique Creators ─────────────────────────
        logger.info("[Pipeline] Step 3: Extracting unique creators")
        creator_map = self._build_creator_map(videos)
        result.total_creators_found = len(creator_map)

        # Build PipelineLeads with best video stats
        leads: list[PipelineLead] = []
        for username, data in creator_map.items():
            lead = PipelineLead(
                username=username,
                display_name=data["display_name"],
                avatar_url=data["avatar_url"],
                profile_url=f"https://www.tiktok.com/@{username}",
                best_play_count=data["best_play_count"],
                best_like_count=data["best_like_count"],
                best_comment_count=data["best_comment_count"],
                best_share_count=data["best_share_count"],
                best_video_text=data["best_video_text"],
                best_video_created_at=data["best_video_created_at"],
            )
            leads.append(lead)

        # ── Step 4: Profile Scrape + Email Extraction ───────────────
        logger.info(f"[Pipeline] Step 4: Scraping {len(leads)} profiles")
        await self._enrich_profiles(leads)

        # ── Step 5: FindEmail Fallback ──────────────────────────────
        logger.info("[Pipeline] Step 5: FindEmail fallback for leads without emails")
        await self._find_email_fallback(leads)

        # ── Step 6: PhantomBuster Instagram Enrichment ──────────────
        if instagram_phantom_id:
            logger.info("[Pipeline] Step 6: PhantomBuster Instagram enrichment")
            await self._instagram_enrichment(leads, instagram_phantom_id)
        else:
            logger.info("[Pipeline] Step 6: Skipping Instagram enrichment (no phantom ID)")

        # ── Step 7: Choose Best Email & Score ───────────────────────
        logger.info("[Pipeline] Step 7: Scoring leads")
        for lead in leads:
            self._choose_outreach_email(lead)
            lead.score = score_lead(
                username=lead.username,
                follower_count=lead.follower_count,
                play_count=lead.best_play_count,
                like_count=lead.best_like_count,
                comment_count=lead.best_comment_count,
                share_count=lead.best_share_count,
                bio=lead.bio,
                video_text=lead.best_video_text,
                created_at=lead.best_video_created_at,
                search_keyword=keyword,
                custom_bio_keywords=custom_bio_keywords,
            )
            lead.tier = lead.score.tier

        result.total_leads_scored = len(leads)
        result.auto_send_count = sum(1 for l in leads if l.tier == "auto_send")
        result.review_count = sum(1 for l in leads if l.tier == "review")
        result.discard_count = sum(1 for l in leads if l.tier == "discard")
        result.emails_found = sum(1 for l in leads if l.outreach_email)

        # ── Step 8: Push to SmartLead ───────────────────────────────
        if auto_push_to_smartlead:
            logger.info("[Pipeline] Step 8: Pushing auto-send leads to SmartLead")
            auto_leads = [l for l in leads if l.tier == "auto_send" and l.outreach_email]
            if auto_leads:
                pushed = await self._push_to_smartlead(auto_leads, keyword)
                result.pushed_to_smartlead = pushed
        else:
            logger.info("[Pipeline] Step 8: Skipping SmartLead push (disabled)")

        result.leads = leads
        result.completed_at = datetime.now(timezone.utc).isoformat()

        logger.info(
            f"[Pipeline] Complete: {result.total_videos_found} videos, "
            f"{result.total_creators_found} creators, "
            f"{result.emails_found} emails, "
            f"{result.auto_send_count} auto-send, "
            f"{result.review_count} review, "
            f"{result.pushed_to_smartlead} pushed"
        )

        return result

    def _build_creator_map(self, videos: list[TikTokVideo]) -> dict:
        """Build a map of unique creators with their best-performing video stats."""
        creators: dict[str, dict] = {}

        for v in videos:
            if not v.author_username:
                continue

            total_engagement = v.like_count + v.comment_count + v.share_count

            if v.author_username not in creators:
                creators[v.author_username] = {
                    "display_name": v.author_name,
                    "avatar_url": v.author_avatar,
                    "best_play_count": v.play_count,
                    "best_like_count": v.like_count,
                    "best_comment_count": v.comment_count,
                    "best_share_count": v.share_count,
                    "best_video_text": v.text,
                    "best_video_created_at": v.created_at,
                    "best_engagement": total_engagement,
                }
            else:
                existing = creators[v.author_username]
                if total_engagement > existing["best_engagement"]:
                    existing.update({
                        "best_play_count": v.play_count,
                        "best_like_count": v.like_count,
                        "best_comment_count": v.comment_count,
                        "best_share_count": v.share_count,
                        "best_video_text": v.text,
                        "best_video_created_at": v.created_at,
                        "best_engagement": total_engagement,
                    })

        return creators

    async def _enrich_profiles(self, leads: list[PipelineLead]) -> None:
        """Scrape each lead's TikTok profile for bio, emails, linktree."""
        for lead in leads:
            try:
                profile = await scrape_profile_with_emails(lead.username, deep_search=True)
                lead.bio = profile.bio
                lead.follower_count = profile.follower_count
                lead.like_count = profile.like_count
                lead.video_count = profile.video_count
                lead.bio_emails = profile.emails
                lead.linktree_emails = profile.linktree_emails
                lead.avatar_url = profile.avatar_url or lead.avatar_url
            except Exception as e:
                lead.pipeline_errors.append(f"profile_scrape: {e}")
                logger.warning(f"Profile scrape failed for @{lead.username}: {e}")

    async def _find_email_fallback(self, leads: list[PipelineLead]) -> None:
        """Use FindEmail API for leads that have no email from scraping."""
        for lead in leads:
            if lead.bio_emails or lead.linktree_emails:
                continue  # Already have an email

            try:
                result = await self.find_email.find_email_by_social(lead.profile_url)
                if result.get("email"):
                    lead.find_email_result = result["email"]
                    logger.info(f"FindEmail found email for @{lead.username}: {result['email']}")
            except Exception as e:
                lead.pipeline_errors.append(f"find_email: {e}")

    async def _instagram_enrichment(
        self, leads: list[PipelineLead], phantom_id: str
    ) -> None:
        """Use PhantomBuster to scrape Instagram profiles for additional data."""
        # Try to find Instagram handles from TikTok bios
        ig_map: dict[str, PipelineLead] = {}
        for lead in leads:
            ig_handle = self._extract_instagram_from_bio(lead.bio)
            if ig_handle:
                lead.instagram_handle = ig_handle
                ig_url = f"https://www.instagram.com/{ig_handle}/"
                ig_map[ig_url] = lead

        if not ig_map:
            return

        try:
            results = await self.phantom.scrape_instagram_profile(
                phantom_id, list(ig_map.keys())
            )
            for ig_data in results:
                ig_url = ig_data.get("profileUrl", "")
                lead = ig_map.get(ig_url)
                if lead:
                    lead.instagram_followers = ig_data.get("followersCount", 0)
                    lead.instagram_bio = ig_data.get("biography", "")
                    # Extract emails from Instagram bio too
                    from scrapers.tiktok.email_extractor import extract_emails
                    lead.instagram_emails = extract_emails(lead.instagram_bio)
        except Exception as e:
            logger.warning(f"Instagram enrichment failed: {e}")

    def _extract_instagram_from_bio(self, bio: str) -> str:
        """Try to extract an Instagram handle from a TikTok bio."""
        if not bio:
            return ""

        import re
        # Match patterns like "IG: @handle", "instagram: handle", "📸 @handle"
        patterns = [
            r"(?:ig|instagram|insta)\s*[:\-]?\s*@?([a-zA-Z0-9_.]+)",
            r"instagram\.com/([a-zA-Z0-9_.]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, bio, re.IGNORECASE)
            if match:
                return match.group(1)
        return ""

    def _choose_outreach_email(self, lead: PipelineLead) -> None:
        """Choose the best email for outreach from all sources.

        Priority: bio email > linktree email > FindEmail > Instagram email
        """
        if lead.bio_emails:
            lead.outreach_email = lead.bio_emails[0]
        elif lead.linktree_emails:
            lead.outreach_email = lead.linktree_emails[0]
        elif lead.find_email_result:
            lead.outreach_email = lead.find_email_result
        elif lead.instagram_emails:
            lead.outreach_email = lead.instagram_emails[0]

    async def _push_to_smartlead(
        self, leads: list[PipelineLead], niche: str
    ) -> int:
        """Push qualified leads to SmartLead campaign."""
        campaign_id = await self.smartlead.find_or_create_campaign(niche)
        if not campaign_id:
            logger.error("Failed to find/create SmartLead campaign")
            return 0

        smartlead_leads = []
        for lead in leads:
            if not lead.outreach_email:
                continue

            # Split display name into first/last
            name_parts = (lead.display_name or lead.username).split(maxsplit=1)
            first_name = name_parts[0] if name_parts else lead.username
            last_name = name_parts[1] if len(name_parts) > 1 else ""

            smartlead_leads.append({
                "email": lead.outreach_email,
                "first_name": first_name,
                "last_name": last_name,
                "custom_fields": {
                    "tiktok_username": f"@{lead.username}",
                    "tiktok_url": lead.profile_url,
                    "follower_count": str(lead.follower_count),
                    "lead_score": str(lead.score.total_score if lead.score else 0),
                    "engagement_score": str(lead.score.engagement_score if lead.score else 0),
                    "bio": lead.bio[:500] if lead.bio else "",
                    "instagram": lead.instagram_handle or "",
                },
            })

            lead.smartlead_campaign_id = campaign_id
            lead.pushed_to_smartlead = True

        if smartlead_leads:
            await self.smartlead.add_leads_batch(campaign_id, smartlead_leads)

        return len(smartlead_leads)
