from __future__ import annotations

from dataclasses import asdict

from creator_scout.brand.brief import build_brand_brief
from creator_scout.brand.crawler import BrandCrawler
from creator_scout.discovery.jobs import enqueue_discovery_query_job
from creator_scout.discovery.store import DiscoveryStore


class BrandScanService:
    def __init__(self, store: DiscoveryStore, crawler: BrandCrawler | None = None) -> None:
        self.store = store
        self.crawler = crawler or BrandCrawler()

    def scan(
        self,
        brand_url: str,
        *,
        org_id: str | None = None,
        geo: str = "India",
        goal: str = "ugc",
        enqueue_discovery: bool = False,
        provider: str = "youtube",
        query_limit: int = 5,
    ) -> dict:
        pages = self.crawler.crawl(brand_url)
        brief = build_brand_brief(brand_url, pages, self.store, geo=geo, goal=goal)
        page_dicts = [asdict(page) for page in pages]
        brief_dict = asdict(brief)
        brand_id = self.store.save_brand_scan(
            org_id=org_id,
            brand_url=brand_url,
            brand_name=brief.brand_name,
            brief=brief_dict,
            confidence=brief.confidence,
            pages=page_dicts,
        )
        jobs = []
        if enqueue_discovery:
            for query in brief.search_queries[:query_limit]:
                jobs.append(
                    enqueue_discovery_query_job(
                        self.store,
                        query=query,
                        provider=provider,
                        limit=10,
                        org_id=org_id,
                    )
                )
        return {
            "brand_id": brand_id,
            "brand_url": brand_url,
            "pages_crawled": len(pages),
            "brief": brief_dict,
            "discovery_job_ids": jobs,
        }

