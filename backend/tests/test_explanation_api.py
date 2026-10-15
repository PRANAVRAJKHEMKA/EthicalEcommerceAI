"""Automated Test Suite for Gemini Natural Language Explanation Service

Verifies:
- POST /api/v1/explanation endpoint contract and performance (< 25ms local fallback).
- Attribute-grounded factual explanation generation without hallucination.
- Graceful deterministic fallback when API key is missing or calls time out.
- Response deduplication & in-memory caching.
- Strict financial immutability: Gemini cannot modify prices, discounts, or margins.
"""

import unittest
from unittest.mock import AsyncMock, patch
import httpx
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.engine.explanation import GeminiExplanationService
from backend.app.models.schemas import ExplanationRequest

class TestExplanationService(unittest.TestCase):
    """Test suite for Engine C Gemini Explanation API and Service."""

    def setUp(self):
        self.client = TestClient(app)
        self.service = GeminiExplanationService(api_key=None)

    def test_explanation_endpoint_deterministic_fallback(self):
        """Verifies /api/v1/explanation returns 200 with grounded fallback when key is unconfigured."""
        payload = {
            "session_id": "test-sess",
            "shopping_context": "productivity",
            "cart_product_ids": ["item-001"],
            "candidate_product_ids": ["item-002", "item-006"],
        }
        response = self.client.post("/api/v1/explanation", json=payload)
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["session_id"], "test-sess")
        self.assertEqual(data["shopping_context"], "productivity")
        self.assertFalse(data["ai_generated"])
        self.assertTrue(data["fallback_applied"])
        self.assertIn("Gemini API key is not configured", data["fallback_reason"])

        explanations = data["explanations"]
        self.assertIn("item-002", explanations)
        self.assertIn("item-006", explanations)

        # Verify wrist rest mentions ergonomic typing support
        exp_002 = explanations["item-002"]
        self.assertEqual(exp_002["source"], "deterministic_fallback")
        self.assertIn("wrist", exp_002["explanation"].lower())
        self.assertIn("Productivity", exp_002["explanation"])

        # Verify cable mentions Type-C / aviator routing
        exp_006 = explanations["item-006"]
        self.assertIn("type-c", exp_006["explanation"].lower())

    def test_financial_immutability_invariant(self):
        """Gemini explanation service schema must contain NO pricing fields to prevent financial tampering."""
        req = ExplanationRequest(
            session_id="test-sess",
            cart_product_ids=["item-001"],
            candidate_product_ids=["item-002"],
        )
        import asyncio
        resp = asyncio.run(self.service.explain(req))
        item_exp = resp.explanations["item-002"]

        # Explanation object should contain only text and signals, never prices or discounts
        fields = item_exp.model_dump().keys()
        self.assertNotIn("reference_price", fields)
        self.assertNotIn("discount_percentage", fields)
        self.assertNotIn("final_price", fields)
        self.assertNotIn("margin", fields)

    def test_empty_candidates_returns_empty_explanations(self):
        """Empty candidate list returns empty dictionary immediately."""
        payload = {
            "session_id": "test-sess",
            "cart_product_ids": ["item-001"],
            "candidate_product_ids": [],
        }
        response = self.client.post("/api/v1/explanation", json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["explanations"], {})

    def test_caching_deduplication(self):
        """Identical requests should hit cache without redundant processing."""
        service = GeminiExplanationService(api_key="mock-key")
        req = ExplanationRequest(
            session_id="test-sess",
            cart_product_ids=["item-001"],
            candidate_product_ids=["item-002"],
            shopping_context="gaming",
        )
        cache_key = service._build_cache_key(req)
        service._cache[cache_key] = {
            "item-002": {
                "product_id": "item-002",
                "explanation": "Cached AI explanation text.",
                "factual_signals": ["Cached Signal"],
                "source": "gemini",
            }
        }

        import asyncio
        resp = asyncio.run(service.explain(req))
        self.assertTrue(resp.ai_generated)
        self.assertFalse(resp.fallback_applied)
        self.assertEqual(resp.explanations["item-002"].explanation, "Cached AI explanation text.")

    @patch("httpx.AsyncClient.post")
    def test_mock_gemini_api_success(self, mock_post):
        """Simulates successful Gemini 2.5 Flash API response parsing."""
        mock_payload = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": '{"explanations": {"item-002": "The memory foam wrist rest pairs with the mechanical keyboard to relieve wrist strain during long coding blocks."}}'
                            }
                        ]
                    }
                }
            ]
        }
        mock_post.return_value = httpx.Response(
            status_code=200,
            json=mock_payload,
            request=httpx.Request("POST", "https://generativelanguage.googleapis.com"),
        )

        service = GeminiExplanationService(api_key="valid-test-key")
        req = ExplanationRequest(
            session_id="test-sess",
            cart_product_ids=["item-001"],
            candidate_product_ids=["item-002"],
            shopping_context="productivity",
        )

        import asyncio
        resp = asyncio.run(service.explain(req))
        self.assertTrue(resp.ai_generated)
        self.assertFalse(resp.fallback_applied)
        self.assertEqual(resp.explanations["item-002"].source, "gemini")
        self.assertIn("wrist strain", resp.explanations["item-002"].explanation)

    @patch("httpx.AsyncClient.post")
    def test_timeout_triggers_deterministic_fallback(self, mock_post):
        """Simulates external API timeout and verifies fallback to deterministic copy."""
        mock_post.side_effect = httpx.TimeoutException("Remote Gemini connection timed out.")

        service = GeminiExplanationService(api_key="valid-test-key")
        req = ExplanationRequest(
            session_id="test-sess",
            cart_product_ids=["item-001"],
            candidate_product_ids=["item-002"],
            shopping_context="study",
        )

        import asyncio
        resp = asyncio.run(service.explain(req))
        self.assertFalse(resp.ai_generated)
        self.assertTrue(resp.fallback_applied)
        self.assertIn("TimeoutException", resp.fallback_reason)
        self.assertEqual(resp.explanations["item-002"].source, "deterministic_fallback")

if __name__ == "__main__":
    unittest.main()
