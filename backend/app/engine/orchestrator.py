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
import time
import uuid
from backend.app.db.repository import CatalogRepository, ProductEntity
from backend.app.engine.optimizer import EconomicOptimizer
from backend.app.engine.recommender import RecommenderEngine, RecommendationAnchor
from backend.app.models.schemas import (
    BasketQuote,
    BasketQuoteItem,
    DecisionRequest,
    DecisionResponse,
    IncentiveResponse,
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
            execution_latency_ms=latency_ms,
        )
