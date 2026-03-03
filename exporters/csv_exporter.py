import csv
import io
from models.profile import TikTokProfile, TikTokVideo


def export_videos_csv(videos: list[TikTokVideo]) -> str:
    """Export videos to CSV string."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Video ID", "Description", "URL", "Author", "Author Name",
        "Play Count", "Likes", "Comments", "Shares", "Created At", "Music"
    ])
    for v in videos:
        writer.writerow([
            v.id, v.text[:200], v.url, v.author_username, v.author_name,
            v.play_count, v.like_count, v.comment_count, v.share_count,
            v.created_at, v.music_title,
        ])
    return output.getvalue()


def export_profiles_csv(profiles: list[TikTokProfile]) -> str:
    """Export profiles to CSV string."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Username", "Display Name", "Bio", "Followers", "Following",
        "Likes", "Videos", "Profile URL", "Bio Link",
        "Emails (Bio)", "Emails (Linktree)",
    ])
    for p in profiles:
        writer.writerow([
            p.username, p.display_name, p.bio[:300], p.follower_count,
            p.following_count, p.like_count, p.video_count,
            p.profile_url, p.bio_link,
            "; ".join(p.emails), "; ".join(p.linktree_emails),
        ])
    return output.getvalue()
