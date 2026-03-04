import logging
from dataclasses import asdict
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from config import PORT
from models.profile import SearchRequest, ProfileSearchRequest
from scrapers.tiktok.profile_scraper import (
    search_videos,
    scrape_profile_with_emails,
    extract_unique_profiles,
)
from exporters.csv_exporter import export_videos_csv, export_profiles_csv
from pipeline.orchestrator import PipelineOrchestrator
from pipeline.review_queue import ReviewQueue

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="TikTok Scraper & Email Finder")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# In-memory state
_last_videos = []
_last_profiles = []
_last_pipeline_result = None

# Singletons
orchestrator = PipelineOrchestrator()
review_queue = ReviewQueue()


# ── Request Models ──────────────────────────────────────────────

class PipelineRequest(BaseModel):
    keyword: str
    max_videos: int = 20
    date_range: int = 7
    custom_bio_keywords: list[str] = []
    instagram_phantom_id: str = ""
    auto_push_to_smartlead: bool = True


class ReviewAction(BaseModel):
    action: str  # "approve" or "reject"
    niche: str = ""


# ── Pages ───────────────────────────────────────────────────────

@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# ── Original Search APIs ────────────────────────────────────────

@app.post("/api/search")
async def api_search(req: SearchRequest):
    """Search TikTok videos by keyword via Apify."""
    global _last_videos

    if not req.keyword.strip():
        raise HTTPException(400, "Keyword is required")

    try:
        videos = await search_videos(req.keyword, req.max_videos, req.date_range)
        profiles = extract_unique_profiles(videos)
        _last_videos = videos

        return {
            "videos": [v.model_dump() for v in videos],
            "profiles": profiles,
            "total": len(videos),
        }
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(500, f"Search failed: {str(e)}")


@app.post("/api/profile")
async def api_profile(req: ProfileSearchRequest):
    """Scrape a single TikTok profile and extract emails."""
    if not req.username.strip():
        raise HTTPException(400, "Username is required")

    try:
        profile = await scrape_profile_with_emails(req.username, req.deep_search)
        return profile.model_dump()
    except Exception as e:
        logger.error(f"Profile scrape failed: {e}")
        raise HTTPException(500, f"Profile scrape failed: {str(e)}")


@app.post("/api/scan-emails")
async def api_scan_emails(data: dict):
    """Scan multiple profiles for emails."""
    global _last_profiles

    usernames = data.get("usernames", [])
    deep_search = data.get("deep_search", True)

    if not usernames:
        raise HTTPException(400, "No usernames provided")

    profiles = []
    for username in usernames:
        try:
            profile = await scrape_profile_with_emails(username, deep_search)
            profiles.append(profile)
        except Exception as e:
            logger.warning(f"Failed to scan @{username}: {e}")

    _last_profiles = profiles

    return {
        "profiles": [p.model_dump() for p in profiles],
        "total": len(profiles),
        "with_emails": sum(1 for p in profiles if p.emails or p.linktree_emails),
    }


# ── Full Pipeline API ──────────────────────────────────────────

@app.post("/api/pipeline/run")
async def api_pipeline_run(req: PipelineRequest):
    """Run the full scrape → score → enrich → outreach pipeline."""
    global _last_pipeline_result

    if not req.keyword.strip():
        raise HTTPException(400, "Keyword is required")

    try:
        result = await orchestrator.run(
            keyword=req.keyword,
            max_videos=req.max_videos,
            date_range=req.date_range,
            custom_bio_keywords=req.custom_bio_keywords or None,
            instagram_phantom_id=req.instagram_phantom_id,
            auto_push_to_smartlead=req.auto_push_to_smartlead,
        )

        _last_pipeline_result = result

        # Add medium-score leads to review queue
        review_leads = [l for l in result.leads if l.tier == "review"]
        if review_leads:
            review_queue.add_batch(review_leads)

        # Serialize leads for JSON response
        leads_data = []
        for lead in result.leads:
            lead_dict = {
                "username": lead.username,
                "display_name": lead.display_name,
                "bio": lead.bio,
                "profile_url": lead.profile_url,
                "avatar_url": lead.avatar_url,
                "follower_count": lead.follower_count,
                "outreach_email": lead.outreach_email,
                "bio_emails": lead.bio_emails,
                "linktree_emails": lead.linktree_emails,
                "find_email_result": lead.find_email_result,
                "instagram_handle": lead.instagram_handle,
                "instagram_emails": lead.instagram_emails,
                "tier": lead.tier,
                "pushed_to_smartlead": lead.pushed_to_smartlead,
                "score": {
                    "total": lead.score.total_score,
                    "engagement": lead.score.engagement_score,
                    "followers": lead.score.follower_score,
                    "bio_keywords": lead.score.bio_keyword_score,
                    "content_relevance": lead.score.content_relevance_score,
                    "recency": lead.score.recency_score,
                    "matched_keywords": lead.score.matched_bio_keywords,
                    "reasoning": lead.score.reasoning,
                } if lead.score else None,
                "errors": lead.pipeline_errors,
            }
            leads_data.append(lead_dict)

        return {
            "keyword": result.keyword,
            "niche_analysis": result.niche_analysis,
            "stats": {
                "videos_found": result.total_videos_found,
                "creators_found": result.total_creators_found,
                "leads_scored": result.total_leads_scored,
                "auto_send": result.auto_send_count,
                "review": result.review_count,
                "discard": result.discard_count,
                "emails_found": result.emails_found,
                "pushed_to_smartlead": result.pushed_to_smartlead,
            },
            "leads": leads_data,
            "started_at": result.started_at,
            "completed_at": result.completed_at,
        }

    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        raise HTTPException(500, f"Pipeline failed: {str(e)}")


