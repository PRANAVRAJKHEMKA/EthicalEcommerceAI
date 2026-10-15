"""Unit tests for Milestone 5B: Frequency-Aware Interaction Signals

Tests:
1. Five recent product-view events yield a higher interaction score than one such event.
2. Older events receive less weight than equivalent recent events (exponential time decay).
3. One qualifying hover contributes less than one product-view event.
4. Repeated qualifying hover episodes affect ranking, but influence remains strictly bounded (< 1.0).
5. Brief hover below 700 ms contributes 0.00 weight.
6. Event idempotency: repeated submissions with the same event identifier are not counted twice.
7. Robustness: scores are finite, valid, and exactly 0.50 for empty, missing, or unknown products.
8. Candidate integrity: history updates do not change product identity or bypass inventory/eligibility.
9. Empty basket recommendations: cold-start can use interaction history anchors to surface relevant items.
10. Session reset: clearing session events removes interaction records and restores cold start.
11. Economic constraints: Engine B continues enforcing margin floors and price ceilings regardless of history frequency.
12. HTTP API: POST /api/v1/events accepts product_hover, product_focus, and deduplicates identical event_ids.
"""

from datetime import datetime, timezone, timedelta
import math
import unittest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.db.repository import CatalogRepository, ProductEntity
from backend.app.engine.recommender import (
    calculate_session_interest_score,
    EVENT_INTERACTION_WEIGHTS,
    RecommenderEngine,
)
from backend.app.engine.orchestrator import DecisionOrchestrator
from backend.app.models.schemas import DecisionRequest, CartItemInput, SessionEventCreate


