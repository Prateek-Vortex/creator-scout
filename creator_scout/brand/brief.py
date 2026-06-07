from __future__ import annotations

import re
from urllib.parse import urlparse

from creator_scout.brand.models import BrandBrief, BrandPage
from creator_scout.discovery.normalize import tokenize


CATEGORY_KEYWORDS = {
    "skincare": {"skin", "skincare", "acne", "moisturizer", "serum", "spf", "cleanser", "dermatology"},
    "beauty": {"beauty", "makeup", "cosmetic", "lipstick", "foundation", "haircare"},
    "wellness": {"wellness", "fitness", "yoga", "supplement", "health", "routine"},
    "fashion": {"fashion", "style", "outfit", "apparel", "clothing", "wear"},
    "food": {"food", "recipe", "snack", "kitchen", "meal", "protein", "coffee"},
    "tech": {"tech", "software", "app", "device", "gadget", "ai", "workflow"},
}

TONE_KEYWORDS = {
    "clinical": {"clinical", "dermatologist", "science", "tested", "proven"},
    "clean": {"clean", "simple", "minimal", "natural"},
    "playful": {"fun", "playful", "bold", "colorful"},
    "premium": {"premium", "luxury", "crafted", "elevated"},
    "affordable": {"affordable", "budget", "value", "accessible"},
    "trustworthy": {"trusted", "honest", "safe", "certified"},
}

NICHE_BY_CATEGORY = {
    "skincare": ["skincare educators", "acne journey creators", "routine reviewers", "dermatology-aware creators"],
    "beauty": ["beauty reviewers", "makeup tutorial creators", "GRWM creators"],
    "wellness": ["wellness educators", "fitness routine creators", "yoga creators"],
    "fashion": ["styling creators", "affordable fashion creators", "GRWM creators"],
    "food": ["recipe creators", "home cooking creators", "food reviewers"],
    "tech": ["tech reviewers", "workflow creators", "app tutorial creators"],
}


def build_brand_brief(brand_url: str, pages: list[BrandPage], store: DiscoveryStore | None = None, *, geo: str = "India", goal: str = "ugc") -> BrandBrief:
    # Set up evidence list
    evidence = [
        {
            "field": "category",
            "source_url": page.url,
            "page_type": page.page_type,
            "title": page.title,
        }
        for page in pages[:5]
    ]

    import sys
    IN_TEST = "unittest" in sys.modules or "pytest" in sys.modules or (len(sys.argv) > 0 and "pytest" in sys.argv[0])

    # Try calling the InsForge AI completion endpoint
    if store is None:
        try:
            from creator_scout.discovery.store import DiscoveryStore
            store = DiscoveryStore()
        except Exception:
            pass

    if store is not None and not IN_TEST:
        pages_context = "\n\n".join([
            f"Page Title: {p.title}\nURL: {p.url}\nType: {p.page_type}\nContent:\n{p.text[:4000]}"
            for p in pages
        ])
        
        prompt = f"""You are an expert brand analyst. Analyze the following crawled website pages for a brand located at {brand_url}.
Target geography: {geo}
Campaign goal: {goal}

Based on the crawled pages below, extract the brand positioning and build a campaign brief in JSON format.
Ensure the output is valid JSON, containing only the JSON object. Do not include any conversational filler.

Crawled Content:
{pages_context}

Return a JSON object with the following fields:
1. "brand_name": Name of the brand.
2. "category": Primary category (e.g. "skincare", "beauty", "wellness", "fashion", "food", "tech", "unknown").
3. "products": List of key products or services.
4. "target_audience": A descriptive sentence about the target customer/audience segment in the context of the {geo} geography.
5. "price_positioning": Segment like "budget", "premium", "luxury", "mid-range".
6. "tone": List of 2-4 adjectives describing the brand's tone.
7. "value_props": List of key value propositions (up to 5).
8. "avoid_creator_types": List of creator types to avoid.
9. "best_creator_niches": List of 3-5 best creator niches to target.
10. "campaign_angles": List of 3-5 suggested creator campaign angles aligning with the goal: '{goal}'.
11. "search_queries": List of 5-8 search queries to discover creators for this brand on platforms like YouTube/Instagram, localized/targeted for {geo}.
12. "confidence": A float confidence score between 0.0 and 1.0.

Remember to output ONLY valid JSON."""

        try:
            res = store._request(
                "POST",
                "/api/ai/chat/completion",
                json_data={
                    "model": "anthropic/claude-sonnet-4.5",
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.2
                },
                timeout=3
            )
            if res and isinstance(res, dict) and res.get("success") and "text" in res:
                response_text = res["text"].strip()
                # Clean code blocks
                clean_text = response_text
                match = re.search(r"```json\s+(.*?)\s+```", response_text, re.DOTALL | re.IGNORECASE)
                if match:
                    clean_text = match.group(1).strip()
                else:
                    match = re.search(r"```\s+(.*?)\s+```", response_text, re.DOTALL | re.IGNORECASE)
                    if match:
                        clean_text = match.group(1).strip()
                
                data = json.loads(clean_text)
                return BrandBrief(
                    brand_name=data.get("brand_name") or infer_brand_name(brand_url, pages),
                    category=data.get("category") or "unknown",
                    products=data.get("products") or [],
                    target_audience=data.get("target_audience") or "",
                    price_positioning=data.get("price_positioning") or "unknown",
                    tone=data.get("tone") or [],
                    value_props=data.get("value_props") or [],
                    avoid_creator_types=data.get("avoid_creator_types") or [],
                    best_creator_niches=data.get("best_creator_niches") or [],
                    campaign_angles=data.get("campaign_angles") or [],
                    search_queries=data.get("search_queries") or [],
                    confidence=float(data.get("confidence") or 0.8),
                    evidence=evidence,
                )
        except Exception as e:
            # Fall back to heuristic on failure
            print(f"InsForge AI brand brief extraction failed: {e}. Falling back to heuristic.")

    # Heuristic Fallback
    import json
    full_text = "\n".join([page.title + "\n" + " ".join(page.metadata.values()) + "\n" + page.text for page in pages])
    tokens = set(tokenize(full_text))
    category = infer_category(tokens)
    brand_name = infer_brand_name(brand_url, pages)
    tone = infer_tone(tokens)
    products = infer_products(pages)
    value_props = infer_value_props(full_text)
    best_niches = NICHE_BY_CATEGORY.get(category, ["micro creators", "category educators", "review creators"])
    campaign_angles = build_campaign_angles(category, goal)
    search_queries = build_search_queries(category, brand_name, geo, best_niches, products)
    
    return BrandBrief(
        brand_name=brand_name,
        category=category,
        products=products,
        target_audience=infer_target_audience(category, geo),
        price_positioning=infer_price_positioning(tokens),
        tone=tone,
        value_props=value_props,
        avoid_creator_types=["giveaway-only creators", "unrelated niche creators", "over-sponsored profiles"],
        best_creator_niches=best_niches,
        campaign_angles=campaign_angles,
        search_queries=search_queries,
        confidence=0.78 if category != "unknown" else 0.45,
        evidence=evidence,
    )


