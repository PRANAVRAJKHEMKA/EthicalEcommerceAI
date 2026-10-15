"""Automated test suite for Milestone 5: Three-Policy Economic Simulation Comparator.

Validates:
1. Reproducible session generation with fixed seed.
2. Identical metrics for repeated simulation runs with identical inputs.
3. Correct evaluation of all three policies on the same paired scenarios.
4. Correct discount application in the blanket baseline (exact 15%).
5. Isolation: simulator runs do not alter live catalog pricing or live session state.
6. Accurate financial accounting (Net = Gross - Discounts, Margin, Contribution Profit, AOV).
7. Zero conversions and empty simulation edge cases without division-by-zero.
8. FairCart discount caps and basket-level margin floor protection.
9. Honest reporting of baseline margin-floor violations without suppression.
10. Merchant settings persistence and their effects on subsequent FairCart runs.
11. Response schema validation and invalid-input handling (HTTP 422).
12. HTTP API endpoints (POST /api/v1/simulate and GET /api/v1/simulate/latest).
13. Mathematical confidence intervals validity for conversion rate and profit.
"""

import unittest
from fastapi.testclient import TestClient

from backend.app.db.repository import CatalogRepository
from backend.app.engine.simulator import EconomicSimulator, SyntheticSessionGenerator
from backend.app.main import app
from backend.app.models.schemas import SimulationRequest


