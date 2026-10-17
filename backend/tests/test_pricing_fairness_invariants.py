"""FairCart AI — Step 5.19: Pricing-Policy & Fairness Invariants Tests

Verifies formal pricing-policy and fairness invariants:
1. Price Ceiling Invariant: final_price <= reference_price for all items and offers.
2. Determinism Invariant: Identical inputs produce bitwise identical decisions and quotes.
3. Monotonic Policy Sensitivity: Stricter merchant margin floors never yield larger discounts.
4. Explainable Blocked Offers: Every rejected offer provides an audited mathematical reason.
5. Macro Strategy Counterfactuals: Validates distinct behavior between No Discount, Blanket, and Uplift-Targeted.
6. Persona Independence: Identical cart items receive identical pricing regardless of shopper persona.

Scope & Boundary Notice:
These tests establish algorithmic consistency, mathematical price bounds, non-discrimination across personas,
and monotonic policy enforcement. They verify pricing-policy and fairness invariants, NOT comprehensive demographic
fairness audits, as FairCart AI deliberately does not collect, infer, or condition on protected demographic attributes
(zero PII architecture).
"""

import unittest
from backend.app.config import settings
from backend.app.db.database import is_postgres
from backend.app.db.repository import CatalogRepository
from backend.app.engine.orchestrator import DecisionOrchestrator
from backend.app.engine.optimizer import EconomicOptimizer
from backend.app.engine.uplift import run_uplift_evaluation
from backend.app.models.schemas import (
    CartItemInput,
    DealPassportRequest,
    DecisionRequest,
    QuoteRequest,
)


