from __future__ import annotations

import re
import urllib.robotparser
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

from creator_scout.discovery.adapters.base import AdapterError, AdapterResult
from creator_scout.discovery.compliance import assert_public_fetch_allowed
from creator_scout.discovery.http import HttpClient
from creator_scout.discovery.models import Platform
from creator_scout.discovery.normalize import extract_public_emails, infer_platform_from_url, normalize_handle


TITLE_RE = re.compile(r"\s+")
TOPIC_HINTS = (
    "skincare",
    "fashion",
    "beauty",
    "food",
    "recipe",
    "fitness",
    "tech",
    "gaming",
    "travel",
    "newsletter",
    "podcast",
    "ugc",
    "creator",
    "youtube",
    "instagram",
    "tiktok",
)


class SimplePageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self.meta: dict[str, str] = {}
        self.links: list[tuple[str, str]] = []
        self._capture_title = False
        self._capture_text = False
        self._current_link: str | None = None
        self._link_text: list[str] = []
        self.text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {key.lower(): value or "" for key, value in attrs}
        if tag == "title":
            self._capture_title = True
        if tag == "meta":
            key = attr.get("name") or attr.get("property")
            content = attr.get("content")
            if key and content:
                self.meta[key.lower()] = content
        if tag == "a" and attr.get("href"):
            self._current_link = attr["href"]
            self._link_text = []
        if tag in {"p", "li", "h1", "h2", "h3", "span", "div"}:
            self._capture_text = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._capture_title = False
        if tag == "a" and self._current_link:
            self.links.append((self._current_link, " ".join(self._link_text).strip()))
            self._current_link = None
            self._link_text = []
        if tag in {"p", "li", "h1", "h2", "h3", "span", "div"}:
            self._capture_text = False

    def handle_data(self, data: str) -> None:
        cleaned = TITLE_RE.sub(" ", data).strip()
        if not cleaned:
            return
        if self._capture_title:
            self.title += cleaned
        if self._current_link:
            self._link_text.append(cleaned)
        if self._capture_text:
            self.text_parts.append(cleaned)

    @property
    def text(self) -> str:
        return "\n".join(self.text_parts)


class PublicWebAdapter:
    provider = "public_web"

    def __init__(self, http: HttpClient | None = None) -> None:
        self.http = http or HttpClient()

    def discover(self, query: str, limit: int = 10) -> AdapterResult:
        raise AdapterError("PublicWebAdapter requires explicit creator-owned profile URLs")

    def fetch_profile(self, profile_url: str) -> AdapterResult:
        assert_public_fetch_allowed(profile_url)
        if not self._robots_allowed(profile_url):
            raise AdapterError(f"robots.txt does not allow fetch: {profile_url}")

        response = self.http.get(profile_url)
        if response.status >= 400:
            raise AdapterError(f"Public page fetch failed {response.status}: {profile_url}")

        parser = SimplePageParser()
        parser.feed(response.text())
        text = "\n".join([parser.title, *parser.meta.values(), parser.text])
        emails = extract_public_emails(text)
        social_links = self._social_links(profile_url, parser.links)
        topics = self._topics(text)
        display_name = parser.meta.get("og:title") or parser.title or urlparse(profile_url).netloc
        description = parser.meta.get("description") or parser.meta.get("og:description") or parser.text[:500]

        accounts = [
            {
                "platform": platform.value,
                "handle": normalize_handle(url.rstrip("/").split("/")[-1]),
                "profile_url": url,
                "bio": description,
            }
            for platform, url in social_links
        ]
        if not accounts:
            accounts = [
                {
                    "platform": "website",
                    "handle": urlparse(profile_url).netloc,
                    "profile_url": profile_url,
                    "bio": description,
                }
            ]

        record = {
            "display_name": display_name.strip(),
            "primary_niche": topics[0] if topics else "creator",
            "summary": description.strip(),
            "topics": topics,
            "accounts": accounts,
            "contacts": [
                {
                    "contact_type": "email",
                    "value": email,
                    "source_url": profile_url,
                    "permission_basis": "public_business_contact",
                    "confidence": 0.68,
                }
                for email in emails
            ],
            "sources": [
                {
                    "source_url": profile_url,
                    "source_type": "creator_owned_site",
                    "confidence": 0.75,
                    "fields_found": {
                        "title": parser.title,
                        "description": description,
                        "emails": emails,
                        "social_links": [url for _, url in social_links],
                        "topics": topics,
                    },
                }
            ],
        }
        return AdapterResult(records=[record], provider=self.provider, source_url=profile_url)

    def _robots_allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        robot_parser = urllib.robotparser.RobotFileParser()
        robot_parser.set_url(robots_url)
        try:
            robot_parser.read()
        except Exception:
            return True
        return robot_parser.can_fetch(self.http.user_agent, url)

    def _social_links(self, base_url: str, links: list[tuple[str, str]]) -> list[tuple[Platform, str]]:
        social: list[tuple[Platform, str]] = []
        for href, _ in links:
            url = urljoin(base_url, href)
            platform = infer_platform_from_url(url)
            if platform in {Platform.INSTAGRAM, Platform.TIKTOK, Platform.YOUTUBE, Platform.TWITCH, Platform.X, Platform.PINTEREST, Platform.SNAPCHAT}:
                social.append((platform, url.split("?")[0].rstrip("/")))
        seen = set()
        unique = []
        for platform, url in social:
            key = (platform, url)
            if key not in seen:
                seen.add(key)
                unique.append((platform, url))
        return unique

    def _topics(self, text: str) -> list[str]:
        lowered = text.lower()
        topics = [topic for topic in TOPIC_HINTS if topic in lowered]
        return topics[:12]

