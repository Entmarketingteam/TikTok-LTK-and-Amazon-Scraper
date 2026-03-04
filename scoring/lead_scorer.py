import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from config import (
    WEIGHT_ENGAGEMENT,
    WEIGHT_FOLLOWERS,
    WEIGHT_BIO_KEYWORDS,
    WEIGHT_CONTENT_RELEVANCE,
    WEIGHT_RECENCY,
    LEAD_SCORE_AUTO_SEND,
    LEAD_SCORE_REVIEW_MIN,
)

logger = logging.getLogger(__name__)

# Default bio keywords that signal openness to collabs/business
DEFAULT_BIO_KEYWORDS = [
    "business inquiries",
    "business email",
    "collab",
    "collaboration",
    "partnerships",
    "brand deals",
    "dm for business",
    "contact me",
    "management:",
    "booking",
    "pr friendly",
    "ugc creator",
    "ugc",
    "content creator",
    "influencer",
    "ambassador",
    "affiliate",
    "link in bio",
    "work with me",
    "sponsor",
    "promo",
]


@dataclass
class LeadScore:
    username: str
    total_score: float = 0.0
    engagement_score: float = 0.0
    follower_score: float = 0.0
    bio_keyword_score: float = 0.0
    content_relevance_score: float = 0.0
    recency_score: float = 0.0
    tier: str = "discard"  # "auto_send", "review", "discard"
    matched_bio_keywords: list[str] = field(default_factory=list)
    reasoning: str = ""


def score_engagement(play_count: int, like_count: int, comment_count: int, share_count: int) -> float:
    """Score engagement rate. Engagement-heavy: this is the primary signal.

    Returns 0-100 normalized score.
    """
    if play_count == 0:
        return 0.0

    # Engagement rate = (likes + comments + shares) / views
    engagement_rate = (like_count + comment_count + share_count) / play_count

    # TikTok benchmarks:
    #   1-3% = average
    #   3-6% = good
    #   6-10% = great
    #   10%+ = viral
    if engagement_rate >= 0.10:
        return 100.0
    elif engagement_rate >= 0.06:
        return 85.0
    elif engagement_rate >= 0.03:
        return 65.0
    elif engagement_rate >= 0.01:
        return 40.0
    else:
        return 15.0


def score_followers(follower_count: int) -> float:
    """Score based on follower count. Lower weight but still relevant.

    Sweet spot for outreach: micro-influencers (10K-100K).
    Returns 0-100 normalized score.
    """
    if follower_count >= 1_000_000:
        return 50.0  # Too big, unlikely to respond
    elif follower_count >= 100_000:
        return 75.0
    elif follower_count >= 50_000:
        return 95.0  # Sweet spot
    elif follower_count >= 10_000:
        return 100.0  # Sweet spot - micro influencers
    elif follower_count >= 5_000:
        return 80.0
    elif follower_count >= 1_000:
        return 55.0
    else:
        return 20.0


def score_bio_keywords(bio: str, custom_keywords: list[str] | None = None) -> tuple[float, list[str]]:
    """Score based on bio keyword matches.

    Returns (score 0-100, list of matched keywords).
    """
    if not bio:
        return 0.0, []

    bio_lower = bio.lower()
    keywords = custom_keywords if custom_keywords else DEFAULT_BIO_KEYWORDS

    matched = [kw for kw in keywords if kw.lower() in bio_lower]

    if len(matched) >= 4:
        return 100.0, matched
    elif len(matched) >= 3:
        return 85.0, matched
    elif len(matched) >= 2:
        return 70.0, matched
    elif len(matched) >= 1:
        return 50.0, matched
    else:
        return 0.0, []


def score_content_relevance(search_keyword: str, video_text: str, bio: str) -> float:
    """Score how relevant the creator's content is to the search keyword.

    Returns 0-100 normalized score.
    """
    if not search_keyword:
        return 50.0  # Neutral if no keyword context

    keyword_lower = search_keyword.lower()
    keyword_parts = keyword_lower.split()

    combined_text = f"{video_text} {bio}".lower()

    # Exact keyword match
    if keyword_lower in combined_text:
        return 100.0

    # Partial matches
    matches = sum(1 for part in keyword_parts if part in combined_text)
    if matches == len(keyword_parts):
        return 90.0
    elif matches > 0:
        return 50.0 + (matches / len(keyword_parts)) * 40.0

    return 10.0


def score_recency(created_at: str) -> float:
    """Score based on how recently content was posted.

    Returns 0-100 normalized score.
    """
    if not created_at:
        return 30.0  # Unknown date gets neutral-low score

    try:
        post_date = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        days_ago = (now - post_date).days

        if days_ago <= 3:
            return 100.0
        elif days_ago <= 7:
            return 90.0
        elif days_ago <= 14:
            return 75.0
        elif days_ago <= 30:
            return 55.0
        elif days_ago <= 60:
            return 35.0
        else:
            return 15.0
    except Exception:
        return 30.0


def score_lead(
    username: str,
    follower_count: int = 0,
    play_count: int = 0,
    like_count: int = 0,
    comment_count: int = 0,
    share_count: int = 0,
    bio: str = "",
    video_text: str = "",
    created_at: str = "",
    search_keyword: str = "",
    custom_bio_keywords: list[str] | None = None,
) -> LeadScore:
    """Calculate a composite lead score for a TikTok creator.

    Engagement-heavy weighting:
      - Engagement rate: 35%
      - Followers: 20%
      - Bio keywords: 20%
      - Content relevance: 15%
      - Recency: 10%
    """
    eng = score_engagement(play_count, like_count, comment_count, share_count)
    fol = score_followers(follower_count)
    bio_score, bio_matched = score_bio_keywords(bio, custom_bio_keywords)
    rel = score_content_relevance(search_keyword, video_text, bio)
    rec = score_recency(created_at)

    total = (
        eng * (WEIGHT_ENGAGEMENT / 100)
        + fol * (WEIGHT_FOLLOWERS / 100)
        + bio_score * (WEIGHT_BIO_KEYWORDS / 100)
        + rel * (WEIGHT_CONTENT_RELEVANCE / 100)
        + rec * (WEIGHT_RECENCY / 100)
    )

    # Determine tier
    if total >= LEAD_SCORE_AUTO_SEND:
        tier = "auto_send"
    elif total >= LEAD_SCORE_REVIEW_MIN:
        tier = "review"
    else:
        tier = "discard"

    reasoning_parts = []
    if eng >= 65:
        reasoning_parts.append(f"strong engagement ({eng:.0f})")
    if fol >= 80:
        reasoning_parts.append(f"ideal follower range ({fol:.0f})")
    if bio_matched:
        reasoning_parts.append(f"bio matches: {', '.join(bio_matched[:3])}")
    if rel >= 75:
        reasoning_parts.append(f"content relevant ({rel:.0f})")
    if rec >= 75:
        reasoning_parts.append(f"recently active ({rec:.0f})")

    return LeadScore(
        username=username,
        total_score=round(total, 1),
        engagement_score=round(eng, 1),
        follower_score=round(fol, 1),
        bio_keyword_score=round(bio_score, 1),
        content_relevance_score=round(rel, 1),
        recency_score=round(rec, 1),
        tier=tier,
        matched_bio_keywords=bio_matched,
        reasoning="; ".join(reasoning_parts) if reasoning_parts else "low signals",
    )