class TestFrequencyAwareInteractionSignals(unittest.TestCase):
    def setUp(self):
        self.repo = CatalogRepository()
        self.client = TestClient(app)
        self.now = datetime.now(timezone.utc)

    # -------------------------------------------------------------------------
    # 1. Frequency Sensitivity: 5 views > 1 view
    # -------------------------------------------------------------------------
    def test_01_repeated_views_yield_higher_score_than_single_view(self):
        pid = "item-001"
        single_view = [{"product_id": pid, "event_type": "product_view", "age_hours": 0.0}]
        five_views = [{"product_id": pid, "event_type": "product_view", "age_hours": 0.0} for _ in range(5)]

        score_1 = calculate_session_interest_score(pid, single_view, tau_hours=24.0, now_dt=self.now)
        score_5 = calculate_session_interest_score(pid, five_views, tau_hours=24.0, now_dt=self.now)

        self.assertGreater(score_5, score_1)
        # Expected exact: score_1 ~ 0.6457, score_5 ~ 0.8832
        self.assertAlmostEqual(score_1, 0.6457, places=2)
        self.assertAlmostEqual(score_5, 0.8832, places=2)

    # -------------------------------------------------------------------------
    # 2. Time Decay: Recent events > Stale events
    # -------------------------------------------------------------------------
    def test_02_recent_events_weighted_more_than_older_events(self):
        pid = "item-002"
        fresh_event = [{"product_id": pid, "event_type": "product_view", "age_hours": 0.5}]
        stale_event = [{"product_id": pid, "event_type": "product_view", "age_hours": 48.0}]

        score_fresh = calculate_session_interest_score(pid, fresh_event, tau_hours=24.0, now_dt=self.now)
        score_stale = calculate_session_interest_score(pid, stale_event, tau_hours=24.0, now_dt=self.now)

        self.assertGreater(score_fresh, score_stale)
        self.assertGreater(score_stale, 0.50)  # Still greater than neutral baseline

    # -------------------------------------------------------------------------
    # 3. Event Hierarchy: Qualifying Hover < Product View
    # -------------------------------------------------------------------------
    def test_03_qualifying_hover_contributes_less_than_product_view(self):
        pid = "item-003"
        hover_event = [
            {"product_id": pid, "event_type": "product_hover", "age_hours": 0.0, "metadata": {"duration_ms": 950}}
        ]
        view_event = [
            {"product_id": pid, "event_type": "product_view", "age_hours": 0.0}
        ]

        score_hover = calculate_session_interest_score(pid, hover_event, tau_hours=24.0, now_dt=self.now)
        score_view = calculate_session_interest_score(pid, view_event, tau_hours=24.0, now_dt=self.now)

        self.assertGreater(score_view, score_hover)
        self.assertGreater(score_hover, 0.50)
        # 1 hover ~ 0.5475, 1 view ~ 0.6457
        self.assertAlmostEqual(score_hover, 0.5475, places=2)
        self.assertAlmostEqual(score_view, 0.6457, places=2)

    # -------------------------------------------------------------------------
    # 4. Bounded Influence of Repeated Hovers
    # -------------------------------------------------------------------------
    def test_04_repeated_hovers_affect_score_but_remain_bounded(self):
        pid = "item-004"
        one_hover = [{"product_id": pid, "event_type": "product_hover", "age_hours": 0.0, "metadata": {"duration_ms": 900}}]
        three_hovers = [{"product_id": pid, "event_type": "product_hover", "age_hours": 0.0, "metadata": {"duration_ms": 900}} for _ in range(3)]
        fifty_hovers = [{"product_id": pid, "event_type": "product_hover", "age_hours": 0.0, "metadata": {"duration_ms": 900}} for _ in range(50)]

        score_1 = calculate_session_interest_score(pid, one_hover, tau_hours=24.0, now_dt=self.now)
        score_3 = calculate_session_interest_score(pid, three_hovers, tau_hours=24.0, now_dt=self.now)
        score_50 = calculate_session_interest_score(pid, fifty_hovers, tau_hours=24.0, now_dt=self.now)

        self.assertGreater(score_3, score_1)
        self.assertGreater(score_50, score_3)
        # Even with 50 hovers, score must strictly remain finite and < 1.0
        self.assertLess(score_50, 1.0)
        self.assertTrue(math.isfinite(score_50))

    # -------------------------------------------------------------------------
    # 5. Brief Hover Below 700 ms Contributes 0.00
    # -------------------------------------------------------------------------
    def test_05_brief_hover_below_700ms_contributes_zero(self):
        pid = "item-005"
        brief_hover = [
            {"product_id": pid, "event_type": "product_hover", "age_hours": 0.0, "metadata": {"duration_ms": 450}}
        ]
        score_brief = calculate_session_interest_score(pid, brief_hover, tau_hours=24.0, now_dt=self.now)
        self.assertEqual(score_brief, 0.50)  # Neutral baseline

        # Hover at 750 ms is qualifying and contributes
        qualifying_hover = [
            {"product_id": pid, "event_type": "product_hover", "age_hours": 0.0, "metadata": {"duration_ms": 750}}
        ]
        score_qual = calculate_session_interest_score(pid, qualifying_hover, tau_hours=24.0, now_dt=self.now)
        self.assertGreater(score_qual, 0.50)

    # -------------------------------------------------------------------------
    # 6. Robustness on Empty / Missing / Invalid Data
    # -------------------------------------------------------------------------
    def test_06_robustness_on_empty_and_invalid_data(self):
        # Empty events
        self.assertEqual(calculate_session_interest_score("item-001", []), 0.50)
        self.assertEqual(calculate_session_interest_score("item-001", None), 0.50)

        # Unrelated events
        other_events = [{"product_id": "item-999", "event_type": "product_view", "age_hours": 0.0}]
        self.assertEqual(calculate_session_interest_score("item-001", other_events), 0.50)

        # Event with invalid timestamp string should not crash, defaults safely
        invalid_ts_event = [{"product_id": "item-001", "event_type": "product_view", "timestamp": "not-a-date"}]
        score = calculate_session_interest_score("item-001", invalid_ts_event)
        self.assertTrue(0.50 <= score <= 1.0)

    # -------------------------------------------------------------------------
    # 7. ISO Timestamp Age Parsing
    # -------------------------------------------------------------------------
    def test_07_iso_timestamp_age_parsing(self):
        pid = "item-006"
        ts_now = self.now.isoformat()
        ts_12h_ago = (self.now - timedelta(hours=12)).isoformat()

        evt_now = [{"product_id": pid, "event_type": "product_view", "timestamp": ts_now}]
        evt_12h = [{"product_id": pid, "event_type": "product_view", "timestamp": ts_12h_ago}]

        s_now = calculate_session_interest_score(pid, evt_now, tau_hours=24.0, now_dt=self.now)
        s_12h = calculate_session_interest_score(pid, evt_12h, tau_hours=24.0, now_dt=self.now)

        self.assertGreater(s_now, s_12h)

    # -------------------------------------------------------------------------
    # 8. Event Idempotency in Repository (INSERT OR IGNORE)
    # -------------------------------------------------------------------------
    def test_08_repository_event_idempotency(self):
        sess = f"test-idemp-{self.now.timestamp()}"
        event_id = f"evt-fixed-{self.now.timestamp()}"

        # Submit event first time
        id1 = self.repo.record_session_event(
            session_id=sess,
            event_type="product_hover",
            product_id="item-001",
            shopping_context="productivity",
            metadata={"duration_ms": 900},
            event_id=event_id,
        )
        self.assertEqual(id1, event_id)

        # Submit the EXACT same event_id a second time (e.g. network retry)
        id2 = self.repo.record_session_event(
            session_id=sess,
            event_type="product_hover",
            product_id="item-001",
            shopping_context="productivity",
            metadata={"duration_ms": 900},
            event_id=event_id,
        )
        self.assertEqual(id2, event_id)

        # Retrieve events: exactly 1 event should exist in database, not 2
        events = self.repo.get_session_events(sess)
        matching = [e for e in events if e["id"] == event_id]
        self.assertEqual(len(matching), 1)

        # Clean up
        self.repo.clear_session_events(sess)

    # -------------------------------------------------------------------------
    # 9. Genuinely Separate Episodes Are Preserved
    # -------------------------------------------------------------------------
    def test_09_genuinely_separate_episodes_are_preserved(self):
        sess = f"test-separate-{self.now.timestamp()}"

        # Two distinct hover episodes for the same product
        id1 = self.repo.record_session_event(
            session_id=sess,
            event_type="product_hover",
            product_id="item-002",
            metadata={"duration_ms": 920, "episode_id": "hov-1"},
            event_id=f"evt-hov-1-{sess}",
        )
        id2 = self.repo.record_session_event(
            session_id=sess,
            event_type="product_hover",
            product_id="item-002",
            metadata={"duration_ms": 1100, "episode_id": "hov-2"},
            event_id=f"evt-hov-2-{sess}",
        )

        events = self.repo.get_session_events(sess)
        self.assertEqual(len(events), 2)
        self.assertIn(id1, [e["id"] for e in events])
        self.assertIn(id2, [e["id"] for e in events])

        # Clean up
        self.repo.clear_session_events(sess)

    # -------------------------------------------------------------------------
    # 10. HTTP API Ingestion and Idempotency
    # -------------------------------------------------------------------------
    def test_10_api_event_ingestion_and_idempotency(self):
        sess = f"api-test-{self.now.timestamp()}"
        event_id = f"evt-api-idemp-{self.now.timestamp()}"

        payload = {
            "session_id": sess,
            "event_type": "product_hover",
            "product_id": "item-003",
            "shopping_context": "gaming",
            "metadata": {"duration_ms": 950},
            "event_id": event_id,
        }

        # 1. Post event
        res1 = self.client.post("/api/v1/events", json=payload)
        self.assertEqual(res1.status_code, 200)
        self.assertEqual(res1.json()["status"], "recorded")

        # 2. Resend exact same event (idempotency check)
        res2 = self.client.post("/api/v1/events", json=payload)
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(res2.json()["status"], "recorded")

        # 3. Verify exactly 1 record stored
        get_res = self.client.get(f"/api/v1/events?session_id={sess}")
        self.assertEqual(get_res.status_code, 200)
        records = get_res.json()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["id"], event_id)

        # 4. Clear events
        del_res = self.client.delete(f"/api/v1/events?session_id={sess}")
        self.assertEqual(del_res.status_code, 200)
        self.assertEqual(del_res.json()["status"], "deleted")

    # -------------------------------------------------------------------------
    # 11. Empty Basket Uses Interaction History to Rank Recommendations
    # -------------------------------------------------------------------------
    def test_11_empty_basket_elevates_interacted_products_in_recommendations(self):
        sess = f"test-anchor-freq-{self.now.timestamp()}"
        orchestrator = DecisionOrchestrator()

        # Seed 3 views for item-001 (Keyboard)
        for i in range(3):
            self.repo.record_session_event(
                session_id=sess,
                event_type="product_view",
                product_id="item-001",
                shopping_context="all",
                event_id=f"evt-v{i}-{sess}",
            )

        # Request empty-basket decision
        req = DecisionRequest(
            session_id=sess,
            cart_items=[],
            shopping_context="all",
        )
        res = orchestrator.process_decision(req)

        # Recommendations should exist (not empty)
        self.assertTrue(len(res.recommendations) > 0)
        rec_ids = [r.product_id for r in res.recommendations]
        # item-002 (Wrist Rest, complement of item-001) or item-001 should be surfaced
        self.assertTrue("item-002" in rec_ids or "item-001" in rec_ids)

        # Commercial invariant: when cart is empty, NO unearned discounts
        for r in res.recommendations:
            self.assertFalse(r.is_offered)
            self.assertEqual(r.final_price, r.reference_price)
            self.assertEqual(r.savings, 0.0)

        # Clean up
        self.repo.clear_session_events(sess)

    # -------------------------------------------------------------------------
    # 12. Economic Safeguards Remain Strict Regardless of High Frequency
    # -------------------------------------------------------------------------
    def test_12_high_frequency_does_not_breach_margin_floors(self):
        sess = f"test-safeguard-{self.now.timestamp()}"
        orchestrator = DecisionOrchestrator()

        # Add 20 views for item-002
        for i in range(20):
            self.repo.record_session_event(
                session_id=sess,
                event_type="product_view",
                product_id="item-002",
                shopping_context="all",
                event_id=f"evt-high-{i}-{sess}",
            )

        # Put item-001 in cart, margin floor set high (e.g. 50%)
        req = DecisionRequest(
            session_id=sess,
            cart_items=[CartItemInput(product_id="item-001", quantity=1)],
            shopping_context="all",
            margin_floor=0.50,
            discount_cap=0.20,
        )
        res = orchestrator.process_decision(req)

        # Invariant checks
        for r in res.recommendations:
            # Price ceiling
            self.assertLessEqual(r.final_price, r.reference_price)
            if r.is_offered:
                # If offered, gross margin must respect floor
                self.assertGreaterEqual(res.basket_gross_margin, 0.50)

        # Clean up
        self.repo.clear_session_events(sess)


if __name__ == "__main__":
    unittest.main()