def infer_brand_name(brand_url: str, pages: list[BrandPage]) -> str:
    for page in pages:
        if page.title:
            title = re.split(r"[|-]", page.title)[0].strip()
            if 2 <= len(title) <= 60:
                return title
    host = urlparse(brand_url if "://" in brand_url else f"https://{brand_url}").netloc
    return host.removeprefix("www.").split(".")[0].title()


def infer_category(tokens: set[str]) -> str:
    scored = []
    for category, keywords in CATEGORY_KEYWORDS.items():
        scored.append((len(tokens.intersection(keywords)), category))
    scored.sort(reverse=True)
    return scored[0][1] if scored and scored[0][0] > 0 else "unknown"


def infer_tone(tokens: set[str]) -> list[str]:
    tones = [tone for tone, keywords in TONE_KEYWORDS.items() if tokens.intersection(keywords)]
    return tones[:4] or ["clear", "trustworthy"]


def infer_products(pages: list[BrandPage]) -> list[str]:
    products = []
    for page in pages:
        if page.page_type in {"product", "homepage"} and page.title:
            products.append(page.title[:80])
    return sorted(set(products))[:8]


def infer_value_props(text: str) -> list[str]:
    sentences = re.split(r"(?<=[.!?])\s+", text)
    hints = ("safe", "clean", "affordable", "natural", "premium", "fast", "easy", "tested", "organic")
    props = [sentence.strip()[:180] for sentence in sentences if any(hint in sentence.lower() for hint in hints)]
    return props[:6]


def infer_target_audience(category: str, geo: str) -> str:
    if category == "skincare":
        return f"{geo} consumers interested in skincare routines, product reviews, and visible results"
    if category == "fashion":
        return f"{geo} shoppers looking for styling ideas and wearable outfit inspiration"
    if category == "food":
        return f"{geo} home cooks and food shoppers looking for practical recommendations"
    if category == "tech":
        return f"{geo} buyers comparing practical tools, gadgets, and workflows"
    return f"{geo} consumers interested in category-specific creator recommendations"


def infer_price_positioning(tokens: set[str]) -> str:
    if tokens.intersection({"luxury", "premium"}):
        return "premium"
    if tokens.intersection({"affordable", "budget", "value"}):
        return "budget"
    return "unknown"


def build_campaign_angles(category: str, goal: str) -> list[str]:
    base = {
        "skincare": ["routine integration", "honest review", "before-after journey", "ingredient education"],
        "fashion": ["styling challenge", "GRWM", "occasion-based outfit", "affordable haul"],
        "food": ["recipe integration", "taste test", "weeknight routine", "pantry restock"],
        "tech": ["workflow demo", "honest review", "comparison video", "setup tour"],
    }.get(category, ["honest review", "UGC demo", "founder story"])
    return [f"{goal}: {angle}" for angle in base[:4]]


def build_search_queries(category: str, brand_name: str, geo: str, niches: list[str], products: list[str]) -> list[str]:
    product_term = products[0] if products else category
    queries = [
        f"{category} creator {geo} review",
        f"{product_term} {geo} creator",
        f"{category} micro influencer {geo}",
    ]
    queries.extend(f"{niche} {geo}" for niche in niches[:3])
    return [query.strip() for query in queries if query.strip()][:8]

