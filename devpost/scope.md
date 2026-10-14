---
doc: scope
status: approved
---

# FairCart AI

Explainable, margin-preserving e-commerce recommendation and incentive optimization engine for responsible commerce.

## The Unique Kernel
FairCart AI optimizes transaction value and incremental merchant contribution profit rather than extracting maximum customer willingness-to-pay. Every recommendation and incentive is bounded by non-bypassable merchant gross-margin floors evaluated across the entire basket, an immutable reference price ceiling (personalization never increases prices above the base price), zero manipulative dark patterns, and transparent dual explainability for both the shopper and the merchant.

## Who It's For
1. **The Thoughtful Shopper:** Browsing online, frustrated by manipulative countdown timers, artificial scarcity warnings, deceptive reference prices, and invasive tracking. They want relevant complementary product recommendations and genuine, transparent savings.
2. **The Independent Merchant:** Running an e-commerce store with tight unit margins. Currently forced to choose between blunt, margin-destroying blanket sales (e.g., 15% off site-wide) that cannibalize organic sales or opaque recommendation black boxes that sacrifice profitability.

## The Core Loop
1. **Browse & Basket:** Shopper browses a realistic 20-product tech and lifestyle catalog and adds an item (e.g., Ergonomic Keyboard, $80) to the cart.
2. **Relevance & Affinity (Engine A):** Engine A identifies compatible accessories (e.g., Wrist Rest, $25) using content-based attributes and computes an affinity score (deterministic cold-start fallback if history is absent).
3. **Constrained Economic Optimization (Engine B):** Engine B evaluates permissible actions (`NO_OFFER` vs. eligible bundle discount) against merchant economics, ensuring the total basket gross margin satisfies `gross_margin >= configured_floor`, selecting an offer only if it yields positive estimated incremental contribution profit over the no-incentive baseline.
4. **Gemini Explanation & Copy:** A real Gemini API integration generates customer-facing explanation and transparent offer copy (e.g., "Bundle & Save $2.50"). If the API key is missing or the call fails, an automatic deterministic local fallback generates the copy without blocking the transaction.
5. **Transparent Disclosure & Simulated Checkout:** Shopper inspects the transparent pricing breakdown (reference price, discount, final price, verified savings, conditions) and completes a simulated zero-payment checkout.
6. **Merchant Telemetry & Simulation:** Merchant dashboard displays live decision logs with exact mathematical attribution, allows adjusting margin floor and discount cap sliders in real time, and runs reproducible simulations comparing three policies: No Discount vs. Blanket 15% Discount vs. FairCart AI.

## Mathematical Definitions & Invariants
- **Gross Margin:** Calculated strictly as:
  $$\text{Gross Margin} = \frac{\text{Net Sales Revenue} - \text{COGS}}{\text{Net Sales Revenue}}$$
  The optimizer strictly enforces that the total basket gross margin satisfies:
  $$\text{Basket Gross Margin} \ge \text{Configured Margin Floor}$$
- **Contribution Profit:** Evaluated separately to account for applicable variable fulfillment, shipping subsidies, and incentive costs:
  $$\text{Contribution Profit} = \text{Net Sales Revenue} - \text{COGS} - \text{Variable Fulfillment Costs} - \text{Incentive Action Costs}$$
- **Incremental Contribution Utility:**
  $$\Delta \text{Contribution} = E[\text{Contribution}(\text{offer})] - E[\text{Contribution}(\text{no\_offer})]$$
  If $\Delta \text{Contribution} \le 0$, or if any required cost/price input is missing, the engine defaults safely to `NO_OFFER`.
- **Price Invariant:** Final personalized price $\le$ original base reference price. Personalization can never increase prices.
- **Precision:** Arithmetic implemented using decimal / integer-minor-unit conventions to avoid floating-point rounding errors.

## Scoring vs. Prediction Transparency
- Content-based recommendation outputs are explicitly labelled as **Affinity / Recommendation Scores**, not calibrated purchase probabilities.
- Abandonment-risk indicators are labelled as **Heuristic Estimates** when generated from session rules.
- Causal uplift is never claimed from purchase propensity alone.

## Evaluation & Honest Simulation
- A 3-policy simulation compares:
  1. **Policy 1:** No Discount (baseline organic conversion).
  2. **Policy 2:** Blanket 15% Discount (conventional promotional tactic).
  3. **Policy 3:** FairCart AI (margin-constrained, targeted value optimization).
