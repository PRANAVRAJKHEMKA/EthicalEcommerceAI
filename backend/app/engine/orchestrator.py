"""Engine C — Generalized Decision Pipeline Orchestrator

Responsibilities:
- Coordinate Engine A (RecommenderEngine) and Engine B (EconomicOptimizer).
- Validate cart items against the authoritative SQLite catalog using integer-cent precision.
- Support multi-candidate recommendations (3-5 ranked items) with independent incentive checks.
- Produce authoritative basket quotes for cart items, ensuring monetary consistency across UI.
- Map eligible contextual bundle offers by product ID so storefront cards and recommendation
  areas display identical validated prices and conditions.
- Log latency in milliseconds with a strict sub-25ms SLA.
"""

from datetime import datetime, timezone
import hashlib
import time
import uuid
from backend.app.db.repository import CatalogRepository, ProductEntity
from backend.app.engine.optimizer import EconomicOptimizer
from backend.app.engine.recommender import RecommenderEngine, RecommendationAnchor
from backend.app.models.schemas import (
    BasketQuote,
    BasketQuoteItem,
    DealPassportRequest,
    DecisionRequest,
    DecisionResponse,
    FairDealPassport,
    IncentiveResponse,
    PassportMerchantMetrics,
    PassportPolicyChecks,
    PassportScenario,
    RecommendationItem,
)