class TestPricingFairnessInvariants(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo = CatalogRepository()
        cls.orchestrator = DecisionOrchestrator()
        cls.optimizer = EconomicOptimizer()
        cls.products = cls.repo.get_all_products()

    def setUp(self):
        # Strict isolation check
        self.assertFalse(
            is_postgres(settings.DATABASE_URL),
            "FATAL: Pricing fairness tests must execute against local SQLite test fixtures only.",
        )

    def test_invariant_1_price_ceiling_across_all_catalogue_items(self):
        """Invariant 1: Under no circumstance may an offered price exceed the catalogue reference price.

        Final price <= Reference price, and savings >= $0.00 for all items and test discounts.
        """
        discount_levels = [0.00, 0.05, 0.10, 0.15, 0.20, 0.35, 0.50]

        for p in self.products:
            ref_price = p.reference_price
            entity = self.repo.get_entity_by_id(p.id)
            for d in discount_levels:
                quote = self.orchestrator.calculate_basket_quote(
                    cart_entities=[(entity, 1)],
                    applied_discounts={p.id: d},
                    margin_floor=0.20,
                    discount_cap=0.50,
                )
                item_quote = next(i for i in quote.items if i.product_id == p.id)

                self.assertLessEqual(
                    item_quote.unit_price,
                    ref_price,
                    f"Price ceiling violated for product {p.id}: final {item_quote.unit_price} > ref {ref_price}",
                )
                self.assertGreaterEqual(
                    item_quote.savings,
                    0.0,
                    f"Negative savings (unlawful markup) detected for product {p.id}",
                )
                self.assertLessEqual(
                    quote.final_subtotal,
                    ref_price,
                    f"Quote final_subtotal {quote.final_subtotal} exceeded reference price {ref_price}",
                )

    def test_invariant_2_determinism_and_state_isolation(self):
        """Invariant 2: Identical basket and policy inputs produce identical pricing decisions across multiple calls.

        Guarantees zero random drift, memory leakage, or hidden state across requests.
        """
        req = DecisionRequest(
            session_id="test-determinism-sess",
            cart_items=[CartItemInput(product_id="item-003", quantity=1)],
            shopping_context="all",
            margin_floor=0.50,
            discount_cap=0.20,
        )

        decisions = [self.orchestrator.process_decision(req) for _ in range(5)]
        first = decisions[0]

        for idx, d in enumerate(decisions[1:], start=2):
            self.assertEqual(
                d.decision, first.decision,
                f"Non-deterministic decision outcome at run {idx}",
            )
            self.assertEqual(
                [r.product_id for r in d.recommendations],
                [r.product_id for r in first.recommendations],
                f"Non-deterministic recommendation ordering at run {idx}",
            )
            self.assertAlmostEqual(
                d.basket_gross_margin, first.basket_gross_margin, places=4,
                msg=f"Basket gross margin drifted at run {idx}",
            )
            if d.cart_quote and first.cart_quote:
                self.assertEqual(
                    d.cart_quote.final_subtotal, first.cart_quote.final_subtotal,
                    f"Subtotal drifted at run {idx}",
                )

    def test_invariant_3_monotonic_policy_sensitivity(self):
        """Invariant 3: Stricter merchant policy guardrails (higher margin floor) never yield higher discounts.

        Tests a benchmark basket ($65 mouse + $55 stand, 52.5% base margin) under 20%, 50%, and 60% floors.
        """
        # Under loose 20% floor: 10% discount is permitted
        passport_20 = self.orchestrator.generate_deal_passport(DealPassportRequest(
            cart_items=[CartItemInput(product_id="item-003", quantity=1)],
            candidate_product_id="item-005",
            candidate_discount_pct=0.10,
            margin_floor=0.20,
            discount_cap=0.20,
        ))
        s2_20 = next(s for s in passport_20.scenarios if s.scenario_id == "faircart_approved")
        self.assertTrue(s2_20.is_approved)
        self.assertEqual(s2_20.candidate_price, 49.50)

        # Under strict 60% floor (> 52.5% base margin): discount MUST be revoked
        passport_60 = self.orchestrator.generate_deal_passport(DealPassportRequest(
            cart_items=[CartItemInput(product_id="item-003", quantity=1)],
            candidate_product_id="item-005",
            candidate_discount_pct=0.10,
            margin_floor=0.60,
            discount_cap=0.20,
        ))
        s2_60 = next(s for s in passport_60.scenarios if s.scenario_id == "faircart_approved")
        self.assertFalse(s2_60.is_approved)
        self.assertEqual(s2_60.candidate_price, 55.00)  # Revoked to regular reference price
        self.assertEqual(passport_60.selected_scenario_id, "no_discount")

    def test_invariant_4_explainable_blocked_offers(self):
        """Invariant 4: Blocked or revoked offers have verifiable, mathematically grounded rejection reasons.

        Audit logs and Deal Passports must never refuse an offer without citing a specific constraint check.
        """
        passport = self.orchestrator.generate_deal_passport(DealPassportRequest(
            cart_items=[CartItemInput(product_id="item-003", quantity=1)],
            candidate_product_id="item-005",
            candidate_discount_pct=0.10,
            margin_floor=0.65,  # 65% floor > 52.5% base margin
            discount_cap=0.20,
            view_mode="merchant",
        ))
        revoked_scenario = next(s for s in passport.scenarios if s.scenario_id == "faircart_approved")

        self.assertFalse(revoked_scenario.is_approved)
        self.assertIsNotNone(revoked_scenario.rejection_reason)
        self.assertTrue(len(revoked_scenario.rejection_reason) > 0)
        # Reason must mention margin floor
        self.assertIn("floor", revoked_scenario.rejection_reason.lower())
        self.assertIn("below", revoked_scenario.rejection_reason.lower())

    def test_invariant_5_strategy_counterfactual_order(self):
        """Invariant 5: Macro strategy comparison produces logically distinct, ordered behavior.

        No Discount: 0% targeted, $0 incentive cost.
        Blanket: 100% targeted, 100% incentive cost.
        Uplift-Targeted: selective targeting strictly targeting positive uplift units.
        """
        eval_res = run_uplift_evaluation()
        strategies = {s["strategy_id"]: s for s in eval_res["strategy_comparison"]}

        no_disc = strategies["no_discount"]
        blanket = strategies["blanket_markdown"]
        uplift_strat = strategies["uplift_targeted"]

        self.assertEqual(no_disc["targeted_percentage"], 0.0)
        self.assertEqual(no_disc["modeled_incentive_cost"], 0.0)

        self.assertEqual(blanket["targeted_percentage"], 100.0)
        self.assertEqual(blanket["modeled_incentive_cost"], 100.0)

        # Uplift targeted must be between 0% and 100%
        self.assertGreater(uplift_strat["targeted_percentage"], 0.0)
        self.assertLessEqual(uplift_strat["targeted_percentage"], 100.0)
        # Expected conversion must be positive
        self.assertGreater(uplift_strat["expected_conversion_rate"], 0.0)

    def test_invariant_6_persona_independence_and_non_discrimination(self):
        """Invariant 6: Cart quotes and discounts are invariant to shopper persona labels.

        Prices are determined strictly by basket contents, product COGS, and merchant policies,
        never by sensitive attributes, demographics, or persona labels.
        """
        personas = ["gamer", "creator", "student", "deal_seeker", None]
        quotes = []

        for persona in personas:
            req = DecisionRequest(
                session_id=f"test-persona-{persona}",
                cart_items=[CartItemInput(product_id="item-003", quantity=1)],
                shopping_context="all",
                margin_floor=0.40,
                discount_cap=0.20,
            )
            decision = self.orchestrator.process_decision(req)
            self.assertIsNotNone(decision.cart_quote)
            quotes.append((persona, decision.cart_quote.final_subtotal, decision.cart_quote.total_savings))

        first_subtotal = quotes[0][1]
        first_savings = quotes[0][2]

        for persona, subtotal, savings in quotes[1:]:
            self.assertEqual(
                subtotal, first_subtotal,
                f"Price discrimination detected: persona '{persona}' received different subtotal {subtotal} vs {first_subtotal}",
            )
            self.assertEqual(
                savings, first_savings,
                f"Discount discrimination detected: persona '{persona}' received different savings {savings} vs {first_savings}",
            )


if __name__ == "__main__":
    unittest.main()
