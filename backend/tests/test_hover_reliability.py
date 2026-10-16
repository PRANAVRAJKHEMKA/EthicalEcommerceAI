import unittest
import uuid
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.db.repository import CatalogRepository

class TestHoverReliability(unittest.TestCase):
    """Verifies Milestone 6B product-hover interaction reliability, event deduplication,
    dwell time metadata capture, and duplicate rejection.
    """

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.repo = CatalogRepository()

    def test_hover_event_records_dwell_metadata(self):
        """Verifies product_hover events capture intentional dwell durations."""
        session_id = f"test-hover-{uuid.uuid4().hex[:8]}"
        episode_id = f"hover-item-001-{uuid.uuid4().hex[:6]}"

        res = self.client.post("/api/v1/events", json={
            "session_id": session_id,
            "event_type": "product_hover",
            "product_id": "item-001",
            "event_id": episode_id,
            "metadata": {"dwell_ms": 780},
        })
        self.assertEqual(res.status_code, 200)

        events = self.repo.get_session_events(session_id)
        self.assertEqual(len(events), 1)
        evt = events[0]
        self.assertEqual(evt["event_type"], "product_hover")
        self.assertEqual(evt["product_id"], "item-001")
        self.assertEqual(evt.get("metadata", {}).get("dwell_ms"), 780)

    def test_duplicate_hover_event_id_is_deduplicated(self):
        """Verifies duplicate event submissions with identical event_id do not create duplicate records."""
        session_id = f"test-dedup-{uuid.uuid4().hex[:8]}"
        episode_id = f"hover-item-002-{uuid.uuid4().hex[:6]}"

        payload = {
            "session_id": session_id,
            "event_type": "product_hover",
            "product_id": "item-002",
            "event_id": episode_id,
            "metadata": {"dwell_ms": 820},
        }

        # First post
        res1 = self.client.post("/api/v1/events", json=payload)
        self.assertEqual(res1.status_code, 200)

        # Immediate replay of the exact same episode
        res2 = self.client.post("/api/v1/events", json=payload)
        self.assertEqual(res2.status_code, 200)

        events = self.repo.get_session_events(session_id)
        # Must only have 1 event stored in database
        self.assertEqual(len(events), 1)

    def test_dwell_threshold_contract(self):
        """Validates that intentional hover dwell contract (700ms) is reflected in dwell timings."""
        session_id = f"test-threshold-{uuid.uuid4().hex[:8]}"
        # Sub-threshold accidental pointer pass (e.g. 250ms)
        sub_episode = f"pass-{uuid.uuid4().hex[:6]}"
        res = self.client.post("/api/v1/events", json={
            "session_id": session_id,
            "event_type": "product_hover",
            "product_id": "item-003",
            "event_id": sub_episode,
            "metadata": {"dwell_ms": 250},
        })
        self.assertEqual(res.status_code, 200)

        # Intentional dwell (750ms)
        intent_episode = f"dwell-{uuid.uuid4().hex[:6]}"
        res2 = self.client.post("/api/v1/events", json={
            "session_id": session_id,
            "event_type": "product_hover",
            "product_id": "item-003",
            "event_id": intent_episode,
            "metadata": {"dwell_ms": 750},
        })
        self.assertEqual(res2.status_code, 200)

        events = self.repo.get_session_events(session_id)
        self.assertEqual(len(events), 2)
        dwells = [e.get("metadata", {}).get("dwell_ms") for e in events]
        self.assertIn(250, dwells)
        self.assertIn(750, dwells)

    def test_sub_700ms_hover_produces_zero_weight_in_recommender(self):
        """Verifies that accidental pointer crossings (< 700ms) with duration_ms or dwell_ms
        contribute 0.00 interaction weight to the session interest score.
        """
        from backend.app.engine.recommender import calculate_session_interest_score

        # Event with dwell_ms = 300 (below 700ms threshold)
        events_accidental = [
            {
                "event_type": "product_hover",
                "product_id": "item-001",
                "metadata": {"dwell_ms": 300},
                "age_hours": 0.1,
            }
        ]
        score_accidental = calculate_session_interest_score("item-001", events_accidental)
        # Neutral baseline for products with zero qualifying interaction is 0.50
        self.assertEqual(score_accidental, 0.50)

        # Event with duration_ms = 450 (below 700ms threshold)
        events_duration = [
            {
                "event_type": "product_hover",
                "product_id": "item-001",
                "metadata": {"duration_ms": 450},
                "age_hours": 0.1,
            }
        ]
        score_duration = calculate_session_interest_score("item-001", events_duration)
        self.assertEqual(score_duration, 0.50)

    def test_qualifying_700ms_hover_boosts_session_interest_score(self):
        """Verifies that intentional pointer dwell (>= 700ms) contributes positive weight
        to the candidate's session interest score.
        """
        from backend.app.engine.recommender import calculate_session_interest_score

        events_intentional = [
            {
                "event_type": "product_hover",
                "product_id": "item-001",
                "metadata": {"dwell_ms": 750},
                "age_hours": 0.1,
            }
        ]
        score_intentional = calculate_session_interest_score("item-001", events_intentional)
        # Intentional hover must boost interest score above the 0.50 neutral baseline
        self.assertGreater(score_intentional, 0.50)

    def test_spa_page_view_navigation_event_recording(self):
        """Verifies that SPA page navigation events are recorded with view metadata and deduplicated."""
        session_id = f"test-nav-{uuid.uuid4().hex[:8]}"
        episode_id = f"nav-store-{uuid.uuid4().hex[:6]}"

        res = self.client.post("/api/v1/events", json={
            "session_id": session_id,
            "event_type": "page_view",
            "shopping_context": "productivity",
            "event_id": episode_id,
            "metadata": {"page": "store"},
        })
        self.assertEqual(res.status_code, 200)

        # Immediate duplicate submission
        res_dup = self.client.post("/api/v1/events", json={
            "session_id": session_id,
            "event_type": "page_view",
            "shopping_context": "productivity",
            "event_id": episode_id,
            "metadata": {"page": "store"},
        })
        self.assertEqual(res_dup.status_code, 200)

        events = self.repo.get_session_events(session_id)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], "page_view")
        self.assertEqual(events[0].get("metadata", {}).get("page"), "store")

    def test_client_hovered_product_ids_influence_decision_immediately(self):
        """Phase 3 / 5: Verifies that client-side hovered_product_ids directly in DecisionRequest
        create hover anchors and shape recommendations without waiting for slow analytics DB persistence.
        """
        session_id = f"test-hover-imm-{uuid.uuid4().hex[:8]}"

        # Baseline empty-cart decision (cold start)
        res_baseline = self.client.post("/api/v1/decision", json={
            "session_id": session_id,
            "cart_items": [],
            "shopping_context": "productivity",
            "viewed_product_ids": [],
            "hovered_product_ids": [],
        })
        self.assertEqual(res_baseline.status_code, 200)
        base_sources = [r["recommendation_source"] for r in res_baseline.json()["recommendations"]]
        self.assertNotIn("product_hover", base_sources)

        # Immediate decision with client-side hovered_product_ids: ['item-004'] (Desk Mat)
        res_hovered = self.client.post("/api/v1/decision", json={
            "session_id": session_id,
            "cart_items": [],
            "shopping_context": "productivity",
            "viewed_product_ids": [],
            "hovered_product_ids": ["item-004"],
        })
        self.assertEqual(res_hovered.status_code, 200)
        hov_recs = res_hovered.json()["recommendations"]
        hov_sources = [r["recommendation_source"] for r in hov_recs]
        # Must immediately surface product_hover recommendations
        self.assertIn("product_hover", hov_sources)
        # Complements of item-004 include item-001 and item-003
        hov_ids = [r["product_id"] for r in hov_recs]
        self.assertTrue("item-001" in hov_ids or "item-003" in hov_ids)

    def test_persisted_interaction_events_become_available_to_later_recommendations(self):
        """Phase 3 / 5: Verifies that confirmed persisted events in session_events become available
        to later recommendation decisions without client re-sending them.
        """
        session_id = f"test-persist-avail-{uuid.uuid4().hex[:8]}"

        # Persist a qualifying product_hover event (750ms dwell) to the DB
        res_evt = self.client.post("/api/v1/events", json={
            "session_id": session_id,
            "event_type": "product_hover",
            "product_id": "item-004",  # Desk Mat
            "event_id": f"persist-{uuid.uuid4().hex[:6]}",
            "metadata": {"duration_ms": 750, "dwell_ms": 750},
        })
        self.assertEqual(res_evt.status_code, 200)

        # Later decision request with empty client hovered_product_ids and empty cart
        res_dec = self.client.post("/api/v1/decision", json={
            "session_id": session_id,
            "cart_items": [],
            "shopping_context": "productivity",
            "viewed_product_ids": [],
            "hovered_product_ids": [],
        })
        self.assertEqual(res_dec.status_code, 200)
        recs = res_dec.json()["recommendations"]
        sources = [r["recommendation_source"] for r in recs]
        self.assertIn("product_hover", sources)
        rec_ids = [r["product_id"] for r in recs]
        self.assertTrue("item-001" in rec_ids or "item-003" in rec_ids)

    def test_cross_session_isolation_guaranteed(self):
        """Phase 5: Verifies that one session's policy overrides and interaction signals
        cannot contaminate another session's recommendations or pricing.
        """
        sess_a = f"sess-a-{uuid.uuid4().hex[:8]}"
        sess_b = f"sess-b-{uuid.uuid4().hex[:8]}"

        # Session A applies a strict 55% margin floor
        res_a = self.client.post("/api/v1/decision", json={
            "session_id": sess_a,
            "cart_items": [
                {"product_id": "item-001", "quantity": 1},
                {"product_id": "item-003", "quantity": 1},
            ],
            "margin_floor": 0.55,
            "discount_cap": 0.20,
        })
        self.assertEqual(res_a.status_code, 200)
        data_a = res_a.json()
        # Session A has NO_OFFER because basket margin is below 55%
        self.assertEqual(data_a["decision"], "NO_OFFER")

        # Session B uses standard 20% margin floor for the identical cart
        res_b = self.client.post("/api/v1/decision", json={
            "session_id": sess_b,
            "cart_items": [
                {"product_id": "item-001", "quantity": 1},
                {"product_id": "item-003", "quantity": 1},
            ],
            "margin_floor": 0.20,
            "discount_cap": 0.20,
        })
        self.assertEqual(res_b.status_code, 200)
        data_b = res_b.json()
        # Session B receives OFFER_APPLIED because basket margin exceeds 20%
        self.assertEqual(data_b["decision"], "OFFER_APPLIED")


if __name__ == "__main__":
    unittest.main()
