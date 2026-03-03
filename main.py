import logging
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from fastapi.responses import PlainTextResponse

from config import PORT
from models.profile import SearchRequest, ProfileSearchRequest
from scrapers.tiktok.profile_scraper import (
    search_videos,
    scrape_profile_with_emails,
    extract_unique_profiles,
)
from exporters.csv_exporter import export_videos_csv, export_profiles_csv

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="TikTok Scraper & Email Finder")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# In-memory cache for last search results (for CSV export)
_last_videos = []
_last_profiles = []


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/search")
async def api_search(req: SearchRequest):
    """Search TikTok videos by keyword via Apify."""
    global _last_videos, _last_profiles

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
    """Scan multiple profiles for emails (from video search results)."""
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
        "with_emails": sum(
            1 for p in profiles if p.emails or p.linktree_emails
        ),
    }


@app.get("/api/export/videos")
async def api_export_videos():
    """Export last video search results as CSV."""
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
    """Export last email scan results as CSV."""
    if not _last_profiles:
        raise HTTPException(404, "No profile results to export")

    csv_content = export_profiles_csv(_last_profiles)
    return PlainTextResponse(
        csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=tiktok_emails.csv"},
    )


@app.get("/api/health")
async def health():
    from scrapers.tiktok.apify_client import ApifyTikTokClient
    client = ApifyTikTokClient()
    apify_ok = await client.health_check()
    return {
        "status": "ok",
        "apify_connected": apify_ok,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=True)
