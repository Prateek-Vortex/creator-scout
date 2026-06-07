from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class BrandPage:
    url: str
    title: str
    page_type: str
    text: str
    metadata: dict
    links: list[str] = field(default_factory=list)
    fetched_at: str = ""


@dataclass(slots=True)
class BrandBrief:
    brand_name: str
    category: str
    products: list[str]
    target_audience: str
    price_positioning: str
    tone: list[str]
    value_props: list[str]
    avoid_creator_types: list[str]
    best_creator_niches: list[str]
    campaign_angles: list[str]
    search_queries: list[str]
    confidence: float
    evidence: list[dict]

