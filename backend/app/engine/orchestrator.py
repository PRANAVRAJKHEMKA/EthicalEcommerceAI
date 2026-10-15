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

import time
import uuid
from backend.app.db.repository import CatalogRepository, ProductEntity
from backend.app.engine.optimizer import EconomicOptimizer
from backend.app.engine.recommender import RecommenderEngine
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
    ) -> BasketQuote:
        """Computes authoritative integer-cent monetary totals for the active cart."""
        discounts = applied_discounts or {}
        quote_items: list[BasketQuoteItem] = []
        standard_subtotal_cents = 0
        final_subtotal_cents = 0
        total_cogs_cents = 0

        for entity, qty in cart_entities:
            ref_cents = entity.reference_price_cents
            discount_pct = discounts.get(entity.id, 0.0)
            discount_cents = round(ref_cents * discount_pct)
            unit_cents = ref_cents - discount_cents

            line_total_cents = unit_cents * qty
            line_standard_cents = ref_cents * qty
            savings_cents = discount_cents * qty

            standard_subtotal_cents += line_standard_cents
            final_subtotal_cents += line_total_cents
            total_cogs_cents += (entity.cogs_cents * qty)

            condition_str = (
                f"Bundle discount ({int(discount_pct * 100)}% off)"
                if discount_pct > 0
                else "Standard price · No discount applied"
            )

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
        gross_margin = (
            ((final_subtotal_cents - total_cogs_cents) / final_subtotal_cents)
            if final_subtotal_cents > 0
            else 0.0
        )

        return BasketQuote(
            items=quote_items,
            standard_subtotal=round(standard_subtotal_cents / 100.0, 2),
            final_subtotal=round(final_subtotal_cents / 100.0, 2),
            total_savings=round(total_savings_cents / 100.0, 2),
            basket_gross_margin=round(gross_margin, 4),
        )

    def process_decision(self, request: DecisionRequest) -> DecisionResponse:
        """Processes a shopper's cart state to produce ranked recommendations and independent offers.

        Execution is entirely local and synchronous (< 25ms SLA).
        """
        start_time = time.perf_counter()
        request_id = f"dec-{uuid.uuid4().hex[:10]}"

        # 1. Input sanitization & catalog verification
        if not request.cart_items:
            latency_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
            return DecisionResponse(
                request_id=request_id,
                session_id=request.session_id,
                shopping_context=request.shopping_context,
                decision="NO_OFFER",
                recommendations=[],
                recommendation=None,
                incentive=None,
                cart_quote=None,
                eligible_offers_by_product_id={},
                deterministic_explanation="Cart is empty. Add products to receive tailored complementary recommendations.",
                decision_reason="No items present in cart to evaluate.",
                basket_gross_margin=0.0,
                fallback_applied=False,
                execution_latency_ms=latency_ms,
            )

        # Retrieve unique product entities for items in cart
        product_ids = [item.product_id for item in request.cart_items]
        entities_by_id = {e.id: e for e in self.repository.get_entities_by_ids(product_ids)}

        cart_entities: list[tuple[ProductEntity, int]] = []
        for item in request.cart_items:
            entity = entities_by_id.get(item.product_id)
            if entity and item.quantity > 0:
                cart_entities.append((entity, item.quantity))

        if not cart_entities:
            latency_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
            return DecisionResponse(
                request_id=request_id,
                session_id=request.session_id,
                shopping_context=request.shopping_context,
                decision="NO_OFFER",
                recommendations=[],
                recommendation=None,
                incentive=None,
                cart_quote=None,
                eligible_offers_by_product_id={},
                deterministic_explanation="No catalog items in cart could be validated.",
                decision_reason="All requested cart product IDs were invalid or zero quantity.",
                basket_gross_margin=0.0,
                fallback_applied=False,
                execution_latency_ms=latency_ms,
            )

        # 2. Compute authoritative baseline quote for the cart
        cart_quote = self.calculate_basket_quote(cart_entities, applied_discounts=request.applied_discounts)

        # 3. Retrieve full catalog and run Engine A (Ranked Candidates)
        catalog = self.repository.get_all_entities()
        candidates = self.recommender.find_recommendations(
            cart_items=cart_entities,
            catalog=catalog,
            shopping_context=request.shopping_context,
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
                deterministic_explanation="No compatible complementary items are currently available for this cart.",
                decision_reason="Engine A found no eligible in-stock complementary candidates.",
                basket_gross_margin=cart_quote.basket_gross_margin,
                fallback_applied=False,
                execution_latency_ms=latency_ms,
            )

        # 4. Run Engine B independently for each candidate
        recommendation_items: list[RecommendationItem] = []
        eligible_offers: dict[str, RecommendationItem] = {}
        has_any_offer = False

        for cand in candidates:
            opt_result = self.optimizer.optimize(
                cart_items=cart_entities,
                candidate=cand.product,
                affinity_score=cand.affinity_score,
                dwell_time_seconds=request.dwell_time_seconds,
                margin_floor=request.margin_floor,
                discount_cap=request.discount_cap,
            )

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
                is_offered=opt_result.is_offered,
                tier=opt_result.action_type,
                discount_percentage=round(opt_result.discount_percentage, 4),
                final_price=opt_result.final_price,
                savings=opt_result.savings,
                currency="USD",
                conditions=opt_result.conditions,
                basket_gross_margin=round(opt_result.basket_gross_margin, 4),
                decision_reason=opt_result.decision_reason,
            )

            recommendation_items.append(item)

            if opt_result.is_offered:
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

        # 5. Build deterministic explanation
        context_label = request.shopping_context.capitalize() if request.shopping_context != "all" else "Current"
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
            decision_reason=(
                f"Evaluated {len(recommendation_items)} candidates across cart; "
                f"{len(eligible_offers)} satisfied margin floor ({request.margin_floor*100:.0f}%) and utility constraints."
            ),
            basket_gross_margin=cart_quote.basket_gross_margin,
            fallback_applied=False,
            execution_latency_ms=latency_ms,
        )
