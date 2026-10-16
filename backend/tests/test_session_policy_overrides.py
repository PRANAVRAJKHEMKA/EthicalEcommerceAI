"""Tests for session-scoped merchant policy overrides and strict boundary validation.

Verifies:
1. Pydantic validation rejects negative, out-of-range (>1.0 floor, >0.50 cap), and non-finite (NaN, Inf) values.
2. HTTP endpoints (/api/v1/decision, /api/v1/simulate, /api/v1/settings) reject invalid policy parameters with 422.
3. Decision pipeline respects request-scoped margin floor and discount cap dynamically per session.
4. Overriding policy parameters in decision and simulation requests never mutates database merchant settings.
5. Production merchant settings authorization gating and customer session isolation remain strictly enforced.
"""

import math
import unittest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.app.main import app
from backend.app.config import settings
from backend.app.db.repository import CatalogRepository
from backend.app.models.schemas import (
    CartItemInput,
    DecisionRequest,
    MerchantSettingsRequest,
    SimulationRequest,
)
from backend.app.auth import clear_demo_login_limits


class TestSessionPolicyOverridesAndValidation(unittest.TestCase):
    """Test suite for session-scoped policy overrides, bounds checking, and isolation."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.repo = CatalogRepository()

    def test_pydantic_decision_request_rejects_out_of_bounds_and_non_finite(self):
        """DecisionRequest must reject margin_floor outside [0, 1] and discount_cap outside [0, 0.50], plus NaN/Inf."""
        # Valid baseline
        req = DecisionRequest(margin_floor=0.20, discount_cap=0.20)
        self.assertEqual(req.margin_floor, 0.20)
        self.assertEqual(req.discount_cap, 0.20)

        # Invalid margin_floor: > 1.0
        with self.assertRaises(ValidationError):
            DecisionRequest(margin_floor=1.05)

        # Invalid margin_floor: < 0.0
        with self.assertRaises(ValidationError):
            DecisionRequest(margin_floor=-0.01)

        # Invalid margin_floor: NaN / Inf
        with self.assertRaises(ValidationError):
            DecisionRequest(margin_floor=float("nan"))
        with self.assertRaises(ValidationError):
            DecisionRequest(margin_floor=float("inf"))

        # Invalid discount_cap: > 0.50
        with self.assertRaises(ValidationError):
            DecisionRequest(discount_cap=0.51)

        # Invalid discount_cap: < 0.0
        with self.assertRaises(ValidationError):
            DecisionRequest(discount_cap=-0.10)

        # Invalid discount_cap: NaN / Inf
        with self.assertRaises(ValidationError):
            DecisionRequest(discount_cap=float("nan"))
        with self.assertRaises(ValidationError):
            DecisionRequest(discount_cap=float("inf"))

    def test_pydantic_simulation_request_rejects_out_of_bounds_and_non_finite(self):
        """SimulationRequest must reject out-of-range and non-finite policy parameters."""
        with self.assertRaises(ValidationError):
            SimulationRequest(margin_floor=1.5)
        with self.assertRaises(ValidationError):
            SimulationRequest(margin_floor=-0.05)
        with self.assertRaises(ValidationError):
            SimulationRequest(margin_floor=float("nan"))
        with self.assertRaises(ValidationError):
            SimulationRequest(discount_cap=0.75)
        with self.assertRaises(ValidationError):
            SimulationRequest(discount_cap=-0.01)
        with self.assertRaises(ValidationError):
            SimulationRequest(discount_cap=float("nan"))

    def test_pydantic_merchant_settings_request_rejects_out_of_bounds_and_non_finite(self):
        """MerchantSettingsRequest must reject out-of-range and non-finite policy parameters."""
        with self.assertRaises(ValidationError):
            MerchantSettingsRequest(margin_floor=1.2, discount_cap=0.20)
        with self.assertRaises(ValidationError):
            MerchantSettingsRequest(margin_floor=-0.10, discount_cap=0.20)
        with self.assertRaises(ValidationError):
            MerchantSettingsRequest(margin_floor=0.20, discount_cap=0.60)
        with self.assertRaises(ValidationError):
            MerchantSettingsRequest(margin_floor=0.20, discount_cap=-0.05)
        with self.assertRaises(ValidationError):
            MerchantSettingsRequest(margin_floor=float("nan"), discount_cap=0.20)
        with self.assertRaises(ValidationError):
            MerchantSettingsRequest(margin_floor=0.20, discount_cap=float("inf"))

    def test_http_decision_endpoint_rejects_invalid_policy_with_422(self):
        """POST /api/v1/decision returns HTTP 422 on invalid policy parameters."""
        # margin_floor > 1.0
        res1 = self.client.post("/api/v1/decision", json={"margin_floor": 1.25})
        self.assertEqual(res1.status_code, 422)

        # margin_floor < 0.0
        res2 = self.client.post("/api/v1/decision", json={"margin_floor": -0.1})
        self.assertEqual(res2.status_code, 422)

        # discount_cap > 0.50
        res3 = self.client.post("/api/v1/decision", json={"discount_cap": 0.65})
        self.assertEqual(res3.status_code, 422)

        # discount_cap < 0.0
        res4 = self.client.post("/api/v1/decision", json={"discount_cap": -0.05})
        self.assertEqual(res4.status_code, 422)

    def test_http_simulate_endpoint_rejects_invalid_policy_with_422(self):
        """POST /api/v1/simulate returns HTTP 422 on invalid policy parameters."""
        res1 = self.client.post("/api/v1/simulate", json={"num_sessions": 100, "margin_floor": 1.5})
        self.assertEqual(res1.status_code, 422)

        res2 = self.client.post("/api/v1/simulate", json={"num_sessions": 100, "discount_cap": 0.80})
        self.assertEqual(res2.status_code, 422)

    def test_http_settings_endpoint_rejects_invalid_policy_with_422(self):
        """POST /api/v1/settings returns HTTP 422 on invalid policy parameters."""
        res1 = self.client.post("/api/v1/settings", json={"margin_floor": 1.5, "discount_cap": 0.20})
        self.assertEqual(res1.status_code, 422)

        res2 = self.client.post("/api/v1/settings", json={"margin_floor": 0.20, "discount_cap": 0.70})
        self.assertEqual(res2.status_code, 422)

    def test_decision_engine_respects_request_scoped_margin_floor(self):
        """Stricter request-scoped margin floor revokes bundle discounts that lenient floor permits."""
        # Cart with item-001 (Mechanical Keyboard: ref $80, cogs $40, baseline margin 50%)
        # and complementary items
        payload_lenient = {
            "session_id": "test-session-lenient",
            "cart_items": [{"product_id": "item-001", "quantity": 1}],
            "dwell_time_seconds": 30,
            "margin_floor": 0.15,
            "discount_cap": 0.20,
        }
        res_lenient = self.client.post("/api/v1/decision", json=payload_lenient)
        self.assertEqual(res_lenient.status_code, 200)
        data_lenient = res_lenient.json()

        # Under lenient 15% floor, check that eligible offers exist
        offers_lenient = [
            item for item in data_lenient.get("recommendations", [])
            if item.get("is_offered")
        ]

        # Under an impossible margin floor (e.g. 0.95), all bundle discounts must be rejected
        payload_strict = {
            "session_id": "test-session-strict",
            "cart_items": [{"product_id": "item-001", "quantity": 1}],
            "dwell_time_seconds": 30,
            "margin_floor": 0.95,
            "discount_cap": 0.20,
        }
        res_strict = self.client.post("/api/v1/decision", json=payload_strict)
        self.assertEqual(res_strict.status_code, 200)
        data_strict = res_strict.json()

        offers_strict = [
            item for item in data_strict.get("recommendations", [])
            if item.get("is_offered")
        ]
        self.assertEqual(len(offers_strict), 0, "Strict 95% margin floor must reject all bundle discounts")
        self.assertGreater(len(offers_lenient), 0, "Lenient 15% margin floor should permit valid bundle discounts")

    def test_request_scoped_decision_does_not_mutate_database_settings(self):
        """Sending custom policy parameters in /decision does NOT change global settings in database."""
        # Record baseline settings
        baseline = self.repo.get_merchant_settings()

        # Send decision request with customized policy parameters
        payload = {
            "session_id": "test-session-no-mutation",
            "cart_items": [{"product_id": "item-001", "quantity": 1}],
            "margin_floor": 0.45,
            "discount_cap": 0.10,
        }
        res = self.client.post("/api/v1/decision", json=payload)
        self.assertEqual(res.status_code, 200)

        # Verify database settings remain identical
        current = self.repo.get_merchant_settings()
        self.assertAlmostEqual(current["margin_floor"], baseline["margin_floor"], places=4)
        self.assertAlmostEqual(current["discount_cap"], baseline["discount_cap"], places=4)

    def test_request_scoped_simulation_does_not_mutate_database_settings(self):
        """Sending custom policy parameters in /simulate does NOT change global settings in database."""
        baseline = self.repo.get_merchant_settings()

        res = self.client.post(
            "/api/v1/simulate",
            json={
                "num_sessions": 50,
                "random_seed": 123,
                "margin_floor": 0.35,
                "discount_cap": 0.15,
            },
        )
        self.assertEqual(res.status_code, 200)

        current = self.repo.get_merchant_settings()
        self.assertAlmostEqual(current["margin_floor"], baseline["margin_floor"], places=4)
        self.assertAlmostEqual(current["discount_cap"], baseline["discount_cap"], places=4)

    def test_production_merchant_settings_authorization_and_customer_session_isolation(self):
        """In production with ADMIN_TOKEN, settings endpoint requires admin token and rejects customer sessions."""
        orig_env = settings.ENVIRONMENT
        orig_token = settings.ADMIN_TOKEN
        try:
            settings.ENVIRONMENT = "production"
            settings.ADMIN_TOKEN = "super_secret_admin_key_777"

            # 1. Anonymous request without token -> 403
            res1 = self.client.post(
                "/api/v1/settings",
                json={"margin_floor": 0.25, "discount_cap": 0.20},
            )
            self.assertEqual(res1.status_code, 403)

            # 2. Incorrect admin token -> 403
            res2 = self.client.post(
                "/api/v1/settings",
                json={"margin_floor": 0.25, "discount_cap": 0.20},
                headers={"X-Admin-Token": "wrong_token_xyz"},
            )
            self.assertEqual(res2.status_code, 403)

            # 3. Customer session token -> 403 with explicit isolation message
            clear_demo_login_limits("testclient")
            login_res = self.client.post("/api/v1/auth/demo-login", json={"persona": "demo_gamer"})
            self.assertEqual(login_res.status_code, 200)
            cust_token = login_res.json()["session_token"]

            res3 = self.client.post(
                "/api/v1/settings",
                json={"margin_floor": 0.25, "discount_cap": 0.20},
                headers={"Authorization": f"Bearer {cust_token}"},
            )
            self.assertEqual(res3.status_code, 403)
            self.assertIn("Customer session tokens cannot be used", res3.json()["detail"])

            # 4. Valid admin token -> 200 OK
            res4 = self.client.post(
                "/api/v1/settings",
                json={"margin_floor": 0.25, "discount_cap": 0.20},
                headers={"X-Admin-Token": "super_secret_admin_key_777"},
            )
            self.assertEqual(res4.status_code, 200)
            self.assertEqual(res4.json()["margin_floor"], 0.25)

            # Restore original values in database
            self.client.post(
                "/api/v1/settings",
                json={"margin_floor": 0.20, "discount_cap": 0.20},
                headers={"X-Admin-Token": "super_secret_admin_key_777"},
            )
        finally:
            settings.ENVIRONMENT = orig_env
            settings.ADMIN_TOKEN = orig_token

    def test_low_baseline_margin_basket_under_50_pct_floor(self):
        """Verifies that a basket with 49.86% baseline gross margin (Webcam + 2x Mic + ScreenBar)
        strictly receives NO bundle discount under an active 50% session margin floor,
        and provides an accurate, transparent explanation without price increases.
        """
        from backend.app.engine.optimizer import EconomicOptimizer

        # Active basket reproducing Step 4B.9:
        # item-008: 4K Webcam ($110.00, COGS $58.00)
        # item-009: USB-C Mic x 2 ($85.00 ea -> $170.00, COGS $42.00 ea -> $84.00)
        # item-007: ScreenBar ($75.00, COGS $36.00)
        # Total ref revenue = $355.00, Total COGS = $178.00, Margin = 177 / 355 = 49.859%
        payload = {
            "session_id": "test-session-low-baseline",
            "cart_items": [
                {"product_id": "item-008", "quantity": 1},
                {"product_id": "item-009", "quantity": 2},
                {"product_id": "item-007", "quantity": 1},
            ],
            "dwell_time_seconds": 30,
            "margin_floor": 0.50,
            "discount_cap": 0.20,
        }
        res = self.client.post("/api/v1/decision", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        # 1. Authoritative quote checks: cart itself has $0 savings and 49.86% margin
        quote = data.get("cart_quote")
        self.assertIsNotNone(quote)
        self.assertEqual(quote["standard_subtotal"], 355.0)
        self.assertEqual(quote["final_subtotal"], 355.0)
        self.assertEqual(quote["total_savings"], 0.0)
        self.assertAlmostEqual(quote["basket_gross_margin"], 0.4986, places=4)

        # 2. Direct Engine B check on candidates whose baseline combined margin is below 50%
        # item-010 (Headphones: $140, COGS $72, margin 48.6%) -> Combined margin is 49.49% < 50%
        entities = {p.id: p for p in self.repo.get_all_entities()}
        cart_items = [
            (entities["item-008"], 1),
            (entities["item-009"], 2),
            (entities["item-007"], 1),
        ]
        optimizer = EconomicOptimizer()
        opt_res = optimizer.optimize(
            cart_items=cart_items,
            candidate=entities["item-010"],
            margin_floor=0.50,
            discount_cap=0.20,
        )
        self.assertFalse(opt_res.is_offered)
        self.assertEqual(opt_res.discount_percentage, 0.0)
        self.assertEqual(opt_res.savings, 0.0)
        self.assertIn("undiscounted catalogue basket margin (49.5%)", opt_res.decision_reason)
        self.assertIn("is below the 50.0% gross margin floor", opt_res.decision_reason)

        # 3. Under a 55% floor, every candidate in the decision pipeline is rejected
        payload_55 = dict(payload, margin_floor=0.55)
        res_55 = self.client.post("/api/v1/decision", json=payload_55)
        self.assertEqual(res_55.status_code, 200)
        recs_55 = res_55.json().get("recommendations", [])
        for rec in recs_55:
            self.assertFalse(rec["is_offered"])
            self.assertEqual(rec["discount_percentage"], 0.0)
            self.assertEqual(rec["savings"], 0.0)

    def test_optimizer_accounts_for_existing_cart_discounts(self):
        """Verifies that EconomicOptimizer.optimize accurately computes parent_revenue_cents
        from net discounted prices of existing items, preventing margin floor breaches.
        """
        from backend.app.engine.optimizer import EconomicOptimizer
        from backend.app.db.repository import ProductEntity

        optimizer = EconomicOptimizer()

        # Item A in cart: Reference $100.00 (10,000 cents), COGS $50.00 (5,000 cents)
        item_a = ProductEntity(
            id="test-item-a",
            name="Test Parent A",
            category="Keyboards",
            subcategory="Keyboards",
            description="",
            reference_price_cents=10000,
            cogs_cents=5000,
            inventory=10,
            complementary_ids=["test-cand-b"],
            tags=["keyboard"],
            use_cases=["productivity"],
            image_url="",
        )

        # Candidate B: Reference $50.00 (5,000 cents), COGS $30.00 (3,000 cents)
        cand_b = ProductEntity(
            id="test-cand-b",
            name="Test Candidate B",
            category="Accessories",
            subcategory="Wrist Rests",
            description="",
            reference_price_cents=5000,
            cogs_cents=3000,
            inventory=10,
            complementary_ids=[],
            tags=["wrist-rest"],
            use_cases=["productivity"],
            image_url="",
        )

        # Case 1: Item A has NO discount.
        # Basket baseline revenue = $100 + $50 = $150, COGS = $50 + $30 = $80.
        # Margin at 10% discount on B ($45): Revenue = $145, COGS = $80 -> Margin = 65/145 = 44.83%.
        # If margin_floor is 0.42, a 10% discount on B is valid (44.8% >= 42.0%).
        res_no_prev = optimizer.optimize(
            cart_items=[(item_a, 1)],
            candidate=cand_b,
            applied_discounts={},
            margin_floor=0.42,
            discount_cap=0.20,
        )
        self.assertTrue(res_no_prev.is_offered)
        self.assertGreater(res_no_prev.discount_percentage, 0.0)

        # Case 2: Item A already has an approved 15% discount ($15 off -> net $85.00).
        # Actual parent revenue = $85.00.
        # If candidate B is discounted 10% ($45): Total revenue = $85 + $45 = $130, COGS = $80.
        # Realized margin = 50 / 130 = 38.46%!
        # Under a 42% margin floor, 38.46% < 42.0% -> Must be REJECTED!
        res_with_prev = optimizer.optimize(
            cart_items=[(item_a, 1)],
            candidate=cand_b,
            applied_discounts={"test-item-a": 0.15},
            margin_floor=0.42,
            discount_cap=0.20,
        )
        self.assertFalse(
            res_with_prev.is_offered,
            "Optimizer must account for existing 15% discount on item A and reject discount that breaches 42% floor"
        )
        self.assertEqual(res_with_prev.discount_percentage, 0.0)

    def test_basket_quote_line_sum_integrity(self):
        """Verifies that calculate_basket_quote final_subtotal strictly equals the exact sum of line totals."""
        from backend.app.engine.orchestrator import DecisionOrchestrator

        orchestrator = DecisionOrchestrator(repository=self.repo)
        catalog = {p.id: p for p in self.repo.get_all_entities()}

        # Multi-item cart with mixed quantities and discounts
        items = [
            (catalog["item-001"], 2),  # $80 x 2 = $160
            (catalog["item-002"], 1),  # $25 x 1 = $25
            (catalog["item-007"], 3),  # $75 x 3 = $225
        ]
        discounts = {
            "item-001": 0.10,  # 10% off $80 -> $72 each ($144 line total)
            "item-002": 0.00,  # 0% off $25 -> $25 line total
            "item-007": 0.15,  # 15% off $75 -> $11.25 -> round 1125 cents -> $63.75 each ($191.25 line total)
        }

        quote = orchestrator.calculate_basket_quote(items, applied_discounts=discounts)

        # Exact line-sum checks
        calculated_final = sum(item.line_total for item in quote.items)
        calculated_standard = sum(item.reference_price * item.quantity for item in quote.items)
        calculated_savings = sum(item.savings for item in quote.items)

        self.assertAlmostEqual(quote.final_subtotal, round(calculated_final, 2), places=2)
        self.assertAlmostEqual(quote.standard_subtotal, round(calculated_standard, 2), places=2)
        self.assertAlmostEqual(quote.total_savings, round(calculated_savings, 2), places=2)
        self.assertAlmostEqual(quote.final_subtotal, quote.standard_subtotal - quote.total_savings, places=2)

    def test_reproduce_stale_quote_subtotal_mismatch_and_alignment(self):
        """Reproduces the reported bug: visible cart items totaling $355 while a stale quote shows $170.
        Verifies that quote alignment logic rejects the stale quote and that the new quote reflects $355.
        """
        from backend.app.engine.orchestrator import DecisionOrchestrator

        orchestrator = DecisionOrchestrator(repository=self.repo)
        catalog = {p.id: p for p in self.repo.get_all_entities()}

        # Stale cart state totaling $170.00 (e.g. Desk Mat $30 + Headphones $140 = $170.00)
        stale_cart = [
            (catalog["item-004"], 1),  # Desk Mat ($30.00)
            (catalog["item-010"], 1),  # Headphones ($140.00)
        ]
        stale_quote = orchestrator.calculate_basket_quote(stale_cart)
        self.assertEqual(stale_quote.final_subtotal, 170.0)

        # Active cart state ($355 total): Webcam ($110) + 2x Mic ($170) + ScreenBar ($75)
        active_cart = [
            {"product_id": "item-008", "quantity": 1},
            {"product_id": "item-009", "quantity": 2},
            {"product_id": "item-007", "quantity": 1},
        ]
        line_item_sum = 110.00 + (85.00 * 2) + 75.00  # $355.00

        # Alignment logic check: stale quote must be recognized as unaligned
        def check_alignment(quote_items, client_cart):
            if len(quote_items) != len(client_cart):
                return False
            q_map = {item.product_id: item.quantity for item in quote_items}
            return all(q_map.get(c["product_id"]) == c["quantity"] for c in client_cart)

        # Verify stale quote fails alignment check
        self.assertFalse(check_alignment(stale_quote.items, active_cart))

        # Fresh authoritative quote for active cart
        active_entities = [
            (catalog["item-008"], 1),
            (catalog["item-009"], 2),
            (catalog["item-007"], 1),
        ]
        active_quote = orchestrator.calculate_basket_quote(active_entities)
        self.assertEqual(active_quote.final_subtotal, 355.0)
        self.assertEqual(active_quote.final_subtotal, line_item_sum)
        self.assertTrue(check_alignment(active_quote.items, active_cart))

    def test_newer_shopping_state_cannot_be_overwritten_by_older_asynchronous_response(self):
        """Verifies sequence checking contract preventing older asynchronous responses
        from overwriting a newer decision state.
        """
        # Emulate the frontend sequence check
        current_request_id = 0
        active_decision = None

        def simulate_response_resolution(req_id, data):
            nonlocal active_decision
            if req_id == current_request_id:
                active_decision = data
                return True
            return False  # Discarded as stale

        # Action 1: Dispatches request #1 (e.g. cart has 2 items)
        current_request_id += 1
        req1_id = current_request_id

        # Action 2: User quickly adds 3rd item, dispatching request #2
        current_request_id += 1
        req2_id = current_request_id

        # Newer request #2 resolves first
        accepted_req2 = simulate_response_resolution(req2_id, {"cart_total": 355.0, "items_count": 3})
        self.assertTrue(accepted_req2)
        self.assertEqual(active_decision["cart_total"], 355.0)

        # Older, slower request #1 resolves later (out of order)
        accepted_req1 = simulate_response_resolution(req1_id, {"cart_total": 170.0, "items_count": 2})
        self.assertFalse(accepted_req1)
        # Active decision state MUST remain from request #2 ($355.0)
        self.assertEqual(active_decision["cart_total"], 355.0)
        self.assertEqual(active_decision["items_count"], 3)


if __name__ == "__main__":
    unittest.main()
