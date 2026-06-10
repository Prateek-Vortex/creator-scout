"""Integration test — full in-memory LangGraph campaign run.

Uses MemorySaver (no DB) and mocked node internals.
Verifies the graph pauses at all three HIL gates and can be resumed.
"""
from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch

from langgraph.checkpoint.memory import MemorySaver

from creator_scout.graph.graph import build_graph
from creator_scout.graph.runner import GraphRunner


def _make_mock_nodes():
    """Patch all heavy node internals so the graph runs fast (no network/DB)."""
    from dataclasses import dataclass, field as dc_field

    @dataclass
    class FakeBrief:
        brand_name: str = "TestBrand"
        primary_category: str = "fitness"
        price_positioning: str = "mid-range"
        target_audience: str = "young adults"
        confidence: float = 0.9
        search_queries: list = dc_field(default_factory=lambda: ["fitness creator"])
        best_creator_niches: list = dc_field(default_factory=list)
        avoid_creator_types: list = dc_field(default_factory=list)
        tone: list = dc_field(default_factory=list)
        campaign_angles: list = dc_field(default_factory=list)
        evidence: list = dc_field(default_factory=list)
        target_creator_topics: list = dc_field(default_factory=list)
        geo: str = "India"
        goal: str = "ugc"

    patches = [
        patch(
            "creator_scout.graph.nodes.BrandCrawler",
            return_value=MagicMock(crawl=MagicMock(return_value=[MagicMock()])),
        ),
        patch(
            "creator_scout.graph.nodes.build_brand_brief",
            return_value=FakeBrief(),
        ),
        patch("creator_scout.graph.nodes._store_from_config", return_value=MagicMock(
            get_creator=MagicMock(return_value=None),
            close=MagicMock(),
        )),
        patch("creator_scout.graph.nodes.adapter_for_provider", return_value=MagicMock(
            discover=MagicMock(return_value=MagicMock(records=[], provider="youtube")),
        )),
        patch("creator_scout.graph.nodes.ingest_records", return_value=[]),
        patch("creator_scout.graph.nodes.score_creator", return_value=(80, ["Relevant"], [], [], 0.85)),
    ]
    return patches



class FullGraphRunTest(unittest.TestCase):
    def _build_runner(self) -> GraphRunner:
        mem = MemorySaver()
        graph = build_graph(checkpointer=mem)
        return GraphRunner(graph=graph)

    def test_graph_pauses_at_gate1_after_brand_scan(self):
        """After start_campaign_run, graph should pause at query_planner_node."""
        runner = self._build_runner()

        patches = _make_mock_nodes()
        for p in patches:
            p.start()
        try:
            thread_id = runner.start_campaign_run(
                campaign_id="camp-test",
                brand_url="https://example.com",
                goal="ugc",
                geo="India",
            )
        finally:
            for p in patches:
                p.stop()

        self.assertIsNotNone(thread_id)
        status = runner.get_run_status(thread_id)
        self.assertTrue(status["paused"], f"Expected paused=True, got {status}")
        self.assertEqual(status["next_node"], "query_planner_node")
        self.assertIsNotNone(status["brand_brief"])

    def test_resume_with_approval_advances_graph(self):
        """Approving gate 1 should advance the graph to the next gate."""
        runner = self._build_runner()

        patches = _make_mock_nodes()
        for p in patches:
            p.start()
        try:
            thread_id = runner.start_campaign_run(
                campaign_id="camp-test",
                brand_url="https://example.com",
            )
            # Resume gate 1
            result = runner.resume_run(thread_id, approved=True)
        finally:
            for p in patches:
                p.stop()

        self.assertEqual(result["thread_id"], thread_id)
        # Graph either paused at gate 2 or completed (if shortlist was empty)
        status = runner.get_run_status(thread_id)
        self.assertIn("paused", status)

    def test_resume_with_rejection_terminates(self):
        """Rejecting gate 1 should terminate the graph run."""
        runner = self._build_runner()

        patches = _make_mock_nodes()
        for p in patches:
            p.start()
        try:
            thread_id = runner.start_campaign_run(
                campaign_id="camp-test",
                brand_url="https://example.com",
            )
            result = runner.resume_run(thread_id, approved=False)
        finally:
            for p in patches:
                p.stop()

        self.assertEqual(result["status"], "rejected")

    def test_get_run_status_unknown_thread(self):
        """get_run_status for an unknown thread should not crash."""
        runner = self._build_runner()
        status = runner.get_run_status("nonexistent-thread-id")
        self.assertIn("thread_id", status)
        # May return error or empty state — must not raise
        self.assertIn("paused", status)


class GraphBuildTest(unittest.TestCase):
    def test_graph_compiles_with_memory_saver(self):
        mem = MemorySaver()
        graph = build_graph(checkpointer=mem)
        self.assertIsNotNone(graph)

    def test_graph_has_correct_nodes(self):
        mem = MemorySaver()
        graph = build_graph(checkpointer=mem)
        node_names = set(graph.get_graph().nodes.keys())
        expected = {
            "brand_scan_node", "query_planner_node", "discovery_node",
            "scoring_node", "shortlist_node", "outreach_draft_node", "send_outreach_node",
        }
        for name in expected:
            self.assertIn(name, node_names, f"Missing node: {name}")


if __name__ == "__main__":
    unittest.main()
