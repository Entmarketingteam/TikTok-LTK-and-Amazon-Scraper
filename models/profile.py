from pydantic import BaseModel
from datetime import datetime


class TikTokVideo(BaseModel):
    id: str = ""
    text: str = ""
    url: str = ""
    cover_url: str = ""
    play_count: int = 0
    like_count: int = 0
    comment_count: int = 0
    share_count: int = 0
    created_at: str = ""
    author_username: str = ""
    author_name: str = ""
    author_avatar: str = ""
    music_title: str = ""


class TikTokProfile(BaseModel):
    username: str
    display_name: str = ""
    bio: str = ""
    follower_count: int = 0
    following_count: int = 0
    like_count: int = 0
    video_count: int = 0
    profile_url: str = ""
    avatar_url: str = ""
    bio_link: str = ""
    emails: list[str] = []
    linktree_emails: list[str] = []
    scraped_at: datetime = datetime.now()


class SearchRequest(BaseModel):
    keyword: str
    date_range: int = 7  # days: 7, 30, 90
    max_videos: int = 20  # 10-100


class ProfileSearchRequest(BaseModel):
    username: str
    deep_search: bool = True  # follow linktree links
