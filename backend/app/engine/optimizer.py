"""Engine B — Economic Incentive Optimizer

Responsibilities:
- Evaluates candidate bundle actions (NO_OFFER vs permitted discounts in [5%, 10%, 15%, 20%]).
- Enforces strict deterministic financial invariants:
    1. gross_margin >= configured_margin_floor across the whole affected basket.
    2. final_price <= reference_price.
    3. zero revenue or negative prices safely force NO_OFFER and gross_margin = 0.0.
    4. zero double-counting of discounts in contribution profit.
- Uses integer cents internally for all monetary calculations.
- Evaluates incremental contribution utility:
    incremental_utility(action) = E[contribution(action)] - E[contribution(no_offer)]

Note on Mathematical Assumptions:
Conversion probabilities under discounts are heuristic baseline estimates based on
product affinity and price elasticity. They do not represent measured causal A/B test results.
"""

from dataclasses import dataclass
from backend.app.db.repository import ProductEntity
from backend.app.models.schemas import IncentiveResponse

@dataclass(frozen=True)
class OptimizationResult:
    is_offered: bool
    action_type: str  # "BUNDLE_DISCOUNT" or "NONE"
    discount_percentage: float
    reference_price: float
    final_price: float
    savings: float
    conditions: str
    basket_gross_margin: float
    decision_reason: str
    incremental_utility_cents: float

class EconomicOptimizer:
    """Engine B: Margin-constrained economic utility optimizer."""

    # Discrete discount actions evaluated by default
    PERMITTED_DISCOUNT_ACTIONS = (0.05, 0.10, 0.15, 0.20)

    def optimize(
        self,
        cart_items: list[tuple[ProductEntity, int]],
        candidate: ProductEntity,
        affinity_score: float = 0.50,
        dwell_time_seconds: int = 30,
        margin_floor: float = 0.20,
        discount_cap: float = 0.20,
        variable_fulfillment_cost_cents: int = 0,
    ) -> OptimizationResult:
        """Determines the optimal incentive action for the candidate complementary product.

        All internal calculations are performed using exact integer cents.
        """
        # 1. Authoritative basket revenue and COGS calculation in integer cents
        parent_revenue_cents = sum(item.reference_price_cents * qty for item, qty in cart_items)
        parent_cogs_cents = sum(item.cogs_cents * qty for item, qty in cart_items)

        candidate_ref_cents = candidate.reference_price_cents
        candidate_cogs_cents = candidate.cogs_cents

        # Boundary Safeguard: zero or negative price/revenue forces NO_OFFER immediately
        if parent_revenue_cents <= 0 or candidate_ref_cents <= 0:
            return OptimizationResult(
                is_offered=False,
                action_type="NONE",
                discount_percentage=0.0,
                reference_price=max(round(candidate_ref_cents / 100.0, 2), 0.0),
                final_price=max(round(candidate_ref_cents / 100.0, 2), 0.0),
                savings=0.0,
                conditions="Standard price · No discount applied",
                basket_gross_margin=0.0,
                decision_reason="Incentive omitted: non-positive or invalid basket revenue.",
                incremental_utility_cents=0.0,
            )

        # 2. Baseline NO_OFFER (action = 0.0) calculations
        baseline_affected_revenue_cents = parent_revenue_cents + candidate_ref_cents
        baseline_affected_cogs_cents = parent_cogs_cents + candidate_cogs_cents
        baseline_gross_margin = (
            (baseline_affected_revenue_cents - baseline_affected_cogs_cents)
            / baseline_affected_revenue_cents
        )
        baseline_contribution_cents = (
            baseline_affected_revenue_cents
            - baseline_affected_cogs_cents
            - variable_fulfillment_cost_cents
        )

        # Heuristic baseline conversion probability P0 in [0.05, 0.40]
        p0 = min(max(0.12 + (0.18 * affinity_score) + (0.02 if dwell_time_seconds > 45 else 0.0), 0.05), 0.40)
        expected_baseline_utility = p0 * baseline_contribution_cents

        # 3. Evaluate candidate discount actions up to discount_cap
        best_discount = 0.0
        best_margin = baseline_gross_margin
        best_savings_cents = 0
        best_final_cents = candidate_ref_cents
        best_incremental_utility = 0.0
        margin_deficit_encountered = False

        # Build list of allowed discount tiers
        allowed_actions = [a for a in self.PERMITTED_DISCOUNT_ACTIONS if a <= discount_cap + 0.001]

        for action in allowed_actions:
            discount_cents = round(candidate_ref_cents * action)
            final_price_cents = candidate_ref_cents - discount_cents

            # Invariant: final_price <= reference_price
            if final_price_cents > candidate_ref_cents:
                continue

            affected_revenue_cents = parent_revenue_cents + final_price_cents
            affected_cogs_cents = parent_cogs_cents + candidate_cogs_cents

            if affected_revenue_cents <= 0:
                continue

            gross_margin = (affected_revenue_cents - affected_cogs_cents) / affected_revenue_cents

            # Invariant: gross_margin >= margin_floor
            if gross_margin < margin_floor:
                margin_deficit_encountered = True
                continue

            # Contribution profit: net revenue - cogs - fulfillment (discounts NOT double-subtracted)
            contribution_cents = (
                affected_revenue_cents
                - affected_cogs_cents
                - variable_fulfillment_cost_cents
            )

            # Heuristic price elasticity conversion uplift (epsilon = 1.6)
            p_action = min(p0 * (1.0 + 1.6 * action), 0.85)
            expected_utility = p_action * contribution_cents
            incremental_utility = expected_utility - expected_baseline_utility

            # Decision Rule: select action maximizing positive incremental utility
            if incremental_utility > best_incremental_utility:
                best_incremental_utility = incremental_utility
                best_discount = action
                best_margin = gross_margin
                best_savings_cents = discount_cents
                best_final_cents = final_price_cents

        parent_name = cart_items[0][0].name if cart_items else "cart item"

        # 4. Formulate authoritative result
        if best_discount > 0.0 and best_incremental_utility > 0.0:
            return OptimizationResult(
                is_offered=True,
                action_type="BUNDLE_DISCOUNT",
                discount_percentage=round(best_discount, 2),
                reference_price=round(candidate_ref_cents / 100.0, 2),
                final_price=round(best_final_cents / 100.0, 2),
                savings=round(best_savings_cents / 100.0, 2),
                conditions=f"Valid when bundled with {parent_name}",
                basket_gross_margin=round(best_margin, 4),
                decision_reason=(
                    f"Eligible bundle: basket gross margin is {best_margin * 100.0:.1f}% "
                    f"(exceeds {margin_floor * 100.0:.1f}% floor) with positive incremental utility."
                ),
                incremental_utility_cents=round(best_incremental_utility, 2),
            )
        else:
            reason = (
                f"Incentive omitted: applying discount would breach the {margin_floor * 100.0:.1f}% gross margin floor."
                if margin_deficit_encountered
                else "Incentive omitted: standard pricing maximizes expected merchant contribution."
            )
            return OptimizationResult(
                is_offered=False,
                action_type="NONE",
                discount_percentage=0.0,
                reference_price=round(candidate_ref_cents / 100.0, 2),
                final_price=round(candidate_ref_cents / 100.0, 2),
                savings=0.0,
                conditions="Standard price · No discount applied",
                basket_gross_margin=round(baseline_gross_margin, 4),
                decision_reason=reason,
                incremental_utility_cents=0.0,
            )
