import re


# Common false positive domains to filter out
FALSE_POSITIVE_EMAILS = {
    "example@example.com",
    "email@example.com",
    "your@email.com",
    "name@domain.com",
    "user@example.com",
}

# Standard email regex
EMAIL_REGEX = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
)

# Obfuscated email patterns
OBFUSCATED_PATTERNS = [
    # "name [at] gmail [dot] com" or "name (at) gmail (dot) com"
    re.compile(
        r"([a-zA-Z0-9._%+\-]+)\s*[\[\(]\s*at\s*[\]\)]\s*"
        r"([a-zA-Z0-9.\-]+)\s*[\[\(]\s*dot\s*[\]\)]\s*"
        r"([a-zA-Z]{2,})",
        re.IGNORECASE,
    ),
    # "name at gmail dot com"
    re.compile(
        r"([a-zA-Z0-9._%+\-]+)\s+at\s+([a-zA-Z0-9.\-]+)\s+dot\s+([a-zA-Z]{2,})",
        re.IGNORECASE,
    ),
]


def extract_emails(text: str) -> list[str]:
    """Extract email addresses from text, handling obfuscation."""
    if not text:
        return []

    emails = set()

    # Direct email matches
    for match in EMAIL_REGEX.findall(text):
        email = match.lower().strip()
        if email not in FALSE_POSITIVE_EMAILS:
            emails.add(email)

    # Obfuscated patterns
    for pattern in OBFUSCATED_PATTERNS:
        for match in pattern.findall(text):
            if len(match) == 3:
                email = f"{match[0]}@{match[1]}.{match[2]}".lower().strip()
                if email not in FALSE_POSITIVE_EMAILS:
                    emails.add(email)

    return list(emails)


def extract_bio_links(text: str) -> list[str]:
    """Extract URLs from bio text (linktree, beacons, etc.)."""
    if not text:
        return []

    url_regex = re.compile(
        r"https?://[a-zA-Z0-9\-._~:/?#\[\]@!$&'()*+,;=%]+"
    )
    links = url_regex.findall(text)

    # Also look for common link-in-bio patterns without https
    bio_link_patterns = re.compile(
        r"(?:linktr\.ee|beacons\.ai|linkin\.bio|lnk\.bio|tap\.bio|campsite\.bio|bio\.link|hoo\.be)"
        r"/[a-zA-Z0-9._\-]+",
        re.IGNORECASE,
    )
    for match in bio_link_patterns.findall(text):
        links.append(f"https://{match}")

    return list(set(links))
