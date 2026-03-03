import httpx
import asyncio
import logging
from bs4 import BeautifulSoup
from scrapers.tiktok.email_extractor import extract_emails

logger = logging.getLogger(__name__)

# Link-in-bio services to deep-scrape
BIO_LINK_DOMAINS = [
    "linktr.ee",
    "beacons.ai",
    "linkin.bio",
    "lnk.bio",
    "tap.bio",
    "campsite.bio",
    "bio.link",
    "hoo.be",
    "stan.store",
    "snipfeed.co",
    "withkoji.com",
    "carrd.co",
    "solo.to",
    "flow.page",
    "milkshake.app",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def is_bio_link(url: str) -> bool:
    """Check if URL is a link-in-bio service we should deep-scrape."""
    return any(domain in url.lower() for domain in BIO_LINK_DOMAINS)


async def scrape_link_for_emails(url: str) -> list[str]:
    """Scrape a single URL for email addresses."""
    try:
        async with httpx.AsyncClient(
            headers=HEADERS, follow_redirects=True, timeout=15.0
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")

            # Get all text content
            page_text = soup.get_text(separator=" ")

            # Also check href attributes for mailto: links
            mailto_emails = []
            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"]
                if href.startswith("mailto:"):
                    email = href.replace("mailto:", "").split("?")[0].strip()
                    if email:
                        mailto_emails.append(email.lower())

            # Extract from page text
            text_emails = extract_emails(page_text)

            # Also extract emails from raw HTML (sometimes hidden in data attributes)
            html_emails = extract_emails(resp.text)

            all_emails = set(text_emails + mailto_emails + html_emails)
            return list(all_emails)

    except Exception as e:
        logger.warning(f"Failed to scrape {url}: {e}")
        return []


async def deep_scrape_bio_links(links: list[str]) -> list[str]:
    """Scrape all bio links for emails concurrently."""
    bio_links = [url for url in links if is_bio_link(url)]

    if not bio_links:
        return []

    tasks = [scrape_link_for_emails(url) for url in bio_links]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_emails = set()
    for result in results:
        if isinstance(result, list):
            all_emails.update(result)

    return list(all_emails)