- The simulation runs on reproducible synthetic sessions generated with fixed seeds (`seed=42`) and documented behavioral assumptions. Results are explicitly labelled as synthetic simulation data, not real-world production measurements.
- Latency benchmarks measure local decision API response time independently from asynchronous Gemini LLM generation, treating $< 100\text{ ms}$ as an empirical performance target.

## Inspiration & Identity
- **Visual Feel:** Clean, modern, high-contrast, professional commerce interface inspired by Shopify Polaris, Stripe, and Linear.
- **Tone:** Transparent, calm, trustworthy. No flashing banners, artificial countdown clocks, or fake stock alerts.
- **Audience Experience:** The shopper feels respected; the merchant feels protected.

## Why This Matters to the Learner
Demonstrating that AI in e-commerce can optimize collaborative economic value rather than exploit consumer cognitive biases, while mastering a disciplined, plan-first full-stack engineering workflow (FastAPI + React + Gemini) for Devpost Build With AI: Basics.

## What "Working" Looks Like
In a 2-minute demonstration:
1. Shopper adds an item to their cart.
2. FairCart AI generates an explainable complementary recommendation with a transparent bundle discount card.
3. Shopper sees original price, final price, and verified savings, with a Gemini-generated explanation of why the offer was made.
4. Merchant Dashboard updates in real time, showing the decision log with exact margin verification (e.g., net margin 34% $\ge$ 20% floor).
5. Merchant toggles the policy simulator to run reproducible synthetic sessions, demonstrating how FairCart AI prevents profit cannibalization compared to blanket discounting.
6. Automated tests pass, proving that financial invariants (no price inflation, margin floor preserved across the basket) cannot be violated.

## The POC Boundary: MVP vs. Optional Extensions

### MVP (Essential for First Working Version)
- **Catalog:** 20 coherent products with realistic reference prices, wholesale COGS, stock, categories, and complementary-product relationships in embedded SQLite.
- **Shopper UI:** React (TypeScript + Vite + Tailwind CSS) storefront with catalog grid, cart management, transparent recommendation card, and simulated zero-payment checkout.
- **Decision API:** FastAPI service (`/api/v1/decision`, `/api/v1/catalog`, `/api/v1/simulate`, `/api/v1/health`) with Pydantic v2 validation.
- **Engine A:** Explainable content-based recommendation/affinity scoring with deterministic cold-start fallback.
- **Engine B:** Deterministic incentive optimizer supporting `NO_OFFER` and eligible bundle discounts with whole-basket gross margin floor enforcement and price ceilings.
- **Gemini Integration:** Server-side Gemini API integration generating transparent customer-facing explanations and offer copy, with an automatic deterministic fallback when the API key is missing or offline.
- **Merchant Dashboard:** Policy sliders (margin floor, discount caps), live decision inspector, and reproducible 3-policy simulation comparator.
- **Automated Tests:** Unit tests for financial invariants, decimal arithmetic, boundary conditions, and API schema contracts.
- **Documentation:** Complete setup guide, architecture documentation, and Devpost planning artifacts.

### Optional Extensions (Only After MVP Is Fully Functional and Tested)
- Separately trained purchase-propensity classifier with scikit-learn.
- Probability calibration (Platt scaling) and ROC-AUC / Brier score evaluation.
- Free-shipping subsidies with explicit shipping-cost modelling.
- Additional Gemini catalog shopping assistant.
- Real-time event streaming and live commerce platform webhook connectors.

## Explicitly Cut
- **Personal Identity / PII Tracking & Fingerprinting:** Replaced by anonymous, ephemeral session UUIDs.
- **Dynamic Price Surging / Personalized Price Increases:** Forbidden; base reference price is an immutable ceiling.
- **Manipulative Scarcity & Fake Timers:** Cut to adhere strictly to responsible commerce principles.
- **Cloud Microservice & Distributed Infrastructure:** Cut to keep the POC lightweight, zero-cost, and 100% locally runnable for hackathon evaluators.

## Completion Criteria
1. Shopper can browse the catalog, manage cart items, receive a valid recommendation and incentive decision, inspect verified financial calculations, see a Gemini-generated explanation (or fallback), and complete simulated checkout without errors.
2. Merchant can inspect live decisions, adjust policy constraints, and run the reproducible 3-policy simulation with clearly labelled simulated metrics.
3. Automated test suite runs and passes, verifying that basket margin floors, discount caps, and price ceilings hold across all inputs.
