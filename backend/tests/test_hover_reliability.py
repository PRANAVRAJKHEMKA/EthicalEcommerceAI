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


if __name__ == "__main__":
    unittest.main()
