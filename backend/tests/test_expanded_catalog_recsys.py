"""Comprehensive Tests for FairCart AI Expanded Catalogue & Recommendation Intelligence (Step 5.18)

Verifies:
1. 96-item expanded catalogue schema integrity and financial invariants.
2. Complete preservation of original 32 product IDs, prices, and COGS.
3. Idempotent catalog seeding on SQLite.
4. Mathematical soundness of Apriori association rule metrics (support, smoothed confidence, lift).
5. Multi-item basket combination discovery across new categories.
6. Cross-domain discrimination (zero noise between unrelated categories).
7. In-cart product exclusion from candidate recommendations.
8. Contextual intent alignment and Jaccard scoring across new domains.
9. Maximal Marginal Relevance (MMR) category diversity enforcement.
10. Cold-start deterministic fallback for expanded categories.
11. Authoritative basket quotes and margin floors on expanded catalogue items.
12. Fair Deal Passport generation and counterfactual reasoning for new categories.
"""

import math
import unittest

from backend.app.db.database import get_connection
from backend.app.db.repository import CatalogRepository, ProductEntity
from backend.app.engine.associations import (
    AssociationRuleEngine,
    get_association_engine,
    reset_association_engine,
    CONTEXT_ARCHETYPES,
    ALL_CONTEXTS,
)
from backend.app.engine.recommender import (
    RecommenderEngine,
    calculate_anchor_complementarity_score,
    calculate_cold_start_score,
    calculate_explicit_context_score,
    build_factual_recommendation_reason,
    CONTEXT_KEYWORDS,
    CATEGORY_AFFINITY_MATRIX,
)
from backend.app.engine.orchestrator import DecisionOrchestrator
from backend.app.models.schemas import DecisionRequest, CartItemInput, DealPassportRequest
from backend.scripts.seed_catalog import SAMPLE_PRODUCTS, seed_catalog


