"""Engine C — Decision Pipeline Orchestrator

Responsibilities:
- Coordinate Engine A (RecommenderEngine) and Engine B (EconomicOptimizer).
- Validate cart items against the authoritative SQLite catalog.
- Measure and record decision pipeline execution latency in milliseconds.
- Return unified, schema-compliant DecisionResponse objects with zero reliance on external APIs.
"""

import time
import uuid
from backend.app.db.repository import CatalogRepository, ProductEntity
from backend.app.engine.optimizer import EconomicOptimizer
from backend.app.engine.recommender import RecommenderEngine
from backend.app.models.schemas import (
    DecisionRequest,
    DecisionResponse,
    IncentiveResponse,
    RecommendationResponse,
)

class DecisionOrchestrator:
    """Engine C: Unified decision pipeline coordinator."""

    def __init__(
        self,
        repository: CatalogRepository | None = None,
        recommender: RecommenderEngine | None = None,
        optimizer: EconomicOptimizer | None = None,
    ):
        self.repository = repository or CatalogRepository()
        self.recommender = recommender or RecommenderEngine()
        self.optimizer = optimizer or EconomicOptimizer()

    def process_decision(self, request: DecisionRequest) -> DecisionResponse:
        """Processes a shopper's cart state to produce a margin-verified recommendation and offer.

        Execution is entirely local and synchronous (< 25ms).
        """
        start_time = time.perf_counter()
        request_id = f"dec-{uuid.uuid4().hex[:10]}"

        # 1. Input sanitization & catalog verification
        if not request.cart_items:
            latency_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
            return DecisionResponse(
                request_id=request_id,
                session_id=request.session_id,
                decision="NO_OFFER",
                recommendation=None,
                incentive=None,
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
                decision="NO_OFFER",
                recommendation=None,
                incentive=None,
                deterministic_explanation="No catalog items in cart could be validated.",
                decision_reason="All requested cart product IDs were invalid or zero quantity.",
                basket_gross_margin=0.0,
                fallback_applied=False,
                execution_latency_ms=latency_ms,
            )

        # 2. Retrieve catalog and run Engine A (Recommendation)
        catalog = self.repository.get_all_entities()
        candidate = self.recommender.find_recommendation(cart_entities, catalog)

        # Baseline cart gross margin for reference
        parent_rev_cents = sum(item.reference_price_cents * qty for item, qty in cart_entities)
        parent_cogs_cents = sum(item.cogs_cents * qty for item, qty in cart_entities)
        cart_baseline_margin = (
            ((parent_rev_cents - parent_cogs_cents) / parent_rev_cents)
            if parent_rev_cents > 0
            else 0.0
        )

        if candidate is None:
            latency_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
            return DecisionResponse(
                request_id=request_id,
                session_id=request.session_id,
                decision="NO_OFFER",
                recommendation=None,
                incentive=None,
                deterministic_explanation="No compatible complementary items are currently available for this cart.",
                decision_reason="Engine A found no eligible in-stock complementary candidates.",
                basket_gross_margin=round(cart_baseline_margin, 4),
                fallback_applied=False,
                execution_latency_ms=latency_ms,
            )

        # 3. Run Engine B (Economic Incentive Optimization)
        opt_result = self.optimizer.optimize(
            cart_items=cart_entities,
            candidate=candidate.product,
            affinity_score=candidate.affinity_score,
            dwell_time_seconds=request.dwell_time_seconds,
            margin_floor=request.margin_floor,
            discount_cap=request.discount_cap,
        )

        # 4. Construct response payloads
        recommendation_payload = RecommendationResponse(
            product_id=candidate.product.id,
            name=candidate.product.name,
            category=candidate.product.category,
            reference_price=candidate.product.reference_price,
            affinity_score=round(candidate.affinity_score, 2),
            compatibility_reason=candidate.compatibility_reason,
            image_url=candidate.product.image_url,
        )

        incentive_payload = IncentiveResponse(
            is_offered=opt_result.is_offered,
            tier=opt_result.action_type,
            discount_percentage=round(opt_result.discount_percentage, 4),
            reference_price=opt_result.reference_price,
            final_price=opt_result.final_price,
            savings=opt_result.savings,
            currency="USD",
            conditions=opt_result.conditions,
        )

        if opt_result.is_offered:
            pct_int = int(round(opt_result.discount_percentage * 100))
            explanation = (
                f"Eligible for a {pct_int}% bundle discount ({opt_result.conditions}) "
                f"paired with your current basket."
            )
            decision_outcome = "OFFER_APPLIED"
        else:
            explanation = (
                f"Recommended complementary product at standard reference price. "
                f"{opt_result.conditions}."
            )
            decision_outcome = "NO_OFFER"

        latency_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

        return DecisionResponse(
            request_id=request_id,
            session_id=request.session_id,
            decision=decision_outcome,
            recommendation=recommendation_payload,
            incentive=incentive_payload,
            deterministic_explanation=explanation,
            decision_reason=opt_result.decision_reason,
            basket_gross_margin=round(opt_result.basket_gross_margin, 4),
            fallback_applied=False,
            execution_latency_ms=latency_ms,
        )
