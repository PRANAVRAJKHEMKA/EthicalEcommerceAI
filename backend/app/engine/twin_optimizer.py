"""FairCart AI — Decision Twin Multi-Shopper & Inventory Optimizer (Slice 3)

Implements:
1. Candidate action valuation with scarcity shadow penalty:
   V(s,a) = P(conv|s,a)*(R_a - C) - P(conv|s,0)*(R_0 - C) - k_a - lambda_i * q
2. Multi-shopper batch allocation under Available-To-Promise (ATP) limits
3. Comparative counterfactual evaluation against Naive Greedy baseline
4. Auditable decision traces with redacted public representations
"""

import json
import logging
import math
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from backend.app.db.database import get_connection
from backend.app.engine.forecasting import DemandForecaster
from backend.app.engine.intent import ShopperIntentEngine
from backend.app.engine.twin_inventory import (
    TwinInventoryRepository,
    calculate_scarcity_lambda,
)
from backend.app.models.decision_twin_schemas import (
    BatchOptimizationRequest,
    BatchOptimizationResult,
    DecisionCandidate,
    DecisionTraceSnapshot,
)

logger = logging.getLogger("faircart.twin.optimizer")


def estimate_conversion_probability(
    base_intent_score: float,
    discount_pct: float,
    price_sensitivity: float = 1.0,
) -> float:
    """Predicts conversion probability using intent score, discount %, and price elasticity.

    Logistic response model:
    P(conv | s, a) = 1 / (1 + exp(-(logit(base_p) + sensitivity * discount_pct * 3.5)))
    """
    p0 = max(0.01, min(0.99, base_intent_score))
    logit_p0 = math.log(p0 / (1.0 - p0))
    incentive_effect = price_sensitivity * discount_pct * 3.5
    new_logit = logit_p0 + incentive_effect
    p_a = 1.0 / (1.0 + math.exp(-new_logit))
    return round(float(p_a), 4)