# ── Review Queue API ────────────────────────────────────────────

@app.get("/api/review-queue")
async def api_review_queue(status: str | None = None):
    """Get the review queue (medium-score leads awaiting approval)."""
    items = review_queue.get_all(status)

    return {
        "items": [
            {
                "id": item.id,
                "status": item.status,
                "added_at": item.added_at,
                "lead": {
                    "username": item.lead.username,
                    "display_name": item.lead.display_name,
                    "bio": item.lead.bio,
                    "profile_url": item.lead.profile_url,
                    "avatar_url": item.lead.avatar_url,
                    "follower_count": item.lead.follower_count,
                    "outreach_email": item.lead.outreach_email,
                    "tier": item.lead.tier,
                    "score": {
                        "total": item.lead.score.total_score,
                        "engagement": item.lead.score.engagement_score,
                        "reasoning": item.lead.score.reasoning,
                    } if item.lead.score else None,
                },
            }
            for item in items
        ],
        "stats": review_queue.stats(),
    }


@app.post("/api/review-queue/{item_id}")
async def api_review_action(item_id: int, action: ReviewAction):
    """Approve or reject a review queue item."""
    if action.action == "approve":
        result = await review_queue.approve(item_id, action.niche)
    elif action.action == "reject":
        result = review_queue.reject(item_id)
    else:
        raise HTTPException(400, "Action must be 'approve' or 'reject'")

    if "error" in result:
        raise HTTPException(400, result["error"])

    return result


# ── Export APIs ─────────────────────────────────────────────────

@app.get("/api/export/videos")
async def api_export_videos():
    if not _last_videos:
        raise HTTPException(404, "No video results to export")
    csv_content = export_videos_csv(_last_videos)
    return PlainTextResponse(
        csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=tiktok_videos.csv"},
    )


@app.get("/api/export/emails")
async def api_export_emails():
    if not _last_profiles:
        raise HTTPException(404, "No profile results to export")
    csv_content = export_profiles_csv(_last_profiles)
    return PlainTextResponse(
        csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=tiktok_emails.csv"},
    )


@app.get("/api/export/pipeline")
async def api_export_pipeline():
    """Export full pipeline results as CSV."""
    if not _last_pipeline_result:
        raise HTTPException(404, "No pipeline results to export")

    import csv
    import io

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Username", "Display Name", "Email", "Tier", "Score",
        "Engagement Score", "Follower Count", "Bio",
        "Profile URL", "Instagram", "Email Source",
        "Pushed to SmartLead", "Score Reasoning",
    ])

    for lead in _last_pipeline_result.leads:
        email_source = "none"
        if lead.bio_emails:
            email_source = "bio"
        elif lead.linktree_emails:
            email_source = "linktree"
        elif lead.find_email_result:
            email_source = "find_email"
        elif lead.instagram_emails:
            email_source = "instagram"

        writer.writerow([
            lead.username,
            lead.display_name,
            lead.outreach_email,
            lead.tier,
            lead.score.total_score if lead.score else 0,
            lead.score.engagement_score if lead.score else 0,
            lead.follower_count,
            lead.bio[:300] if lead.bio else "",
            lead.profile_url,
            lead.instagram_handle,
            email_source,
            "Yes" if lead.pushed_to_smartlead else "No",
            lead.score.reasoning if lead.score else "",
        ])

    return PlainTextResponse(
        output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=tiktok_pipeline_results.csv"},
    )


# ── Health Check ────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    from scrapers.tiktok.apify_client import ApifyTikTokClient
    from integrations.find_email import FindEmailClient
    from integrations.smartlead import SmartLeadClient
    from integrations.phantom_buster import PhantomBusterClient

    apify_ok = await ApifyTikTokClient().health_check()
    smartlead_ok = await SmartLeadClient().health_check()
    find_email_ok = await FindEmailClient().health_check()
    phantom_ok = await PhantomBusterClient().health_check()

    return {
        "status": "ok",
        "services": {
            "apify": apify_ok,
            "smartlead": smartlead_ok,
            "find_email": find_email_ok,
            "phantom_buster": phantom_ok,
        },
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=True)
