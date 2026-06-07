# AI Creator Scout - Product, UX, Market, Technical Research, and PRD

Date: 2026-05-31
Status: Strategy and build handoff
Working product name: Creator Scout AI

## 1. Executive Summary

Creator Scout AI turns a brand website into an actionable creator marketing campaign.

The core flow should be:

```text
Brand URL -> brand intelligence -> ideal creator profile -> creator discovery -> fit scoring -> public contact enrichment -> personalized outreach -> campaign tracking
```

The product should not be positioned as "find influencers from a URL." That is too easy to copy and too close to existing databases. The stronger positioning is:

```text
AI creator scout for DTC and SMB brands: understand the brand, find right-fit creators, explain every match, enrich compliant public contact paths, draft personalized outreach, and track campaign execution.
```

Recommended wedge:

```text
Initial market: DTC beauty, skincare, wellness, fashion, and food brands
Initial geography: India-first or US-first, but do not launch both at full depth on day one
Initial platforms: Instagram + YouTube
Initial buyer: founder-led DTC brands and small growth teams who cannot afford enterprise influencer platforms
```

Why this wedge:

- DTC brands already understand creator marketing but often manage it through spreadsheets, DMs, agencies, and manual research.
- Micro and nano creators are becoming a larger budget category, creating a need for high-volume but high-quality vetting.
- Existing platforms are either expensive, database-heavy, enterprise-heavy, or workflow-heavy without deep brand understanding.
- The biggest unsolved product gap is not "more creator data"; it is "which creators should this exact brand contact, why, with what offer, and how do we run it without chaos?"

## 2. Source Conversation Summary

The shared ChatGPT conversation defined a strong product flow:

1. User enters a brand website URL.
2. System crawls website pages such as homepage, products, about, reviews, FAQs, pricing, blog, and social links.
3. System extracts brand category, target customer, value proposition, pricing, tone, audience, and key selling points.
4. System creates a brand/content brief.
5. System defines an ideal creator profile.
6. System discovers creators across social platforms and public web sources.
7. System scores creators by brand relevance, audience fit, engagement quality, authenticity, content quality, sponsor fit, affordability, reply likelihood, and brand safety.
8. System segments results into practical buckets such as contact first, backup, gifting, UGC, authority, local, and avoid.
9. System enriches public contact details, avoiding private/personal data scraping.
10. System drafts personalized outreach and campaign briefs.
11. System tracks creator outreach and campaign status in a lightweight CRM.

The most important insight: creator matching should start from brand understanding, not keyword search.

## 3. Market Research

### 3.1 Market Direction

Creator marketing is moving from experimental campaigns to a core paid media and commerce channel.

Key signals:

- IAB's 2025 Creator Economy Ad Spend & Strategy Report says U.S. creator ad spend was projected to reach USD 37B in 2025, up 26% year over year, with creator advertising growing far faster than the overall media industry. IAB also notes that identifying the right creators is a top challenge and that many brands are using or planning to use AI for creator marketing tasks. Source: [IAB](https://www.iab.com/insights/2025-creator-economy-ad-spend-strategy-report/)
- EMARKETER expects micro and nano influencers to claim 45.5% of influencer marketing spending in 2026. This supports a product focused on high-volume evaluation of smaller creators. Source: [EMARKETER](https://www.emarketer.com/chart/c/361073/micro-nano-influencers-will-claim-almost-half-of-influencer-marketing-budgets-2026-361073)
- India's creator/influencer market is formalizing. Economic Times, citing Kofluence's 2026 report, says India's influencer marketing sector was valued around INR 3,000-3,500 crore in 2025 and projected to reach INR 4,500-5,000 crore by 2027. It also notes Instagram dominance, regional creator growth, e-commerce and FMCG spend, AI adoption, and compliance pressure. Source: [Economic Times](https://m.economictimes.com/industry/services/advertising/indias-influencer-marketing-industry-to-reach-rs-5000-crore-by-2027-as-creator-economy-formalises-kofluence-report/amp_articleshow/131085735.cms)

### 3.2 Buyer Pain Points

For small and mid-size brands:

- They do not know what kind of creator actually fits their brand.
- They over-index on follower count because it is visible.
- They spend hours manually searching Instagram, YouTube, TikTok, Google, Reddit, and competitor pages.
- They struggle to detect fake engagement, low-quality comments, over-sponsored creators, and audience mismatch.
- They cannot reliably find public business emails or manager contacts.
- Their outreach sounds generic and gets low response rates.
- Their campaign briefs are inconsistent.
- They manage relationships across spreadsheets, Notion, WhatsApp, Gmail, Instagram DMs, and Shopify.
- They cannot clearly attribute campaign value to sales, content assets, or learning.

For agencies:

- They need faster research and shortlist generation.
- They need clear "why this creator" explanations for client approval.
- They need exports, reporting, and repeatable workflows.

For creators:

- They hate irrelevant, mass-produced brand outreach.
- They need clear briefs, payment/gifting expectations, content rights terms, and disclosure requirements.

### 3.3 Market Gap

Most tools are database-first:

```text
Search filters -> creator list -> metrics -> outreach
```

Creator Scout should be brand-intelligence-first:

```text
Website understanding -> campaign strategy -> creator hypothesis -> evidence-backed shortlist -> outreach plan
```

The gap is especially strong for:

- Founder-led Shopify brands with limited budgets.
- Brands trying micro/nano creator programs.
- Teams that want campaign output, not just data.
- India and other regional markets where language, city, audience trust, and local context matter.

## 4. Competitive Analysis

### 4.1 Competitor Table

| Competitor | Positioning | Strengths | Weakness / Gap To Exploit | What To Learn |
|---|---|---|---|---|
| Modash | All-in-one influencer marketing platform and Discovery API competitor | Large creator database, discovery, CRM, outreach, tracking, payments. Help docs mention 350M+ profiles and end-to-end workflow. API pricing starts around USD 16,200/year for Discovery API and USD 10,000/year for Raw API. Sources: [Modash help](https://help.modash.io/en/articles/13714522-what-is-modash-and-how-does-it-work), [Modash API pricing](https://www.modash.io/fr/influencer-marketing-api/pricing) | API is annual-contract-heavy and expensive for developers/SMBs. Product is still search/filter-led. We should not use them as a provider because discovery is our moat. | Build our own first-party Discovery API with lower pricing, faster cached responses, exact handle lookup, evidence, freshness, and developer-first docs. |
| HypeAuditor | Analytics and fraud detection heavyweight | Deep creator analytics, fraud detection, audience demographics, market analysis, competitor benchmarking. Claims 227M+ accounts and 35+ vetting metrics. Source: [HypeAuditor](https://hypeauditor.com/) | Can feel analyst-heavy and budget-heavy. Less suited for a tiny team that wants a fast campaign plan. | Build a trust layer: authenticity, brand safety, sponsor saturation, and evidence-backed scoring. |
| Aspire | Marketplace plus relationship management for brands | Inbound creator marketplace, outbound discovery, Shopify integration, ROI workflows. Source: [Aspire platform](https://www.aspire.io/platform-overview) | More mid-market/enterprise and campaign-program oriented. | Combine inbound applications with outbound search later. Let creators claim profiles. |
| GRIN | Creator management command center for ecommerce brands | Discovery, social listening, content management, relationship management, reporting, payments. Source: [GRIN](https://grin.co/product/) | Enterprise-style platform. Not optimized for scrappy first campaigns. | Long-term moat is relationship management plus commerce attribution. |
| SARAL | Influencer OS for consumer/DTC brands | Seeding, outreach, CRM, affiliate tracking, UGC rights, performance insights. Source: [SARAL](https://www.getsaral.com/) | Strong workflow focus, less obvious as a brand-understanding and AI-matching product. | Keep the workflow simple and DTC-native. Product seeding and affiliate tracking matter. |
| Favikon | AI creator discovery across B2B and B2C platforms | AI search, creator profiles, 10M+ creators across major platforms, 30M+ post search, email/DM outreach. Source: [Favikon](https://www.favikon.com/) | Lower-cost competitor; broad across many categories, less campaign-specific from brand URL. | AI search and content search are important. Cross-platform creator identity matters. |
| Shopify Collabs | Native Shopify affiliate and creator management | Recruit creators, direct invites, open access offers, gifts, discount codes, affiliate sales, payments. Source: [Shopify Help](https://help.shopify.com/en/manual/promoting-marketing/collabs/merchants) | Useful for affiliate operations but not a deep discovery/vetting/research engine. | Native commerce integrations reduce friction. |
| Upfluence / CreatorIQ / Captiv8 / Traackr | Enterprise influencer platforms | Mature workflows, reporting, enterprise integrations, brand safety, campaign management | Expensive, complex, sales-led, not founder-friendly | Avoid enterprise bloat in MVP. Win with speed, explainability, and pricing. |

### 4.2 Competitive Lessons

Implement:

- AI-assisted natural language creator search.
- First-party creator index and public Discovery API.
- Creator fit explanations with evidence.
- Audience/engagement quality checks.
- Public contact enrichment with confidence and source.
- CRM-style status tracking.
- Automated follow-up sequences.
- Shopify attribution and affiliate code support.
- Campaign brief generation.
- Export to CSV/Sheets.

Avoid:

- Building a giant generic database as the only moat.
- Depending on Modash or similar competitor APIs for core discovery.
- Hiding behind vanity metrics like followers and likes.
- Sending unsafe mass outreach without opt-out and deliverability controls.
- Depending on unauthorized scraping from platforms where terms are strict.
- Trying every niche and platform before one wedge works.

### 4.3 Differentiation Strategy

Primary wedge:

```text
The first creator marketing tool that understands your website before it searches creators.
```

Secondary differentiators:

- Brand-fit score is explainable and editable.
- Every recommendation has evidence: posts, bio signals, comment signals, audience assumptions, risks, and confidence.
- Shortlist is organized into action buckets, not a flat table.
- Outreach is personalized from creator-specific content and brand-specific campaign angle.
- Built for first 50 creators, not enterprise teams managing 5,000 creators.
- Compliance-first public contact policy.
- Developer-facing Discovery API priced below Modash, with cached low-latency search and exact response contracts.

## 5. Product Requirements Document

### 5.1 Vision

Help any DTC or SMB brand launch a creator marketing campaign in under one hour, starting from only a website URL.

### 5.2 Problem Statement

Brands do not lack creator data. They lack confidence and workflow:

- Who exactly should we contact?
- Why are they a fit?
- What should we offer them?
- What should we say?
- How do we avoid fake/low-fit creators?
- How do we track outreach and results?

### 5.3 Target Users

Primary user:

```text
DTC founder or growth marketer
Team size: 1-10
Budget: low to mid
Current workflow: spreadsheet + manual Instagram/YouTube search + DMs/email
Goal: find 30-100 right-fit creators and run a campaign without hiring an agency
```

Secondary user:

```text
Small influencer marketing agency
Team size: 2-20
Goal: create shortlists and outreach plans faster for multiple clients
```

Developer user:

```text
AI app builder, agency engineer, growth tooling team, or data team
Goal: access creator search, profile, contact, collaboration, and scoring signals through a self-serve API without enterprise minimums
```

Future user:

```text
Creator manager at mid-market ecommerce brand
Goal: manage always-on creator seeding, affiliate, and UGC rights workflows
```

### 5.4 Jobs To Be Done

- "When I launch a product, I want to find creators who match my audience and brand tone so I do not waste money on poor-fit partnerships."
- "When I see a creator recommendation, I want to understand why they are a fit so I can trust the shortlist."
- "When I contact creators, I want messages that reference their actual content so my outreach does not feel spammy."
- "When creators respond, I want one place to track status, offer, notes, deliverables, links, and payment/gifting."
- "When my boss/client asks why we selected these creators, I want a clear report."

### 5.5 Success Metrics

North star:

```text
Qualified creator conversations started per brand per month
```

Activation metrics:

- Brand scan completed.
- Brand brief accepted or edited.
- Campaign goal selected.
- At least 25 creators saved to shortlist.
- At least 10 outreach drafts generated.
- At least 1 outreach sequence sent or exported.

Quality metrics:

- User accepts at least 60% of top 20 creator recommendations.
- At least 70% of recommendations include 3+ evidence points.
- Contact confidence high/medium for at least 50% of shortlisted creators.
- Bounce rate below 5% when sending through product.
- Spam complaint rate below 0.1%.

Business metrics:

- Free scan to signup conversion.
- Signup to paid campaign conversion.
- Paid retention after first campaign.
- Cost per generated shortlist.
- Gross margin after data/API/LLM costs.

### 5.6 MVP Scope

MVP should do these eight things very well:

1. Accept a brand website URL.
2. Crawl and summarize the brand into an editable brand intelligence brief.
3. Generate an ideal creator profile.
4. Discover 30-50 candidate creators from one or two platforms.
5. Score creators and explain why each is a fit.
6. Show public business contact info if available, with source and confidence.
7. Generate personalized email/DM outreach and a campaign brief.
8. Export CSV and/or push to a simple CRM board.

### 5.7 MVP Non-Goals

Do not build these in the first product version:

- Full marketplace where creators apply.
- Creator payments.
- Contract e-signing.
- Advanced attribution modeling.
- All platforms and all geographies.
- Private phone/email scraping.
- Automated Instagram/LinkedIn DM sending through unauthorized automation.
- Large-scale scraping of Meta, TikTok, or LinkedIn without permission, official access, or creator opt-in.

### 5.8 P0 Features

#### Brand URL Scan

Inputs:

- Brand website URL
- Optional product URL
- Target geography
- Campaign goal: awareness, UGC, sales, affiliate, launch, local event, product seeding
- Budget range
- Preferred platforms

Crawler pages:

- Homepage
- Product pages
- About page
- Reviews/testimonials
- FAQ
- Blog/resources
- Pricing or product collections
- Social links
- Sitemap and structured data where available

Output:

```json
{
  "brand_name": "string",
  "category": "string",
  "products": ["string"],
  "target_audience": "string",
  "price_positioning": "budget | mid | premium | luxury | unknown",
  "tone": ["clean", "clinical", "playful"],
  "value_props": ["string"],
  "avoid_creator_types": ["string"],
  "best_creator_niches": ["string"],
  "campaign_angles": ["string"],
  "confidence": 0.0
}
```

#### Ideal Creator Profile Generator

Output:

- Platform recommendation.
- Follower/subscriber range.
- Creator niches.
- Target geographies/languages.
- Audience assumptions.
- Content formats.
- Brand safety constraints.
- Suggested offer type: paid, gifting, affiliate, hybrid.
- Search queries to discover creators.

#### Creator Discovery

MVP discovery methods:

- YouTube Data API for channels/videos, because official access is clearer.
- Search engine results for public creator pages, media kits, blogs, podcasts, Linktree/Beacons pages, and public websites.
- User-provided imports via CSV/social handles.
- Licensed social data provider if budget allows.
- Optional Meta/Instagram official pathways where applicable, but do not depend on unauthorized scraping.

Creator profile fields:

```text
name
platforms
profile URLs
bio
niche
location/language signals
followers/subscribers
average views
engagement estimate
recent content topics
posting frequency
sponsor saturation
past relevant brand mentions
comment quality summary
brand safety notes
public contact methods
contact source URL
contact confidence
estimated collaboration cost range
last verified date
```

#### Fit Scoring

Initial weighted model:

```text
brand relevance: 25%
audience match: 20%
content quality: 15%
engagement quality: 15%
authenticity / fraud risk: 10%
sponsor fit / saturation: 5%
affordability: 5%
reply likelihood: 5%
```

Score output:

```json
{
  "fit_score": 87,
  "score_breakdown": {
    "brand_relevance": 92,
    "audience_match": 83,
    "engagement_quality": 78,
    "content_quality": 90,
    "authenticity": 82,
    "sponsor_fit": 75,
    "affordability": 80,
    "reply_likelihood": 72
  },
  "brand_safety": "low | medium | high",
  "confidence": "low | medium | high",
  "evidence": [
    "Creator posts weekly about acne-prone skincare",
    "Comments include real product questions",
    "Recent content tone is educational and non-gimmicky"
  ],
  "recommended_pitch_angle": "Acne-safe moisturizer for humid Indian weather"
}
```

#### Segmented Shortlists

Default buckets:

- Contact first
- Good backup
- Budget/gifting
- UGC creators
- Authority/educators
- Local/regional creators
- High reach
- Risky/high upside
- Avoid

#### Outreach Drafting

Generate:

- Personalized opening based on creator content.
- Why the brand fits their audience.
- Campaign angle.
- Offer type.
- CTA.
- Follow-up sequence.
- FTC/ASCI disclosure reminder based on geography.

Output examples:

- Email subject options.
- Email body.
- Instagram DM version.
- Follow-up 1 after 3 days.
- Follow-up 2 after 7 days.
- "No response" close.

#### CRM Lite

Statuses:

```text
Shortlisted
Contact ready
Contacted
Opened
Replied
Negotiating
Accepted
Product sent
Content pending
Content live
Paid
Rejected
No response
Do not contact
```

Data captured:

- Creator
- Campaign
- Contact method
- Outreach text
- Last contact date
- Next follow-up date
- Owner
- Notes
- Offer
- Deliverables
- UTM/promo code
- Status history

#### Export

CSV/Google Sheets export:

- Creator details
- Score breakdown
- Evidence
- Contact details
- Outreach draft
- CRM status
- Source URLs

### 5.9 P1 Features

- Gmail/Google Workspace integration.
- Reply detection.
- Follow-up scheduling.
- Shopify integration for product gifting, discount codes, affiliate links, and revenue tracking.
- UGC content collection.
- Disclosure checker for live posts.
- Creator claim/update profile.
- Competitor creator discovery: "show creators who posted about competitors."
- Lookalike discovery from saved creators.
- Team collaboration and comments.

### 5.10 P2 Features

- Creator marketplace / inbound applications.
- Payments and tax workflows.
- Contract templates and content rights.
- Multi-brand agency workspace.
- Advanced reporting.
- Creator relationship health score.
- AI campaign agent that recommends next action.
- Regional language discovery and translation.

## 6. UI/UX Specification

### 6.1 Product Principles

- Show the campaign workspace, not a marketing landing page, after login.
- Make AI output editable. Users must be able to correct brand assumptions.
- Explain every creator recommendation.
- Keep data dense and scannable.
- Use evidence and confidence labels everywhere.
- Make compliance visible but not scary.
- Avoid a giant empty dashboard. First screen should ask for a brand URL.

### 6.2 Information Architecture

```text
Dashboard
  New Campaign
  Campaigns
  Creators
  Inbox
  Tasks
  Reports
  Settings

Campaign Workspace
  Brand Brief
  Creator Strategy
  Discover
  Shortlist
  Outreach
  CRM
  Report
```

### 6.3 Primary Flow

#### Screen 1: New Campaign

Fields:

- Website URL
- Campaign goal
- Target country/city
- Product/category
- Budget range
- Platform preference

CTA:

```text
Analyze Brand
```

Progress steps:

```text
Crawling website -> extracting brand signals -> building creator profile -> generating discovery plan
```

#### Screen 2: Brand Intelligence Review

Layout:

```text
Left: extracted brand brief
Right: evidence from website pages
Bottom: editable campaign angles and creator niches
```

Cards:

- Brand category
- Target customer
- Price positioning
- Tone
- Best campaign angles
- Suggested creator niches
- Avoid list
- Confidence warnings

User action:

- Accept brief
- Edit brief
- Re-run analysis

#### Screen 3: Creator Strategy

Controls:

- Platform segmented control: Instagram, YouTube, TikTok, LinkedIn
- Follower range slider
- Country/city/language
- Creator niche chips
- Content format chips
- Offer type: paid, gifting, affiliate, hybrid
- Budget per creator
- Safety strictness

CTA:

```text
Find Creators
```

#### Screen 4: Ranked Creator Results

Views:

- Table view
- Card view
- Bucket view

Table columns:

```text
Fit score
Creator
Platform
Niche
Audience/geography signal
Followers/views
Engagement quality
Contact confidence
Estimated cost
Risk
Why this creator
Actions
```

Actions:

- Save to shortlist
- Reject
- Compare
- Generate outreach
- Open profile

Filters:

- Score
- Platform
- Niche
- Location
- Contact available
- Brand safety
- Sponsor saturation
- Budget

#### Screen 5: Creator Profile Drawer

Sections:

- Summary
- Score breakdown
- Evidence
- Recent content
- Audience assumptions
- Contact info
- Risk notes
- Suggested pitch
- Past collaborations
- Add note

Important UX detail:

The "why" explanation must be above raw metrics. That is the trust builder.

#### Screen 6: Outreach Composer

Panel layout:

```text
Left: creator context
Center: generated email/DM
Right: campaign brief and offer
```

Controls:

- Tone: warm, concise, premium, founder-led, agency
- Offer type
- Personalization depth
- Follow-up cadence
- Include disclosure reminder
- Add unsubscribe footer for email

#### Screen 7: CRM Board

Kanban columns:

```text
Shortlisted | Contacted | Replied | Negotiating | Accepted | Product Sent | Content Pending | Live | Done
```

Card data:

- Creator name
- Platform
- Score
- Last action
- Next follow-up
- Owner
- Offer
- Alert badges

#### Screen 8: Campaign Report

Sections:

- Pipeline summary
- Outreach performance
- Accepted creators
- Content live
- Sales/traffic if Shopify connected
- Top creators by quality
- Learnings for next campaign
- Export/share

### 6.4 ASCII Wireframe

```text
+--------------------------------------------------------------+
| Creator Scout AI                                  New Campaign|
+------------------+-------------------------------------------+
| Campaigns        | Brand: GlowSkin                           |
| Creators         | Goal: Product seeding + paid reels         |
| Inbox            |                                           |
| Tasks            | [Brand Brief] [Strategy] [Discover]       |
| Reports          | [Shortlist] [Outreach] [CRM] [Report]    |
+------------------+-------------------------------------------+
| Fit | Creator        | Why fit                | Contact | CTA  |
| 92  | Ananya Skin    | Acne-safe routines...  | High    | Save |
| 88  | Derm Talk      | Educational content... | Medium  | Save |
| 81  | Beauty Daily   | Strong views, risky... | Low     | View |
+--------------------------------------------------------------+
| Profile Drawer: Ananya Skin                                  |
| Score breakdown | Evidence | Suggested pitch | Draft outreach |
+--------------------------------------------------------------+
```

## 7. Technical Research and Architecture

### 7.1 Recommended Stack

Frontend:

- Next.js / React
- TypeScript
- Tailwind or existing design system
- TanStack Query
- shadcn/ui or Radix primitives

Backend:

- Node.js/TypeScript API routes or NestJS/Fastify
- Postgres
- pgvector for embeddings
- Redis + BullMQ for background jobs
- Object storage for crawled snapshots and exports

AI:

- LLM provider abstraction so the app can use OpenAI, Anthropic, or other models.
- Structured outputs with JSON schemas.
- Embeddings for brand and creator content similarity.
- Evaluation prompts for scoring consistency.

Integrations:

- Website crawler: Playwright/Browserless, Firecrawl, Apify, or custom crawler with robots/rate limits.
- Search API: SerpAPI, Tavily, Exa, Brave Search, Google Custom Search, or Bing Web Search.
- YouTube Data API for official YouTube metadata.
- First-party Creator Discovery API backed by our own index; Modash/HypeAuditor/CreatorIQ are competitors/benchmarks, not core providers.
- Email: AutoSend for lifecycle/contact automation; Gmail OAuth later for brand-owned outreach.
- Shopify: Admin API for products, orders, discount codes; Collabs export/import later.
- Sheets export: CSV first, Google Sheets later.

### 7.2 Data Source Reality Check

This product lives or dies on data quality and platform compliance.

YouTube:

- Official YouTube Data API is useful for channels, videos, search, comments, and metadata.
- Quota matters. Google says projects get a default 10,000 units/day, and `search.list` costs 100 units per request. Source: [YouTube Data API quota](https://developers.google.com/youtube/v3/determine_quota_cost)

Instagram/Meta:

- Be careful. Meta's terms restrict automated data collection without permission. Search results for Meta's Automated Data Collection Terms state that automated data collection requires express written permission. Source: [Meta Automated Data Collection Terms](https://www.facebook.com/legal/automated_data_collection_terms)
- Instagram Graph API can be useful in limited official contexts, but broad discovery is constrained. For scalable commercial discovery, use our first-party index built from allowed public web sources, creator opt-in, brand-provided imports, and official partner routes.

TikTok:

- TikTok Research API is not for commercial users. TikTok's FAQ says creators, advertisers, and commercial users are not eligible for Research Tools; it also lists quotas for approved research users. Source: [TikTok Research API FAQ](https://developers.tiktok.com/doc/research-api-faq?enter_method=left_navigation)
- For commercial TikTok creator data, use our first-party index, TikTok Creator Marketplace routes, official partner APIs where available, creator opt-in, and brand-provided imports.

LinkedIn:

- LinkedIn explicitly prohibits third-party crawlers, bots, browser plugins, extensions, and other automation that scrape or automate activity. Source: [LinkedIn Help](https://www.linkedin.com/help/linkedin/answer/a1341387/prohibited-software-and-extensions%3Flang%3Den)
- Do not start with LinkedIn unless using approved APIs, creator opt-in, or user-provided data.

Recommended MVP data strategy:

```text
Phase 0: user-provided handles + public websites + YouTube official API + search API
Phase 1: first-party creator index for Instagram/TikTok/YouTube/blogs/newsletters
Phase 2: public Developer Discovery API + creator opt-in profiles + claim/update flow
Phase 3: official marketplace or partner integrations
```

### 7.3 System Architecture

```text
Client
  |
  | REST/GraphQL
  v
API Server
  |
  +-- Auth / orgs / billing
  +-- Campaign service
  +-- Brand intelligence service
  +-- Creator discovery service
  +-- Scoring service
  +-- Outreach service
  +-- CRM service
  +-- Export/report service
  |
  v
Postgres + pgvector
  |
  +-- Redis/BullMQ workers
      +-- website crawl jobs
      +-- LLM extraction jobs
      +-- search jobs
      +-- creator enrichment jobs
      +-- scoring jobs
      +-- email jobs
```

### 7.4 Core Pipelines

#### Brand Intelligence Pipeline

1. Normalize URL.
2. Fetch robots.txt and sitemap.
3. Crawl limited pages.
4. Extract text, structured data, product info, social links, pricing, images metadata.
5. Chunk and embed page content.
6. Run LLM extraction into schema.
7. Generate brand brief and campaign angles.
8. Store extracted evidence with page URLs.
9. Ask user to accept/edit.

#### Creator Discovery Pipeline

1. Convert brand brief into search queries.
2. Query supported sources.
3. Resolve creator identities across platforms when possible.
4. Fetch available metadata.
5. Analyze recent content summaries.
6. Extract public business contacts from allowed sources.
7. Estimate relevance and risks.
8. De-duplicate.
9. Score and bucket.
10. Present results with evidence.

#### Contact Enrichment Policy

Allowed:

- Public business email in creator bio.
- Contact email on creator website/media kit.
- Agency/manager contact published by creator.
- Linktree/Beacons/public profile contact pages.
- Creator-claimed contact details.
- Licensed enrichment provider with compliance terms.

Avoid:

- Private phone scraping.
- Personal email guessing.
- Hidden emails from non-public sources.
- Platform account automation to reveal gated emails.
- Bulk scraping against platform terms.

### 7.5 Data Model

Suggested tables:

```text
organizations
users
brands
brand_scans
brand_scan_pages
campaigns
campaign_goals
ideal_creator_profiles
creator_profiles
creator_platform_accounts
creator_posts
creator_contacts
creator_scores
creator_score_evidence
creator_lists
campaign_creators
outreach_sequences
outreach_messages
crm_events
tasks
exports
integration_accounts
compliance_events
audit_logs
```

Important fields:

```text
source_url
source_type
confidence
last_verified_at
permission_basis
contact_source
do_not_contact
unsubscribe_at
data_retention_until
```

### 7.6 API Sketch

```text
POST /api/campaigns
POST /api/brand-scans
GET  /api/brand-scans/:id
PATCH /api/brand-briefs/:id
POST /api/campaigns/:id/discover
GET  /api/campaigns/:id/creators
POST /api/campaigns/:id/creators/:creatorId/score
POST /api/campaigns/:id/outreach/draft
POST /api/campaigns/:id/outreach/send
PATCH /api/campaign-creators/:id/status
GET  /api/campaigns/:id/export.csv
```

Developer Discovery API:

```text
POST /v1/discovery/search
POST /v1/discovery/semantic-search
POST /v1/discovery/lookalikes
GET  /v1/creators/:creatorId
POST /v1/creators/batch
GET  /v1/creators/:creatorId/report
GET  /v1/creators/:creatorId/audience
GET  /v1/creators/:creatorId/collaborations
POST /v1/contact/lookup
POST /v1/discovery/refresh
GET  /v1/jobs/:jobId
GET  /v1/usage
```

Public API requirements:

- Self-serve API keys.
- Credit ledger and metered billing.
- Cached search/profile responses for speed.
- Async refresh jobs for fresh crawl/enrichment.
- Exact handle/profile URL lookup before semantic search.
- Source URL, freshness, confidence, and missing fields in every response.

### 7.7 AI Prompting Requirements

Use structured prompts with:

- Role: brand strategist, creator marketer, compliance-aware assistant.
- Input: brand brief, creator profile, recent content summaries, campaign goal.
- Output: strict JSON.
- Require evidence.
- Require confidence.
- Require unknowns instead of hallucinated metrics.
- Prohibit sensitive data inference.

Example output contract:

```json
{
  "recommendation": "contact_first",
  "fit_score": 91,
  "explanation": ["..."],
  "risks": ["..."],
  "unknowns": ["audience gender not verified"],
  "recommended_offer": "paid reel + gifted product",
  "outreach_angle": "...",
  "confidence": "medium"
}
```

### 7.8 Evaluation Plan

Create a test set of 50 brands and 500 creators:

- 10 beauty/skincare brands
- 10 food/beverage brands
- 10 fashion/accessory brands
- 10 fitness/wellness brands
- 10 SaaS/B2B brands for out-of-wedge testing

Human labels:

- Good fit / maybe / poor fit
- Brand safety risk
- Content quality
- Outreach quality

Track:

- Precision@10
- Acceptance rate of top 20
- Hallucinated claim rate
- Contact accuracy
- Outreach personalization quality
- Time to shortlist

## 8. Compliance and Trust

This product must be compliance-first from day one.

### 8.1 Endorsement Disclosures

FTC guidance says influencers should disclose financial, employment, personal, or family relationships with brands, and free/discounted products can trigger disclosure when mentioned. Source: [FTC Disclosures 101](https://www.ftc.gov/business-guidance/resources/disclosures-101-social-media-influencers?c78861a6_page=2)

Product requirements:

- Add disclosure reminders to campaign briefs.
- Include disclosure checklist by geography.
- Flag live posts that appear to miss required disclosure keywords, where allowed.
- Store disclosure requirement accepted by brand.

### 8.2 Email Outreach

FTC CAN-SPAM guidance requires accurate sender/header info and non-deceptive subject lines. Source: [FTC CAN-SPAM guide](https://www.ftc.gov/business-guidance/resources/can-spam-act-compliance-guide-business?src_trk=em670645f342be80.177423381649473731)

Product requirements:

- Verified sender domain.
- Unsubscribe link in commercial email.
- Business address/profile footer.
- Suppression list.
- Bounce handling.
- Rate limits.
- No deceptive subject line templates.

### 8.3 Privacy

India:

- NIST summarizes India's Digital Personal Data Protection Act, 2023 as a consent-based framework, with 2025 rules and phased enforcement. Source: [NIST DPDP crosswalk](https://www.nist.gov/privacy-framework/nist-privacy-framework-10-digital-personal-data-protection-act-2023-and-rules-2025)

California:

- CPPA states CCPA gives consumers rights over personal information and requires businesses to inform consumers how personal information is collected, used, and retained. Source: [CPPA FAQ](https://cppa.ca.gov/faq.html)

Product requirements:

- Privacy policy from day one.
- Data deletion request path.
- Creator opt-out / do-not-contact path.
- Contact source and last verified date.
- No sensitive personal data collection.
- Retention policy.
- Vendor data-processing review.

## 9. Pricing Strategy

Competitor anchor:

- Modash app pricing starts around USD 199/mo annually for Essentials and USD 299/mo when billed monthly. Its API pricing page lists Discovery API from USD 16,200/year for 3,000 credits/month and Raw API from USD 10,000/year for 40,000 requests/month. Sources: [Modash pricing](https://www.modash.io/pricing/), [Modash API pricing](https://www.modash.io/fr/influencer-marketing-api/pricing)
- Favikon public pricing search results show lower tiers around USD 99/199/449 depending on billing and plan. Source: [Favikon pricing](https://www.favikon.com/pricing)

Recommended beta pricing:

```text
Free: brand scan preview + 5 creator previews
Starter: USD 79/mo or INR 4,999/mo
Growth: USD 199/mo or INR 14,999/mo
Agency: USD 499/mo or INR 39,999/mo
Concierge campaign: INR 15,000-50,000 or USD 300-1,000 per done-with-you shortlist
```

Why include concierge:

- Data quality can be validated before full automation.
- You learn buyer language.
- You build labeled training/evaluation data.
- You can charge before the product is perfect.

Usage limits should be based on:

- Brand scans/month
- Creator profile views/enrichments
- Contact unlocks
- Outreach sends
- Active campaigns
- Team seats

Developer API pricing should intentionally undercut Modash API while staying profitable:

```text
Developer Free: 500 credits/month, no bulk export
Developer Starter: USD 99/mo, 10,000 credits/month
Developer Growth: USD 299/mo, 50,000 credits/month
Developer Scale: USD 799/mo, 200,000 credits/month
Enterprise API: custom SLA, dedicated refresh jobs, higher concurrency
```

Suggested credit model:

```text
search_result: 0.01 credit
semantic_search_result: 0.02 credit
profile_report: 0.25 credit
audience_snapshot: 0.5 credit
collaboration_lookup: 0.1 credit
compliant_contact_lookup: 0.25 credit only on matched result
fresh_refresh_job: variable by provider/crawl cost plus margin
```

Pricing principle:

```text
Self-serve monthly API access is the wedge. Modash API appears annual-contract-heavy, so we win with developer onboarding, lower minimums, fast cached responses, and clear source-backed JSON.
```

## 10. Go-To-Market Plan

### 10.1 Recommended First Niche

Best first wedge:

```text
India DTC beauty/skincare/wellness brands on Instagram + YouTube
```

Why:

- India has fast creator market growth and strong Instagram concentration.
- Beauty/skincare/wellness creator fit is highly contextual, so brand-intelligence scoring matters.
- DTC founders feel the pain directly.
- Smaller creators and regional creators create more discovery/vetting burden.

Alternative wedge:

```text
US Shopify DTC brands with Instagram + YouTube, then TikTok through first-party index + official/creator-opt-in paths
```

This may monetize faster but will face more expensive data expectations and stronger competition.

### 10.2 Early Acquisition Channels

- Founder communities and DTC groups.
- Shopify agency partnerships.
- Cold outreach to DTC brands with a free "creator campaign audit."
- Public teardown posts: "We scanned Brand X and found 30 creators they should contact."
- Templates: influencer shortlist CSV, campaign brief template, outreach template.
- SEO pages by niche: "best skincare creators in India", "how to find micro influencers for DTC beauty", etc.
- Agency/reseller partnerships.

### 10.3 Validation Experiments

Run before building full SaaS:

1. Manual concierge: ask 10 brands for URL, return 30 scored creators and outreach drafts.
2. Landing page: "Turn your brand URL into a creator campaign in 10 minutes."
3. Paid pilot: charge INR 10k-25k per shortlist.
4. Compare against spreadsheet/manual research.
5. Measure whether users contact recommended creators.

Validation bar:

- 10 paid pilots.
- 60% of top 20 creators accepted by users.
- At least 20% creator response rate from personalized outreach.
- At least 3 brands ask to run another campaign.

## 11. Roadmap

### Phase 0: Concierge Prototype - 2 weeks

- Build internal scripts for brand scan.
- Manually source creators.
- Use LLM scoring.
- Deliver Google Sheet + outreach drafts.
- Interview users.

### Phase 1: MVP Web App - 4 to 6 weeks

- Auth/orgs.
- New campaign flow.
- Brand URL scan.
- Editable brand brief.
- Creator discovery from limited sources.
- Creator scoring.
- Shortlist.
- Outreach drafts.
- CSV export.

### Phase 2: Workflow Product - 6 to 10 weeks

- CRM board.
- Gmail/Postmark sending.
- Follow-up scheduling.
- Contact enrichment confidence.
- Team comments.
- Campaign brief builder.

### Phase 3: Commerce/Attribution - 8 to 12 weeks

- Shopify integration.
- Discount code generation.
- Affiliate link tracking.
- Product gifting workflow.
- UGC tracking and download.

### Phase 4: Data Moat - ongoing

- Creator opt-in profile claiming.
- Licensed data partnerships.
- Brand/customer influencer discovery.
- Competitor creator monitoring.
- Regional language models and taxonomies.

## 12. Risks and Mitigations

| Risk | Severity | Mitigation |
|---|---:|---|
| Platform data access restrictions | High | Use official APIs, licensed vendors, user imports, creator opt-in, and compliant public web data. |
| Poor creator recommendations | High | Human-labeled eval set, explainable scoring, user feedback loop. |
| Contact data inaccuracies | High | Show source/confidence, verify dates, bounce handling, never guess private contacts. |
| Spam/deliverability issues | High | Sender verification, rate limits, unsubscribe, suppression list, warmed domains, Gmail OAuth later. |
| Existing competitors copy URL scan | Medium | Build workflow depth, data quality, niche-specific scoring, and customer learning loops. |
| Users want all platforms immediately | Medium | Position around wedge quality, add platforms only when data path is safe. |
| Legal/privacy exposure | High | Privacy policy, opt-out, retention, source trails, no sensitive data, vendor review. |
| LLM hallucinations | High | Structured extraction, evidence requirements, unknown fields, confidence labels. |

## 13. Build Handoff For Claude or Codex

Use this prompt to start building:

```text
Build an MVP called Creator Scout AI.

Goal:
Turn a brand website URL into an editable brand brief, ideal creator profile, ranked creator shortlist, outreach drafts, and CSV export.

Stack:
Next.js, TypeScript, Postgres, Prisma or Drizzle, Tailwind, shadcn/ui, BullMQ/Redis for background jobs.

P0 screens:
1. New campaign: URL, goal, geography, platform, budget.
2. Brand scan progress.
3. Editable brand brief.
4. Creator strategy editor.
5. Ranked creator shortlist table.
6. Creator profile drawer with score breakdown and evidence.
7. Outreach draft generator.
8. CSV export.

Data:
Start with website crawling, search API, YouTube API, and manual CSV imports. Do not implement unauthorized scraping of Instagram, TikTok, or LinkedIn.

AI:
Use structured JSON outputs. Every score must include evidence, confidence, and unknowns.

Compliance:
Only store public business contact info with source URL and last verified date. Add opt-out and do-not-contact fields. Include email unsubscribe support before sending outreach.

Deliver:
Working local app, seed data, database schema, core API endpoints, and a README explaining setup and limitations.
```

## 14. Recommended MVP Database Schema Sketch

```sql
create table brands (
  id uuid primary key,
  org_id uuid not null,
  name text,
  website_url text not null,
  category text,
  created_at timestamptz default now()
);

create table campaigns (
  id uuid primary key,
  brand_id uuid not null references brands(id),
  goal text not null,
  geography text,
  platforms text[],
  budget_range text,
  status text default 'draft',
  created_at timestamptz default now()
);

create table brand_scans (
  id uuid primary key,
  brand_id uuid not null references brands(id),
  status text not null,
  extracted_json jsonb,
  confidence numeric,
  created_at timestamptz default now()
);

create table creators (
  id uuid primary key,
  display_name text not null,
  primary_platform text,
  niche text,
  location text,
  bio text,
  created_at timestamptz default now()
);

create table creator_accounts (
  id uuid primary key,
  creator_id uuid not null references creators(id),
  platform text not null,
  profile_url text not null,
  handle text,
  follower_count integer,
  avg_views integer,
  engagement_rate numeric,
  last_verified_at timestamptz
);

create table creator_contacts (
  id uuid primary key,
  creator_id uuid not null references creators(id),
  type text not null,
  value text not null,
  source_url text not null,
  confidence text not null,
  last_verified_at timestamptz,
  do_not_contact boolean default false
);

create table campaign_creators (
  id uuid primary key,
  campaign_id uuid not null references campaigns(id),
  creator_id uuid not null references creators(id),
  status text default 'shortlisted',
  fit_score integer,
  score_breakdown jsonb,
  evidence jsonb,
  risks jsonb,
  recommended_pitch text,
  created_at timestamptz default now()
);

create table outreach_messages (
  id uuid primary key,
  campaign_creator_id uuid not null references campaign_creators(id),
  channel text not null,
  subject text,
  body text not null,
  status text default 'draft',
  sent_at timestamptz,
  created_at timestamptz default now()
);
```

## 15. Final Recommendation

Build this as a narrow, practical workflow product first:

```text
DTC brand URL -> creator strategy -> 50 ranked creators -> personalized outreach -> export/CRM
```

Do not begin with a giant platform vision. Begin with one killer output: a brand-specific creator shortlist that a founder trusts enough to contact.

The strongest product promise:

```text
In 10 minutes, get the creator campaign your growth team would have spent 2 days researching.
```

The long-term moat is not just data. It is:

- brand understanding,
- creator fit intelligence,
- campaign workflow,
- reply/outcome learning,
- creator relationship history,
- compliant contact graph,
- and evidence-backed recommendations.

## 16. Research Sources

- [Shared ChatGPT conversation](https://chatgpt.com/s/t_6a1c56820560819191163f933af962c4)
- [IAB 2025 Creator Economy Ad Spend & Strategy Report](https://www.iab.com/insights/2025-creator-economy-ad-spend-strategy-report/)
- [EMARKETER micro/nano influencer budget forecast](https://www.emarketer.com/chart/c/361073/micro-nano-influencers-will-claim-almost-half-of-influencer-marketing-budgets-2026-361073)
- [Economic Times on Kofluence India influencer report 2026](https://m.economictimes.com/industry/services/advertising/indias-influencer-marketing-industry-to-reach-rs-5000-crore-by-2027-as-creator-economy-formalises-kofluence-report/amp_articleshow/131085735.cms)
- [Modash help: what Modash does](https://help.modash.io/en/articles/13714522-what-is-modash-and-how-does-it-work)
- [Modash pricing](https://www.modash.io/pricing/)
- [Modash API pricing](https://www.modash.io/fr/influencer-marketing-api/pricing)
- [HypeAuditor](https://hypeauditor.com/)
- [Aspire platform overview](https://www.aspire.io/platform-overview)
- [Aspire creator sourcing help](https://help.aspireiq.com/en/articles/5834954-how-to-source-creators-with-aspire)
- [GRIN product overview](https://grin.co/product/)
- [SARAL](https://www.getsaral.com/)
- [Favikon](https://www.favikon.com/)
- [Favikon pricing](https://www.favikon.com/pricing)
- [Shopify Collabs merchant help](https://help.shopify.com/en/manual/promoting-marketing/collabs/merchants)
- [YouTube Data API quota docs](https://developers.google.com/youtube/v3/determine_quota_cost)
- [TikTok Research API FAQ](https://developers.tiktok.com/doc/research-api-faq?enter_method=left_navigation)
- [Meta Automated Data Collection Terms](https://www.facebook.com/legal/automated_data_collection_terms)
- [LinkedIn prohibited software and extensions](https://www.linkedin.com/help/linkedin/answer/a1341387/prohibited-software-and-extensions%3Flang%3Den)
- [FTC Disclosures 101 for Social Media Influencers](https://www.ftc.gov/business-guidance/resources/disclosures-101-social-media-influencers?c78861a6_page=2)
- [FTC CAN-SPAM compliance guide](https://www.ftc.gov/business-guidance/resources/can-spam-act-compliance-guide-business?src_trk=em670645f342be80.177423381649473731)
- [NIST DPDP Act 2023 and Rules 2025 crosswalk](https://www.nist.gov/privacy-framework/nist-privacy-framework-10-digital-personal-data-protection-act-2023-and-rules-2025)
- [California Privacy Protection Agency CCPA FAQ](https://cppa.ca.gov/faq.html)