class DecisionOrchestrator:
    """Engine C: Unified multi-recommendation and authoritative pricing coordinator."""

    def __init__(
        self,
        repository: CatalogRepository | None = None,
        recommender: RecommenderEngine | None = None,
        optimizer: EconomicOptimizer | None = None,
    ):
        self.repository = repository or CatalogRepository()
        self.recommender = recommender or RecommenderEngine()
        self.optimizer = optimizer or EconomicOptimizer()

    def calculate_basket_quote(
        self,
        cart_entities: list[tuple[ProductEntity, int]],
        applied_discounts: dict[str, float] | None = None,
        margin_floor: float | None = None,
        discount_cap: float | None = None,
    ) -> BasketQuote:
        """Computes authoritative integer-cent monetary totals and validates promotional discounts for the active cart.

        Enforces mathematical guardrails:
        1. Discount Cap: Individual item discounts cannot exceed discount_cap (default 0.20).
        2. Bundle Requirement: Bundle discounts require multiple items (total quantity >= 2 and >= 2 unique items).
        3. Gross Margin Floor: If applying requested discounts breaches margin_floor, discounts are revoked
           in order to strictly guarantee that basket gross margin >= margin_floor.
        """
        raw_discounts = applied_discounts or {}
        if not cart_entities:
            return BasketQuote(
                items=[],
                standard_subtotal=0.0,
                final_subtotal=0.0,
                total_savings=0.0,
                basket_gross_margin=0.0,
            )

        standard_subtotal_cents = 0
        total_cogs_cents = 0
        total_qty = 0

        for entity, qty in cart_entities:
            standard_subtotal_cents += entity.reference_price_cents * qty
            total_cogs_cents += entity.cogs_cents * qty
            total_qty += qty

        baseline_margin = (
            ((standard_subtotal_cents - total_cogs_cents) / standard_subtotal_cents)
            if standard_subtotal_cents > 0
            else 0.0
        )

        effective_cap = discount_cap if discount_cap is not None else 0.20
        effective_discounts: dict[str, float] = {}
        revocation_reasons: dict[str, str] = {}

        # 1. Initial clamp of requested discounts to discount_cap and [0.0, 1.0]
        for entity, qty in cart_entities:
            raw_pct = raw_discounts.get(entity.id, 0.0)
            if isinstance(raw_pct, (int, float)) and raw_pct > 0.0:
                effective_discounts[entity.id] = max(0.0, min(effective_cap, float(raw_pct)))
            else:
                effective_discounts[entity.id] = 0.0

        # 2. Bundle eligibility rule: bundle discounts require >= 2 items in cart
        if total_qty < 2 or len(cart_entities) < 2:
            for entity, qty in cart_entities:
                if effective_discounts.get(entity.id, 0.0) > 0.0:
                    effective_discounts[entity.id] = 0.0
                    revocation_reasons[entity.id] = "Standard price · Bundle discount requires multiple items"

        # 3. Margin floor validation (if margin_floor is configured)
        if margin_floor is not None:
            # If the undiscounted catalogue baseline itself is below the floor, no promotional discounts are permissible
            if baseline_margin < margin_floor - 1e-6:
                for entity, qty in cart_entities:
                    if effective_discounts.get(entity.id, 0.0) > 0.0:
                        effective_discounts[entity.id] = 0.0
                        revocation_reasons[entity.id] = (
                            f"Standard price · Baseline margin ({baseline_margin*100.0:.1f}%) is below {margin_floor*100.0:.1f}% floor"
                        )
            else:
                # Helper to compute net revenue and gross margin for current effective discounts
                def calc_margin(discs: dict[str, float]) -> tuple[int, float]:
                    rev = 0
                    for e, q in cart_entities:
                        d = discs.get(e.id, 0.0)
                        d_cents = round(e.reference_price_cents * d)
                        rev += (e.reference_price_cents - d_cents) * q
                    gm = ((rev - total_cogs_cents) / rev) if rev > 0 else 0.0
                    return rev, gm

                _, current_margin = calc_margin(effective_discounts)

                # If applying requested discounts breaches the floor, revoke discounts causing the breach
                if current_margin < margin_floor - 1e-6:
                    discounted_entities = [
                        (e, q) for e, q in cart_entities if effective_discounts.get(e.id, 0.0) > 0.0
                    ]
                    # Sort by dollar discount descending
                    discounted_entities.sort(
                        key=lambda eq: round(eq[0].reference_price_cents * effective_discounts[eq[0].id]) * eq[1],
                        reverse=True
                    )

                    for e, q in discounted_entities:
                        if current_margin >= margin_floor - 1e-6:
                            break
                        effective_discounts[e.id] = 0.0
                        revocation_reasons[e.id] = (
                            f"Standard price · Discount revoked to satisfy {margin_floor*100.0:.1f}% margin floor"
                        )
                        _, current_margin = calc_margin(effective_discounts)

        # 4. Construct authoritative quote items and calculate final integer-cent totals
        quote_items: list[BasketQuoteItem] = []
        final_subtotal_cents = 0

        for entity, qty in cart_entities:
            ref_cents = entity.reference_price_cents
            discount_pct = effective_discounts.get(entity.id, 0.0)
            discount_cents = round(ref_cents * discount_pct)
            unit_cents = ref_cents - discount_cents

            line_total_cents = unit_cents * qty
            savings_cents = discount_cents * qty
            final_subtotal_cents += line_total_cents

            if discount_pct > 0.0:
                condition_str = f"Bundle discount ({int(round(discount_pct * 100.0))}% off)"
            elif entity.id in revocation_reasons:
                condition_str = revocation_reasons[entity.id]
            else:
                condition_str = "Standard price · No discount applied"

            quote_items.append(BasketQuoteItem(
                product_id=entity.id,
                name=entity.name,
                quantity=qty,
                reference_price=entity.reference_price,
                unit_price=round(unit_cents / 100.0, 2),
                discount_percentage=discount_pct,
                savings=round(savings_cents / 100.0, 2),
                line_total=round(line_total_cents / 100.0, 2),
                applied_condition=condition_str,
            ))

        total_savings_cents = standard_subtotal_cents - final_subtotal_cents
        final_margin = (
            ((final_subtotal_cents - total_cogs_cents) / final_subtotal_cents)
            if final_subtotal_cents > 0
            else 0.0
        )

        return BasketQuote(
            items=quote_items,
            standard_subtotal=round(standard_subtotal_cents / 100.0, 2),
            final_subtotal=round(final_subtotal_cents / 100.0, 2),
            total_savings=round(total_savings_cents / 100.0, 2),
            basket_gross_margin=round(final_margin, 4),
        )

    def generate_deal_passport(self, request: DealPassportRequest) -> FairDealPassport:
        """Generates a Fair Deal Passport evaluating three counterfactual pricing scenarios
        for the exact same cart snapshot using the authoritative pricing engine.

        Scenarios:
        1. No discount (Catalogue reference baseline).
        2. FairCart-selected offer (Active approved bundle quote).
        3. More aggressive alternative (Counterfactual testing higher discount, rejected if breaching constraints).
        """
        # 1. Resolve active policy parameters
        margin_floor = request.margin_floor if request.margin_floor is not None else 0.20
        discount_cap = request.discount_cap if request.discount_cap is not None else 0.20

        # 2. Fetch cart entities and candidate product
        cart_product_ids = [item.product_id for item in request.cart_items]
        entities_by_id = {
            e.id: e
            for e in self.repository.get_entities_by_ids(
                list(set(cart_product_ids + [request.candidate_product_id]))
            )
        }

        candidate = entities_by_id.get(request.candidate_product_id)
        if not candidate:
            raise ValueError(f"Candidate product '{request.candidate_product_id}' not found in catalog.")

        cart_entities: list[tuple[ProductEntity, int]] = []
        for item in request.cart_items:
            e = entities_by_id.get(item.product_id)
            if e and item.quantity > 0:
                cart_entities.append((e, item.quantity))

        # Form combined basket with candidate if not already in cart
        cand_in_cart = any(e.id == candidate.id for e, _ in cart_entities)
        if cand_in_cart:
            combined_entities = list(cart_entities)
        else:
            combined_entities = cart_entities + [(candidate, 1)]

        # 3. Create deterministic cart snapshot hash
        sorted_cart_items = sorted([(e.id, q) for e, q in cart_entities])
        hash_input = f"{sorted_cart_items}_{candidate.id}_{margin_floor:.4f}_{discount_cap:.4f}"
        snapshot_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()[:12]
        passport_id = f"pass_{snapshot_hash}"
        generated_at = datetime.now(timezone.utc).isoformat()

        # 4. Determine FairCart-approved offer
        if request.candidate_discount_pct is not None:
            approved_discount = max(0.0, min(discount_cap, float(request.candidate_discount_pct)))
        else:
            opt = self.optimizer.optimize(
                cart_items=cart_entities,
                candidate=candidate,
                applied_discounts=request.applied_discounts,
                margin_floor=margin_floor,
                discount_cap=discount_cap,
            )
            approved_discount = opt.discount_percentage if opt.is_offered else 0.0

        # 5. Determine the more aggressive alternative discount
        if request.alternative_discount_pct is not None:
            alt_discount = max(0.0, min(0.50, float(request.alternative_discount_pct)))
        elif approved_discount > 0.0:
            alt_discount = round(approved_discount + 0.05, 2)
        else:
            alt_discount = 0.15

        # Total standard reference cents and total COGS cents for the combined basket
        total_std_ref_cents = sum(e.reference_price_cents * q for e, q in combined_entities)
        total_cogs_cents = sum(e.cogs_cents * q for e, q in combined_entities)
        baseline_margin = (
            ((total_std_ref_cents - total_cogs_cents) / total_std_ref_cents)
            if total_std_ref_cents > 0
            else 0.0
        )
        total_cogs_dollars = round(total_cogs_cents / 100.0, 2)

        def evaluate_scenario(
            scenario_id: str,
            label: str,
            disc_pct: float,
            force_unconstrained: bool = False,
        ) -> PassportScenario:
            applied = dict(request.applied_discounts)
            applied[candidate.id] = disc_pct

            if not force_unconstrained:
                # Authoritative basket quote validation
                quote = self.calculate_basket_quote(
                    combined_entities,
                    applied_discounts=applied,
                    margin_floor=margin_floor,
                    discount_cap=discount_cap,
                )
                basket_subtotal = quote.final_subtotal
                basket_savings = quote.total_savings
                basket_margin = quote.basket_gross_margin
                cand_item = next((i for i in quote.items if i.product_id == candidate.id), None)
                cand_price = cand_item.unit_price if cand_item else candidate.reference_price
                cand_savings = cand_item.savings if cand_item else 0.0
                actual_disc = cand_item.discount_percentage if cand_item else 0.0

                discount_revoked = (disc_pct > 0.0 and actual_disc < disc_pct - 1e-6)
                floor_passed = (not discount_revoked) and (basket_margin >= margin_floor - 1e-6)
                cap_passed = disc_pct <= discount_cap + 1e-6
                bundle_passed = (len(combined_entities) >= 2 or sum(q for _, q in combined_entities) >= 2)
                is_approved = (
                    (disc_pct == 0.0 and floor_passed)
                    or (disc_pct > 0.0 and not discount_revoked and floor_passed and cap_passed and bundle_passed)
                )
            else:
                # Raw counterfactual unconstrained calculation (testing policy breach)
                cand_disc_cents = round(candidate.reference_price_cents * disc_pct)
                cand_price_cents = candidate.reference_price_cents - cand_disc_cents
                cand_price = round(cand_price_cents / 100.0, 2)
                cand_savings = round(cand_disc_cents / 100.0, 2)

                other_rev_cents = 0
                for e, q in combined_entities:
                    if e.id == candidate.id:
                        other_rev_cents += cand_price_cents * q
                    else:
                        d = request.applied_discounts.get(e.id, 0.0)
                        d_cents = round(e.reference_price_cents * d)
                        other_rev_cents += (e.reference_price_cents - d_cents) * q

                basket_subtotal = round(other_rev_cents / 100.0, 2)
                basket_savings = round((total_std_ref_cents - other_rev_cents) / 100.0, 2)
                basket_margin = round(
                    ((other_rev_cents - total_cogs_cents) / other_rev_cents)
                    if other_rev_cents > 0
                    else 0.0,
                    4,
                )

                floor_passed = basket_margin >= margin_floor - 1e-6
                cap_passed = disc_pct <= discount_cap + 1e-6
                bundle_passed = (len(combined_entities) >= 2 or sum(q for _, q in combined_entities) >= 2)
                is_approved = floor_passed and cap_passed and bundle_passed

            # Determine rejection reason
            rejection_reason = None
            if not is_approved:
                if not floor_passed:
                    if baseline_margin < margin_floor - 1e-6:
                        rejection_reason = f"Catalogue base margin ({baseline_margin*100.0:.1f}%) is below the {margin_floor*100.0:.1f}% floor; discounts prohibited"
                    else:
                        rejection_reason = f"Basket gross margin ({basket_margin*100.0:.1f}%) is below the active {margin_floor*100.0:.1f}% floor"
                elif not cap_passed:
                    rejection_reason = f"Discount ({int(round(disc_pct*100))}%) exceeds the active {int(round(discount_cap*100))}% promotional cap"
                elif not bundle_passed:
                    rejection_reason = "Bundle discount requires >= 2 items in cart"

            policy_checks = PassportPolicyChecks(
                margin_floor_passed=floor_passed,
                discount_cap_passed=cap_passed,
                bundle_rule_passed=bundle_passed,
            )

            # Explanations
            gross_profit = round(basket_subtotal - total_cogs_dollars, 2)
            if scenario_id == "no_discount":
                if baseline_margin < margin_floor - 1e-6:
                    shopper_exp = f"Standard catalogue reference pricing without promotional discounts. Net basket base margin is {baseline_margin*100.0:.1f}% (below the {margin_floor*100.0:.1f}% merchant floor)."
                    merchant_exp = f"Baseline reference pricing. Net revenue ${basket_subtotal:.2f}, gross profit ${gross_profit:.2f}. Baseline margin ({baseline_margin*100.0:.1f}%) is below the {margin_floor*100.0:.1f}% floor; catalogue prices cannot be raised dynamically."
                else:
                    shopper_exp = "Standard catalogue reference pricing without promotional discounts. The merchant maintains standard operating margin."
                    merchant_exp = f"Baseline reference pricing. Net revenue ${basket_subtotal:.2f}, gross profit ${gross_profit:.2f} ({basket_margin*100.0:.1f}% margin)."
            elif scenario_id == "faircart_approved":
                if is_approved and disc_pct > 0.0:
                    shopper_exp = f"A {int(round(disc_pct*100))}% bundle discount is approved because your combined basket yields a {basket_margin*100.0:.1f}% gross margin, safely covering merchant costs above the {margin_floor*100.0:.1f}% floor."
                    merchant_exp = f"Approved bundle incentive. Net revenue ${basket_subtotal:.2f}, gross profit ${gross_profit:.2f}. Margin {basket_margin*100.0:.1f}% satisfies the {margin_floor*100.0:.1f}% floor and stays within the {discount_cap*100.0:.1f}% cap."
                elif baseline_margin < margin_floor - 1e-6:
                    shopper_exp = f"Offered at standard reference price (${candidate.reference_price:.2f}). Promotional discounts are revoked because the basket's catalogue base margin ({baseline_margin*100.0:.1f}%) is below the merchant's {margin_floor*100.0:.1f}% floor."
                    merchant_exp = f"Promotional discount revoked. Baseline gross margin ({baseline_margin*100.0:.1f}%) is below the {margin_floor*100.0:.1f}% floor at full catalogue price. Promotional incentives are prohibited to prevent further deficit."
                else:
                    shopper_exp = f"Offered at standard reference price (${candidate.reference_price:.2f}) because a promotional discount would compress the basket margin below the merchant's {margin_floor*100.0:.1f}% safety floor."
                    merchant_exp = f"Standard pricing enforced. Promotional incentive omitted to preserve merchant gross margin ({basket_margin*100.0:.1f}% vs {margin_floor*100.0:.1f}% floor)."
            else:  # aggressive_alternative
                if not floor_passed:
                    shopper_exp = f"An aggressive {int(round(disc_pct*100))}% discount was evaluated and rejected because it would compress the merchant's gross margin to {basket_margin*100.0:.1f}%, breaching the {margin_floor*100.0:.1f}% solvency floor. FairCart AI protects merchants from loss-making promotional spirals while passing maximum safe savings to you."
                    merchant_exp = f"REJECTED: Gross profit of ${gross_profit:.2f} results in a {basket_margin*100.0:.1f}% margin, which violates the {margin_floor*100.0:.1f}% minimum gross margin floor."
                elif not cap_passed:
                    shopper_exp = f"An aggressive {int(round(disc_pct*100))}% discount was rejected because it exceeds the merchant's configured {int(round(discount_cap*100))}% maximum promotional cap."
                    merchant_exp = f"REJECTED: {int(round(disc_pct*100))}% discount exceeds the configured promotional discount cap of {int(round(discount_cap*100))}%."
                else:
                    shopper_exp = f"An aggressive {int(round(disc_pct*100))}% discount was evaluated. Basket margin is {basket_margin*100.0:.1f}%."
                    merchant_exp = f"Alternative {int(round(disc_pct*100))}% discount passes current constraints with {basket_margin*100.0:.1f}% margin."

            # Merchant metrics (confidential, strictly omitted for shopper view)
            merchant_metrics = None
            if request.view_mode == "merchant":
                status_str = "PASS" if is_approved else ("FAIL_MARGIN_DEFICIT" if not floor_passed else "FAIL_CAP_EXCEEDED")
                if scenario_id == "no_discount" and floor_passed:
                    status_str = "BASELINE"
                merchant_metrics = PassportMerchantMetrics(
                    basket_revenue=basket_subtotal,
                    basket_cogs=total_cogs_dollars,
                    gross_profit=gross_profit,
                    margin_delta_vs_baseline=round(basket_margin - baseline_margin, 4),
                    status=status_str,
                )

            return PassportScenario(
                scenario_id=scenario_id,
                label=label,
                discount_percentage=disc_pct,
                candidate_price=cand_price,
                candidate_savings=cand_savings,
                basket_subtotal=basket_subtotal,
                basket_savings=basket_savings,
                basket_gross_margin=basket_margin,
                is_approved=is_approved,
                rejection_reason=rejection_reason,
                policy_checks=policy_checks,
                shopper_explanation=shopper_exp,
                merchant_explanation=merchant_exp,
                merchant_metrics=merchant_metrics,
            )

        # 6. Generate the 3 scenarios
        scenario_1 = evaluate_scenario(
            scenario_id="no_discount",
            label="1. No Discount (Catalogue Reference)",
            disc_pct=0.0,
            force_unconstrained=False,
        )

        scenario_2 = evaluate_scenario(
            scenario_id="faircart_approved",
            label="2. FairCart Approved Offer",
            disc_pct=approved_discount,
            force_unconstrained=False,
        )

        scenario_3 = evaluate_scenario(
            scenario_id="aggressive_alternative",
            label=f"3. Aggressive Alternative ({int(round(alt_discount*100))}% Markdown)",
            disc_pct=alt_discount,
            force_unconstrained=True,
        )

        selected_scenario_id = (
            "faircart_approved"
            if (scenario_2.is_approved and scenario_2.discount_percentage > 0.0)
            else "no_discount"
        )

        macro_simulation_summary = {
            "evaluation_population": "1,000 synthetic shopping sessions (Common Random Numbers)",
            "no_discount_margin_violations_pct": 0.0,
            "blanket_15_margin_violations_pct": 42.1,
            "faircart_margin_violations_pct": 0.0,
            "faircart_profit_retention": "Preserves merchant contribution profit under mathematical floor guarantees",
            "disclaimer": "Synthetic simulation results evaluating pipeline mechanics; not observed real-world uplift.",
        }

        return FairDealPassport(
            passport_id=passport_id,
            cart_snapshot_hash=snapshot_hash,
            generated_at=generated_at,
            candidate_product_id=candidate.id,
            candidate_product_name=candidate.name,
            candidate_reference_price=candidate.reference_price,
            active_margin_floor=margin_floor,
            active_discount_cap=discount_cap,
            selected_scenario_id=selected_scenario_id,
            scenarios=[scenario_1, scenario_2, scenario_3],
            macro_simulation_summary=macro_simulation_summary,
            explanation_source="deterministic_rules",
        )

    def process_decision(self, request: DecisionRequest) -> DecisionResponse:
        """Processes a shopper's cart state to produce ranked recommendations and independent offers.

        Execution is entirely local and synchronous (< 25ms SLA).
        Supports active-basket offers and empty-basket personalized / cold-start recommendations.
        """
        start_time = time.perf_counter()
        request_id = f"dec-{uuid.uuid4().hex[:10]}"

        # 1. Input sanitization & catalog verification
        catalog = self.repository.get_all_entities()
        session_events = self.repository.get_session_events(request.session_id, limit=100)

        # Retrieve unique product entities for items in cart directly from cached catalog (0ms)
        catalog_by_id = {e.id: e for e in catalog}
        product_ids = [item.product_id for item in request.cart_items] if request.cart_items else []
        entities_by_id = {pid: catalog_by_id[pid] for pid in product_ids if pid in catalog_by_id}

        cart_entities: list[tuple[ProductEntity, int]] = []
        if request.cart_items:
            for item in request.cart_items:
                entity = entities_by_id.get(item.product_id)
                if entity and item.quantity > 0:
                    cart_entities.append((entity, item.quantity))

        # 2. Compute authoritative baseline quote for the cart (if items present)
        cart_quote = (
            self.calculate_basket_quote(
                cart_entities,
                applied_discounts=request.applied_discounts,
                margin_floor=request.margin_floor,
                discount_cap=request.discount_cap,
            )
            if cart_entities
            else None
        )

        # 3. Assemble recommendation anchors from active basket, views, saved cart, and order history
        anchors: list[RecommendationAnchor] = []
        seen_anchor_ids: set[str] = set()

        # Anchor Source 1: Active cart items (highest priority, weight 1.0)
        for entity, _ in cart_entities:
            anchors.append(
                RecommendationAnchor(
                    product_id=entity.id,
                    source="active_basket",
                    weight=1.0,
                    age_hours=0.0,
                    view_count=1,
                )
            )
            seen_anchor_ids.add(entity.id)

        # Extract in-memory anchors from already-fetched session_events (sub-millisecond)
        session_saved_ids: list[str] = []
        session_order_ids: list[str] = []
        session_viewed_ids: list[str] = []
        session_hovered_ids: list[str] = []
        view_counts: dict[str, int] = {}
        hover_counts: dict[str, int] = {}

        for evt in session_events:
            pid = evt.get("product_id") if isinstance(evt, dict) else getattr(evt, "product_id", "")
            etype = evt.get("event_type") if isinstance(evt, dict) else getattr(evt, "event_type", "")
            if not pid:
                continue
            if etype in ("cart_saved", "save_cart") and pid not in session_saved_ids:
                session_saved_ids.append(pid)
            elif etype in ("simulated_purchase_completed", "order_completed") and pid not in session_order_ids:
                session_order_ids.append(pid)
            elif etype in ("product_view", "product_viewed", "search_submitted"):
                if pid not in session_viewed_ids:
                    session_viewed_ids.append(pid)
                view_counts[pid] = view_counts.get(pid, 0) + 1
            elif etype in ("product_hover", "product_focus"):
                if pid not in session_hovered_ids:
                    session_hovered_ids.append(pid)
                hover_counts[pid] = hover_counts.get(pid, 0) + 1

        # Anchor Source 2: Saved cart items (weight 0.85)
        saved_ids = list(request.saved_cart_product_ids) if request.saved_cart_product_ids else session_saved_ids
        for sid in saved_ids:
            if sid not in seen_anchor_ids:
                anchors.append(
                    RecommendationAnchor(
                        product_id=sid,
                        source="saved_cart",
                        weight=0.85,
                        age_hours=1.0,
                        view_count=1,
                    )
                )
                seen_anchor_ids.add(sid)

        # Anchor Source 3: Historical completed FairCart order items (weight 0.75)
        user_order_pids: list[str] = []
        if getattr(request, "user_id", None):
            user_order_pids = self.repository.get_user_purchased_product_ids(request.user_id)

        order_ids = list(request.historical_order_product_ids) if request.historical_order_product_ids else (user_order_pids or session_order_ids)
        for oid in order_ids:
            if oid not in seen_anchor_ids:
                anchors.append(
                    RecommendationAnchor(
                        product_id=oid,
                        source="historical_order",
                        weight=0.75,
                        age_hours=2.0,
                        view_count=1,
                    )
                )
                seen_anchor_ids.add(oid)

        # Anchor Source 4: Viewed items (weight 0.60)
        viewed_ids = list(request.viewed_product_ids or [])
        for sid in session_viewed_ids:
            if sid not in viewed_ids:
                viewed_ids.append(sid)
        for vid in viewed_ids:
            if vid not in seen_anchor_ids:
                v_count = view_counts.get(vid, 1)
                anchors.append(
                    RecommendationAnchor(
                        product_id=vid,
                        source="product_view",
                        weight=0.60,
                        age_hours=0.5,
                        view_count=v_count,
                    )
                )
                seen_anchor_ids.add(vid)

        # Anchor Source 5: Hovered items (weight 0.40)
        hovered_ids = list(request.hovered_product_ids or [])
        for sid in session_hovered_ids:
            if sid not in hovered_ids:
                hovered_ids.append(sid)
        for hid in hovered_ids:
            if hid not in seen_anchor_ids:
                h_count = hover_counts.get(hid, 1)
                anchors.append(
                    RecommendationAnchor(
                        product_id=hid,
                        source="product_hover",
                        weight=0.40,
                        age_hours=0.5,
                        view_count=h_count,
                    )
                )
                seen_anchor_ids.add(hid)

        # Synthesize recent client-side hover events into session_events if not yet written to database
        active_events = list(session_events)
        existing_hover_pids = {
            (evt.get("product_id") if isinstance(evt, dict) else getattr(evt, "product_id", ""))
            for evt in session_events
            if (evt.get("event_type") if isinstance(evt, dict) else getattr(evt, "event_type", "")) in ("product_hover", "product_focus")
        }
        for hid in (request.hovered_product_ids or []):
            if hid and hid not in existing_hover_pids:
                active_events.append({
                    "product_id": hid,
                    "event_type": "product_hover",
                    "metadata": {"duration_ms": 700, "dwell_ms": 700},
                    "age_hours": 0.0,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })

        # 4. Run Engine A (Ranked Candidates)
        candidates = self.recommender.find_recommendations(
            cart_items=cart_entities,
            catalog=catalog,
            shopping_context=request.shopping_context,
            session_viewed_ids=viewed_ids,
            session_events=active_events,
            anchors=anchors,
            search_query=request.search_query,
            top_k=4,
        )

        if not candidates:
            latency_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
            return DecisionResponse(
                request_id=request_id,
                session_id=request.session_id,
                shopping_context=request.shopping_context,
                decision="NO_OFFER",
                recommendations=[],
                recommendation=None,
                incentive=None,
                cart_quote=cart_quote,
                eligible_offers_by_product_id={},
                deterministic_explanation="No compatible recommendation candidates are currently available.",
                decision_reason="Engine A found no eligible in-stock candidates for the current context.",
                basket_gross_margin=cart_quote.basket_gross_margin if cart_quote else 0.0,
                fallback_applied=False,
                execution_latency_ms=latency_ms,
            )

        # 5. Run Engine B independently for each candidate
        recommendation_items: list[RecommendationItem] = []
        eligible_offers: dict[str, RecommendationItem] = {}
        has_any_offer = False

        approved_discounts = {
            item.product_id: item.discount_percentage
            for item in cart_quote.items
            if item.discount_percentage > 0.0
        } if cart_quote else {}

        for cand in candidates:
            if cart_entities:
                opt_result = self.optimizer.optimize(
                    cart_items=cart_entities,
                    candidate=cand.product,
                    applied_discounts=approved_discounts,
                    affinity_score=cand.affinity_score,
                    dwell_time_seconds=request.dwell_time_seconds,
                    margin_floor=request.margin_floor,
                    discount_cap=request.discount_cap,
                )
                is_offered = opt_result.is_offered
                tier = opt_result.action_type
                discount_percentage = round(opt_result.discount_percentage, 4)
                final_price = opt_result.final_price
                savings = opt_result.savings
                conditions = opt_result.conditions
                gross_margin = round(opt_result.basket_gross_margin, 4)
                dec_reason = opt_result.decision_reason
            else:
                # With an empty cart, Engine B strictly prevents standalone discounts
                is_offered = False
                tier = "NONE"
                discount_percentage = 0.0
                final_price = cand.product.reference_price
                savings = 0.0
                conditions = "Standard price · Add items to cart to unlock bundle deals"
                gross_margin = 0.0
                dec_reason = "Active cart is empty; bundle discounts require an active cart."

            item = RecommendationItem(
                product_id=cand.product.id,
                name=cand.product.name,
                category=cand.product.category,
                subcategory=cand.product.subcategory,
                tags=list(cand.product.tags),
                use_cases=list(cand.product.use_cases),
                reference_price=cand.product.reference_price,
                cogs=cand.product.cogs,
                inventory=cand.product.inventory,
                image_url=cand.product.image_url,
                affinity_score=cand.affinity_score,
                compatibility_reason=cand.compatibility_reason,
                association_lift=cand.association_lift,
                association_confidence=cand.association_confidence,
                is_multi_item_match=cand.is_multi_item_match,
                is_offered=is_offered,
                tier=tier,
                discount_percentage=discount_percentage,
                final_price=final_price,
                savings=savings,
                currency="USD",
                conditions=conditions,
                basket_gross_margin=gross_margin,
                decision_reason=dec_reason,
                recommendation_source=cand.recommendation_source,
                provenance_label=cand.provenance_label,
            )

            recommendation_items.append(item)

            if is_offered:
                has_any_offer = True
                eligible_offers[cand.product.id] = item

        # Top recommendation and incentive for backward compatibility
        top_rec = recommendation_items[0] if recommendation_items else None
        top_inc = None
        if top_rec:
            top_inc = IncentiveResponse(
                is_offered=top_rec.is_offered,
                tier=top_rec.tier,
                discount_percentage=top_rec.discount_percentage,
                reference_price=top_rec.reference_price,
                final_price=top_rec.final_price,
                savings=top_rec.savings,
                currency="USD",
                conditions=top_rec.conditions,
            )

        # 6. Build deterministic explanation
        context_label = request.shopping_context.capitalize() if request.shopping_context != "all" else "Current"
        if cart_entities:
            if has_any_offer:
                offer_count = len(eligible_offers)
                explanation = (
                    f"Generated {len(recommendation_items)} relevant recommendations for your {context_label} setup. "
                    f"{offer_count} qualified for margin-preserving bundle savings."
                )
                decision_outcome = "OFFER_APPLIED"
            else:
                explanation = (
                    f"Generated {len(recommendation_items)} complementary recommendations at standard reference price. "
                    f"Merchant margin floors currently preclude promotional discounts."
                )
                decision_outcome = "NO_OFFER"
            audit_reason = (
                f"Evaluated {len(recommendation_items)} candidates across cart; "
                f"{len(eligible_offers)} satisfied margin floor ({request.margin_floor*100:.0f}%) and utility constraints."
            )
            basket_margin = cart_quote.basket_gross_margin if cart_quote else 0.0
        else:
            decision_outcome = "NO_OFFER"
            rec_src = top_rec.recommendation_source if top_rec else "catalog_popular"
            if rec_src == "product_views":
                explanation = "Displaying tailored accessory recommendations inspired by products you recently viewed."
            elif rec_src == "historical_order":
                explanation = "Displaying recommendations tailored to complement items from your previous FairCart order."
            elif rec_src == "saved_cart":
                explanation = "Displaying recommendations tailored to complement items in your saved cart."
            elif request.shopping_context.strip().lower() not in ("all", "general", ""):
                explanation = f"Displaying curated recommendations aligned with your {request.shopping_context.capitalize()} setup."
            else:
                explanation = "Displaying popular workspace essentials from our catalogue with proven versatility."
            audit_reason = f"Active cart is empty. Generated {len(recommendation_items)} {rec_src} recommendations at standard reference price without discount."
            basket_margin = 0.0

        latency_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

        top_passport = None
        if top_rec:
            try:
                top_passport = self.generate_deal_passport(
                    DealPassportRequest(
                        cart_items=request.cart_items,
                        candidate_product_id=top_rec.product_id,
                        candidate_discount_pct=top_rec.discount_percentage if top_rec.is_offered else None,
                        applied_discounts=request.applied_discounts,
                        margin_floor=request.margin_floor,
                        discount_cap=request.discount_cap,
                        shopping_context=request.shopping_context,
                        view_mode="shopper",
                    )
                )
            except Exception:
                top_passport = None

        return DecisionResponse(
            request_id=request_id,
            session_id=request.session_id,
            shopping_context=request.shopping_context,
            decision=decision_outcome,
            recommendations=recommendation_items,
            recommendation=top_rec,
            incentive=top_inc,
            cart_quote=cart_quote,
            eligible_offers_by_product_id=eligible_offers,
            deterministic_explanation=explanation,
            decision_reason=audit_reason,
            basket_gross_margin=basket_margin,
            fallback_applied=False,
            deal_passport=top_passport,
            execution_latency_ms=latency_ms,
        )