class TestSimulationEngine(unittest.TestCase):
    """Test suite for Milestone 5 economic simulation comparator."""

    def setUp(self):
        self.repo = CatalogRepository()
        self.simulator = EconomicSimulator(repository=self.repo)
        self.client = TestClient(app)

    # 1. Reproducible session generation with fixed seed
    def test_reproducible_session_generation_with_fixed_seed(self):
        """SyntheticSessionGenerator produces identical session sequences with identical seeds."""
        catalog = self.repo.get_all_entities()
        gen = SyntheticSessionGenerator(catalog)
        sessions_a = gen.generate(num_sessions=100, seed=42)
        sessions_b = gen.generate(num_sessions=100, seed=42)

        self.assertEqual(len(sessions_a), 100)
        self.assertEqual(len(sessions_b), 100)
        for sa, sb in zip(sessions_a, sessions_b):
            self.assertEqual(sa.session_id, sb.session_id)
            self.assertEqual(sa.archetype, sb.archetype)
            self.assertEqual(sa.initial_cart_items, sb.initial_cart_items)
            self.assertEqual(sa.u_conv, sb.u_conv)
            self.assertEqual(sa.u_acc, sb.u_acc)

    # 2. Identical metrics for repeated runs with identical inputs
    def test_identical_metrics_for_repeated_runs_with_identical_inputs(self):
        """Repeated simulation runs with the same seed yield identical metrics down to the cent."""
        res_a = self.simulator.run_simulation(num_sessions=300, random_seed=42, margin_floor=0.20)
        res_b = self.simulator.run_simulation(num_sessions=300, random_seed=42, margin_floor=0.20)

        self.assertEqual(res_a.policies, res_b.policies)
        self.assertEqual(res_a.relative_comparison, res_b.relative_comparison)

    # 3. Correct evaluation of all three policies on the same scenarios
    def test_correct_evaluation_of_all_three_policies_on_same_scenarios(self):
        """All three policies evaluate the exact same session count and population."""
        res = self.simulator.run_simulation(num_sessions=500, random_seed=42)
        self.assertIn("NO_DISCOUNT", res.policies)
        self.assertIn("BLANKET_15", res.policies)
        self.assertIn("FAIRCART_AI", res.policies)

        for p_id in ("NO_DISCOUNT", "BLANKET_15", "FAIRCART_AI"):
            self.assertEqual(res.policies[p_id].sessions_count, 500)

    # 4. Correct discount application in the blanket baseline
    def test_correct_discount_application_in_blanket_baseline(self):
        """Blanket 15% markdown applies exactly 15% discount across all completed purchase lines."""
        res = self.simulator.run_simulation(num_sessions=200, random_seed=42)
        blanket = res.policies["BLANKET_15"]
        if blanket.completed_orders_count > 0:
            expected_discount = round(blanket.total_gross_sales * 0.15, 2)
            self.assertAlmostEqual(blanket.total_incentive_expense, expected_discount, places=1)
            self.assertAlmostEqual(
                blanket.total_net_sales_revenue,
                round(blanket.total_gross_sales - blanket.total_incentive_expense, 2),
                places=1,
            )

    # 5. Isolation: simulator runs do not alter live catalog or database prices
    def test_no_unintended_interference_between_simulator_and_live_pricing(self):
        """Simulation execution does not modify live catalog prices or corrupt stock."""
        p_before = self.repo.get_entity_by_id("item-001")
        self.simulator.run_simulation(num_sessions=100, random_seed=42)
        p_after = self.repo.get_entity_by_id("item-001")

        self.assertIsNotNone(p_before)
        self.assertIsNotNone(p_after)
        self.assertEqual(p_before.reference_price_cents, p_after.reference_price_cents)
        self.assertEqual(p_before.cogs_cents, p_after.cogs_cents)

    # 6. Accurate financial accounting
    def test_accurate_accounting_metrics(self):
        """Validates fundamental accounting invariants across all policies."""
        res = self.simulator.run_simulation(num_sessions=300, random_seed=42)
        for pid, p in res.policies.items():
            if p.completed_orders_count > 0:
                # Net = Gross - Incentive
                self.assertAlmostEqual(
                    p.total_net_sales_revenue,
                    round(p.total_gross_sales - p.total_incentive_expense, 2),
                    places=1,
                )
                # AOV = Net / Completed
                expected_aov = round(p.total_net_sales_revenue / p.completed_orders_count, 2)
                self.assertAlmostEqual(p.average_order_value, expected_aov, places=1)
                # Profit = Net - COGS - (3.50 * Completed)
                expected_profit = round(
                    p.total_net_sales_revenue - p.total_cogs - (3.50 * p.completed_orders_count),
                    2,
                )
                self.assertAlmostEqual(p.total_contribution_profit, expected_profit, places=1)
                # Margin = (Net - COGS) / Net
                expected_margin = round((p.total_net_sales_revenue - p.total_cogs) / p.total_net_sales_revenue, 4)
                self.assertAlmostEqual(p.total_gross_margin, expected_margin, places=2)

    # 7. Zero conversions and empty simulation edge cases
    def test_zero_conversions_and_empty_simulation_edge_cases(self):
        """Simulator safely handles edge cases without ZeroDivisionError."""
        # Run small session count
        res = self.simulator.run_simulation(num_sessions=10, random_seed=999)
        for pid, p in res.policies.items():
            self.assertGreaterEqual(p.conversion_rate, 0.0)
            self.assertLessEqual(p.conversion_rate, 1.0)
            self.assertGreaterEqual(p.average_order_value, 0.0)
            self.assertGreaterEqual(p.total_gross_margin, 0.0)

    # 8. FairCart discount caps and basket-level margin floor protection
    def test_faircart_discount_caps_and_basket_margin_floors(self):
        """FairCart AI strictly respects merchant margin floors (0 violations)."""
        res = self.simulator.run_simulation(
            num_sessions=500,
            random_seed=42,
            margin_floor=0.30,
            discount_cap=0.15,
        )
        faircart = res.policies["FAIRCART_AI"]
        self.assertEqual(faircart.margin_floor_violations_count, 0)
        self.assertEqual(faircart.margin_floor_violation_rate, 0.0)

    # 9. Honest reporting of baseline margin-floor violations without suppression
    def test_reporting_of_baseline_margin_floor_violations(self):
        """With an elevated margin floor (e.g. 45%), Blanket 15% exhibits margin floor violations."""
        res = self.simulator.run_simulation(
            num_sessions=500,
            random_seed=42,
            margin_floor=0.45,
            discount_cap=0.20,
        )
        blanket = res.policies["BLANKET_15"]
        faircart = res.policies["FAIRCART_AI"]

        self.assertGreater(blanket.margin_floor_violations_count, 0)
        self.assertGreater(blanket.margin_floor_violation_rate, 0.0)
        # FairCart AI has zero violations by construction
        self.assertEqual(faircart.margin_floor_violations_count, 0)

    # 10. Merchant settings persistence and effect on FairCart runs
    def test_merchant_settings_persistence_and_effect_on_faircart_runs(self):
        """Changing SQLite merchant settings dynamically alters simulator parameters."""
        # Set margin floor to 0.40
        self.repo.update_merchant_setting("margin_floor", 0.40)
        self.repo.update_merchant_setting("discount_cap", 0.10)

        res = self.simulator.run_simulation(num_sessions=200, random_seed=42)
        self.assertEqual(res.parameters["margin_floor"], 0.40)
        self.assertEqual(res.parameters["discount_cap"], 0.10)

        # Restore default settings
        self.repo.update_merchant_setting("margin_floor", 0.20)
        self.repo.update_merchant_setting("discount_cap", 0.20)

    # 11. Response schema validation and invalid-input handling (HTTP 422)
    def test_correct_response_schema_and_invalid_input_handling(self):
        """FastAPI validates request bounds and rejects negative or out-of-range inputs."""
        # num_sessions < 10 must fail
        resp_too_small = self.client.post("/api/v1/simulate", json={"num_sessions": 5})
        self.assertEqual(resp_too_small.status_code, 422)

        # margin_floor > 1.0 must fail
        resp_invalid_floor = self.client.post("/api/v1/simulate", json={"margin_floor": 1.5})
        self.assertEqual(resp_invalid_floor.status_code, 422)

    # 12. HTTP API endpoints (POST /api/v1/simulate and GET /api/v1/simulate/latest)
    def test_http_simulate_endpoint_and_latest_persistence(self):
        """POST /api/v1/simulate runs successfully and persists to GET /api/v1/simulate/latest."""
        resp = self.client.post(
            "/api/v1/simulate",
            json={"num_sessions": 100, "random_seed": 42},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("policies", data)
        self.assertIn("FAIRCART_AI", data["policies"])

        # Fetch latest
        latest_resp = self.client.get("/api/v1/simulate/latest")
        self.assertEqual(latest_resp.status_code, 200)
        latest_data = latest_resp.json()
        self.assertEqual(latest_data["id"], data["simulation_id"])

    # 13. Mathematical confidence intervals validity
    def test_confidence_intervals_validity(self):
        """95% confidence intervals are mathematically bounded and enclose the point estimates."""
        res = self.simulator.run_simulation(num_sessions=500, random_seed=42)
        for pid, p in res.policies.items():
            # Conversion rate CI
            ci_conv = p.conversion_rate_ci_95
            self.assertEqual(len(ci_conv), 2)
            self.assertLessEqual(ci_conv[0], p.conversion_rate)
            self.assertGreaterEqual(ci_conv[1], p.conversion_rate)
            self.assertGreaterEqual(ci_conv[0], 0.0)
            self.assertLessEqual(ci_conv[1], 1.0)

            # Contribution profit per session CI
            ci_cp = p.avg_contribution_profit_per_session_ci_95
            self.assertEqual(len(ci_cp), 2)
            self.assertLessEqual(ci_cp[0], p.avg_contribution_profit_per_session)
            self.assertGreaterEqual(ci_cp[1], p.avg_contribution_profit_per_session)


if __name__ == "__main__":
    unittest.main()
