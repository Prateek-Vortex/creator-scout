# Creator Scout AI - Production Technical Spec, API Research, and LangGraph Agent Design

Date: 2026-05-31
Status: Build handoff
Related doc: `creator-scout-product-prd.md`

## 1. Technical Thesis

Creator Scout should be built as its own production product from day one. The core stack should optimize for reliable brand crawling, compliant creator discovery, evidence-backed scoring, human approval, and resumable background workflows.

```text
Dodo Payments for subscriptions
AutoSend for lifecycle emails, contact automation, and later compliant outbound workflows
Kinde for auth/org management if we want quick B2B SaaS auth
Redis-based rate limiting
provider-neutral integration wrappers
env-driven config
webhook signature verification tests
LangGraph for production agent orchestration
```

For Creator Scout specifically, the technical center of gravity should be:

```text
brand crawling + creator data adapters + bounded AI agents + evidence-backed scoring + compliant outreach workflow + billing/onboarding automation
```

Use agents for judgment-heavy subtasks, not for uncontrolled scraping. The core system should remain deterministic, auditable, resumable, source-aware, and compliance-aware.

## 2. Core Tooling Decisions

### 2.1 Dodo Payments

Use Dodo Payments for paid SaaS subscriptions, especially if we want India-friendly/global payment coverage without immediately wiring Stripe.

Build a small first-party billing module around Dodo:

- Hosted checkout creation.
- Subscription webhook handling.
- Webhook signature verification.
- Plan metadata attached to checkout.
- Tests for checkout payload, signature verification, idempotency, and webhook plan activation.

Creator Scout Dodo flow:

```text
POST /billing/checkout
  -> DodoBillingProvider.create_checkout()
  -> POST https://test.dodopayments.com/checkouts or https://live.dodopayments.com/checkouts
  -> store checkout session id on org

POST /billing/webhook
  -> verify webhook-id/webhook-timestamp/webhook-signature
  -> process subscription.active / renewed / updated / cancelled / expired / failed
  -> update org.plan and dodo_subscription_id
```

Recommended Creator Scout plans:

```text
free: 1 brand scan, 5 creator previews, no export
starter: 3 campaigns/month, 150 creator profiles/month
growth: 15 campaigns/month, 1,000 creator profiles/month, exports, CRM
agency: multi-brand workspace, team seats, higher creator/data credits
```

Creator Scout billing entitlements should be usage-based, not just seats:

```text
brand_scans_per_month
creator_searches_per_month
creator_profile_unlocks
contact_unlocks
outreach_drafts
exports
active_campaigns
team_seats
```

Use Dodo metadata:

```json
{
  "org_id": "uuid",
  "org_slug": "glowskin",
  "plan": "growth",
  "provider": "dodo"
}
```

