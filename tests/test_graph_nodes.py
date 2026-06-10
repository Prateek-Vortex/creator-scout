"""Unit tests for individual LangGraph node functions.

Each node is tested in isolation with a mocked DiscoveryStore and
mocked external service calls. No network or DB required.
"""
from __future__ import annotations

import unittest
from dataclasses import asdict, dataclass, field
from unittest.mock import MagicMock, patch

from creator_scout.graph.nodes import (
    SHORTLIST_SCORE_THRESHOLD,
    brand_scan_node,
    outreach_draft_node,
    query_planner_node,
    scoring_node,
    shortlist_node,
    send_outreach_node,
)
from creator_scout.graph.state import GraphState


# ─── Fixtures ─────────────────────────────────────────────────────────────────

def _base_state(**overrides) -> GraphState:
    state: GraphState = {
        "campaign_id": "camp-001",
        "brand_url": "https://example.com",
        "org_id": "org-001",
        "goal": "ugc",
        "geo": "India",
        "brand_brief": None,
        "search_queries": [],
        "raw_records": [],
        "creator_ids": [],
        "scored_creators": [],
        "shortlist": [],
        "outreach_drafts": [],
        "stream_tokens": [],
        "error": None,
        "human_feedback": None,
        "current_node": "",
    }
    state.update(overrides)
    return state


def _mock_brief(**kwargs):
    """Return a minimal BrandBrief-like object."""
    @dataclass
    class Brief:
        brand_name: str = "TestBrand"
        primary_category: str = "fitness"
        price_positioning: str = "mid-range"
        target_audience: str = "young adults"
        confidence: float = 0.85
        search_queries: list = field(default_factory=lambda: ["fitness creator India", "yoga influencer"])
        best_creator_niches: list = field(default_factory=list)
        avoid_creator_types: list = field(default_factory=list)
        tone: list = field(default_factory=list)
        campaign_angles: list = field(default_factory=list)
        evidence: list = field(default_factory=list)
        target_creator_topics: list = field(default_factory=list)
        geo: str = "India"
        goal: str = "ugc"
    b = Brief()
    for k, v in kwargs.items():
        setattr(b, k, v)
    return b


# ─── brand_scan_node ──────────────────────────────────────────────────────────

class BrandScanNodeTest(unittest.TestCase):
    def test_happy_path_returns_brief_and_queries(self):
        mock_brief = _mock_brief()
        mock_pages = [MagicMock()]

        with patch("creator_scout.graph.nodes.BrandCrawler") as MockCrawler, \
             patch("creator_scout.graph.nodes.build_brand_brief", return_value=mock_brief), \
             patch("creator_scout.graph.nodes._store_from_config", return_value=MagicMock()):
            MockCrawler.return_value.crawl.return_value = mock_pages
            result = brand_scan_node(_base_state())

        self.assertIn("brand_brief", result)
        self.assertEqual(result["brand_brief"]["brand_name"], "TestBrand")
        self.assertIn("fitness creator India", result["search_queries"])
        self.assertIsNone(result["error"])
        self.assertEqual(result["current_node"], "brand_scan")

    def test_crawler_error_sets_error_field(self):
        with patch("creator_scout.graph.nodes.BrandCrawler") as MockCrawler, \
             patch("creator_scout.graph.nodes._store_from_config", return_value=MagicMock()):
            MockCrawler.return_value.crawl.side_effect = RuntimeError("DNS failure")
            result = brand_scan_node(_base_state())

        self.assertIn("DNS failure", result["error"])
        self.assertEqual(result["current_node"], "brand_scan")
        self.assertNotIn("brand_brief", result)


# ─── query_planner_node ───────────────────────────────────────────────────────

class QueryPlannerNodeTest(unittest.TestCase):
    def test_deduplicates_queries(self):
        state = _base_state(search_queries=["yoga India", "yoga india", "fitness creator"])
        result = query_planner_node(state)
        self.assertEqual(len(result["search_queries"]), 2)

    def test_limits_to_ten_queries(self):
        state = _base_state(search_queries=[f"query {i}" for i in range(20)])
        result = query_planner_node(state)
        self.assertLessEqual(len(result["search_queries"]), 10)

    def test_human_feedback_json_overrides_queries(self):
        import json
        feedback = json.dumps({"search_queries": ["custom query 1", "custom query 2"]})
        state = _base_state(
            search_queries=["original query"],
            human_feedback=feedback,
        )
        result = query_planner_node(state)
        self.assertIn("custom query 1", result["search_queries"])
        self.assertNotIn("original query", result["search_queries"])

    def test_human_feedback_consumed(self):
        state = _base_state(search_queries=["q1"], human_feedback="approved")
        result = query_planner_node(state)
        self.assertIsNone(result["human_feedback"])


# ─── scoring_node ─────────────────────────────────────────────────────────────