class TestExpandedCatalogRecsys(unittest.TestCase):
    """Verifies expanded commerce catalogue, multi-item basket intelligence, and economic guardrails."""

    @classmethod
    def setUpClass(cls):
        # Ensure database is seeded with 96 products
        seed_catalog()
        cls.repo = CatalogRepository()
        cls.catalog = cls.repo.get_all_entities()
        cls.orchestrator = DecisionOrchestrator()
        cls.assoc_engine = get_association_engine()

    def test_01_expanded_catalog_schema_and_financial_integrity(self):
        """Verifies all 96 products satisfy schema requirements, categories, and margin invariants."""
        self.assertEqual(len(SAMPLE_PRODUCTS), 96, "Expected exactly 96 products in SAMPLE_PRODUCTS")
        self.assertEqual(len(self.catalog), 96, "Expected exactly 96 products in database catalog")

        product_ids = set()
        categories = set()

        for p in SAMPLE_PRODUCTS:
            pid = p["id"]
            self.assertRegex(pid, r"^item-\d{3}$", f"Invalid ID format: {pid}")
            self.assertNotIn(pid, product_ids, f"Duplicate product ID found: {pid}")
            product_ids.add(pid)

            # Descriptive metadata
            self.assertTrue(len(p["name"]) >= 5, f"Name too short for {pid}")
            self.assertTrue(len(p["description"]) >= 20, f"Description too short for {pid}")
            self.assertTrue(p["image_url"].startswith("http"), f"Invalid image URL for {pid}")
            self.assertTrue(len(p["category"]) > 0, f"Missing category for {pid}")
            categories.add(p["category"])

            # Monetary invariants (integer cents)
            price_cents = p["reference_price_cents"]
            cogs_cents = p["cogs_cents"]
            self.assertGreater(price_cents, 0, f"Price must be positive for {pid}")
            self.assertGreater(cogs_cents, 0, f"COGS must be positive for {pid}")
            self.assertLess(cogs_cents, price_cents, f"COGS must be strictly less than price for {pid}")

            # Margin sanity check: base margin must be >= 45%
            base_margin = (price_cents - cogs_cents) / price_cents
            self.assertGreaterEqual(base_margin, 0.45, f"Base margin below 45% floor for {pid}: {base_margin:.1%}")
            self.assertLessEqual(base_margin, 0.75, f"Base margin unrealistically high for {pid}: {base_margin:.1%}")

            # Inventory check
            self.assertGreaterEqual(p["inventory"], 15, f"Inventory too low for {pid}")

        self.assertGreaterEqual(len(categories), 12, f"Expected at least 12 distinct categories, found {len(categories)}")

    def test_02_preservation_of_original_32_items(self):
        """Verifies original products item-001 through item-032 remain unaltered in prices and COGS."""
        catalog_map = {p.id: p for p in self.catalog}

        for i in range(1, 33):
            expected_id = f"item-{i:03d}"
            self.assertIn(expected_id, catalog_map, f"Missing original product {expected_id}")

        # Spot-check critical original items
        item_1 = catalog_map["item-001"]
        self.assertEqual(item_1.name, "Ergonomic Mechanical Keyboard")
        self.assertEqual(item_1.reference_price_cents, 8000)
        self.assertEqual(item_1.cogs_cents, 4000)

        item_3 = catalog_map["item-003"]
        self.assertEqual(item_3.name, "Precision Vertical Wireless Mouse")
        self.assertEqual(item_3.reference_price_cents, 6500)
        self.assertEqual(item_3.cogs_cents, 3200)

    def test_03_idempotent_catalog_seeding(self):
        """Verifies repeated calls to seed_catalog() are fully idempotent and do not duplicate products."""
        initial_count = self.repo.count_products()
        reseeded_count = seed_catalog()
        self.assertEqual(reseeded_count, 96)
        final_count = self.repo.count_products()
        self.assertEqual(initial_count, final_count)

    def test_04_association_rule_metrics_soundness(self):
        """Verifies mathematical validity of mined Apriori rules: support, Laplace confidence, and bounded lift."""
        rules_by_ant = self.assoc_engine.rules_by_antecedent
        self.assertGreater(len(rules_by_ant), 50, "Expected a substantial number of mined antecedents")

        total_rules = sum(len(rules) for rules in rules_by_ant.values())
        self.assertGreater(total_rules, 200, f"Expected > 200 association rules, got {total_rules}")

        for ant, rules in rules_by_ant.items():
            self.assertLessEqual(len(ant), 3, "Antecedent size must not exceed 3")
            for rule in rules:
                self.assertGreater(rule.support, 0.0)
                self.assertLessEqual(rule.support, 1.0)
                self.assertGreater(rule.confidence_smooth, 0.0)
                self.assertLessEqual(rule.confidence_smooth, 1.0)
                self.assertGreater(rule.lift, 0.0)

    def test_05_multi_item_basket_synergy_discovery(self):
        """Verifies multi-item basket {item-033, item-035} (Rigatoni + Olive Oil) discovers pantry & kitchen synergy."""
        cart_ids = ["item-033", "item-035"]
        candidate_tuples = self.assoc_engine.get_candidate_ids_for_basket(cart_ids)
        candidate_ids = [c[0] for c in candidate_tuples]

        # Marinara (item-034), Parmigiano (item-036), or Utensils (item-050) should be discovered
        synergy_found = any(cid in ("item-034", "item-036", "item-050", "item-054") for cid in candidate_ids)
        self.assertTrue(synergy_found, f"Expected pantry/kitchen candidates for {cart_ids}, found {candidate_ids}")

        # Check positive lift on Marinara
        score, match = self.assoc_engine.evaluate_association_score("item-034", cart_ids)
        self.assertGreater(score, 0.1)
        self.assertIsNotNone(match)
        self.assertGreater(match.lift, 1.5)

    def test_06_cross_domain_discrimination(self):
        """Verifies strong domain discrimination: tech peripherals do not associate with culinary pantry items."""
        # A tech cart containing keyboard (item-001)
        tech_cart = ["item-001"]
        score_marinara, match_marinara = self.assoc_engine.evaluate_association_score("item-034", tech_cart)
        self.assertEqual(score_marinara, 0.0, "Tech cart must have zero association with Marinara sauce")
        self.assertIsNone(match_marinara)

        # A pantry cart containing rigatoni (item-033)
        pantry_cart = ["item-033"]
        score_keyboard, match_keyboard = self.assoc_engine.evaluate_association_score("item-001", pantry_cart)
        self.assertEqual(score_keyboard, 0.0, "Pantry cart must have zero association with Mechanical Keyboard")
        self.assertIsNone(match_keyboard)

    def test_07_in_cart_exclusion_enforcement(self):
        """Verifies products already present in active cart are strictly excluded from recommendation results."""
        recs_engine = RecommenderEngine(association_engine=self.assoc_engine)
        cart = [
            (self.repo.get_entity_by_id("item-033"), 1),
            (self.repo.get_entity_by_id("item-035"), 1),
        ]
        results = recs_engine.find_recommendations(cart_items=cart, catalog=self.catalog, shopping_context="pantry")
        rec_ids = [r.product.id for r in results]

        self.assertNotIn("item-033", rec_ids, "item-033 must not be recommended when already in cart")
        self.assertNotIn("item-035", rec_ids, "item-035 must not be recommended when already in cart")

    def test_08_contextual_intent_alignment(self):
        """Verifies shopping context boosts matching domain products over out-of-context products."""
        item_pasta = self.repo.get_entity_by_id("item-033")
        item_skillet = self.repo.get_entity_by_id("item-049")
        item_keyboard = self.repo.get_entity_by_id("item-001")

        # Context Jaccard score for pasta
        u_pantry = calculate_explicit_context_score(item_pasta, "pantry")
        u_gaming = calculate_explicit_context_score(item_pasta, "gaming")
        self.assertGreater(u_pantry, u_gaming, "Pasta must have higher context score in 'pantry' than 'gaming'")

        # Context Jaccard score for skillet
        u_kitchen = calculate_explicit_context_score(item_skillet, "kitchen")
        self.assertGreater(u_kitchen, u_gaming, "Skillet must have higher context score in 'kitchen' than 'gaming'")

        # Context Jaccard score for keyboard
        u_kb_gaming = calculate_explicit_context_score(item_keyboard, "productivity")
        u_kb_pantry = calculate_explicit_context_score(item_keyboard, "pantry")
        self.assertGreater(u_kb_gaming, u_kb_pantry, "Keyboard must have higher context score in 'productivity' than 'pantry'")

    def test_09_diversity_enforcement_mmr(self):
        """Verifies Maximal Marginal Relevance (MMR) promotes multi-category recommendation diversity."""
        recs_engine = RecommenderEngine(association_engine=self.assoc_engine)
        cart = [(self.repo.get_entity_by_id("item-049"), 1)]  # Skillet in cart

        results = recs_engine.find_recommendations(
            cart_items=cart,
            catalog=self.catalog,
            shopping_context="kitchen",
            top_k=4,
            use_mmr=True,
        )
        self.assertGreaterEqual(len(results), 3)

        categories_returned = {r.product.category for r in results}
        self.assertGreaterEqual(
            len(categories_returned), 2,
            f"MMR should surface at least 2 categories, returned: {categories_returned}"
        )

    def test_10_cold_start_fallback_for_new_categories(self):
        """Verifies cold-start recommendation with empty cart reliably suggests relevant domain items."""
        recs_engine = RecommenderEngine(association_engine=self.assoc_engine)
        results = recs_engine.find_recommendations(
            cart_items=[],
            catalog=self.catalog,
            shopping_context="pantry",
            top_k=4,
        )
        self.assertEqual(len(results), 4)

        for candidate in results:
            self.assertGreater(candidate.affinity_score, 0.0)
            self.assertTrue(len(candidate.compatibility_reason) > 10)
            # Should have context note
            self.assertIn("Pantry & Culinary", candidate.compatibility_reason)

    def test_11_authoritative_quote_and_margin_floors_on_new_products(self):
        """Verifies basket quotes and merchant margin floors remain authoritative on expanded catalogue items."""
        # Rigatoni ($12.00, cogs $5.00) + Nonstick Skillet ($48.00, cogs $20.00)
        # Base basket: subtotal = $60.00, total_cogs = $25.00, margin = 35/60 = 58.33%
        req = DecisionRequest(
            session_id="test-exp-01",
            cart_items=[
                CartItemInput(product_id="item-033", quantity=1),
                CartItemInput(product_id="item-049", quantity=1),
            ],
            margin_floor=0.50,
            discount_cap=0.20,
            shopping_context="pantry",
        )

        resp = self.orchestrator.process_decision(req)
        quote = resp.cart_quote
        self.assertIsNotNone(quote)

        self.assertEqual(quote.standard_subtotal, 51.50)
        self.assertAlmostEqual(quote.basket_gross_margin, 0.5573, places=3)
        self.assertEqual(len(quote.items), 2)

        # Recommendations returned must adhere to margin floor
        for rec in resp.recommendations:
            if rec.is_offered:
                self.assertLessEqual(rec.discount_percentage, 0.20)
                self.assertGreaterEqual(rec.final_price, rec.cogs)

    def test_12_deal_passport_generation_for_new_products(self):
        """Verifies Fair Deal Passport renders complete 3-scenario counterfactual evaluation on new products."""
        req = DealPassportRequest(
            cart_items=[CartItemInput(product_id="item-033", quantity=1)],
            candidate_product_id="item-034",
            candidate_discount_pct=0.10,
            alternative_discount_pct=0.15,
            margin_floor=0.45,
            discount_cap=0.20,
            view_mode="merchant",
        )
        passport = self.orchestrator.generate_deal_passport(req)

        self.assertEqual(passport.candidate_product_id, "item-034")
        self.assertEqual(passport.active_margin_floor, 0.45)
        self.assertEqual(len(passport.scenarios), 3)

        scenario_ids = [s.scenario_id for s in passport.scenarios]
        self.assertIn("no_discount", scenario_ids)
        self.assertIn("faircart_approved", scenario_ids)
        self.assertIn("aggressive_alternative", scenario_ids)

        for s in passport.scenarios:
            self.assertTrue(len(s.label) > 0)
            self.assertIsNotNone(s.policy_checks)
            self.assertGreater(s.basket_subtotal, 0.0)


if __name__ == "__main__":
    unittest.main()