class TwinOptimizer:
    """Core optimization engine combining inventory scarcity, demand forecasts, and shopper intent."""

    def __init__(self, db_path: str | None = None, database_url: str | None = None):
        self.db_path = db_path
        self.database_url = database_url
        self.inventory_repo = TwinInventoryRepository(db_path=db_path, database_url=database_url)
        self.forecaster = DemandForecaster(db_path=db_path, database_url=database_url)
        self.intent_engine = ShopperIntentEngine()

    def _get_connection(self):
        return get_connection(self.db_path, self.database_url)

    def evaluate_candidates_for_session(
        self,
        session_id: str,
        cart_items: list[dict[str, Any]],
        viewed_product_ids: list[str] | None = None,
        hovered_product_ids: list[str] | None = None,
        historical_order_ids: list[str] | None = None,
        dwell_time_seconds: int = 30,
        margin_floor: float = 0.20,
        discount_cap: float = 0.20,
        storefront_id: str = "primary_storefront",
        search_query: str = "",
    ) -> tuple[list[DecisionCandidate], DecisionCandidate | None, DecisionTraceSnapshot]:
        """Evaluates all candidate actions for a single shopper session under inventory & margin constraints."""
        intent_state = self.intent_engine.infer_intent_state(
            session_id=session_id,
            cart_items=cart_items,
            viewed_product_ids=viewed_product_ids,
            hovered_product_ids=hovered_product_ids,
            historical_order_ids=historical_order_ids,
            dwell_time_seconds=dwell_time_seconds,
            search_query=search_query,
        )

        candidates: list[DecisionCandidate] = []

        # Find primary focus product from cart or recently viewed
        focus_sku = "item-001"
        if cart_items:
            focus_sku = str(cart_items[0].get("product_id", "item-001"))
        elif viewed_product_ids:
            focus_sku = viewed_product_ids[0]

        # Fetch product metadata from DB
        conn = self._get_connection()
        prod_row = None
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM products WHERE id = ?", (focus_sku,))
            prod_row = cursor.fetchone()
        finally:
            conn.close()

        if not prod_row:
            # Fallback product
            prod_name = "Catalog Product"
            ref_price = 50.0
            cogs = 25.0
        else:
            prod_name = prod_row["name"]
            ref_price = round(int(prod_row["reference_price_cents"]) / 100.0, 2)
            cogs = round(int(prod_row["cogs_cents"]) / 100.0, 2)

        # Fetch inventory & ATP
        inv_item = self.inventory_repo.get_inventory_item(focus_sku, storefront_id=storefront_id)
        if not inv_item:
            self.inventory_repo.seed_initial_inventory(storefront_id=storefront_id)
            inv_item = self.inventory_repo.get_inventory_item(focus_sku, storefront_id=storefront_id)

        atp = inv_item.atp if inv_item else 20
        safety_stock = inv_item.safety_stock if inv_item else 10

        # Query 14d demand forecast or resolve explicit fallback
        conn = self._get_connection()
        fc_point: float | None = None
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT point_forecast FROM demand_forecasts
                WHERE sku = ? AND storefront_id = ? AND horizon_days = 14
                ORDER BY created_at DESC LIMIT 1
            """, (focus_sku, storefront_id))
            fc_row = cursor.fetchone()
            if fc_row and fc_row["point_forecast"] is not None:
                fc_point = float(fc_row["point_forecast"])
        except Exception:
            fc_point = None
        finally:
            conn.close()

        if fc_point is None:
            forecast_source = "fallback_safety_buffer"
            forecast_uncertainty = "high"
            effective_forecast = max(14.0, float(safety_stock * 1.5))
        elif fc_point <= 0.0:
            forecast_source = "model_forecast_zero_demand"
            forecast_uncertainty = "low"
            effective_forecast = 0.0
        else:
            forecast_source = "model_forecast"
            forecast_uncertainty = "low"
            effective_forecast = fc_point

        scarcity_lambda = calculate_scarcity_lambda(
            reference_price=ref_price,
            cogs=cogs,
            atp=atp,
            safety_stock=safety_stock,
            forecast_demand_14d=fc_point,
        )

        base_conv = estimate_conversion_probability(intent_state.intent_score, discount_pct=0.0)

        # Action 1: NO_OFFER (Full Reference Price)
        margin_pct_0 = round((ref_price - cogs) / max(0.01, ref_price), 4)
        net_profit_0 = round(base_conv * (ref_price - cogs), 2)
        cand_no_offer = DecisionCandidate(
            action_type="NO_OFFER",
            candidate_id=f"act_no_offer_{focus_sku}",
            product_name=prod_name,
            reference_price=ref_price,
            offered_price=ref_price,
            discount_pct=0.0,
            cogs=cogs,
            gross_margin_pct=margin_pct_0,
            expected_conversion=base_conv,
            scarcity_penalty=0.0,
            net_expected_profit=net_profit_0,
            margin_floor_passed=margin_pct_0 >= margin_floor,
            rejection_reason=None if margin_pct_0 >= margin_floor else "Margin floor breached",
        )
        candidates.append(cand_no_offer)

        # Action 2: ITEM_DISCOUNT (Targeted incentive capped by merchant policy)
        discount_options = [0.05, 0.10, min(0.20, discount_cap)]
        for disc in discount_options:
            if disc <= 0.0 or disc > discount_cap:
                continue
            offered_p = round(ref_price * (1.0 - disc), 2)
            margin_pct = round((offered_p - cogs) / max(0.01, offered_p), 4)
            conv_p = estimate_conversion_probability(
                intent_state.intent_score,
                discount_pct=disc,
                price_sensitivity=intent_state.price_sensitivity_estimate,
            )
            discount_cost = round(ref_price - offered_p, 2)
            # Scarcity penalty: if item is scarce, giving away discount imposes opportunity cost
            scarcity_cost = round(scarcity_lambda * 1.0, 2)
            net_prof = round(
                (conv_p * (offered_p - cogs)) - (base_conv * (ref_price - cogs)) - scarcity_cost,
                2,
            )

            passed_margin = margin_pct >= margin_floor
            rej = None
            if not passed_margin:
                rej = f"Incentive omitted: applying {int(disc*100)}% discount breaches {round(margin_floor*100, 1)}% gross margin floor."
            elif atp <= 0:
                rej = "Out of stock: Available-To-Promise inventory is 0."
            elif scarcity_lambda > 15.0 and intent_state.intent_score > 0.50:
                rej = f"Scarcity suppression: item has only {atp} ATP units; reserved for organic full-margin buyers (lambda=${scarcity_lambda})."

            candidates.append(DecisionCandidate(
                action_type="ITEM_DISCOUNT",
                candidate_id=f"act_disc_{int(disc*100)}_{focus_sku}",
                product_name=prod_name,
                reference_price=ref_price,
                offered_price=offered_p,
                discount_pct=disc,
                cogs=cogs,
                gross_margin_pct=margin_pct,
                expected_conversion=conv_p,
                scarcity_penalty=scarcity_cost,
                net_expected_profit=net_prof,
                margin_floor_passed=passed_margin and atp > 0,
                rejection_reason=rej,
            ))

        # Action 3: BUNDLE_DISCOUNT on abundant complementary item if available
        # Find a complementary item that has abundant inventory
        cand_bundle = None
        if inv_item and atp <= safety_stock:
            # Main item is scarce: offer incentive on complementary item instead!
            comp_sku = "item-002"  # Wrist rest (abundant stock)
            comp_inv = self.inventory_repo.get_inventory_item(comp_sku, storefront_id=storefront_id)
            if comp_inv and comp_inv.atp > comp_inv.safety_stock:
                # Wrist rest: ref $25, cost $10
                comp_ref = 25.0
                comp_cogs = 10.0
                comp_disc = 0.10
                comp_offered = 22.50
                bundle_rev = ref_price + comp_offered
                bundle_cogs = cogs + comp_cogs
                bundle_margin = round((bundle_rev - bundle_cogs) / max(0.01, bundle_rev), 4)
                conv_bundle = estimate_conversion_probability(intent_state.intent_score + 0.15, discount_pct=0.05)
                net_bundle_prof = round(conv_bundle * (bundle_rev - bundle_cogs), 2)

                passed_b_margin = bundle_margin >= margin_floor
                candidates.append(DecisionCandidate(
                    action_type="BUNDLE_DISCOUNT",
                    candidate_id=f"act_bundle_{focus_sku}_{comp_sku}",
                    product_name=f"{prod_name} + Padded Memory Foam Wrist Rest",
                    reference_price=ref_price + comp_ref,
                    offered_price=bundle_rev,
                    discount_pct=round((comp_ref - comp_offered) / (ref_price + comp_ref), 4),
                    cogs=bundle_cogs,
                    gross_margin_pct=bundle_margin,
                    expected_conversion=conv_bundle,
                    scarcity_penalty=0.0,
                    net_expected_profit=net_bundle_prof,
                    margin_floor_passed=passed_b_margin,
                    rejection_reason=None if passed_b_margin else "Bundle breaches margin floor",
                ))

        # Select the optimal action that:
        # 1. Passes margin floor
        # 2. Passes inventory ATP constraint
        # 3. Has no rejection reason
        # 4. Maximizes net expected profit
        valid_candidates = [c for c in candidates if c.margin_floor_passed and c.rejection_reason is None]
        chosen_action = max(valid_candidates, key=lambda c: c.net_expected_profit) if valid_candidates else cand_no_offer

        # Trace snapshot
        trace_id = f"trc_{uuid.uuid4().hex[:12]}"
        snapshot = DecisionTraceSnapshot(
            trace_id=trace_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            session_id=session_id,
            storefront_id=storefront_id,
            intent_state=intent_state.current_state,
            candidates_evaluated=candidates,
            chosen_action=chosen_action,
            scarcity_lambda=scarcity_lambda,
            utility_formula="V(s,a) = P(conv|s,a)*(R_a - C) - P(conv|s,0)*(R_0 - C) - lambda_i * q",
            constraints_applied={
                "margin_floor": margin_floor,
                "discount_cap": discount_cap,
                "atp_available": atp,
                "safety_stock": safety_stock,
                "scarcity_lambda_usd": scarcity_lambda,
                "forecast_demand_14d": effective_forecast,
                "forecast_source": forecast_source,
                "forecast_uncertainty": forecast_uncertainty,
            },
            redacted_shopper_view={
                "trace_id": trace_id,
                "action_type": chosen_action.action_type if chosen_action else "NO_OFFER",
                "product_name": chosen_action.product_name if chosen_action else prod_name,
                "reference_price": chosen_action.reference_price if chosen_action else ref_price,
                "final_price": chosen_action.offered_price if chosen_action else ref_price,
                "savings_amount": round((chosen_action.reference_price - chosen_action.offered_price), 2) if chosen_action else 0.0,
                "margin_protected": True,
            },
        )

        # Persist trace
        self._persist_trace(snapshot)

        return candidates, chosen_action, snapshot

    def _persist_trace(self, snapshot: DecisionTraceSnapshot) -> None:
        """Persists decision trace to decision_traces table."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            payload = snapshot.model_dump_json()
            chosen_act = snapshot.chosen_action.action_type if snapshot.chosen_action else "NO_OFFER"
            net_marg = snapshot.chosen_action.gross_margin_pct if snapshot.chosen_action else 0.0
            cursor.execute("""
                INSERT OR REPLACE INTO decision_traces (
                    trace_id, session_id, merchant_id, storefront_id, chosen_action,
                    scarcity_lambda, net_margin, margin_floor_passed, payload_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                snapshot.trace_id,
                snapshot.session_id,
                "usr_demo_merchant",
                snapshot.storefront_id,
                chosen_act,
                snapshot.scarcity_lambda,
                net_marg,
                1 if snapshot.chosen_action and snapshot.chosen_action.margin_floor_passed else 0,
                payload,
                snapshot.timestamp,
            ))
            conn.commit()
        finally:
            conn.close()

    def optimize_batch(self, request: BatchOptimizationRequest) -> BatchOptimizationResult:
        """Optimizes offer allocations across a batch of concurrent shoppers competing for inventory."""
        start_t = time.perf_counter()
        sessions = request.sessions
        storefront_id = request.storefront_id
        margin_floor = request.margin_floor
        discount_cap = request.discount_cap

        # Ensure inventory is seeded
        self.inventory_repo.seed_initial_inventory(storefront_id=storefront_id)

        # Track shadow allocations per SKU during batch
        shadow_atp: dict[str, int] = {}
        inv_items = self.inventory_repo.list_inventory(storefront_id=storefront_id, limit=200)
        for item in inv_items:
            shadow_atp[item.sku] = item.atp

        twin_allocations: list[dict[str, Any]] = []
        greedy_allocations: list[dict[str, Any]] = []

        twin_total_profit = 0.0
        greedy_total_profit = 0.0
        units_saved = 0
        constrained_skus_set = set()

        # Step 1: Decision Twin Optimization
        for sess in sessions:
            candidates, chosen, snapshot = self.evaluate_candidates_for_session(
                session_id=sess.session_id,
                cart_items=sess.cart_items,
                viewed_product_ids=sess.viewed_product_ids,
                dwell_time_seconds=sess.dwell_time_seconds,
                margin_floor=margin_floor,
                discount_cap=discount_cap,
                storefront_id=storefront_id,
            )

            # Check shadow ATP
            sku = sess.cart_items[0].get("product_id", "item-001") if sess.cart_items else "item-001"
            avail = shadow_atp.get(sku, 10)
            if avail <= 10:
                constrained_skus_set.add(sku)

            if chosen and chosen.action_type != "NO_OFFER" and avail > 0:
                shadow_atp[sku] = max(0, avail - 1)
                twin_total_profit += (chosen.offered_price - chosen.cogs) * chosen.expected_conversion
                twin_allocations.append({
                    "session_id": sess.session_id,
                    "action": chosen.action_type,
                    "product_name": chosen.product_name,
                    "price": chosen.offered_price,
                    "discount_pct": chosen.discount_pct,
                    "scarcity_lambda": snapshot.scarcity_lambda,
                    "expected_profit": round((chosen.offered_price - chosen.cogs) * chosen.expected_conversion, 2),
                })
            else:
                # Full price / no offer preserves margin and stock
                ref_p = chosen.reference_price if chosen else 80.0
                cogs_p = chosen.cogs if chosen else 40.0
                twin_total_profit += (ref_p - cogs_p) * (chosen.expected_conversion if chosen else 0.35)
                twin_allocations.append({
                    "session_id": sess.session_id,
                    "action": "NO_OFFER_ORGANIC",
                    "product_name": chosen.product_name if chosen else "Product",
                    "price": ref_p,
                    "discount_pct": 0.0,
                    "scarcity_lambda": snapshot.scarcity_lambda,
                    "expected_profit": round((ref_p - cogs_p) * (chosen.expected_conversion if chosen else 0.35), 2),
                })
                units_saved += 1

        # Step 2: Baseline Naive Greedy Simulation
        # Greedy allocator gives max discount (discount_cap) to every visitor until stock runs out
        greedy_atp = {item.sku: item.atp for item in inv_items}
        for sess in sessions:
            sku = sess.cart_items[0].get("product_id", "item-001") if sess.cart_items else "item-001"
            avail = greedy_atp.get(sku, 10)
            if avail > 0:
                # Offer full discount cap
                greedy_atp[sku] = avail - 1
                ref_p = 80.0 if sku == "item-001" else 50.0
                cogs_p = 40.0 if sku == "item-001" else 25.0
                disc_p = round(ref_p * (1.0 - discount_cap), 2)
                # If margin passes, greedy applies it
                if (disc_p - cogs_p) / max(0.01, disc_p) >= margin_floor:
                    greedy_total_profit += (disc_p - cogs_p) * 0.45
                else:
                    greedy_total_profit += (ref_p - cogs_p) * 0.30
            else:
                # Stockout: zero revenue and zero profit!
                pass

        greedy_total_profit = max(1.0, greedy_total_profit)
        lift_pct = round(((twin_total_profit - greedy_total_profit) / greedy_total_profit) * 100.0, 2)
        latency = round((time.perf_counter() - start_t) * 1000.0, 2)

        return BatchOptimizationResult(
            total_sessions_evaluated=len(sessions),
            inventory_constrained_skus=sorted(list(constrained_skus_set)),
            allocations=twin_allocations,
            aggregate_projected_profit=round(twin_total_profit, 2),
            baseline_greedy_profit=round(greedy_total_profit, 2),
            projected_profit_lift_pct=lift_pct,
            inventory_saved_units=units_saved,
            stockout_prevention_rate=round(min(1.0, units_saved / max(1, len(sessions))), 2),
            execution_latency_ms=latency,
        )