class ScoringNodeTest(unittest.TestCase):
    def _mock_creator(self, creator_id: str):
        from creator_scout.discovery.models import CreatorProfile, CreatorAccount, Platform
        return CreatorProfile(
            creator_id=creator_id,
            display_name="Test Creator",
            primary_niche="fitness",
            languages=["en"],
            topics=["fitness", "yoga"],
            accounts=[
                CreatorAccount(
                    platform=Platform.YOUTUBE,
                    handle="testcreator",
                    profile_url="https://youtube.com/@testcreator",
                    follower_count=10000,
                )
            ],
        )

    def test_scores_each_creator(self):
        creator = self._mock_creator("c1")
        mock_store = MagicMock()
        mock_store.get_creator.return_value = creator

        with patch("creator_scout.graph.nodes._store_from_config", return_value=mock_store), \
             patch("creator_scout.graph.nodes.score_creator", return_value=(75, ["Topic match"], [], [], 0.8)):
            result = scoring_node(_base_state(creator_ids=["c1"], brand_brief={"primary_category": "fitness"}))

        self.assertEqual(len(result["scored_creators"]), 1)
        self.assertEqual(result["scored_creators"][0]["score"], 75)
        self.assertEqual(result["current_node"], "scoring")

    def test_empty_creator_ids_returns_empty_scored(self):
        with patch("creator_scout.graph.nodes._store_from_config", return_value=MagicMock()):
            result = scoring_node(_base_state(creator_ids=[]))
        self.assertEqual(result["scored_creators"], [])


# ─── shortlist_node ───────────────────────────────────────────────────────────

class ShortlistNodeTest(unittest.TestCase):
    def _scored(self, n: int, score: int) -> list:
        return [{"creator_id": f"c{i}", "score": score, "confidence": 0.8} for i in range(n)]

    def test_filters_below_threshold(self):
        scored = self._scored(5, SHORTLIST_SCORE_THRESHOLD - 1)
        result = shortlist_node(_base_state(scored_creators=scored))
        self.assertEqual(result["shortlist"], [])

    def test_keeps_above_threshold(self):
        scored = self._scored(5, SHORTLIST_SCORE_THRESHOLD + 10)
        result = shortlist_node(_base_state(scored_creators=scored))
        self.assertEqual(len(result["shortlist"]), 5)

    def test_caps_at_max(self):
        scored = self._scored(30, SHORTLIST_SCORE_THRESHOLD + 1)
        result = shortlist_node(_base_state(scored_creators=scored))
        self.assertLessEqual(len(result["shortlist"]), 20)


# ─── outreach_draft_node ──────────────────────────────────────────────────────

class OutreachDraftNodeTest(unittest.TestCase):
    def test_generates_draft_per_creator(self):
        shortlist = [{"creator_id": "c1"}, {"creator_id": "c2"}]
        mock_outreach = MagicMock()
        mock_outreach.draft_outreach.return_value = {"creator_id": "c1", "subject": "Hi", "body": "Body"}

        with patch("creator_scout.graph.nodes._store_from_config", return_value=MagicMock()), \
             patch("creator_scout.campaign.service.CampaignService", return_value=MagicMock()), \
             patch("creator_scout.outreach.service.OutreachService", return_value=mock_outreach):
            result = outreach_draft_node(_base_state(shortlist=shortlist))

        self.assertEqual(result["current_node"], "outreach_draft")
        self.assertIn("outreach_drafts", result)


# ─── send_outreach_node ───────────────────────────────────────────────────────

class SendOutreachNodeTest(unittest.TestCase):
    def test_sends_each_draft(self):
        drafts = [{"creator_id": "c1", "subject": "Hi", "body": "Body"}]
        mock_outreach = MagicMock()
        mock_outreach.send_campaign_creator_outreach.return_value = {"ok": True}

        with patch("creator_scout.graph.nodes._store_from_config", return_value=MagicMock()), \
             patch("creator_scout.campaign.service.CampaignService", return_value=MagicMock()), \
             patch("creator_scout.outreach.service.OutreachService", return_value=mock_outreach):
            result = send_outreach_node(_base_state(outreach_drafts=drafts))

        self.assertEqual(result["current_node"], "send_outreach")

    def test_rejected_feedback_skips_send(self):
        drafts = [{"creator_id": "c1", "subject": "Hi", "body": "Body"}]
        mock_outreach = MagicMock()

        with patch("creator_scout.graph.nodes._store_from_config", return_value=MagicMock()), \
             patch("creator_scout.campaign.service.CampaignService", return_value=MagicMock()), \
             patch("creator_scout.outreach.service.OutreachService", return_value=mock_outreach):
            result = send_outreach_node(_base_state(outreach_drafts=drafts, human_feedback="rejected"))

        mock_outreach.send_campaign_creator_outreach.assert_not_called()


if __name__ == "__main__":
    unittest.main()
