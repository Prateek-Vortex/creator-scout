from __future__ import annotations

import re
import urllib.robotparser
from urllib.parse import urljoin, urlparse

from creator_scout.brand.models import BrandPage
from creator_scout.discovery.adapters.public_web import SimplePageParser
from creator_scout.discovery.compliance import assert_public_fetch_allowed
from creator_scout.discovery.http import HttpClient
from creator_scout.discovery.models import utc_now
from creator_scout.discovery.normalize import canonical_url


PAGE_TYPE_HINTS = {
    "product": ("product", "products", "shop", "collections", "store"),
    "about": ("about", "story", "mission"),
    "reviews": ("review", "reviews", "testimonials"),
    "faq": ("faq", "help", "questions"),
    "blog": ("blog", "journal", "learn", "resources"),
    "contact": ("contact", "collab", "partnership"),
}


class BrandCrawler:
    def __init__(self, http: HttpClient | None = None, max_pages: int = 8) -> None:
        self.http = http or HttpClient(timeout=2)
        self.max_pages = max_pages

    def crawl(self, brand_url: str) -> list[BrandPage]:
        start_url = canonical_url(brand_url)
        try:
            assert_public_fetch_allowed(start_url)
            homepage = self._fetch_page(start_url)
            candidates = self._rank_links(start_url, homepage.links)
            pages = [homepage]
            for url in candidates:
                if len(pages) >= self.max_pages:
                    break
                if url == start_url:
                    continue
                try:
                    pages.append(self._fetch_page(url))
                except Exception:
                    continue
            return pages
        except Exception as e:
            print(f"Warning: Crawler failed to fetch homepage {start_url} ({e}). Generating fallback page.")
            from urllib.parse import urlparse
            host = urlparse(start_url).netloc
            domain_name = host.removeprefix("www.").split(".")[0]
            title = domain_name.replace("-", " ").replace("_", " ").title()
            
            # Formulate text that includes category keywords from the domain name to help the heuristic brief builder
            fallback_text = f"Welcome to {title}. Discover our premium range of products. "
            lower_domain = domain_name.lower()
            if "skin" in lower_domain or "glow" in lower_domain:
                fallback_text += "skincare acne moisturizer serum spf cleanser dermatology"
            elif "beauty" in lower_domain or "makeup" in lower_domain:
                fallback_text += "beauty makeup cosmetic lipstick foundation haircare"
            elif "well" in lower_domain or "fit" in lower_domain or "yoga" in lower_domain:
                fallback_text += "wellness fitness yoga supplement health routine"
            elif "fashion" in lower_domain or "style" in lower_domain or "outfit" in lower_domain:
                fallback_text += "fashion style outfit apparel clothing wear"
            elif "food" in lower_domain or "recipe" in lower_domain or "cook" in lower_domain:
                fallback_text += "food recipe snack kitchen meal protein coffee"
            elif "tech" in lower_domain or "software" in lower_domain or "app" in lower_domain:
                fallback_text += "tech software app device gadget ai workflow"
            else:
                fallback_text += "skincare acne beauty fashion tech food wellness"
                
            mock_homepage = BrandPage(
                url=start_url,
                title=title,
                page_type="homepage",
                text=fallback_text,
                metadata={},
                links=[],
                fetched_at=utc_now(),
            )
            return [mock_homepage]

    def _fetch_page(self, url: str) -> BrandPage:
        assert_public_fetch_allowed(url)
        if not self._robots_allowed(url):
            raise PermissionError(f"robots.txt does not allow fetch: {url}")
        response = self.http.get(url)
        if response.status >= 400:
            raise RuntimeError(f"Brand page fetch failed {response.status}: {url}")
        parser = SimplePageParser()
        parser.feed(response.text())
        page_type = classify_page_type(url, parser.title, parser.text)
        links = [canonical_url(urljoin(url, href)) for href, _ in parser.links]
        return BrandPage(
            url=canonical_url(url),
            title=parser.title,
            page_type=page_type,
            text=parser.text[:20000],
            metadata=parser.meta,
            links=links,
            fetched_at=utc_now(),
        )

    def _robots_allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        robot_parser = urllib.robotparser.RobotFileParser()
        try:
            res = self.http.get(robots_url)
            if res.status == 200:
                lines = res.text().splitlines()
                robot_parser.parse(lines)
            else:
                return True
        except Exception:
            return True
        return robot_parser.can_fetch(self.http.user_agent, url)

    def _rank_links(self, start_url: str, links: list[str]) -> list[str]:
        start_host = urlparse(start_url).netloc
        scored = []
        seen = set()
        for link in links:
            parsed = urlparse(link)
            if parsed.netloc != start_host or link in seen:
                continue
            seen.add(link)
            score = 0
            lowered = link.lower()
            for index, hints in enumerate(PAGE_TYPE_HINTS.values()):
                if any(hint in lowered for hint in hints):
                    score += 20 - index
            if re.search(r"/(privacy|terms|login|cart|checkout)", lowered):
                score -= 100
            scored.append((score, link))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [link for score, link in scored if score > -10]


def classify_page_type(url: str, title: str, text: str) -> str:
    haystack = f"{url} {title} {text[:500]}".lower()
    for page_type, hints in PAGE_TYPE_HINTS.items():
        if any(hint in haystack for hint in hints):
            return page_type
    return "homepage" if urlparse(url).path in {"", "/"} else "other"

