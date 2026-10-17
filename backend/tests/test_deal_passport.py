"""Automated Tests for Fair Deal Passport & Counterfactual Offer Transparency (Step 5.17)

Verifies:
1. Exact integer-cent counterfactual scenario calculations using actual seeded product costs.
2. The illustrative $65 mouse + $55 stand scenario (No discount $120.00, approved 10% $114.50, rejected 15% $111.75 under 50% floor).
3. Cart quote consistency: approved passport offer matches final basket quote.
4. Margin floor rejection: alternatives breaching margin floor are explicitly rejected with human-readable rationale.
5. Dynamic recalculation when cart or policy parameters change.
6. Deterministic snapshot hashing for cache freshness and stale-data prevention.
7. Confidentiality protection: zero supplier COGS or dollar profits disclosed on shopper surface (view_mode="shopper").
8. Full merchant metrics disclosed exclusively on merchant surface (view_mode="merchant").
9. Local SQLite hermetic test isolation.
10. End-to-end HTTP API via FastAPI TestClient.
"""

import unittest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.engine import DecisionOrchestrator
from backend.app.models.schemas import (
    CartItemInput,
    DealPassportRequest,
    DecisionRequest,
)
from backend.app.config import settings
from backend.app.db.database import is_postgres


class TestFairDealPassport(unittest.TestCase):
    """Unit and integration tests for the Fair Deal Passport engine."""

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)
        cls.orchestrator = DecisionOrchestrator()

    def test_00_test_isolation(self):
        """Ensures tests run strictly against local SQLite and never touch live Neon PostgreSQL."""
        self.assertFalse(
            is_postgres(settings.DATABASE_URL),
            "FATAL: Tests must execute against local SQLite test fixtures, never production PostgreSQL."
        )

    def test_01_illustrative_mouse_and_stand_scenario(self):
        """Verifies the exact illustrative $65 mouse + $55 stand scenario from actual seeded costs.
        Catalogue data:
        - item-003 (Precision Vertical Wireless Mouse): ref $65.00, cogs $32.00
        - item-005 (Aluminum Monitor Riser Stand): ref $55.00, cogs $25.00
        - Total reference price: $120.00, Total COGS: $57.00
        Expected outcomes with 50% margin floor:
        - Scenario 1 (No discount): $120.00 subtotal, $0 savings, 52.5% margin -> Approved.
        - Scenario 2 (Approved 10%): $114.50 subtotal, $5.50 savings, 50.2% margin -> Approved.
        - Scenario 3 (Alternative 15%): $111.75 subtotal, $8.25 savings, 49.0% margin -> Rejected (below 50% floor).
        """
        req = DealPassportRequest(
            cart_items=[CartItemInput(product_id="item-003", quantity=1)],
            candidate_product_id="item-005",
            candidate_discount_pct=0.10,
            alternative_discount_pct=0.15,
            margin_floor=0.50,
            discount_cap=0.20,
            view_mode="merchant",
        )
        passport = self.orchestrator.generate_deal_passport(req)

        self.assertEqual(passport.candidate_product_id, "item-005")
        self.assertEqual(passport.candidate_reference_price, 55.00)
        self.assertEqual(passport.active_margin_floor, 0.50)
        self.assertEqual(passport.active_discount_cap, 0.20)
        self.assertEqual(len(passport.scenarios), 3)

        scenarios_by_id = {s.scenario_id: s for s in passport.scenarios}

        # Scenario 1: No discount
        s1 = scenarios_by_id["no_discount"]
        self.assertEqual(s1.discount_percentage, 0.0)
        self.assertEqual(s1.candidate_price, 55.00)
        self.assertEqual(s1.candidate_savings, 0.0)
        self.assertEqual(s1.basket_subtotal, 120.00)
        self.assertEqual(s1.basket_savings, 0.0)
        self.assertAlmostEqual(s1.basket_gross_margin, 0.525, places=3)
        self.assertTrue(s1.is_approved)
        self.assertTrue(s1.policy_checks.margin_floor_passed)

        # Scenario 2: FairCart approved 10% offer
        s2 = scenarios_by_id["faircart_approved"]
        self.assertEqual(s2.discount_percentage, 0.10)
        self.assertEqual(s2.candidate_price, 49.50)
        self.assertEqual(s2.candidate_savings, 5.50)
        self.assertEqual(s2.basket_subtotal, 114.50)
        self.assertEqual(s2.basket_savings, 5.50)
        self.assertAlmostEqual(s2.basket_gross_margin, 0.5022, places=3)
        self.assertTrue(s2.is_approved)
        self.assertTrue(s2.policy_checks.margin_floor_passed)
        self.assertTrue(s2.policy_checks.discount_cap_passed)

        # Scenario 3: Aggressive 15% markdown (counterfactual)
        s3 = scenarios_by_id["aggressive_alternative"]
        self.assertEqual(s3.discount_percentage, 0.15)
        self.assertEqual(s3.candidate_price, 46.75)
        self.assertEqual(s3.candidate_savings, 8.25)
        self.assertEqual(s3.basket_subtotal, 111.75)
        self.assertEqual(s3.basket_savings, 8.25)
        self.assertAlmostEqual(s3.basket_gross_margin, 0.4899, places=3)
        self.assertFalse(s3.is_approved)
        self.assertFalse(s3.policy_checks.margin_floor_passed)
        self.assertIsNotNone(s3.rejection_reason)
        self.assertIn("49.0%", s3.shopper_explanation)

    def test_02_quote_consistency(self):
        """Verifies that the approved passport offer price and subtotal match the authoritative cart quote exactly."""
        req = DealPassportRequest(
            cart_items=[CartItemInput(product_id="item-003", quantity=1)],
            candidate_product_id="item-005",
            candidate_discount_pct=0.10,
            margin_floor=0.50,
            discount_cap=0.20,
            view_mode="shopper",
        )
        passport = self.orchestrator.generate_deal_passport(req)
        approved_scenario = next(s for s in passport.scenarios if s.scenario_id == "faircart_approved")

        # Now simulate customer accepting the bundle: cart contains Mouse + Stand (with 10% off Stand)
        combined_cart = [
            (self.orchestrator.repository.get_entity_by_id("item-003"), 1),
            (self.orchestrator.repository.get_entity_by_id("item-005"), 1),
        ]
        cart_quote = self.orchestrator.calculate_basket_quote(
            combined_cart,
            applied_discounts={"item-005": 0.10},
            margin_floor=0.50,
            discount_cap=0.20,
        )

        # Both authoritative surfaces must report identical subtotal, savings, and line price
        self.assertEqual(cart_quote.final_subtotal, approved_scenario.basket_subtotal)
        self.assertEqual(cart_quote.total_savings, approved_scenario.basket_savings)
        stand_quote_item = next(i for i in cart_quote.items if i.product_id == "item-005")
        self.assertEqual(stand_quote_item.unit_price, approved_scenario.candidate_price)
        self.assertEqual(stand_quote_item.savings, approved_scenario.candidate_savings)

    def test_03_stricter_margin_floor_rejects_10pct_offer(self):
        """Verifies that raising the margin floor to 52% safely rejects the 10% discount."""
        req = DealPassportRequest(
            cart_items=[CartItemInput(product_id="item-003", quantity=1)],
            candidate_product_id="item-005",
            candidate_discount_pct=0.10,
            margin_floor=0.52,  # 52% floor > 50.22% margin
            discount_cap=0.20,
            view_mode="merchant",
        )
        passport = self.orchestrator.generate_deal_passport(req)
        s2 = next(s for s in passport.scenarios if s.scenario_id == "faircart_approved")
        # Under 52% floor, the 10% discount is revoked/unapproved
        self.assertFalse(s2.is_approved)
        self.assertFalse(s2.policy_checks.margin_floor_passed)

    def test_04_lenient_floor_approves_aggressive_alternative(self):
        """Verifies that with a 45% floor, a 15% markdown (48.99% margin) passes the margin floor check."""
        req = DealPassportRequest(
            cart_items=[CartItemInput(product_id="item-003", quantity=1)],
            candidate_product_id="item-005",
            candidate_discount_pct=0.10,
            alternative_discount_pct=0.15,
            margin_floor=0.45,
            discount_cap=0.20,
            view_mode="merchant",
        )
        passport = self.orchestrator.generate_deal_passport(req)
        s3 = next(s for s in passport.scenarios if s.scenario_id == "aggressive_alternative")
        self.assertTrue(s3.is_approved)
        self.assertTrue(s3.policy_checks.margin_floor_passed)
        self.assertIsNone(s3.rejection_reason)

    def test_05_shopper_privacy_scrubs_internal_merchant_economics(self):
        """Guarantees that view_mode='shopper' never discloses supplier COGS or dollar gross profit."""
        req = DealPassportRequest(
            cart_items=[CartItemInput(product_id="item-003", quantity=1)],
            candidate_product_id="item-005",
            candidate_discount_pct=0.10,
            alternative_discount_pct=0.15,
            margin_floor=0.50,
            discount_cap=0.20,
            view_mode="shopper",
        )
        passport = self.orchestrator.generate_deal_passport(req)

        for s in passport.scenarios:
            self.assertIsNone(
                s.merchant_metrics,
                f"Privacy violation: Scenario '{s.scenario_id}' exposed merchant metrics to shopper!"
            )
            # Ensure shopper explanation does not leak supplier wholesale costs
            self.assertNotIn("cogs", s.shopper_explanation.lower())
            self.assertNotIn("$57.00", s.shopper_explanation)
            self.assertNotIn("$32.00", s.shopper_explanation)
            self.assertNotIn("$25.00", s.shopper_explanation)

    def test_06_merchant_view_mode_discloses_full_financial_metrics(self):
        """Guarantees that view_mode='merchant' includes full revenue, COGS, and profit breakdown."""
        req = DealPassportRequest(
            cart_items=[CartItemInput(product_id="item-003", quantity=1)],
            candidate_product_id="item-005",
            candidate_discount_pct=0.10,
            alternative_discount_pct=0.15,
            margin_floor=0.50,
            discount_cap=0.20,
            view_mode="merchant",
        )
        passport = self.orchestrator.generate_deal_passport(req)

        for s in passport.scenarios:
            self.assertIsNotNone(s.merchant_metrics)
            self.assertEqual(s.merchant_metrics.basket_cogs, 57.00)
            self.assertGreater(s.merchant_metrics.basket_revenue, 0)
            self.assertEqual(
                round(s.merchant_metrics.basket_revenue - s.merchant_metrics.basket_cogs, 2),
                s.merchant_metrics.gross_profit,
            )

    def test_07_cart_snapshot_hash_invalidation(self):
        """Verifies that changing cart items, quantities, or policy parameters updates the snapshot hash."""
        req1 = DealPassportRequest(
            cart_items=[CartItemInput(product_id="item-003", quantity=1)],
            candidate_product_id="item-005",
            margin_floor=0.50,
            discount_cap=0.20,
        )
        hash1 = self.orchestrator.generate_deal_passport(req1).cart_snapshot_hash

        # Change quantity
        req2 = DealPassportRequest(
            cart_items=[CartItemInput(product_id="item-003", quantity=2)],
            candidate_product_id="item-005",
            margin_floor=0.50,
            discount_cap=0.20,
        )
        hash2 = self.orchestrator.generate_deal_passport(req2).cart_snapshot_hash
        self.assertNotEqual(hash1, hash2)

        # Change margin floor
        req3 = DealPassportRequest(
            cart_items=[CartItemInput(product_id="item-003", quantity=1)],
            candidate_product_id="item-005",
            margin_floor=0.35,
            discount_cap=0.20,
        )
        hash3 = self.orchestrator.generate_deal_passport(req3).cart_snapshot_hash
        self.assertNotEqual(hash1, hash3)

    def test_08_http_api_post_deal_passport(self):
        """Tests HTTP POST /api/v1/deal-passport endpoint end-to-end via FastAPI TestClient."""
        payload = {
            "cart_items": [{"product_id": "item-003", "quantity": 1}],
            "candidate_product_id": "item-005",
            "candidate_discount_pct": 0.10,
            "alternative_discount_pct": 0.15,
            "margin_floor": 0.50,
            "discount_cap": 0.20,
            "view_mode": "shopper",
        }
        res = self.client.post("/api/v1/deal-passport", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertEqual(data["candidate_product_id"], "item-005")
        self.assertEqual(len(data["scenarios"]), 3)
        self.assertIn("macro_simulation_summary", data)
        self.assertEqual(data["scenarios"][1]["basket_subtotal"], 114.50)
        self.assertEqual(data["scenarios"][2]["is_approved"], False)

    def test_09_decision_endpoint_includes_deal_passport_for_top_rec(self):
        """Tests that POST /api/v1/decision includes a pre-computed deal_passport for the top recommendation."""
        payload = {
            "cart_items": [{"product_id": "item-003", "quantity": 1}],
            "shopping_context": "productivity",
            "margin_floor": 0.20,
            "discount_cap": 0.20,
        }
        res = self.client.post("/api/v1/decision", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        if data.get("recommendation"):
            self.assertIsNotNone(data.get("deal_passport"))
            passport = data["deal_passport"]
            self.assertEqual(passport["candidate_product_id"], data["recommendation"]["product_id"])
            self.assertEqual(len(passport["scenarios"]), 3)

    def test_10_basket_below_margin_floor_regular_price_distinction(self):
        """Verifies that a basket whose catalogue base margin is below the configured margin floor:
        1. Fully revokes any requested promotional discounts to standard regular prices.
        2. Does NOT falsely claim that the configured margin floor has been met.
        3. Accurately distinguishes discount revocation from overall basket policy compliance.
        4. Introduces zero fabricated numbers (exact $120.00 subtotal, $57.00 COGS, 52.5% margin).
        5. Preserves existing 50% floor calculations unchanged.
        """
        # Mouse ($65.00 ref, $32.00 cogs) + Stand ($55.00 ref, $25.00 cogs)
        # Combined: $120.00 revenue, $57.00 COGS, $63.00 profit, 52.5% base margin
        mouse = self.orchestrator.repository.get_entity_by_id("item-003")
        stand = self.orchestrator.repository.get_entity_by_id("item-005")

        # 1. Authoritative Basket Quote check under strict 65% floor
        combined_cart = [(mouse, 1), (stand, 1)]
        quote = self.orchestrator.calculate_basket_quote(
            combined_cart,
            applied_discounts={"item-005": 0.10},  # Requested 10% discount
            margin_floor=0.65,                    # 65% floor > 52.5% base margin
            discount_cap=0.20,
        )
        self.assertEqual(quote.standard_subtotal, 120.00)
        self.assertEqual(quote.final_subtotal, 120.00)
        self.assertEqual(quote.total_savings, 0.00)
        self.assertAlmostEqual(quote.basket_gross_margin, 0.525, places=3)

        # Stand discount must be revoked to 0.0%
        stand_item = next(i for i in quote.items if i.product_id == "item-005")
        self.assertEqual(stand_item.unit_price, 55.00)
        self.assertEqual(stand_item.discount_percentage, 0.0)
        self.assertEqual(stand_item.savings, 0.0)
        self.assertIn("Baseline margin (52.5%) is below 65.0% floor", stand_item.applied_condition)

        # 2. Fair Deal Passport check under strict 65% floor
        req = DealPassportRequest(
            cart_items=[CartItemInput(product_id="item-003", quantity=1)],
            candidate_product_id="item-005",
            candidate_discount_pct=0.10,
            alternative_discount_pct=0.15,
            margin_floor=0.65,
            discount_cap=0.20,
            view_mode="merchant",
        )
        passport = self.orchestrator.generate_deal_passport(req)
        scenarios_by_id = {s.scenario_id: s for s in passport.scenarios}

        # Selected scenario must be "no_discount" since no discount can be approved
        self.assertEqual(passport.selected_scenario_id, "no_discount")

        # Scenario 1 (No discount / Baseline)
        s1 = scenarios_by_id["no_discount"]
        self.assertEqual(s1.candidate_price, 55.00)
        self.assertEqual(s1.basket_subtotal, 120.00)
        self.assertAlmostEqual(s1.basket_gross_margin, 0.525, places=3)
        self.assertFalse(s1.policy_checks.margin_floor_passed, "Regular price quote must not claim 65% floor is met")
        self.assertFalse(s1.is_approved)
        self.assertIsNotNone(s1.rejection_reason)
        self.assertEqual(s1.merchant_metrics.status, "FAIL_MARGIN_DEFICIT")

        # Scenario 2 (FairCart Offer - Revoked)
        s2 = scenarios_by_id["faircart_approved"]
        self.assertEqual(s2.candidate_price, 55.00)
        self.assertEqual(s2.candidate_savings, 0.00)
        self.assertFalse(s2.policy_checks.margin_floor_passed)
        self.assertFalse(s2.is_approved)
        self.assertIn("discounts", s2.rejection_reason.lower())
        self.assertIn("revoked", s2.shopper_explanation.lower())
        self.assertIn("revoked", s2.merchant_explanation.lower())
        self.assertEqual(s2.merchant_metrics.status, "FAIL_MARGIN_DEFICIT")

        # Scenario 3 (Aggressive 15% Alternative)
        s3 = scenarios_by_id["aggressive_alternative"]
        self.assertFalse(s3.policy_checks.margin_floor_passed)
        self.assertFalse(s3.is_approved)
        self.assertEqual(s3.merchant_metrics.status, "FAIL_MARGIN_DEFICIT")


if __name__ == "__main__":
    unittest.main()