Official Dodo docs confirm programmatic payment/subscription APIs and webhook events such as `payment.succeeded` and `subscription.active`. Source: [Dodo docs](https://docs.dodopayments.com/), [Dodo webhooks](https://docs.dodopayments.com/developer-resources/webhooks)

### 2.2 AutoSend

Use AutoSend for product lifecycle emails and contact automation. It can also become the outbound email layer later, but only after suppression, unsubscribe, sender-domain, and consent/compliance rules are implemented.

AutoSend should be wrapped as a small `EmailAutomationProvider`:

```text
POST https://api.autosend.com/v1/contacts/email
POST https://api.autosend.com/v1/mails/send
GET  https://api.autosend.com/v1/contacts/{id}/unsubscribe-groups
```

Official AutoSend docs show `/v1/mails/send` accepts:

```text
to
from
subject
html/text or templateId
dynamicData
replyTo
unsubscribeGroupId
attachments
```

AutoSend also supports transactional email, marketing campaigns, contact-triggered automations, unsubscribe groups, and webhooks for contact/email events. Sources: [AutoSend docs](https://docs.autosend.com/), [AutoSend API reference](https://docs.autosend.com/api-reference), [AutoSend send email](https://docs.autosend.com/api-reference/mails/send), [AutoSend automations](https://docs.autosend.com/automations), [AutoSend unsubscribe groups](https://docs.autosend.com/api-reference/contacts/get-unsubscribe-groups), [AutoSend event types](https://docs.autosend.com/others/webhooks/event-type)

Recommended Creator Scout AutoSend uses:

```text
user.created -> welcome email
brand_scan.completed -> "your brand brief is ready"
creator_shortlist.ready -> "50 creators ready to review"
export.completed -> export ready email
billing.trial_ending -> upgrade prompt
campaign.followup_due -> internal reminder email to brand user
```

Use AutoSend contact automations for:

```text
signup onboarding
brand scan education sequence
trial activation nudges
creator shortlist education
export/download notifications
inactive campaign reminders
paid plan onboarding
failed payment / subscription status emails
```

Recommended AutoSend contact custom fields:

```json
{
  "signup_source": "app",
  "onboarding_stage": "brand_scan_completed",
  "plan": "starter",
  "campaign_count": 2,
  "last_campaign_goal": "ugc",
  "primary_category": "skincare"
}
```

For creator outreach, use this rule:

```text
P0: generate drafts only.
P1: Gmail OAuth from brand inbox.
P2: AutoSend sending only with unsubscribeGroupId, suppression list, verified sender domain, contact provenance, opt-out handling, bounce handling, and CAN-SPAM compliance.
```

### 2.3 Kinde Auth And Organizations

Kinde is useful if Creator Scout should become a B2B SaaS quickly:

- Login/signup.
- Organizations/workspaces.
- Org switcher.
- SSO/SAML later.
- Webhook sync for users/orgs.
- JWT org claims for tenant scoping.

Use if speed matters. If we want lower vendor dependency, Clerk/Auth.js/Supabase Auth are alternatives.

Recommended Creator Scout org model:

```text
organization = brand/company workspace
members = founder/growth marketer/agency teammate
roles = admin/member/viewer
brand profiles belong to organization
campaigns belong to brand profile
```

### 2.4 Redis Rate Limiting

Use Redis rate limits for both product entitlements and external provider protection.

Creator Scout rate limit buckets:

```text
rl:user:{user_id}
rl:org:{org_id}
rl:provider:youtube:{org_id}
rl:provider:firecrawl:{org_id}
rl:provider:tinyfish:{org_id}
rl:provider:modash:{org_id}
rl:email_sender:{domain}
```

Provider limits must be stricter than API limits:

```text
youtube: daily quota and request cost
modash: credit and request quotas
firecrawl: credits and concurrency
tinyfish: endpoint credits, browser/agent concurrency, run timeouts
openai/anthropic: TPM/RPM/cost
autosend/gmail: per-domain sending limits
shopify: API leaky bucket limits
```

### 2.5 Config And Env Pattern

Creator Scout should group env vars by provider and keep required/optional config explicit:

```text
APP_URL
FRONTEND_URL
DATABASE_URL
REDIS_URL

KINDE_*
DODO_PAYMENTS_*
AUTOSEND_*

FIRECRAWL_API_KEY
TINYFISH_API_KEY
TAVILY_API_KEY
EXA_API_KEY
YOUTUBE_API_KEY
OPENAI_API_KEY
ANTHROPIC_API_KEY
LANGSMITH_API_KEY
```

### 2.6 What Not To Build Now

Do not include in the first production build:

- Unofficial Instagram/TikTok/LinkedIn scrapers.
- Automated creator cold email sending before unsubscribe/suppression exists.
- Private phone/email scraping.
- Creator payments/contracts.
- A generic autonomous browsing agent that can visit any website without policy gates.

Build now:

- Dodo subscription billing.
- AutoSend lifecycle email wrapper and contact sync.
- Kinde org auth idea.
- Provider-neutral service interfaces.
- Webhook signature verification tests.
- Env/config discipline.
- Redis rate limiting.
- LangGraph campaign workflow.

## 3. Independent Service Layout

Recommended layout based on Creator Scout's own needs:

```text
creator-scout/
  apps/web/              # Next.js dashboard
  apps/api/              # API service
  apps/worker/           # crawl/data/LLM background jobs
  packages/shared/       # schemas, shared TS types
  packages/python-engine/# scoring, extraction, taxonomy, dedupe
  docs/
```

The service split is recommended because crawling, LLM calls, and provider APIs are slow, quota-bound, and retry-heavy.

## 4. Multi-Agent Architecture

### 4.1 Recommendation

Use LangGraph from the start for production workflow orchestration.

Do not let one autonomous agent freely browse and decide everything. Use deterministic graph state transitions, typed node outputs, checkpoints, retries, human approval gates, and event logs.

Why LangGraph:

- Explicit state graph for long-running campaigns.
- Checkpointing/resume for crawl and provider failures.
- Human-in-the-loop approval before outreach/export.
- Clear node-level retries and fallbacks.
- Easier production tracing with LangSmith or internal `agent_runs`.
- Better fit for multi-step workflows than a single prompt chain.

Recommended starting graph:

```text
campaign_start
  -> brand_crawl_router
  -> brand_intelligence
  -> strategy_profile
  -> discovery_query_planner
  -> source_adapter_fanout
  -> candidate_normalize_dedupe
  -> profile_analysis
  -> fit_scoring
  -> shortlist_generation
  -> human_review
  -> outreach_draft_generation
  -> export_or_crm_sync
```

### 4.2 Agent Roles

#### Campaign Orchestrator Agent

Purpose:

- Decides the job plan for a campaign.
- Splits work into brand scan, creator discovery, enrichment, scoring, outreach.
- Schedules crawler/API adapter nodes rather than embedding crawl logic inside the LLM.
- Records policy decisions, provider choices, retries, and human approval requirements.

Input:

```json
{
  "campaign_id": "uuid",
  "brand_url": "https://brand.com",
  "goal": "ugc|awareness|sales|affiliate|launch",
  "geo": "India",
  "platforms": ["instagram", "youtube"],
  "budget": "low|medium|high"
}
```

Output:

```json
{
  "jobs": [
    {"type": "brand_scan", "priority": 1},
    {"type": "creator_strategy", "priority": 2},
    {"type": "creator_discovery", "priority": 3},
    {"type": "creator_scoring", "priority": 4}
  ],
  "warnings": []
}
```

#### Crawl Planner Agent

Purpose:

- Chooses which brand pages to crawl.
- Reads sitemap, robots, links, page titles, and URL paths.
- Prioritizes product/category/about/reviews/FAQ/blog/social pages.

Output:

```json
{
  "crawl_plan": [
    {"url": "https://brand.com", "reason": "homepage"},
    {"url": "https://brand.com/products/acne-safe-moisturizer", "reason": "product page"}
  ],
  "max_pages": 20,
  "requires_browser": false,
  "blocked_paths": []
}
```

#### Brand Intelligence Agent

Purpose:

- Converts crawled pages into brand/product/customer intelligence.
- Returns evidence-backed fields.

Output:

```json
{
  "brand_name": "GlowSkin",
  "category": "skincare",
  "products": [],
  "target_customer": "urban women 22-35",
  "price_positioning": "mid-premium",
  "brand_tone": ["clean", "clinical", "trustworthy"],
  "value_props": [],
  "campaign_angles": [],
  "best_creator_niches": [],
  "avoid_creator_types": [],
  "evidence": [
    {"field": "category", "url": "...", "quote": "short snippet or paraphrase"}
  ],
  "unknowns": [],
  "confidence": 0.82
}
```

#### Creator Strategy Agent

Purpose:

- Builds the ideal creator profile from brand intelligence.
- Produces platform, location, niche, format, audience, and query strategy.

Output:

```json
{
  "platforms": ["instagram", "youtube"],
  "creator_niches": ["skincare educators", "acne journey creators"],
  "follower_range": {"min": 5000, "max": 100000},
  "languages": ["en", "hi"],
  "locations": ["India", "Mumbai", "Delhi", "Bangalore"],
  "content_formats": ["routine reel", "honest review", "before-after journey"],
  "search_queries": [
    "site:youtube.com acne prone skincare India moisturizer review",
    "acne safe moisturizer Indian skincare creator"
  ],
  "negative_signals": ["giveaway spam", "makeup-only", "luxury-only"]
}
```

#### Discovery Query Agent

Purpose:

- Creates and expands search queries for each source.
- Converts brand strategy into provider-specific filter parameters.

Output:

```json
{
  "youtube_queries": [],
  "web_queries": [],
  "modash_filters": {},
  "search_locations": [],
  "dedupe_keys": []
}
```

#### Source Adapter Agents

These should mostly be deterministic wrappers, not free-form LLM agents:

- YouTube Adapter
- Instagram Adapter
- TikTok Adapter
- Search Adapter
- First-party Creator Index Adapter
- Firecrawl/TinyFish/Tavily/Exa Adapter
- Snapchat Adapter
- Twitch Adapter
- X Adapter
- Pinterest Adapter
- Reddit Adapter
- Newsletter/Podcast/RSS Adapter
- Import CSV Adapter
- Shopify Adapter

Output normalized to a common `CreatorCandidate` schema.

#### Creator Profile Analysis Agent

Purpose:

- Summarizes creator bio, recent content, topics, tone, sponsor saturation, and risk.
- Uses raw metadata and available public content.

Output:

```json
{
  "topics": [],
  "tone": [],
  "content_quality": 0,
  "sponsor_saturation": "low|medium|high",
  "audience_assumptions": [],
  "brand_safety_flags": [],
  "evidence": [],
  "unknowns": [],
  "confidence": 0.0
}
```

#### Fit Scoring Agent

Purpose:

- Scores candidates against the brand and campaign.
- Must include score breakdown, evidence, unknowns, and risk.

Output:

```json
{
  "fit_score": 91,
  "breakdown": {
    "brand_relevance": 92,
    "audience_match": 85,
    "engagement_quality": 78,
    "content_quality": 90,
    "authenticity": 82,
    "sponsor_fit": 74,
    "affordability": 80,
    "reply_likelihood": 70
  },
  "bucket": "contact_first",
  "why": [],
  "risks": [],
  "unknowns": [],
  "recommended_pitch_angle": "..."
}
```

#### Contact Enrichment Agent

Purpose:

- Finds and verifies compliant public contact paths.
- Never guesses private/personal contacts in MVP.

Allowed output:

```json
{
  "contacts": [
    {
      "type": "email|website|manager|media_kit|dm_link",
      "value": "collab@example.com",
      "source_url": "https://...",
      "source_type": "creator_bio|website|media_kit|licensed_provider",
      "confidence": "high|medium|low",
      "last_verified_at": "iso"
    }
  ],
  "blocked": false,
  "blocked_reason": null
}
```

#### Outreach Agent

Purpose:

- Generates personalized outreach using brand brief plus creator evidence.
- Must include opt-out footer for email sends and disclosure reminders in campaign briefs.

Output:

```json
{
  "email_subjects": [],
  "email_body": "...",
  "dm_body": "...",
  "followups": [],
  "brief": {},
  "compliance_notes": []
}
```

#### Compliance Agent

Purpose:

- Reviews job outputs before contact storage, outreach, and export.
- Flags risky fields and unsafe sending behavior.

Examples:

```text
private phone number detected -> block
personal email inferred from pattern -> block
no contact source URL -> block
email send without unsubscribe -> block
TikTok Research API requested for commercial use -> block
LinkedIn scraping requested -> block
```

### 4.3 Multi-Agent State Graph

```text
CampaignCreated
  -> BrandCrawlPlanned
  -> BrandPagesFetched
  -> BrandBriefExtracted
  -> BrandBriefApproved
  -> CreatorStrategyGenerated
  -> DiscoveryQueriesGenerated
  -> CandidatesFetched
  -> CandidatesNormalized
  -> ProfilesAnalyzed
  -> ContactsEnriched
  -> FitScoresGenerated
  -> ComplianceReviewed
  -> ShortlistReady
  -> OutreachDrafted
  -> CRMTracking
```

Human-in-the-loop checkpoints:

```text
BrandBriefApproved
ShortlistReady
OutreachBeforeSend
```

## 5. API and Provider Research

### 5.1 Brand Website Crawling APIs

#### Option A: Custom Crawler

Use for:

- Low-cost MVP.
- Brand-owned websites.
- Static pages.
- Full control and compliance.

Stack:

```text
httpx or undici
robots.txt parser
sitemap parser
BeautifulSoup/readability/trafilatura
Playwright fallback
object storage for snapshots
```

Pros:

- Cheapest at scale.
- Full control over robots, rate limits, caching, and data retention.
- Easy to store raw evidence.

Cons:

- More engineering.
- Dynamic ecommerce sites can be messy.
- Need proxy/browser fallback eventually.

Required rules:

- Respect robots.txt. RFC 9309 defines robots.txt behavior and longest-match allow/disallow handling. Source: [RFC 9309](https://www.rfc-editor.org/rfc/rfc9309)
- Identify user agent.
- Limit pages per domain.
- Do not bypass logins/paywalls.
- Do not scrape private/customer data.

#### Option B: Firecrawl

Use for:

- Fastest MVP brand crawl.
- Clean markdown for LLM.
- Site map/crawl/search/extract in one API family.

Relevant capabilities:

- `/scrape`: markdown, summary, HTML, raw HTML, links, images, screenshots, JSON, branding.
- `/crawl`: crawl websites.
- `/map`: list URLs.
- `/search`: search web and get content.
- Browser actions, location, proxy modes, caching, zero data retention option.

Source: [Firecrawl v2 docs](https://docs.firecrawl.dev/api-reference/v2-introduction), [Firecrawl scrape docs](https://docs.firecrawl.dev/api-reference/v2-endpoint/scrape)

Pros:

- Very fast to implement.
- Outputs LLM-ready content.
- Handles JavaScript/proxies/cookie popups better than a basic crawler.
- Branding extraction can help UI/brand tone.

Cons:

- Credit cost.
- Vendor dependency.
- Still validate structured data yourself.

Recommendation:

```text
Use Firecrawl for beta and keep a custom crawler interface behind an adapter.
```

#### Option C: TinyFish

Use for:

- Search/fetch/browser extraction through one API key.
- Dynamic JavaScript pages where a normal HTML crawler returns thin content.
- Search result retrieval for agent pipelines.
- Browser automation for brand-owned or explicitly authorized workflows.
- Structured extraction from pages that require interaction, pagination, or modal dismissal.

Relevant capabilities:

- Search API: structured ranked web results.
- Fetch API: browser-rendered page content returned as clean markdown, JSON, or HTML.
- Browser API: remote browser sessions for direct Playwright/CDP control.
- Agent API: natural-language automation goals with `/run`, `/run-async`, and `/run-sse`.
- Agent runs accept `url`, `goal`, `browser_profile`, proxy config, and optional credential vault references.

TinyFish docs describe four API surfaces: Agent, Search, Fetch, and Browser. Canonical endpoints include `https://agent.tinyfish.ai/v1/automation/...`, `GET https://api.search.tinyfish.ai`, `POST https://api.fetch.tinyfish.ai`, and `POST https://api.browser.tinyfish.ai`. Sources: [TinyFish docs](https://docs.tinyfish.ai/), [TinyFish Agent API](https://docs.tinyfish.ai/agent-api/reference), [TinyFish AI integration](https://docs.tinyfish.ai/using-with-ai), [TinyFish homepage](https://www.tinyfish.ai/)

Important compliance rule:

```text
TinyFish is an extraction/browser infrastructure provider, not permission to collect restricted platform data.
Use it for brand sites, public web research, creator-owned sites/media kits, and authorized workflows.
Do not use it to scrape Instagram, TikTok, LinkedIn, private contacts, login-gated social data, or platform areas blocked by terms.
```

Recommendation:

```text
Add TinyFishCrawlerAdapter next to FirecrawlCrawlerAdapter.
Use Search/Fetch first because they are simpler and cheaper.
Use Browser/Agent only for dynamic pages that fail normal extraction or for authorized multi-step workflows.
Store TinyFish run_id, endpoint, goal, status, result hash, and source URL in provider_requests.
```

#### Option D: Tavily

Use for:

- Search + extract + crawl + map.
- Agent-oriented research workflows.
- Competitive and category research.

Relevant capabilities:

- `/search`
- `/extract`
- `/crawl`
- `/map`
- `/research`

Tavily Crawl supports starting from a URL, max depth, max breadth, total limit, query-guided prioritization, path/domain filters, image inclusion, and extraction depth. Source: [Tavily product](https://www.tavily.com/product), [Tavily Crawl help](https://help.tavily.com/articles/5815909991-what-is-tavily-crawl-api)

Recommendation:

```text
Use Tavily for research/search if you want one API for search + crawl.
Use Firecrawl for site content extraction if output quality is better in tests.
```

#### Option E: Exa

Use for:

- Neural/deep web search.
- Finding creators, blogs, newsletters, podcasts, and public profile pages.
- Pulling text content from search results.

Exa's search endpoint can search the web and extract contents from results. Source: [Exa search docs](https://docs.exa.ai/reference/search)

Recommendation:

```text
Use Exa as a discovery/search source, not necessarily the primary crawler.
```

#### Option F: Brave Search API

Use for:

- Independent web index.
- Lower-level search results.
- Backup search provider.

Source: [Brave Search API](https://brave.com/search/api/)

Recommendation:

```text
Good backup search provider. Pair with your own extractor or Firecrawl/Tavily.
```

#### Option G: SerpAPI

Use for:

- Google SERP results.
- Geo-specific queries.
- Local creator discovery.

SerpAPI offers Google Search API with location, language, and country parameters. Source: [SerpAPI](https://serpapi.com/)

Pros:

- Google SERP quality.
- Geo targeting.

Cons:

- Cost.
- Search results only; still need page extraction.

Recommendation:

```text
Use when search quality matters more than cost, especially for local/regional creator discovery.
```

#### Option H: Apify

Use for:

- Prebuilt actors.
- Rapid experiments.
- One-off sources with clear legal/terms comfort.

Apify Actors take structured JSON input and produce structured output, and can be run via API. Source: [Apify API docs](https://docs.apify.com/api), [Apify Actors docs](https://docs.apify.com/platform/actors)

Risk:

- Actor quality varies.
- Some actors scrape platforms where terms may be strict.
- Do not assume using Apify makes a data source compliant.

Recommendation:

```text
Use Apify for non-sensitive public web sources or proof-of-concepts. Avoid relying on unofficial social platform scrapers for core product.
```

#### Option I: Browserbase + Stagehand

Use for:

- Browser automation where no stable API exists.
- Brand-owned websites with dynamic pages.
- Logged-in flows only when the user explicitly connects/authorizes.

Stagehand offers `act`, `extract`, `observe`, and `agent` browser primitives. Source: [Browserbase Stagehand](https://www.browserbase.com/stagehand/)

Recommendation:

```text
Use as fallback browser extraction for brand websites and internal workflows, not for scraping Instagram/TikTok/LinkedIn at scale.
```

#### Option J: Zyte

Use for:

- Production-grade extraction at scale.
- Browser-rendered HTML, screenshots, geolocation, sessions, automatic extraction.

Zyte API supports browser automation and extraction from HTTP body or browser HTML. Source: [Zyte browser docs](https://docs.zyte.com/zyte-api/usage/browser.html), [Zyte API reference](https://docs.zyte.com/zyte-api/usage/reference.html)

Recommendation:

```text
Consider later if crawler reliability becomes a bottleneck.
```

### 5.2 Social and Creator Data APIs

#### YouTube Data API

Use for P0.

Relevant endpoints:

- `search.list` to discover channels/videos by keyword.
- `channels.list` for channel stats.
- `videos.list` for video stats and metadata.
- `commentThreads.list` for comment quality sampling.

Important limits:

- Default quota is 10,000 units/day.
- `search.list` costs 100 units per call.
- Many read calls cost 1 unit.

Sources: [YouTube Data API overview](https://developers.google.com/youtube/v3/getting-started), [YouTube search.list docs](https://developers.google.com/youtube/v3/docs/search/list), [YouTube quota docs](https://developers.google.com/youtube/v3/determine_quota_cost)

Recommendation:

```text
Use YouTube official API as the first reliable social data source.
Cache aggressively.
Use search.list sparingly because it is expensive.
```

#### Instagram / Meta Graph API

Include Instagram in the product, but do not build the product around headless Instagram scraping.

What official API can help with:

- For authenticated business/creator accounts, profile and owned insights.
- Business Discovery can retrieve basic metadata and metrics for other Instagram professional accounts through an authenticated Instagram professional account.
- Instagram creator marketplace helps brands discover creators, create campaigns, and message creators inside Meta's approved workflow.

What it does not solve:

- Broad creator discovery.
- Personal accounts.
- Private accounts.
- Follower lists.
- Large-scale competitor scraping.

Important constraint:

- Meta's automated data collection terms restrict automated collection without permission.
- Business Discovery is useful for known handles, validation, and enrichment; it is not a full influencer search API.

Sources: [Instagram Business Discovery](https://developers.facebook.com/docs/instagram-platform/instagram-api-with-facebook-login/business-discovery), [Instagram creator marketplace help](https://www.facebook.com/help/instagram/337707278243327/), [Meta Automated Data Collection Terms](https://www.facebook.com/legal/automated_data_collection_terms)

Recommendation:

```text
P0: include Instagram in campaign platform selection and creator schema.
P0: discover Instagram creators through our first-party index, public creator websites/media kits, search, CSV import, and user-provided handles.
P1: add Instagram Business Discovery for known professional handles when the brand connects a qualified IG business context.
Do not use headless Instagram scraping.
```

#### TikTok

Include TikTok, but avoid TikTok Research API for commercial creator discovery.

TikTok Research API access is for approved non-commercial researchers, and TikTok's FAQ says creators, advertisers, and commercial users are not eligible for Research Tools. Source: [TikTok Research API FAQ](https://developers.tiktok.com/doc/research-api-faq?enter_method=left_navigation), [TikTok Research API product page](https://developers.tiktok.com/products/research-api/)

Commercial paths to investigate:

- TikTok One / TikTok Creator Marketplace for approved brand and creator collaboration workflows.
- TikTok API for Business TTO endpoints, including authorized Creator Marketplace accounts, public insights, creator rankings/search labels, top creator rankings, creator discovery, campaigns, video linking requests, and campaign reporting.
- Our first-party creator index, creator opt-in, public web research, official TikTok One/API for Business access, and non-competitive enrichment providers where legally appropriate.
- User-imported handles and creator-owned websites/media kits.

Sources: [TikTok One support](https://support.tiktok.com/en/business-and-creator/tiktok-one/tiktok-one), [TikTok One API docs index](https://business-api.tiktok.com/gateway/docs/index?doc_id=1833997679342594&identify_key=c0138ffadd90a955c1f0670a56fe348d1d40680b3c89461e09f78ed26785164b&language=ENGLISH), [TikTok TTO creator discovery endpoint](https://business-api.tiktok.com/gateway/docs/index?doc_id=1825017307843585&identify_key=c0138ffadd90a955c1f0670a56fe348d1d40680b3c89461e09f78ed26785164b&language=ENGLISH)

Recommendation:

```text
P0: include TikTok in platform selection and schema.
P0: discover TikTok creators through our first-party index, CSV import, public web research, creator-owned sites/media kits, and user-provided handles.
P1/P2: apply for TikTok One / TikTok API for Business access if creator marketplace workflows become core.
Do not use TikTok Research API or headless TikTok scraping for commercial discovery.
```

#### Snapchat

Snapchat is worth tracking for fashion, beauty, lifestyle, entertainment, and youth-oriented campaigns.

Official path:

- Snapchat Public Profile API supports Creator Discovery and Content Management.
- Public endpoints can return a subset of public metadata and stats for Public Profiles.
- Creator OAuth can unlock authorized creator data sharing for partner platforms.

Sources: [Snap Public Profile API](https://developers.snap.com/api/marketing-api/Public-Profile-API/Introduction), [Snap Creator Discovery](https://developers.snap.com/api/marketing-api/Public-Profile-API/CreatorDiscovery), [Snap Public Profile API setup](https://developers.snap.com/api/marketing-api/Public-Profile-API/GetStarted)

Recommendation:

```text
Add as P2 platform if target customers ask for Snapchat.
Prioritize official Public Profile API / partner access, not scraping.
```

#### Twitch

Twitch matters for gaming, tech, live shopping, entertainment, music, and creator communities with strong trust.

Official path:

- Twitch Helix API can look up users, streams, videos, clips, channel metadata, and schedules with app/user access tokens.
- Good for public channel stats and content activity, less directly useful for audience demographics.

Source: [Twitch API reference](https://dev.twitch.tv/docs/api/reference), [Twitch videos docs](https://dev.twitch.tv/docs/api/videos)

Recommendation:

```text
Add Twitch as a P1/P2 adapter for gaming/tech categories.
Use official Helix endpoints and public channel URLs.
```

#### X / Twitter

X can matter for thought leaders, builders, crypto, finance, AI, B2B creators, and journalists.

Official path:

- X API v2 supports public conversation access, users, posts, timelines, search, Spaces, lists, and trends depending on plan/access.
- Pricing and access constraints can be material.

Source: [X API docs](https://docs.x.com/x-api/introduction)

Recommendation:

```text
Add later for B2B/thought-leader campaigns.
Do not make X a P0 dependency because pricing and API access can change product economics.
```

#### Pinterest

Pinterest is useful for home decor, food, fashion, beauty, travel, crafts, weddings, and visual shopping.

Official path:

- Pinterest API v5 supports user accounts, Pins, Boards, catalogs, ads, and analytics for authorized accounts/apps.
- Strong for owned/authorized creator or brand workflows; not a broad creator discovery API by itself.

Source: [Pinterest API docs](https://developers.pinterest.com/docs/new/welcome/), [Pinterest API call example](https://developers.pinterest.com/docs/getting-started/make-an-api-call/)

Recommendation:

```text
Add as P2 platform for visual commerce categories.
Use public web search plus licensed/authorized data; avoid unofficial Pinterest scraping as a core dependency.
```

#### Reddit

Reddit is better for community insight than creator outreach.

Official path:

- Reddit APIs can read/write Reddit content under Reddit's developer terms and policy constraints.
- Private user data is not exposed through Devvit.

Sources: [Reddit API overview](https://developers.reddit.com/docs/capabilities/server/reddit-api), [Reddit Data API wiki](https://support.reddithelp.com/hc/en-us/articles/16160319875092-Reddit-Data-API-Wiki)

Recommendation:

```text
Use Reddit for audience/category research and subreddit discovery, not influencer contact scraping.
Keep it out of P0 unless community intelligence becomes a differentiator.
```

#### LinkedIn

Do not scrape LinkedIn.

LinkedIn states that it does not permit third-party crawlers, bots, browser plug-ins, or extensions that scrape, modify, or automate activity on LinkedIn. Source: [LinkedIn prohibited software](https://www.linkedin.com/help/linkedin/answer/a1341387/prohibited-software-and-extensions%3Flang%3Den)

Recommendation:

```text
Keep LinkedIn out of P0 unless using approved APIs, user-provided exports, or creator opt-in.
```

#### Competitor Benchmark: Modash Discovery API

Do not use Modash as a provider. Treat it as the benchmark competitor for our own Creator Discovery API.

Modash docs and pricing pages show the market they are selling:

- Instagram, YouTube, and TikTok search.
- Profile reports.
- Audience analytics.
- Search by email.
- AI Search for creators by content.
- Collaboration endpoints for brand/creator partnership research.
- Discovery API pricing starts at $16,200/year for 3,000 credits/month on the public API pricing page.
- Raw API pricing starts at $10,000/year for 40,000 requests/month.
- Their app pricing is around $199/month annually or $299/month monthly for Essentials.

Sources: [Modash Discovery API docs](https://docs.modash.io/products/discovery_api/openapi_doc/discovery), [Modash API pricing](https://www.modash.io/fr/influencer-marketing-api/pricing), [Modash app pricing](https://www.modash.io/pricing)

What to learn from Modash:

```text
Developers want one stable API contract.
Search, profile reports, audience snapshots, collaboration history, and email lookup are separate billable units.
Credits are easier to understand than per-endpoint custom pricing.
Annual enterprise API contracts leave a large opening for cheaper self-serve monthly plans.
```

Creator Scout response:

```text
Build first-party Creator Discovery API as a product line.
Do not depend on Modash/HypeAuditor/CreatorIQ for core discovery.
Use public web crawling, official APIs, creator opt-in, customer imports, marketplace/partner routes, and our own evidence graph.
Price below Modash API while keeping positive gross margin through caching, async refresh, and strict credit costs.
```

Target first-party API endpoints:

```text
POST /v1/discovery/search
POST /v1/discovery/semantic-search
GET  /v1/creators/{creator_id}
POST /v1/creators/batch
GET  /v1/creators/{creator_id}/report
GET  /v1/creators/{creator_id}/audience
GET  /v1/creators/{creator_id}/collaborations
POST /v1/contact/lookup
POST /v1/discovery/lookalikes
POST /v1/discovery/refresh
GET  /v1/jobs/{job_id}
```

API pricing target:

```text
developer_free: 500 credits/month, rate limited, no bulk export
developer_starter: $99/month, 10,000 credits/month
developer_growth: $299/month, 50,000 credits/month
developer_scale: $799/month, 200,000 credits/month
enterprise: custom SLA, dedicated refresh jobs, higher concurrency

search_result: 0.01 credit
semantic_search_result: 0.02 credit
profile_report: 0.25 credit
audience_snapshot: 0.5 credit
collaboration_lookup: 0.1 credit
contact_lookup: 0.25 credit only on matched compliant business contact
refresh_job: charged by provider/crawl cost plus margin
```

Gross margin rule:

```text
Target 75%+ blended gross margin.
Serve hot cached profiles for low marginal cost.
Charge higher credits for fresh refresh, audience analysis, contact lookup, and LLM summaries.
Never let an API request trigger uncontrolled crawling without budget, timeout, and queue controls.
```

Performance target:

```text
cached search p95: < 500 ms
cached profile p95: < 300 ms
fresh profile refresh: async job, usually 30 sec - 5 min
bulk export: async job
exact-match handle lookup: deterministic first, semantic fallback second
all API responses include source timestamps, freshness, confidence, and unavailable fields instead of hallucinated values
```

#### Social Blade Business API

Use for:

- Creator profile stats.
- Historical performance.
- Top lists.
- YouTube/TikTok/Facebook/Instagram/Twitch support.

Social Blade docs describe profile/channel statistics and top list endpoints, credit-based usage, and supported platforms. Source: [Social Blade API docs](https://socialblade.com/developers/docs)

Recommendation:

```text
Useful for stats/history, less useful for deep audience fit. Consider as secondary enrichment.
```

#### HypeAuditor / CreatorIQ / Enterprise APIs

Use later.

HypeAuditor and CreatorIQ are strong but usually enterprise/mid-market. They can provide analytics, fraud detection, audience demographics, and campaign workflows. Sources: [HypeAuditor](https://hypeauditor.com/), [CreatorIQ API docs](https://apidocs.creatoriq.com/)

Recommendation:

```text
Do not start here unless you already have enterprise data budget or partnerships.
```

#### Platform Coverage Matrix

Prioritize platforms by product value and compliant access path:

| Platform | Best use case | P0/P1/P2 | Preferred access path | Do not do |
|---|---:|---:|---|---|
| YouTube | Long-form, Shorts, review creators, education | P0 | YouTube Data API + web search | Burn quota with broad `search.list` loops |
| Instagram | Beauty, fashion, food, DTC, lifestyle | P0 | First-party index, search, creator-owned sites, CSV/imported handles, Business Discovery for known professional accounts | Headless scraping, private data collection |
| TikTok | Viral UGC, short-form, Gen Z, TikTok Shop | P0 | First-party index, public web research, TikTok One/API for Business if approved, imported handles | TikTok Research API for commercial use, headless scraping |
| Blogs/newsletters | Niche authority, SEO, affiliate | P0 | Search + TinyFish/Firecrawl/Exa + RSS | Hidden email extraction |
| Podcasts | Authority, community, long-form trust | P1 | Listen Notes/Podcast Index/manual RSS later, public show notes now | Scrape private listener data |
| Twitch | Gaming, tech, live creators | P1/P2 | Twitch Helix API | Unofficial chat/user scraping at scale |
| X | B2B, AI, finance, crypto, founders | P2 | X API | Session scraping or bot automation |
| Pinterest | Visual commerce, home, fashion, food | P2 | Pinterest API + web search | Unofficial bulk scraping |
| Snapchat | Youth/lifestyle creators | P2 | Snap Public Profile API / partner access | Unapproved profile scraping |
| Reddit | Community insight | P2 | Reddit API under terms | Treat redditors as outreach contacts |
| LinkedIn | B2B creators | Later/blocked | Approved APIs or user-provided exports only | Scraping or profile automation |
| Shopify Collabs | Ecommerce affiliate creators | P1/P2 | Shopify Collabs/manual import/partner integrations | Assume Shopify exposes broad creator discovery API |

### 5.3 Contact Enrichment APIs

Contact data is sensitive. Treat it as compliance-critical.

Allowed MVP sources:

- Public business email in creator bio.
- Public creator website/media kit.
- Agency/manager contact published by creator.
- Creator-claimed contact details.
- Licensed provider with clear compliance terms.

Avoid:

- Personal email guessing.
- Private phone scraping.
- Hidden emails.
- LinkedIn scraping.
- Platform automation to reveal gated contact data.

#### Hunter

Useful APIs:

- Domain Search.
- Email Finder.
- Email Verifier.
- Email Enrichment.

Source: [Hunter API](https://hunter.io/api), [Hunter API reference](https://hunter.io/api-documentation)

Recommendation:

```text
Use Hunter only for public/professional business contact enrichment, mostly manager/agency/website domains.
Store source, confidence, and last verified date.
```

#### Apollo

Apollo has People Search and People Enrichment APIs. People API Search does not return email/phone by default; enrichment can reveal personal emails/phone with flags. Sources: [Apollo People Search](https://docs.apollo.io/reference/people-api-search), [Apollo People Enrichment](https://docs.apollo.io/reference/people-enrichment)

Recommendation:

```text
Not ideal for creator discovery MVP.
Avoid personal email/phone reveal options unless legal review and explicit use case.
```

#### ZeroBounce

Use for:

- Email deliverability validation before sending.

Source: [ZeroBounce validation API docs](https://www.zerobounce.net/docs/email-validation-api-quickstart/v2-validate-emails)

Recommendation:

```text
Use email validation before outbound sends. Do not treat validation as proof of consent.
```

### 5.4 Email and Outreach APIs

#### AutoSend

Use for:

- Product lifecycle email.
- Contact sync and segmentation.
- Contact-triggered onboarding/activation automations.
- Brand scan ready, shortlist ready, export ready, and billing lifecycle messages.
- Future compliant outbound once unsubscribe/suppression and sender policies are production-ready.

Why AutoSend is a good fit here:

- It combines transactional email, marketing campaigns, contacts, automations, webhooks, SMTP/API sending, and AI-agent-friendly docs/MCP.
- It can own lifecycle messaging while Creator Scout keeps the campaign/outreach approval logic in-app.
- Its `unsubscribeGroupId` and unsubscribe group APIs are useful for future creator outreach compliance.

Recommendation:

```text
Use AutoSend as the default product email and lifecycle automation provider.
Do not use AutoSend for automated creator cold outreach in P0.
In P1/P2, allow AutoSend-powered outreach only after sender verification, unsubscribe groups, suppression list, contact provenance, and rate limits exist.
```

#### Resend

Use for:

- Transactional email.
- Beta outbound if volume is low and compliant.
- Webhooks and logs.

Resend supports API sends, batch/scheduled emails, webhooks/logs, and idempotency keys. Source: [Resend Email API](https://resend.com/features/email-api)

Recommendation:

```text
Use Resend or Postmark only as fallback transactional providers if AutoSend does not meet deliverability or API needs.
For creator outreach, Gmail OAuth is often better because it sends from the brand's own inbox and maintains relationship context.
```

#### Gmail API

Use for:

- User-authorized brand inbox sending.
- Reply detection.
- Threading.

Gmail API supports `messages.send` and `drafts.send` with OAuth and MIME/base64url messages. Source: [Gmail sending docs](https://developers.google.com/gmail/api/guides/sending)

Recommendation:

```text
P1: Gmail OAuth for real outreach.
MVP: generate drafts/export first, then send after compliance and deliverability are implemented.
```

#### Postmark / SendGrid

Use for:

- Transactional email.
- Webhook-based events.

Source: [Postmark Email API](https://postmarkapp.com/developer/api/email-api), [SendGrid Mail Send API](https://sendgrid.kke.co.jp/docs/API_Reference/Web_API_v3/Mail/index.html)

Recommendation:

```text
Postmark is cleaner for transactional. SendGrid is broader but can be heavy.
```

### 5.5 Shopify and Ecommerce APIs

Shopify should be P1, not P0, unless the first niche is Shopify-only DTC.

Use cases:

- Pull brand products and prices.
- Generate creator-specific discount codes.
- Track orders by discount code or UTM.
- Import campaign revenue.
- Product gifting workflow.
- Future Shopify app listing.

Relevant APIs/features:

- Shopify Admin GraphQL Product API for product catalog.
- `discountCodeBasicCreate` mutation requires `write_discounts` scope and creates a discount code. Source: [Shopify discountCodeBasicCreate](https://shopify.dev/docs/api/admin-graphql/latest/mutations/discountcodebasiccreate)
- Webhook subscriptions for orders, discounts, products, app uninstall, etc. Source: [Shopify WebhookSubscription](https://shopify.dev/docs/api/admin-graphql/latest/objects/WebhookSubscription)
- Shopify Collabs lets merchants invite creators, share commission offers, send gifts/discount codes, track affiliate sales, and pay affiliates. Source: [Shopify Collabs help](https://help.shopify.com/en/manual/promoting-marketing/collabs)

Recommendation:

```text
P0: no Shopify dependency; manually enter product/campaign info.
P1: Shopify OAuth + product import + discount code generation + order attribution.
P2: Collabs import/export or direct workflow support if API access allows.
```

## 6. Recommended API Stack By Phase

### Phase 0 Concierge

Use:

```text
Firecrawl or TinyFish Fetch for brand pages
YouTube Data API
Search API: Exa or SerpAPI or Brave
Instagram/TikTok via first-party index seed, manual imports, public web research, and creator-owned sites
AutoSend for product lifecycle email
Dodo for subscription billing
LangGraph for campaign workflow orchestration
LLM: OpenAI/Anthropic
CSV/Google Sheets export
```

Do not send emails from product yet. Generate drafts.

### Phase 1 SaaS MVP

Use:

```text
Firecrawl for brand crawling
TinyFish Search/Fetch/Browser fallback for dynamic brand and creator-owned pages
Tavily/Exa for creator/web discovery
YouTube Data API for YouTube creators
First-party Creator Discovery API for Instagram/TikTok/YouTube/blog/newsletter creator search
Instagram Business Discovery for known professional handles if eligible
TikTok One / TikTok API for Business research and access application
Hunter only for public business contact verification/enrichment
ZeroBounce or equivalent for email validation
AutoSend for lifecycle emails and contact automation
Gmail OAuth optional for outreach drafts/sends
LangGraph checkpoints and human approval gates
OpenAI/Anthropic for structured extraction and scoring
```

### Phase 2 Workflow Product

Add:

```text
Gmail OAuth send/reply sync
AutoSend unsubscribe/suppression integration for compliant outbound
Shopify Admin API
Shopify webhooks
Discount code generation
Contact suppression/unsubscribe service
Public developer API keys and usage billing
Twitch adapter
Podcast/RSS adapter
CRM integrations: HubSpot/Pipedrive optional
```

### Phase 3 Data Moat

Add:

```text
Creator claim profile
Creator opt-in portal
First-party creator database
Public Discovery API product
Developer dashboard, API keys, docs, SDKs, webhooks
Campaign outcome learning
Lookalike creator graph
Competitor collaboration tracking
Regional language content analysis
Snapchat/Pinterest/X/Reddit adapters where customers demand them
```

## 7. Data Architecture

### 7.1 Core Entities

```text
organizations
users
brands
brand_sources
brand_pages
campaigns
campaign_jobs
agent_runs
provider_requests
creator_profiles
creator_accounts
creator_posts
creator_contacts
creator_evidence
creator_index_sources
creator_index_refreshes
developer_api_keys
api_credit_ledger
api_usage_events
campaign_creators
creator_scores
outreach_sequences
outreach_messages
crm_events
tasks
exports
suppression_entries
integration_accounts
shopify_orders
attribution_events
audit_logs
```

### 7.2 Evidence Graph

Long-term, use an evidence graph because Creator Scout needs traceable evidence from brand pages, creator posts, contacts, scores, outreach, and outcomes.

Nodes:

```text
brand
product
campaign
creator
creator_account
post
contact
topic
niche
audience_signal
brand_safety_signal
outreach_message
conversion_event
```

Edges:

```text
creator_has_account
creator_published_post
post_mentions_topic
creator_matches_campaign
contact_found_on_source
campaign_sent_message
message_received_reply
creator_generated_order
creator_similar_to_creator
creator_collaborated_with_brand
```

Store this first as relational tables plus JSONB evidence. Add graph queries later if needed.

### 7.3 Database Schema Sketch

```sql
create table campaign_jobs (
  id uuid primary key,
  org_id uuid not null,
  campaign_id uuid not null,
  job_type text not null,
  status text not null default 'queued',
  priority integer default 100,
  provider text,
  input jsonb,
  artifacts jsonb,
  errors jsonb,
  provider_usage jsonb,
  retry_count integer default 0,
  started_at timestamptz,
  finished_at timestamptz,
  created_at timestamptz default now()
);

create table agent_runs (
  id uuid primary key,
  org_id uuid not null,
  campaign_id uuid,
  job_id uuid,
  agent_name text not null,
  model_provider text,
  model_name text,
  prompt_version text,
  input_hash text,
  output_json jsonb,
  evidence jsonb,
  token_usage jsonb,
  cost_usd numeric,
  status text not null,
  error text,
  created_at timestamptz default now()
);

create table provider_requests (
  id uuid primary key,
  org_id uuid not null,
  campaign_id uuid,
  job_id uuid,
  provider text not null,
  endpoint text,
  request_hash text,
  response_status integer,
  response_summary jsonb,
  cost_units numeric,
  rate_limit_remaining integer,
  cached boolean default false,
  created_at timestamptz default now()
);

create table brand_pages (
  id uuid primary key,
  brand_id uuid not null,
  source_url text not null,
  canonical_url text,
  title text,
  page_type text,
  markdown text,
  extracted_json jsonb,
  content_hash text,
  fetched_at timestamptz,
  fetch_status text,
  robots_allowed boolean,
  created_at timestamptz default now()
);

create table creator_profiles (
  id uuid primary key,
  org_id uuid not null,
  display_name text not null,
  primary_niche text,
  location text,
  languages text[],
  summary text,
  raw_json jsonb,
  created_at timestamptz default now(),
  updated_at timestamptz default now()
);

create table creator_accounts (
  id uuid primary key,
  creator_id uuid not null,
  platform text not null,
  handle text,
  profile_url text not null,
  follower_count integer,
  subscriber_count integer,
  avg_views integer,
  engagement_rate numeric,
  provider text,
  provider_user_id text,
  raw_json jsonb,
  last_verified_at timestamptz,
  unique(platform, profile_url)
);

create table creator_contacts (
  id uuid primary key,
  creator_id uuid not null,
  contact_type text not null,
  value text not null,
  source_url text not null,
  source_type text not null,
  confidence text not null,
  verification_status text,
  do_not_contact boolean default false,
  last_verified_at timestamptz,
  created_at timestamptz default now()
);

create table creator_index_sources (
  id uuid primary key,
  creator_id uuid,
  account_id uuid,
  source_type text not null,
  source_url text not null,
  source_provider text,
  source_hash text,
  crawl_allowed boolean,
  fields_found jsonb,
  confidence numeric,
  fetched_at timestamptz,
  created_at timestamptz default now()
);

create table creator_index_refreshes (
  id uuid primary key,
  creator_id uuid,
  account_id uuid,
  requested_by_org_id uuid,
  requested_by_api_key_id uuid,
  refresh_reason text,
  status text not null default 'queued',
  provider_cost jsonb,
  credits_reserved numeric,
  credits_charged numeric,
  started_at timestamptz,
  finished_at timestamptz,
  created_at timestamptz default now()
);

create table developer_api_keys (
  id uuid primary key,
  org_id uuid not null,
  name text not null,
  key_hash text not null,
  scopes text[] not null,
  rate_limit_per_minute integer not null default 60,
  monthly_credit_limit numeric not null,
  revoked_at timestamptz,
  created_at timestamptz default now()
);

create table api_credit_ledger (
  id uuid primary key,
  org_id uuid not null,
  api_key_id uuid,
  event_type text not null,
  endpoint text,
  credits numeric not null,
  balance_after numeric,
  request_id text,
  created_at timestamptz default now()
);

create table api_usage_events (
  id uuid primary key,
  org_id uuid not null,
  api_key_id uuid,
  request_id text not null,
  endpoint text not null,
  status_code integer,
  latency_ms integer,
  cache_status text,
  credits_charged numeric,
  result_count integer,
  created_at timestamptz default now()
);

create table campaign_creators (
  id uuid primary key,
  campaign_id uuid not null,
  creator_id uuid not null,
  status text default 'shortlisted',
  bucket text,
  fit_score integer,
  score_breakdown jsonb,
  evidence jsonb,
  risks jsonb,
  unknowns jsonb,
  recommended_pitch text,
  created_at timestamptz default now()
);
```

### 7.4 Vector Storage

Use `pgvector` for:

- Brand page embeddings.
- Creator bio/content embeddings.
- Campaign strategy embeddings.
- Lookalike creator discovery.
- Evidence retrieval for scoring/outreach.

Embedding records:

```text
embedding_id
entity_type: brand_page|creator_post|creator_profile|campaign
entity_id
embedding vector
text_hash
model
created_at
```

## 8. Crawler Design

### 8.1 Brand Crawl Flow

```text
1. Normalize URL.
2. Fetch robots.txt.
3. Fetch sitemap.xml and sitemap index.
4. Fetch homepage.
5. Extract internal links.
6. Rank URLs by page type.
7. Fetch top N pages.
8. Use TinyFish/Playwright browser fallback for pages with poor extraction.
9. Extract markdown, metadata, JSON-LD, OpenGraph, product schema.
10. Store raw snapshot and normalized text.
11. Run Brand Intelligence Agent.
```

### 8.2 Page Type Classifier

Classify URLs into:

```text
homepage
product
collection
pricing
about
faq
reviews
blog
case_study
press
contact
social_link
legal
other
```

Prioritize:

```text
homepage: 1
product: 2
collection: 3
about: 4
reviews: 5
faq: 6
blog: 7
contact: 8
legal: skip unless compliance text needed
```

### 8.3 Extraction Fields

Brand page extraction should parse:

```text
title
description
h1/h2
product names
prices
currency
benefits
ingredients/materials/specs
target audience language
testimonials
social links
email/contact
shipping/geo hints
structured data
brand colors/assets if available
```

### 8.4 Crawler Guardrails

Hard limits:

```text
max_pages_per_brand_scan: 25 for MVP
max_page_bytes: 5 MB
max_crawl_duration: 120 seconds
max_browser_pages: 5
max_concurrent_fetches_per_domain: 2
cache_ttl: 7 days for brand pages
```

Never:

```text
bypass login
submit forms
add products to cart unless user-authorized test mode
scrape customer/private areas
ignore robots disallow
hammer failed domains
```

## 9. Discovery Pipeline

### 9.1 Candidate Discovery Sources

P0:

```text
YouTube Data API
Web search: Exa/Tavily/SerpAPI/Brave
TinyFish Search/Fetch for dynamic public web pages
Instagram via first-party index, creator-owned sites, search, or imported handles
TikTok via first-party index, creator-owned sites, search, or imported handles
Blogs/newsletters/RSS
User CSV import
Manual handles
First-party Creator Discovery API backed by our own index
```

P1:

```text
Instagram Business Discovery for known professional handles
TikTok One / TikTok API for Business if access is approved
Shopify customer/social integrations
Creator opt-in profiles
Twitch Helix API
Podcast source adapter
Snapchat Public Profile API if partner access exists
```

P2:

```text
X API for thought-leader campaigns
Pinterest API/web discovery for visual commerce
Reddit API for community intelligence
LinkedIn only through approved APIs or user-provided data
```

### 9.2 Candidate Normalization

Every provider returns different fields. Normalize to:

```json
{
  "source": "youtube|instagram|tiktok|modash|search|tinyfish|import|twitch|snapchat|x|pinterest|reddit|rss",
  "source_id": "string",
  "platform": "youtube",
  "display_name": "string",
  "handle": "string",
  "profile_url": "string",
  "bio": "string",
  "followers": 0,
  "avg_views": 0,
  "engagement_rate": null,
  "recent_posts": [],
  "location_signals": [],
  "language_signals": [],
  "contact_candidates": [],
  "raw": {}
}
```

### 9.3 Deduplication

Deduplicate by:

```text
normalized profile URL
platform + handle
website domain
email
Linktree/Beacons links
name + platform + location fuzzy match
cross-platform social links
```

Use a confidence score:

```text
1.0 exact platform URL
0.9 exact email or website claimed by profile
0.75 shared Linktree/Beacons
0.6 same name + same niche + same location
below 0.6 keep separate and mark possible_duplicate
```

## 10. Scoring Engine

### 10.1 Scoring Should Be Hybrid

Use deterministic metrics where possible and LLM judgment where needed.

Deterministic:

```text
follower range
avg views
posting frequency
engagement estimate
contact availability
location match
language match
sponsor saturation count
```

LLM-assisted:

```text
brand relevance
tone match
content quality
audience inference
comment quality summary
brand safety risk
outreach angle
```

### 10.2 Score Formula

```text
fit_score =
  0.25 * brand_relevance
  0.20 * audience_match
  0.15 * engagement_quality
  0.15 * content_quality
  0.10 * authenticity
  0.05 * sponsor_fit
  0.05 * affordability
  0.05 * reply_likelihood
```

Also store:

```text
confidence
unknowns
evidence
provider freshness
```

### 10.3 Quality Checks

Block or demote:

```text
missing profile URL
no evidence
high bot/comment-spam indicators
unsafe brand content
irrelevant niche
over-sponsored
no public contact and campaign requires email
data older than 90 days for volatile stats
```

## 11. Compliance Architecture

### 11.1 Contact Policy

Every contact must have:

```text
contact_type
value
source_url
source_type
confidence
last_verified_at
permission_basis
do_not_contact flag
```

Allowed `permission_basis`:

```text
public_business_contact
creator_claimed
licensed_provider
user_imported_with_attestation
existing_relationship
```

Blocked:

```text
personal_email_guessed
private_phone_scraped
linkedin_scraped
instagram_headless_scrape
tiktok_headless_scrape
hidden_source
unknown_source
```

### 11.2 Email Compliance

FTC CAN-SPAM guidance requires commercial email rules such as truthful header/subject information and a way to opt out. Source: [FTC CAN-SPAM guide](https://www.ftc.gov/business-guidance/resources/can-spam-act-compliance-guide-business?src_trk=em67fb78d29c0f11.425078391463537401)

Product requirements:

- Verified sender domain or Gmail OAuth.
- Unsubscribe/suppression system before bulk sending.
- Sender identity and business address fields.
- No deceptive subject templates.
- Bounce handling.
- Complaint handling.
- Rate limits per sender/domain.

### 11.3 Influencer Disclosure

FTC guidance says creators should disclose financial, employment, personal, family, free-product, or discount relationships when endorsing brands. Source: [FTC Disclosures 101](https://www.ftc.gov/business-guidance/resources/disclosures-101-social-media-influencers?c78861a6_page=2)

Product requirements:

- Disclosure reminders in every campaign brief.
- Geography-based disclosure notes.
- Required hashtags/phrases configurable by brand.
- Store disclosure checklist accepted by user.

### 11.4 Platform Terms Boundaries

Hard blocks:

```text
LinkedIn scraping/automation
TikTok Research API for commercial use
private Instagram/TikTok data collection
TinyFish/Browserbase/Playwright use against restricted social pages
browser automation to reveal gated contact data
phone scraping
```

## 12. API Endpoints For Creator Scout

### Campaigns

```text
POST /api/v1/campaigns
GET  /api/v1/campaigns
GET  /api/v1/campaigns/{id}
PATCH /api/v1/campaigns/{id}
POST /api/v1/campaigns/{id}/start
POST /api/v1/campaigns/{id}/retry
```

### Brand Scan

```text
POST /api/v1/campaigns/{id}/brand-scan
GET  /api/v1/campaigns/{id}/brand-brief
PATCH /api/v1/campaigns/{id}/brand-brief
```

### Creator Discovery

```text
POST /api/v1/campaigns/{id}/discover
GET  /api/v1/campaigns/{id}/creators
POST /api/v1/campaigns/{id}/creators/import
POST /api/v1/campaigns/{id}/creators/{creator_id}/score
PATCH /api/v1/campaign-creators/{id}/status
```

### Public Developer Discovery API

This is a product surface, not just internal infrastructure. It should be versioned, documented, metered, and priced separately from the SaaS dashboard.

```text
POST /v1/discovery/search
POST /v1/discovery/semantic-search
POST /v1/discovery/lookalikes
GET  /v1/creators/{creator_id}
POST /v1/creators/batch
GET  /v1/creators/{creator_id}/report
GET  /v1/creators/{creator_id}/audience
GET  /v1/creators/{creator_id}/collaborations
POST /v1/contact/lookup
POST /v1/discovery/refresh
GET  /v1/jobs/{job_id}
GET  /v1/usage
```

Response contract:

```json
{
  "data": [],
  "meta": {
    "request_id": "req_...",
    "credits_used": 0.25,
    "freshness": "cached|fresh|stale",
    "sources": [],
    "confidence": 0.86,
    "missing_fields": [],
    "next_page": null
  }
}
```

API design rules:

```text
Exact handle/profile URL lookup before semantic search.
Every field must have source, timestamp, and confidence internally.
Unknown values return null with missing_fields, never invented estimates.
Fresh refreshes are async jobs, not blocking API requests.
Credits are reserved before expensive jobs and released/adjusted on failure.
```

### Outreach

```text
POST /api/v1/campaigns/{id}/outreach/draft
POST /api/v1/campaigns/{id}/outreach/send
GET  /api/v1/campaigns/{id}/outreach/messages
POST /api/v1/outreach/webhooks/resend
POST /api/v1/outreach/webhooks/gmail
```

### Integrations

```text
GET  /api/v1/integrations
POST /api/v1/integrations/shopify/connect
POST /api/v1/integrations/gmail/connect
POST /api/v1/integrations/firecrawl/test
POST /api/v1/integrations/tinyfish/test
```

### Events

```text
GET /api/v1/campaigns/{id}/events
GET /api/v1/jobs/{id}/events
```

## 13. Job Status Model

Use explicit terminal and non-terminal states so long-running crawl, enrichment, and scoring work is easy to debug and retry.

```text
queued
running
passed
partial
failed
blocked
unsupported
rate_limited
cancelled
```

When to use:

```text
passed: job completed fully
partial: job produced some useful output with warnings
failed: unexpected failure
blocked: missing key, compliance block, user approval needed
unsupported: source/platform not supported
rate_limited: provider quota exceeded, retry after known
cancelled: user/system cancelled
```

## 14. Observability and Cost Control

Track:

```text
provider
endpoint
request count
credit units
tokens
cost_usd
latency
cache hit rate
429/rate-limit events
failure rate
result count
accepted result count
```

Add dashboards:

```text
cost per campaign
cost per accepted creator
cost per contact unlocked
LLM hallucination/error rate
provider reliability
creator recommendation acceptance rate
```

## 15. Environment Variables

```text
DATABASE_URL=
REDIS_URL=
APP_URL=
FRONTEND_URL=

OPENAI_API_KEY=
ANTHROPIC_API_KEY=
DEFAULT_LLM_PROVIDER=openai
DEFAULT_EXTRACTION_MODEL=
DEFAULT_SCORING_MODEL=
LANGSMITH_API_KEY=

FIRECRAWL_API_KEY=
TINYFISH_API_KEY=
TAVILY_API_KEY=
EXA_API_KEY=
BRAVE_SEARCH_API_KEY=
SERPAPI_API_KEY=

YOUTUBE_API_KEY=
SOCIALBLADE_CLIENT_ID=
SOCIALBLADE_TOKEN=
TWITCH_CLIENT_ID=
TWITCH_CLIENT_SECRET=
X_API_KEY=
PINTEREST_CLIENT_ID=
PINTEREST_CLIENT_SECRET=
SNAP_CLIENT_ID=
SNAP_CLIENT_SECRET=

HUNTER_API_KEY=
ZEROBOUNCE_API_KEY=

AUTOSEND_API_KEY=
DODO_PAYMENTS_API_KEY=
DODO_PAYMENTS_WEBHOOK_SECRET=
KINDE_CLIENT_ID=
KINDE_CLIENT_SECRET=
KINDE_ISSUER_URL=

RESEND_API_KEY=
POSTMARK_SERVER_TOKEN=
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=

SHOPIFY_CLIENT_ID=
SHOPIFY_CLIENT_SECRET=
SHOPIFY_WEBHOOK_SECRET=

RUNNER_TOKEN=
```

## 16. MVP Build Plan

### Week 1: Foundation

- Monorepo structure.
- API service.
- Postgres schema.
- Redis queue.
- Runner service.
- Job status/events.
- LLM provider adapter.
- LangGraph campaign state graph with checkpointing.
- Dodo billing skeleton.
- AutoSend contact/email skeleton.
- Internal creator index schema and ingestion jobs.
- Developer API key + usage meter skeleton.
- Basic web dashboard.

### Week 2: Brand Scan

- URL normalization.
- Firecrawl/TinyFish/custom crawler adapter.
- Robots/sitemap handling.
- Brand page storage.
- Brand Intelligence Agent.
- Editable brand brief UI.

### Week 3: Creator Discovery

- YouTube adapter.
- Instagram adapter through first-party index, public web, official eligible APIs, or imported handles.
- TikTok adapter through first-party index, public web, official eligible APIs, or imported handles.
- Search adapter.
- Blogs/newsletters/RSS source adapter.
- Public Discovery API search endpoint.
- API credit ledger and rate limits.
- CSV import.
- Candidate normalization.
- Deduplication.
- Creator list UI.

### Week 4: Scoring

- Creator Profile Analysis Agent.
- Fit Scoring Agent.
- Evidence-first score breakdown.
- Buckets and filters.
- Creator drawer UI.

### Week 5: Contacts and Outreach

- Contact enrichment policy.
- Public contact extraction.
- Hunter/ZeroBounce optional.
- Outreach draft generation.
- Campaign brief generation.
- AutoSend lifecycle emails for shortlist/export/follow-up reminders.
- CSV export.

### Week 6: CRM Lite and Hardening

- CRM board.
- Task/follow-up statuses.
- Audit logs.
- Rate limits.
- Provider cost dashboard.
- Compliance blocks.
- Seed/demo campaigns.

## 17. Concrete Codex/Claude Build Prompt

```text
Build Creator Scout AI as a production B2B SaaS for AI-powered creator discovery and outreach planning. Use Dodo Payments for subscriptions, AutoSend for lifecycle email/contact automation, Kinde or equivalent for org auth, Redis for rate limits/queues, and LangGraph for the campaign agent workflow.

Services:
- apps/web: Next.js TypeScript dashboard
- apps/api: backend with Postgres, Redis, billing, auth, integrations, campaigns
- apps/worker: background workers for crawling, discovery, enrichment, and LLM jobs
- packages/shared: shared schemas/types
- packages/python-engine: scoring, extraction, taxonomy, dedupe

MVP capabilities:
1. Create campaign from brand URL, goal, geography, platforms, budget.
2. Enqueue brand_scan job.
3. Crawl brand site using Firecrawl/TinyFish if configured, otherwise use a simple robots-aware crawler.
4. Extract brand brief with structured LLM output and evidence.
5. Let user edit/approve brand brief.
6. Generate ideal creator profile and search queries.
7. Discover creators via YouTube Data API, first-party Instagram/TikTok creator index, web search, blogs/newsletters/RSS, creator-owned sites, and CSV import.
8. Normalize creators into common schema.
9. Score creators using hybrid deterministic + LLM score with evidence, risks, unknowns, confidence.
10. Show ranked shortlist table and creator drawer.
11. Extract/store only public business contact paths with source URL and confidence.
12. Generate personalized email/DM draft and campaign brief.
13. Export CSV.
14. Add Dodo Payments subscription plans and entitlement checks.
15. Add AutoSend lifecycle emails for user onboarding, brand scan ready, shortlist ready, and trial/upgrade flows.

Technical requirements:
- Keep provider integrations behind interfaces: billing, email, crawler, search, creator-data, contact-enrichment, LLM.
- Add Dodo billing provider with hosted checkout, subscription webhook verification, org plan updates, and tests.
- Add AutoSend client with contact upsert, template send, dynamicData, replyTo, unsubscribeGroupId support, and graceful no-op when disabled.
- Add Kinde or equivalent auth/org model if speed matters for B2B SaaS onboarding.
- Add LangGraph nodes for brand crawl, brand intelligence, strategy, discovery, dedupe, scoring, human review, and outreach draft generation.
- Add first-party Discovery API endpoints, API keys, credit ledger, usage reporting, and fast cached search/profile responses.
- All LLM calls must produce strict JSON and create agent_runs rows with prompt_version, model, usage, cost, output_json.
- Add provider_requests rows for every external API request.
- Add Redis rate limits for app users and external provider usage.
- Add compliance guard that blocks private phone scraping, LinkedIn scraping, TikTok Research API commercial usage, and guessed emails.

Do not implement:
- Instagram/TikTok scraping.
- LinkedIn scraping.
- Email sending before unsubscribe/suppression logic exists.
- Creator payments/contracts. SaaS subscription billing via Dodo is in scope.

Deliver:
- Working local docker-compose with Postgres + Redis.
- Seed demo campaign.
- README with setup and env vars.
- Tests for crawler URL ranking, creator dedupe, scoring formula, and compliance guard.
```

## 18. Final Technical Recommendation

The fastest credible product path is:

```text
Dodo for billing, AutoSend for lifecycle email/contact automation, Kinde for org auth if useful, and Redis for rate limits/queues.
LangGraph as the production campaign workflow from day one.
Firecrawl/TinyFish/Tavily/Exa for brand and public web research.
YouTube official API for first reliable social source.
First-party Creator Discovery API/index for Instagram/TikTok/YouTube/blog/newsletter discovery.
Bounded LLM nodes only for extraction, strategy, scoring, and outreach drafts.
Use Postgres/JSONB/pgvector for evidence, not a black-box agent memory.
Do not scrape LinkedIn, private contacts, or TikTok Research API for commercial use.
```

The technical moat should be:

```text
brand intelligence + first-party creator index + public Discovery API + evidence graph + source adapters + scoring feedback loop + campaign outcome learning
```

Not:

```text
one fragile scraper or one giant prompt
```

## 19. Source Links

- [RFC 9309 robots.txt standard](https://www.rfc-editor.org/rfc/rfc9309)
- [Dodo Payments docs](https://docs.dodopayments.com/)
- [Dodo Payments webhooks](https://docs.dodopayments.com/developer-resources/webhooks)
- [AutoSend API reference](https://docs.autosend.com/api-reference)
- [AutoSend send email API](https://docs.autosend.com/api-reference/mails/send)
- [AutoSend automations](https://docs.autosend.com/automations)
- [AutoSend unsubscribe groups](https://docs.autosend.com/api-reference/contacts/get-unsubscribe-groups)
- [AutoSend webhook event types](https://docs.autosend.com/others/webhooks/event-type)
- [Firecrawl API v2 introduction](https://docs.firecrawl.dev/api-reference/v2-introduction)
- [Firecrawl scrape endpoint](https://docs.firecrawl.dev/api-reference/v2-endpoint/scrape)
- [TinyFish docs](https://docs.tinyfish.ai/)
- [TinyFish Agent API](https://docs.tinyfish.ai/agent-api/reference)
- [TinyFish AI integration](https://docs.tinyfish.ai/using-with-ai)
- [Tavily product](https://www.tavily.com/product)
- [Tavily Crawl API help](https://help.tavily.com/articles/5815909991-what-is-tavily-crawl-api)
- [Exa search docs](https://docs.exa.ai/reference/search)
- [Brave Search API](https://brave.com/search/api/)
- [SerpAPI](https://serpapi.com/)
- [Apify API docs](https://docs.apify.com/api)
- [Apify Actors docs](https://docs.apify.com/platform/actors)
- [Browserbase Stagehand](https://www.browserbase.com/stagehand/)
- [Zyte browser automation](https://docs.zyte.com/zyte-api/usage/browser.html)
- [Zyte API reference](https://docs.zyte.com/zyte-api/usage/reference.html)
- [YouTube Data API overview](https://developers.google.com/youtube/v3/getting-started)
- [YouTube search.list docs](https://developers.google.com/youtube/v3/docs/search/list)
- [YouTube quota docs](https://developers.google.com/youtube/v3/determine_quota_cost)
- [Instagram Business Discovery](https://developers.facebook.com/docs/instagram-platform/instagram-api-with-facebook-login/business-discovery)
- [Instagram creator marketplace](https://www.facebook.com/help/instagram/337707278243327/)
- [Meta Automated Data Collection Terms](https://www.facebook.com/legal/automated_data_collection_terms)
- [TikTok Research API FAQ](https://developers.tiktok.com/doc/research-api-faq?enter_method=left_navigation)
- [TikTok Research API product page](https://developers.tiktok.com/products/research-api/)
- [TikTok One support](https://support.tiktok.com/en/business-and-creator/tiktok-one/tiktok-one)
- [TikTok One API docs index](https://business-api.tiktok.com/gateway/docs/index?doc_id=1833997679342594&identify_key=c0138ffadd90a955c1f0670a56fe348d1d40680b3c89461e09f78ed26785164b&language=ENGLISH)
- [TikTok TTO creator discovery endpoint](https://business-api.tiktok.com/gateway/docs/index?doc_id=1825017307843585&identify_key=c0138ffadd90a955c1f0670a56fe348d1d40680b3c89461e09f78ed26785164b&language=ENGLISH)
- [Snap Public Profile API](https://developers.snap.com/api/marketing-api/Public-Profile-API/Introduction)
- [Snap Creator Discovery](https://developers.snap.com/api/marketing-api/Public-Profile-API/CreatorDiscovery)
- [Twitch API reference](https://dev.twitch.tv/docs/api/reference)
- [Twitch videos docs](https://dev.twitch.tv/docs/api/videos)
- [X API docs](https://docs.x.com/x-api/introduction)
- [Pinterest API docs](https://developers.pinterest.com/docs/new/welcome/)
- [Pinterest API call example](https://developers.pinterest.com/docs/getting-started/make-an-api-call/)
- [Reddit API overview](https://developers.reddit.com/docs/capabilities/server/reddit-api)
- [Reddit Data API wiki](https://support.reddithelp.com/hc/en-us/articles/16160319875092-Reddit-Data-API-Wiki)
- [LinkedIn prohibited software](https://www.linkedin.com/help/linkedin/answer/a1341387/prohibited-software-and-extensions%3Flang%3Den)
- [Modash Discovery API docs](https://docs.modash.io/products/discovery_api/openapi_doc/discovery)
- [Modash API pricing](https://www.modash.io/fr/influencer-marketing-api/pricing)
- [Modash app pricing](https://www.modash.io/pricing)
- [Social Blade API docs](https://socialblade.com/developers/docs)
- [HypeAuditor](https://hypeauditor.com/)
- [CreatorIQ API docs](https://apidocs.creatoriq.com/)
- [Hunter API](https://hunter.io/api)
- [Hunter API reference](https://hunter.io/api-documentation)
- [Apollo People Search](https://docs.apollo.io/reference/people-api-search)
- [Apollo People Enrichment](https://docs.apollo.io/reference/people-enrichment)
- [ZeroBounce validation API](https://www.zerobounce.net/docs/email-validation-api-quickstart/v2-validate-emails)
- [Resend Email API](https://resend.com/features/email-api)
- [Gmail sending docs](https://developers.google.com/gmail/api/guides/sending)
- [Postmark Email API](https://postmarkapp.com/developer/api/email-api)
- [Shopify discountCodeBasicCreate](https://shopify.dev/docs/api/admin-graphql/latest/mutations/discountcodebasiccreate)
- [Shopify WebhookSubscription](https://shopify.dev/docs/api/admin-graphql/latest/objects/WebhookSubscription)
- [Shopify Collabs help](https://help.shopify.com/en/manual/promoting-marketing/collabs)
- [LangGraph Graph API docs](https://docs.langchain.com/oss/python/langgraph/graph-api)
