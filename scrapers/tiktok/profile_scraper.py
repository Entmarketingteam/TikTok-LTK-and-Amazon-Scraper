import logging
from models.profile import TikTokProfile, TikTokVideo
from scrapers.tiktok.apify_client import ApifyTikTokClient
from scrapers.tiktok.email_extractor import extract_emails, extract_bio_links
from scrapers.tiktok.link_scraper import deep_scrape_bio_links

logger = logging.getLogger(__name__)


def parse_video(item: dict) -> TikTokVideo:
    """Parse an Apify result item into a TikTokVideo model."""
    author_meta = item.get("authorMeta", {})
    music_meta = item.get("musicMeta", {})
    video_meta = item.get("videoMeta", {})
    covers = video_meta.get("coverUrl", "") or item.get("covers", {}).get(
        "default", ""
    )

    return TikTokVideo(
        id=item.get("id", ""),
        text=item.get("text", ""),
        url=item.get("webVideoUrl", "") or f"https://www.tiktok.com/@{author_meta.get('name', '')}/video/{item.get('id', '')}",
        cover_url=covers if isinstance(covers, str) else "",
        play_count=item.get("playCount", 0),
        like_count=item.get("diggCount", 0) or item.get("likes", 0),
        comment_count=item.get("commentCount", 0),
        share_count=item.get("shareCount", 0),
        created_at=item.get("createTimeISO", ""),
        author_username=author_meta.get("name", ""),
        author_name=author_meta.get("nickName", ""),
        author_avatar=author_meta.get("avatar", ""),
        music_title=music_meta.get("musicName", ""),
    )


def parse_profile(item: dict) -> TikTokProfile:
    """Parse an Apify result item into a TikTokProfile model."""
    author_meta = item.get("authorMeta", {})

    username = author_meta.get("name", "")
    bio = author_meta.get("signature", "") or item.get("signature", "")
    bio_link = author_meta.get("bioLink", "") or ""

    return TikTokProfile(
        username=username,
        display_name=author_meta.get("nickName", ""),
        bio=bio,
        follower_count=author_meta.get("fans", 0),
        following_count=author_meta.get("following", 0),
        like_count=author_meta.get("heart", 0),
        video_count=author_meta.get("video", 0),
        profile_url=f"https://www.tiktok.com/@{username}",
        avatar_url=author_meta.get("avatar", ""),
        bio_link=bio_link,
        emails=extract_emails(bio),
    )


async def search_videos(keyword: str, max_videos: int = 20, date_range: int = 7) -> list[TikTokVideo]:
    """Search TikTok for videos by keyword."""
    client = ApifyTikTokClient()
    results = await client.search_videos(keyword, max_videos, date_range)

    videos = []
    for item in results[:max_videos]:
        try:
            videos.append(parse_video(item))
        except Exception as e:
            logger.warning(f"Failed to parse video: {e}")

    return videos


async def scrape_profile_with_emails(username: str, deep_search: bool = True) -> TikTokProfile:
    """Scrape a TikTok profile and extract emails, optionally following bio links."""
    client = ApifyTikTokClient()
    results = await client.scrape_profile(username)

    if not results:
        return TikTokProfile(
            username=username,
            profile_url=f"https://www.tiktok.com/@{username}",
        )

    profile = parse_profile(results[0])

    # Deep search: follow bio links for emails
    if deep_search:
        all_links = extract_bio_links(profile.bio)
        if profile.bio_link:
            all_links.append(profile.bio_link)

        if all_links:
            linktree_emails = await deep_scrape_bio_links(all_links)
            profile.linktree_emails = linktree_emails

    return profile


def extract_unique_profiles(videos: list[TikTokVideo]) -> list[dict]:
    """Extract unique creator profiles from video results."""
    seen = set()
    profiles = []
    for video in videos:
        if video.author_username and video.author_username not in seen:
            seen.add(video.author_username)
            profiles.append({
                "username": video.author_username,
                "display_name": video.author_name,
                "avatar_url": video.author_avatar,
                "profile_url": f"https://www.tiktok.com/@{video.author_username}",
            })
    return profiles
