"""
migrate_db.py — Seed sample creator data into InsForge Postgres.

Run from the project root:
    python creator_scout/discovery/migrate_db.py

Idempotent: uses merge-duplicates upserts.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from creator_scout.config import load_env
from creator_scout.discovery.models import (
    CreatorAccount,
    CreatorContact,
    CreatorProfile,
    PermissionBasis,
    Platform,
    SourceEvidence,
    utc_now,
)
from creator_scout.discovery.normalize import stable_id
from creator_scout.discovery.store import DiscoveryStore

load_env()

# ─── Sample Creators ────────────────────────────────────────────────────────────
SAMPLE_CREATORS: list[dict] = [
    {
        "display_name": "Sneha Sharma",
        "primary_niche": "skincare",
        "location": "Mumbai, India",
        "languages": ["english", "hindi"],
        "summary": "Skincare educator with a focus on affordable routines for Indian skin. Known for ingredient-breakdown reels and SPF reviews.",
        "topics": ["skincare", "acne", "moisturizer", "spf", "routine"],
        "accounts": [
            {"platform": "youtube", "handle": "snehaskincare", "profile_url": "https://youtube.com/@snehaskincare", "subscriber_count": 45000, "avg_views": 8000, "engagement_rate": 4.2, "bio": "Skincare simplified 🌿 | Dermat-backed tips"},
            {"platform": "instagram", "handle": "sneha.skincare", "profile_url": "https://instagram.com/sneha.skincare", "follower_count": 62000, "engagement_rate": 3.8, "bio": "Skincare nerd | DM for collabs"},
        ],
        "contacts": [
            {"contact_type": "email", "value": "sneha@skincreators.in", "source_url": "https://youtube.com/@snehaskincare/about", "permission_basis": "public_business_contact", "confidence": 0.9},
        ],
    },
    {
        "display_name": "Arjun Tech Reviews",
        "primary_niche": "tech",
        "location": "Bangalore, India",
        "languages": ["english"],
        "summary": "Consumer tech reviewer covering phones, laptops, and productivity gadgets. Clean minimal editing, honest reviews style.",
        "topics": ["tech", "gadget", "workflow", "app", "phone"],
        "accounts": [
            {"platform": "youtube", "handle": "arjuntechreviews", "profile_url": "https://youtube.com/@arjuntechreviews", "subscriber_count": 120000, "avg_views": 22000, "engagement_rate": 3.5, "bio": "Tech reviews you can trust 🔧"},
        ],
        "contacts": [
            {"contact_type": "email", "value": "arjun@techreviews.co", "source_url": "https://youtube.com/@arjuntechreviews/about", "permission_basis": "public_business_contact", "confidence": 0.85},
        ],
    },
    {
        "display_name": "Priya Kitchen Diaries",
        "primary_niche": "food",
        "location": "Delhi, India",
        "languages": ["english", "hindi"],
        "summary": "Home cook creating quick weeknight meals, traditional Indian recipes with a modern twist, and pantry restock videos.",
        "topics": ["food", "recipe", "meal", "kitchen", "cooking"],
        "accounts": [
            {"platform": "youtube", "handle": "priyakitchen", "profile_url": "https://youtube.com/@priyakitchen", "subscriber_count": 78000, "avg_views": 15000, "engagement_rate": 5.1, "bio": "Mom | Cook | Creator 🍳"},
            {"platform": "instagram", "handle": "priya.kitchen", "profile_url": "https://instagram.com/priya.kitchen", "follower_count": 38000, "engagement_rate": 4.8, "bio": "Recipes that actually work"},
        ],
        "contacts": [
            {"contact_type": "email", "value": "priya@kitchendiaries.in", "source_url": "https://youtube.com/@priyakitchen/about", "permission_basis": "public_business_contact", "confidence": 0.88},
        ],
    },
    {
        "display_name": "Riya Outfit Studio",
        "primary_niche": "fashion",
        "location": "Jaipur, India",
        "languages": ["english", "hindi"],
        "summary": "Affordable fashion creator sharing GRWM, thrift hauls, and styling challenges for college students.",
        "topics": ["fashion", "style", "outfit", "clothing", "wear"],
        "accounts": [
            {"platform": "instagram", "handle": "riya.outfitstudio", "profile_url": "https://instagram.com/riya.outfitstudio", "follower_count": 55000, "engagement_rate": 6.2, "bio": "Style without the splurge ✨"},
            {"platform": "tiktok", "handle": "riyaoutfits", "profile_url": "https://tiktok.com/@riyaoutfits", "follower_count": 32000, "engagement_rate": 7.1, "bio": "GRWM daily 🌸"},
        ],
        "contacts": [
            {"contact_type": "email", "value": "riya@outfitstudio.com", "source_url": "https://instagram.com/riya.outfitstudio", "permission_basis": "public_business_contact", "confidence": 0.82},
        ],
    },
    {
        "display_name": "Dr. Meera Glow",
        "primary_niche": "skincare",
        "location": "Chennai, India",
        "languages": ["english", "tamil"],
        "summary": "Dermatologist-turned-creator educating about science-backed skincare. Known for myth-busting and product reviews.",
        "topics": ["skincare", "dermatology", "science", "serum", "spf", "acne"],
        "accounts": [
            {"platform": "youtube", "handle": "drmeera", "profile_url": "https://youtube.com/@drmeera", "subscriber_count": 210000, "avg_views": 50000, "engagement_rate": 4.8, "bio": "Dermatologist | Skincare science made simple"},
            {"platform": "instagram", "handle": "dr.meera.glow", "profile_url": "https://instagram.com/dr.meera.glow", "follower_count": 180000, "engagement_rate": 5.2, "bio": "Evidence-based skincare 🔬"},
        ],
        "contacts": [
            {"contact_type": "email", "value": "meera@dermcreators.in", "source_url": "https://youtube.com/@drmeera/about", "permission_basis": "public_business_contact", "confidence": 0.95},
        ],
    },
    {
        "display_name": "Vikram Fitness Hub",
        "primary_niche": "wellness",
        "location": "Pune, India",
        "languages": ["english", "hindi", "marathi"],
        "summary": "Fitness coach sharing home workout routines, supplement reviews, and wellness transformation stories.",
        "topics": ["wellness", "fitness", "supplement", "health", "workout"],
        "accounts": [
            {"platform": "youtube", "handle": "vikramfitness", "profile_url": "https://youtube.com/@vikramfitness", "subscriber_count": 95000, "avg_views": 18000, "engagement_rate": 3.9, "bio": "Transform your body and mind 💪"},
        ],
        "contacts": [
            {"contact_type": "email", "value": "vikram@fitnesshub.co", "source_url": "https://youtube.com/@vikramfitness/about", "permission_basis": "public_business_contact", "confidence": 0.87},
        ],
    },
    {
        "display_name": "Aarav Dev Logs",
        "primary_niche": "tech",
        "location": "Hyderabad, India",
        "languages": ["english"],
        "summary": "Software developer creating workflow demos, setup tours, and app comparison videos for the Indian dev community.",
        "topics": ["tech", "software", "app", "workflow", "ai", "developer"],
        "accounts": [
            {"platform": "youtube", "handle": "aaravdevlogs", "profile_url": "https://youtube.com/@aaravdevlogs", "subscriber_count": 35000, "avg_views": 6000, "engagement_rate": 4.5, "bio": "Dev life | Tools | AI workflows"},
            {"platform": "tiktok", "handle": "aaravdev", "profile_url": "https://tiktok.com/@aaravdev", "follower_count": 15000, "engagement_rate": 5.8, "bio": "Coding tips in 60s ⚡"},
        ],
        "contacts": [
            {"contact_type": "email", "value": "aarav@devlogs.io", "source_url": "https://youtube.com/@aaravdevlogs/about", "permission_basis": "public_business_contact", "confidence": 0.80},
        ],
    },
    {
        "display_name": "Nisha Beauty Tales",
        "primary_niche": "beauty",
        "location": "Kolkata, India",
        "languages": ["english", "bengali"],
        "summary": "Beauty reviewer known for drugstore makeup dupes, honest GRWM videos, and festival-look tutorials.",
        "topics": ["beauty", "makeup", "cosmetic", "lipstick", "foundation", "haircare"],
        "accounts": [
            {"platform": "youtube", "handle": "nishabeautytales", "profile_url": "https://youtube.com/@nishabeautytales", "subscriber_count": 67000, "avg_views": 12000, "engagement_rate": 4.1, "bio": "Budget beauty that actually works 💄"},
            {"platform": "instagram", "handle": "nisha.beautytales", "profile_url": "https://instagram.com/nisha.beautytales", "follower_count": 48000, "engagement_rate": 4.5, "bio": "Honest beauty reviews ✨"},
        ],
        "contacts": [
            {"contact_type": "email", "value": "nisha@beautytales.in", "source_url": "https://youtube.com/@nishabeautytales/about", "permission_basis": "public_business_contact", "confidence": 0.88},
        ],
    },
    {
        "display_name": "Rahul Coffee & Code",
        "primary_niche": "tech",
        "location": "Noida, India",
        "languages": ["english", "hindi"],
        "summary": "Tech content creator blending productivity tips, coffee culture, and developer tool reviews.",
        "topics": ["tech", "coffee", "workflow", "app", "productivity"],
        "accounts": [
            {"platform": "youtube", "handle": "rahulcoffeecode", "profile_url": "https://youtube.com/@rahulcoffeecode", "subscriber_count": 22000, "avg_views": 4500, "engagement_rate": 5.0, "bio": "☕ + 💻 = content"},
        ],
        "contacts": [
            {"contact_type": "email", "value": "rahul@coffeecode.dev", "source_url": "https://youtube.com/@rahulcoffeecode/about", "permission_basis": "public_business_contact", "confidence": 0.78},
        ],
    },
    {
        "display_name": "Kavya Yoga Flow",
        "primary_niche": "wellness",
        "location": "Rishikesh, India",
        "languages": ["english", "hindi"],
        "summary": "Certified yoga instructor sharing morning flows, meditation guides, and wellness lifestyle content.",
        "topics": ["wellness", "yoga", "health", "routine", "meditation"],
        "accounts": [
            {"platform": "youtube", "handle": "kavyayogaflow", "profile_url": "https://youtube.com/@kavyayogaflow", "subscriber_count": 48000, "avg_views": 9000, "engagement_rate": 5.5, "bio": "Find your flow 🧘‍♀️"},
            {"platform": "instagram", "handle": "kavya.yogaflow", "profile_url": "https://instagram.com/kavya.yogaflow", "follower_count": 72000, "engagement_rate": 6.0, "bio": "Yoga | Wellness | Mindfulness"},
        ],
        "contacts": [
            {"contact_type": "email", "value": "kavya@yogaflow.in", "source_url": "https://youtube.com/@kavyayogaflow/about", "permission_basis": "public_business_contact", "confidence": 0.90},
        ],
    },
    {
        "display_name": "Siddharth Foodie Trails",
        "primary_niche": "food",
        "location": "Lucknow, India",
        "languages": ["english", "hindi"],
        "summary": "Street food explorer and recipe creator covering Awadhi cuisine, taste tests, and restaurant reviews across UP.",
        "topics": ["food", "recipe", "snack", "kitchen", "protein"],
        "accounts": [
            {"platform": "youtube", "handle": "siddharthfoodie", "profile_url": "https://youtube.com/@siddharthfoodie", "subscriber_count": 155000, "avg_views": 35000, "engagement_rate": 4.7, "bio": "From street to kitchen 🍛"},
        ],
        "contacts": [
            {"contact_type": "email", "value": "sid@foodietrails.in", "source_url": "https://youtube.com/@siddharthfoodie/about", "permission_basis": "public_business_contact", "confidence": 0.92},
        ],
    },
    {
        "display_name": "Anika Clean Living",
        "primary_niche": "skincare",
        "location": "Goa, India",
        "languages": ["english"],
        "summary": "Clean beauty advocate focusing on organic, cruelty-free skincare. Ingredient transparency and minimal routines.",
        "topics": ["skincare", "clean", "natural", "organic", "routine", "serum"],
        "accounts": [
            {"platform": "instagram", "handle": "anika.cleanliving", "profile_url": "https://instagram.com/anika.cleanliving", "follower_count": 28000, "engagement_rate": 7.2, "bio": "Clean beauty only 🌱"},
            {"platform": "youtube", "handle": "anikacleanliving", "profile_url": "https://youtube.com/@anikacleanliving", "subscriber_count": 18000, "avg_views": 3500, "engagement_rate": 4.8, "bio": "Simple, clean skincare"},
        ],
        "contacts": [
            {"contact_type": "email", "value": "anika@cleanliving.co", "source_url": "https://instagram.com/anika.cleanliving", "permission_basis": "public_business_contact", "confidence": 0.83},
        ],
    },
]


def build_creator_profile(data: dict) -> CreatorProfile:
    """Convert a sample dict to a CreatorProfile model."""
    creator_id = stable_id("creator", data["display_name"])
    now = utc_now()

    accounts = []
    for acc in data.get("accounts", []):
        accounts.append(
            CreatorAccount(
                platform=Platform(acc["platform"]),
                handle=acc["handle"],
                profile_url=acc["profile_url"],
                follower_count=acc.get("follower_count"),
                subscriber_count=acc.get("subscriber_count"),
                avg_views=acc.get("avg_views"),
                engagement_rate=acc.get("engagement_rate"),
                bio=acc.get("bio", ""),
                last_verified_at=now,
                raw={},
            )
        )

    contacts = []
    for ct in data.get("contacts", []):
        contacts.append(
            CreatorContact(
                contact_type=ct["contact_type"],
                value=ct["value"],
                source_url=ct["source_url"],
                permission_basis=PermissionBasis(ct["permission_basis"]),
                confidence=ct.get("confidence", 0.8),
                do_not_contact=False,
                last_verified_at=now,
            )
        )

    sources = []
    for acc in data.get("accounts", []):
        sources.append(
            SourceEvidence(
                source_url=acc["profile_url"],
                source_type="platform_profile",
                fields_found={"handle": acc["handle"], "platform": acc["platform"]},
                confidence=0.9,
                fetched_at=now,
            )
        )

    return CreatorProfile(
        creator_id=creator_id,
        display_name=data["display_name"],
        primary_niche=data["primary_niche"],
        location=data.get("location"),
        languages=data.get("languages", []),
        summary=data.get("summary", ""),
        topics=data.get("topics", []),
        accounts=accounts,
        contacts=contacts,
        sources=sources,
        updated_at=now,
        raw={},
    )


def main() -> None:
    print("╔══════════════════════════════════════════╗")
    print("║   Creator Scout — Data Migration Seed    ║")
    print("╚══════════════════════════════════════════╝")
    print()

    store = DiscoveryStore()
    print(f"✓ Connected to InsForge at {store.url}")
    print(f"  Seeding {len(SAMPLE_CREATORS)} sample creators...")
    print()

    for i, data in enumerate(SAMPLE_CREATORS, 1):
        creator = build_creator_profile(data)
        try:
            store.upsert_creator(creator)
            print(f"  [{i:2d}/{len(SAMPLE_CREATORS)}] ✓ {creator.display_name} ({creator.primary_niche})")
        except Exception as e:
            print(f"  [{i:2d}/{len(SAMPLE_CREATORS)}] ✗ {creator.display_name} — {e}")

    print()
    print("─" * 44)

    # Verify
    all_creators = store.all_creators()
    print(f"✓ Total creators in database: {len(all_creators)}")
    print()
    print("Done! Sample data is now available for campaigns.")


if __name__ == "__main__":
    main()
